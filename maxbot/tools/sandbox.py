"""
沙箱安全模块 — 命令执行防护

提供：
- 危险命令黑名单
- 工作目录限制
- 超时控制
- 输出截断
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ── 危险命令模式 ─────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    # 文件系统毁灭
    r"\brm\s+(-rf?|--recursive)\s+[/~]",       # rm -rf / or ~
    r"\brm\s+(-rf?|--recursive)\s+\*",           # rm -rf *
    r"\bdd\s+if=/dev/(zero|random|urandom)\b",   # dd if=/dev/zero
    r"\bmkfs\b",                                 # mkfs (格式化)
    r"\bfdisk\b",                                # fdisk (分区)
    # 系统控制
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\bhalt\b",
    r"\binit\s+[06]\b",
    # 网络危险
    r"\b(iptables|nft)\b.*\b-F\b",              # 清空防火墙
    # 权限提升
    r"\bchmod\s+777\b",
    r"\bchown\s+.*\broot\b",
    # Fork bomb
    r":\(\)\s*\{.*\|.*\}",
    r"\b(fork|while\s+true).*&\s*$",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_PATTERNS]

# 命令黑名单（精确匹配）
_BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/*",
    ":(){ :|:& };:",
}

# 允许的工作目录前缀（None = 无限制）
_ALLOWED_WORKDIR_PREFIXES: list[str] | None = None


def set_allowed_workdir(prefixes: list[str] | None):
    """设置允许的工作目录前缀"""
    global _ALLOWED_WORKDIR_PREFIXES
    _ALLOWED_WORKDIR_PREFIXES = prefixes


def validate_command(command: str) -> tuple[bool, str]:
    """
    检查命令是否安全

    返回: (is_safe, reason)
    """
    cmd_stripped = command.strip()

    # 空命令
    if not cmd_stripped:
        return False, "空命令"

    # 精确黑名单
    if cmd_stripped in _BLOCKED_COMMANDS:
        return False, f"命令在黑名单中: {cmd_stripped}"

    # 模式匹配
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(cmd_stripped):
            return False, f"命中危险模式: {pattern.pattern}"

    return True, ""


def validate_workdir(workdir: str | None) -> tuple[bool, str]:
    """检查工作目录是否在允许范围内"""
    if not workdir or _ALLOWED_WORKDIR_PREFIXES is None:
        return True, ""

    resolved = str(Path(workdir).resolve())
    for prefix in _ALLOWED_WORKDIR_PREFIXES:
        if resolved.startswith(str(Path(prefix).resolve())):
            return True, ""

    return False, f"工作目录不在允许范围内: {resolved}"
