"""Shell 执行工具 — 沙箱命令执行"""

from __future__ import annotations

import json
import subprocess
import shlex

from maxbot.tools._registry import registry


@registry.tool(name="shell", description="执行 shell 命令（前台执行，有超时）")
def shell(command: str, timeout: int = 60, workdir: str | None = None) -> str:
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
        return json.dumps({
            "output": output[:50_000],  # 50KB 上限
            "exit_code": result.returncode,
            "truncated": len(output) > 50_000,
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"命令超时 ({timeout}s)", "command": command})
    except Exception as e:
        return json.dumps({"error": str(e), "command": command})


@registry.tool(name="exec_python", description="执行 Python 代码并返回结果")
def exec_python(code: str, timeout: int = 30) -> str:
    """在子进程中执行 Python 代码"""
    # 转义代码中的引号
    escaped = code.replace("'", "'\\''")
    cmd = f"python3 -c '{escaped}'"
    return shell(cmd, timeout=timeout)
