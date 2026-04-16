"""Shell 执行工具 — 带安全防护的命令执行"""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile

from maxbot.tools._registry import registry
from maxbot.tools.sandbox import validate_command, validate_workdir


@registry.tool(name="shell", description="执行 shell 命令（前台执行，有超时，有安全限制）")
def shell(command: str, timeout: int = 60, workdir: str | None = None) -> str:
    # 安全检查
    safe, reason = validate_command(command)
    if not safe:
        return json.dumps({"error": f"命令被拒绝: {reason}", "command": command}, ensure_ascii=False)

    safe, reason = validate_workdir(workdir)
    if not safe:
        return json.dumps({"error": reason}, ensure_ascii=False)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        # 50KB 输出上限
        truncated = len(output) > 50_000
        return json.dumps({
            "output": output[:50_000],
            "exit_code": result.returncode,
            "truncated": truncated,
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"命令超时 ({timeout}s)", "command": command})
    except Exception as e:
        return json.dumps({"error": str(e), "command": command})


@registry.tool(name="exec_python", description="在沙箱中执行 Python 代码并返回结果")
def exec_python(code: str, timeout: int = 30) -> str:
    """在子进程中执行 Python 代码（安全隔离）"""
    # 安全检查 — 检查代码内容
    safe, reason = validate_command(code)
    if not safe:
        return json.dumps({"error": f"代码被拒绝: {reason}"}, ensure_ascii=False)

    # 用临时文件代替 shell 引号转义（避免转义问题）
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        truncated = len(output) > 50_000
        return json.dumps({
            "output": output[:50_000],
            "exit_code": result.returncode,
            "truncated": truncated,
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Python 执行超时 ({timeout}s)"})
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
