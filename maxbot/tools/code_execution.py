"""
execute_code 沙箱 — 沙箱脚本内可调用 MaxBot 工具

参考 Hermes code_execution_tool.py 的文件 RPC 模式：
1. 父进程生成 maxbot_tools.py stub（文件 RPC 函数）
2. 父进程启动子进程执行 LLM 写的脚本
3. 脚本通过 maxbot_tools.read_file() 等调用回父进程
4. 父进程轮询请求文件、分发工具调用、写回响应
5. 只返回 stdout，中间工具调用不进 context window

用法（工具注册后 LLM 可直接调用）：
    execute_code(code='''
import maxbot_tools
data = maxbot_tools.read_file("/tmp/test.txt")
print(data)
''')
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from maxbot.tools._registry import registry

# ── 沙箱内可用的工具 ──────────────────────────────────────

SANDBOX_ALLOWED_TOOLS = frozenset([
    "read_file",
    "write_file",
    "search_files",
    "patch_file",
    "list_files",
    "shell",
    "exec_python",
    "web_search",
    "web_fetch",
    "git_status",
    "git_diff",
    "git_log",
])

DEFAULT_TIMEOUT = 300        # 5 分钟
DEFAULT_MAX_TOOL_CALLS = 50
MAX_STDOUT_BYTES = 50_000    # 50 KB


# ── 生成 maxbot_tools.py stub ──────────────────────────────

_TOOL_STUBS = {
    "read_file": (
        "read_file",
        "path: str, offset: int = 1, limit: int = 500",
        '{"path": path, "offset": offset, "limit": limit}',
    ),
    "write_file": (
        "write_file",
        "path: str, content: str",
        '{"path": path, "content": content}',
    ),
    "search_files": (
        "search_files",
        'pattern: str, target: str = "content", path: str = ".", file_glob: str = None, limit: int = 50',
        '{"pattern": pattern, "target": target, "path": path, "file_glob": file_glob, "limit": limit}',
    ),
    "patch_file": (
        "patch_file",
        "path: str, old_string: str, new_string: str, replace_all: bool = False",
        '{"path": path, "old_string": old_string, "new_string": new_string, "replace_all": replace_all}',
    ),
    "list_files": (
        "list_files",
        'path: str = ".", pattern: str = "*"',
        '{"path": path, "pattern": pattern}',
    ),
    "shell": (
        "shell",
        "command: str, timeout: int = 30, workdir: str = None",
        '{"command": command, "timeout": timeout, "workdir": workdir}',
    ),
    "exec_python": (
        "exec_python",
        "code: str, timeout: int = 30",
        '{"code": code, "timeout": timeout}',
    ),
    "web_search": (
        "web_search",
        "query: str, limit: int = 5",
        '{"query": query, "limit": limit}',
    ),
    "web_fetch": (
        "web_fetch",
        "url: str, max_chars: int = 10000",
        '{"url": url, "max_chars": max_chars}',
    ),
    "git_status": (
        "git_status",
        "",
        '{}',
    ),
    "git_diff": (
        "git_diff",
        "file_path: str = None",
        '{"file_path": file_path}',
    ),
    "git_log": (
        "git_log",
        "limit: int = 10",
        '{"limit": limit}',
    ),
}


def _generate_stub_module(rpc_dir: str, enabled_tools: list[str]) -> str:
    """生成 maxbot_tools.py 源码"""
    tools = sorted(SANDBOX_ALLOWED_TOOLS & set(enabled_tools))

    stubs = []
    for name in tools:
        if name not in _TOOL_STUBS:
            continue
        func_name, sig, args_expr = _TOOL_STUBS[name]
        stubs.append(
            f"def {func_name}({sig}):\n"
            f'    """Call {name} via RPC to parent process."""\n'
            f"    return _call('{func_name}', {args_expr})\n"
        )

    return f'''"""
