"""Git 操作工具"""

from __future__ import annotations

import json
import subprocess

from maxbot.tools._registry import registry


def _git(args: str, workdir: str | None = None) -> dict:
    result = subprocess.run(
        f"git {args}",
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=workdir,
    )
    return {
        "output": result.stdout.strip(),
        "error": result.stderr.strip() if result.returncode != 0 else None,
        "exit_code": result.returncode,
    }


@registry.tool(name="git_status", description="查看 Git 仓库状态")
def git_status(workdir: str | None = None) -> str:
    return json.dumps(_git("status --short", workdir), ensure_ascii=False)


@registry.tool(name="git_diff", description="查看 Git 差异")
def git_diff(path: str | None = None, staged: bool = False, workdir: str | None = None) -> str:
    cmd = "git diff"
    if staged:
        cmd += " --cached"
    if path:
        cmd += f" -- {path}"
    return json.dumps(_git(cmd, workdir), ensure_ascii=False)


@registry.tool(name="git_log", description="查看 Git 提交历史")
def git_log(n: int = 10, oneline: bool = True, workdir: str | None = None) -> str:
    cmd = f"git log -{n}"
    if oneline:
        cmd += " --oneline"
    return json.dumps(_git(cmd, workdir), ensure_ascii=False)


@registry.tool(name="git_commit", description="Git 提交")
def git_commit(message: str, add_all: bool = False, workdir: str | None = None) -> str:
    if add_all:
        _git("add -A", workdir)
    return json.dumps(_git(f'commit -m "{message}"', workdir), ensure_ascii=False)


@registry.tool(name="git_branch", description="列出/创建 Git 分支")
def git_branch(name: str | None = None, workdir: str | None = None) -> str:
    if name:
        return json.dumps(_git(f"checkout -b {name}", workdir), ensure_ascii=False)
    return json.dumps(_git("branch -a", workdir), ensure_ascii=False)