Auto-generated MaxBot tools RPC stubs.
Sandbox scripts import this module to call MaxBot tools.
"""
import json as _json, os as _os, time as _time, shlex as _shlex

_RPC_DIR = {rpc_dir!r}
_seq = 0

def _call(tool_name, args):
    """File-based RPC: write request, poll for response."""
    global _seq
    _seq += 1
    seq_str = f"{{_seq:06d}}"
    req_file = _os.path.join(_RPC_DIR, f"req_{{seq_str}}")
    res_file = _os.path.join(_RPC_DIR, f"res_{{seq_str}}")

    # Atomic write
    tmp = req_file + ".tmp"
    with open(tmp, "w") as f:
        _json.dump({{"tool": tool_name, "args": args, "seq": _seq}}, f)
    _os.rename(tmp, req_file)

    # Poll for response
    deadline = _time.monotonic() + 60
    poll = 0.05
    while not _os.path.exists(res_file):
        if _time.monotonic() > deadline:
            raise RuntimeError(f"RPC timeout: {{tool_name}}")
        _time.sleep(poll)
        poll = min(poll * 1.2, 0.25)

    with open(res_file) as f:
        raw = f.read()
    try:
        _os.unlink(res_file)
    except OSError:
        pass

    result = _json.loads(raw)
    if isinstance(result, str):
        try:
            return _json.loads(result)
        except (_json.JSONDecodeError, TypeError):
            return result
    return result

def json_parse(text):
    """Parse JSON with strict=False (handles control chars)."""
    return _json.loads(text, strict=False)

def shell_quote(s):
    """Shell-escape a string."""
    return _shlex.quote(s)

def retry(fn, max_attempts=3, delay=2):
    """Retry with exponential backoff."""
    last_err = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < max_attempts - 1:
                _time.sleep(delay * (2 ** attempt))
    raise last_err

# Tool stubs
{"".join(stubs)}
'''


# ── RPC 分发（父进程侧）────────────────────────────────────

def _dispatch_rpc_requests(
    rpc_dir: str,
    tool_call_counter: list,
    max_tool_calls: int,
    enabled_tools: frozenset,
) -> None:
    """
    轮询 rpc_dir 中的请求文件，分发工具调用，写回响应。

    在子线程中运行。
    """
    while True:
        # 查找请求文件
        try:
            req_files = sorted(Path(rpc_dir).glob("req_*"))
        except OSError:
            break

        if not req_files:
            time.sleep(0.05)
            # 超时退出：没有新请求且已经结束
            continue

        for req_file in req_files:
            if tool_call_counter[0] >= max_tool_calls:
                _write_error(req_file, rpc_dir, f"Tool call limit ({max_tool_calls}) reached")
                continue

            try:
                raw = req_file.read_text()
                request = json.loads(raw)
            except Exception as e:
                _write_error(req_file, rpc_dir, f"Invalid request: {e}")
                continue

            tool_name = request.get("tool", "")
            tool_args = request.get("args", {})

            # 检查工具是否可用
            if tool_name not in enabled_tools:
                _write_error(req_file, rpc_dir, f"Tool '{tool_name}' not available in sandbox")
                continue

            # 调用工具
            try:
                tool = registry.get(tool_name)
                if tool:
                    result = tool.handler(**tool_args)
                else:
                    result = json.dumps({"error": f"Tool not found: {tool_name}"})
            except Exception as e:
                result = json.dumps({"error": str(e)})

            tool_call_counter[0] += 1

            # 写响应
            seq = req_file.stem.split("_", 1)[1]
            res_file = Path(rpc_dir) / f"res_{seq}"
            res_file.write_text(result if isinstance(result, str) else json.dumps(result))

            # 清理请求文件
            try:
                req_file.unlink()
            except OSError:
                pass

        time.sleep(0.02)


def _write_error(req_file: Path, rpc_dir: str, error_msg: str):
    """写错误响应并清理请求文件"""
    seq = req_file.stem.split("_", 1)[1]
    res_file = Path(rpc_dir) / f"res_{seq}"
    res_file.write_text(json.dumps({"error": error_msg}))
    try:
        req_file.unlink()
    except OSError:
        pass


# ── 工具定义 ──────────────────────────────────────────────

@registry.tool(
    name="execute_code",
    description=(
        "执行 Python 代码，脚本内可通过 maxbot_tools 模块调用 MaxBot 工具。"
        "多步工具链压成 1 次调用，中间结果不进 context window。"
        "只返回脚本 stdout（最多 50KB）。"
        "\n\n用法:\n"
        "```\n"
        "import maxbot_tools\n"
        "data = maxbot_tools.read_file('/path/to/file')\n"
        "lines = data['content'].split('\\n')\n"
        "for line in lines[:10]:\n"
        "    print(line)\n"
        "```\n"
        "\n可用工具: " + ", ".join(sorted(SANDBOX_ALLOWED_TOOLS))
    ),
    toolset="builtin",
)
def execute_code(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
) -> str:
    """
    执行代码，沙箱内可调用工具。

    流程：
    1. 创建临时 RPC 目录
    2. 生成 maxbot_tools.py stub
    3. 启动 RPC 分发线程
    4. 子进程执行用户代码
    5. 返回 stdout
    """
    # 准备 RPC 目录
    rpc_dir = tempfile.mkdtemp(prefix="maxbot_rpc_")
    tool_call_counter = [0]
    enabled_tools = frozenset(SANDBOX_ALLOWED_TOOLS & set(
        t.name for t in registry.list_tools()
    ))

    # 生成 stub 模块
    stub_code = _generate_stub_module(rpc_dir, list(enabled_tools))
    stub_path = os.path.join(rpc_dir, "maxbot_tools.py")
    with open(stub_path, "w") as f:
        f.write(stub_code)

    # 写用户脚本
    script_path = os.path.join(rpc_dir, "__script__.py")
    with open(script_path, "w") as f:
        f.write(code)

    # 启动 RPC 分发线程
    dispatcher = threading.Thread(
        target=_dispatch_rpc_requests,
        args=(rpc_dir, tool_call_counter, max_tool_calls, enabled_tools),
        daemon=True,
    )
    dispatcher.start()

    # 执行脚本
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=rpc_dir,
            env={**os.environ, "PYTHONPATH": rpc_dir},
        )
        stdout = proc.stdout
        stderr = proc.stderr

        # 截断输出
        if len(stdout.encode()) > MAX_STDOUT_BYTES:
            stdout = stdout[:MAX_STDOUT_BYTES] + "\n... (truncated)"

        result = {
            "exit_code": proc.returncode,
            "output": stdout,
        }
        if stderr:
            result["stderr"] = stderr[-2000:]  # 最多保留 2KB stderr
        if tool_call_counter[0] > 0:
            result["tool_calls"] = tool_call_counter[0]

        return json.dumps(result, ensure_ascii=False)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "error": f"Timeout after {timeout}s",
            "exit_code": -1,
            "tool_calls": tool_call_counter[0],
        })
    except Exception as e:
        return json.dumps({"error": str(e), "exit_code": -1})
    finally:
        # 清理
        import shutil
        shutil.rmtree(rpc_dir, ignore_errors=True)
