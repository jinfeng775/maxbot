"""
精确代码编辑器 — 参考 Claude Code FileEditTool

核心设计（来自 CC types.ts + utils.ts）：
- old_string / new_string 精确替换，不靠行号
- replace_all 批量替换
- 结构化 diff patch 生成
- 引号标准化（花引号 ↔ 直引号）
- 文件历史追踪（可撤销）
- 多 edit 顺序应用 + 冲突检测
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.tools._registry import registry


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class EditOperation:
    """单次编辑操作"""
    old_string: str
    new_string: str
    replace_all: bool = False


@dataclass
class EditResult:
    """编辑结果"""
    success: bool
    file_path: str
    old_string: str = ""
    new_string: str = ""
    replacements: int = 0
    diff: str = ""
    snippet: str = ""
    error: str = ""
    history_path: str = ""


# ── 引号标准化（CC utils.ts normalizeQuotes）──────────────

_CURLY_QUOTES = {
    "\u2018": "'",  # ' LEFT SINGLE
    "\u2019": "'",  # ' RIGHT SINGLE
    "\u201c": '"',  # " LEFT DOUBLE
    "\u201d": '"',  # " RIGHT DOUBLE
}


def normalize_quotes(text: str) -> str:
    """花引号 → 直引号"""
    for curly, straight in _CURLY_QUOTES.items():
        text = text.replace(curly, straight)
    return text


def find_actual_string(content: str, search: str) -> str | None:
    """
    在内容中查找匹配（CC findActualString）
    先精确匹配，再引号标准化匹配
    """
    if search in content:
        return search

    norm_search = normalize_quotes(search)
    norm_content = normalize_quotes(content)

    idx = norm_content.find(norm_search)
    if idx != -1:
        return content[idx:idx + len(search)]

    return None


# ── Diff 生成 ─────────────────────────────────────────────

def generate_diff(original: str, modified: str, file_path: str = "file") -> str:
    """生成 unified diff"""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def generate_structured_patch(original: str, modified: str) -> list[dict]:
    """
    生成结构化 patch（CC 风格的 hunks）
    每个 hunk: {oldStart, oldLines, newStart, newLines, lines}
    """
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = list(difflib.unified_diff(orig_lines, mod_lines, n=3))

    hunks = []
    current_hunk = None

    for line in diff:
        # 解析 hunk header: @@ -old_start,old_count +new_start,new_count @@
        match = re.match(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            current_hunk = {
                "oldStart": old_start,
                "oldLines": old_count,
                "newStart": new_start,
                "newLines": new_count,
                "lines": [],
            }
        elif current_hunk and (line.startswith("+") or line.startswith("-") or line.startswith(" ")):
            current_hunk["lines"].append(line.rstrip("\n"))

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def get_snippet(content: str, change_line: int, context: int = 4) -> str:
    """获取变更位置的上下文 snippet（CC getSnippet）
    change_line: 1-indexed 行号
    """
    lines = content.splitlines()
    # change_line 是 1-indexed，转成 0-indexed
    center = change_line - 1
    start = max(0, center - context)
    end = min(len(lines), center + context + 1)
    snippet_lines = []
    for i in range(start, end):
        snippet_lines.append(f"{i+1:4d}|{lines[i]}")
    return "\n".join(snippet_lines)


# ── 文件历史（CC fileHistory）─────────────────────────────

_HISTORY_DIR = Path.home() / ".maxbot" / "file_history"


def _save_history(file_path: str) -> str:
    """保存文件编辑前的副本"""
    p = Path(file_path)
    if not p.exists():
        return ""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_name = str(p).replace("/", "_").replace("\\", "_")
    history_file = _HISTORY_DIR / f"{safe_name}_{ts}.bak"
    shutil.copy2(str(p), str(history_file))
    return str(history_file)


# ── 核心编辑逻辑（CC applyEditToFile + getPatchForEdits）──

def apply_edit(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> tuple[str, int]:
    """
    应用编辑到内容字符串

    返回：(新内容, 替换次数)
    """
    if not old_string:
        # 空文件写入
        return new_string, 1

    # 引号标准化查找
    actual_old = find_actual_string(content, old_string)
    if actual_old is None:
        return content, 0

    if replace_all:
        count = content.count(actual_old)
        new_content = content.replace(actual_old, new_string)
    else:
        count = 1
        new_content = content.replace(actual_old, new_string, 1)

    # 特殊处理：删除时如果 old_string 后面有换行也删掉
    if not new_string and not old_string.endswith("\n") and (actual_old + "\n") in content:
        new_content = content.replace(actual_old + "\n", new_string, 1 if not replace_all else -1)

    return new_content, count


def apply_edits(content: str, edits: list[EditOperation]) -> tuple[str, list[int]]:
    """
    顺序应用多个编辑（CC getPatchForEdits）

    返回：(新内容, 每个 edit 的替换次数列表)
    """
    current = content
    counts = []
    applied_new_strings = []

    for edit in edits:
        # 冲突检测：old_string 不能是之前某个 new_string 的子串
        for prev_new in applied_new_strings:
            if edit.old_string and edit.old_string in prev_new:
                raise ValueError(
                    f"编辑冲突: old_string 是之前 new_string 的子串\n"
                    f"  old_string: {edit.old_string[:80]}\n"
                    f"  prev_new: {prev_new[:80]}"
                )

        new_content, count = apply_edit(current, edit.old_string, edit.new_string, edit.replace_all)

        if count == 0 and edit.old_string:
            raise ValueError(f"未找到匹配文本: {edit.old_string[:80]}")

        counts.append(count)
        applied_new_strings.append(edit.new_string)
        current = new_content

    if current == content:
        raise ValueError("所有编辑均未修改文件内容")

    return current, counts


# ── 工具定义 ──────────────────────────────────────────────

@registry.tool(
    name="code_edit",
    description=(
        "精确编辑文件内容。通过 old_string（原文）→ new_string（替换文本）进行替换。"
        "替换前会展示 diff 预览。支持 replace_all 批量替换。"
        "编辑前自动保存历史副本，可通过 undo_edit 撤销。"
    ),
)
def code_edit(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"}, ensure_ascii=False)

    # 读取原内容
    original = p.read_text(encoding="utf-8", errors="replace")

    # 检查匹配
    actual_old = find_actual_string(original, old_string)
    if actual_old is None:
        # 提供上下文帮助
        lines = original.splitlines()
        suggestions = []
        for i, line in enumerate(lines):
            if old_string[:20] in line:
                suggestions.append(f"  行 {i+1}: {line.strip()[:80]}")
        hint = f"\n可能的匹配:\n" + "\n".join(suggestions[:5]) if suggestions else ""
        return json.dumps({
            "error": f"未找到匹配文本",
            "old_string": old_string[:100],
            "hint": hint,
        }, ensure_ascii=False)

    # 多处匹配检查（非 replace_all 时）
    if not replace_all:
        match_count = original.count(actual_old)
        if match_count > 1:
            return json.dumps({
                "error": f"找到 {match_count} 处匹配，请使用 replace_all=true 或提供更精确的上下文",
                "match_count": match_count,
            }, ensure_ascii=False)

    # 保存历史
    history_path = _save_history(file_path)

    # 应用编辑
    try:
        new_content, count = apply_edit(original, old_string, new_string, replace_all)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # 生成 diff
    diff = generate_diff(original, new_content, file_path)

    # 生成 snippet
    # 找到变更发生的大致行号
    before = original.split(old_string)[0] if old_string else ""
    change_line = before.count("\n") + 1
    snippet = get_snippet(new_content, change_line, context=3)

    # 写入文件
    p.write_text(new_content, encoding="utf-8")

    # 结构化 patch
    patch = generate_structured_patch(original, new_content)

    result = EditResult(
        success=True,
        file_path=str(p),
        old_string=old_string[:200],
        new_string=new_string[:200],
        replacements=count,
        diff=diff,
        snippet=snippet,
        history_path=history_path,
    )

    return json.dumps({
        "success": result.success,
        "file_path": result.file_path,
        "replacements": result.replacements,
        "diff": result.diff,
        "snippet": result.snippet,
        "history_path": result.history_path,
        "patch": patch,
    }, ensure_ascii=False)


@registry.tool(
    name="code_edit_multi",
    description="批量编辑文件。按顺序应用多个 old_string→new_string 替换。",
)
def code_edit_multi(file_path: str, edits: list[dict]) -> str:
    """
    批量编辑
    edits: [{"old_string": "...", "new_string": "...", "replace_all": false}, ...]
    """
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"}, ensure_ascii=False)

    original = p.read_text(encoding="utf-8", errors="replace")
    history_path = _save_history(file_path)

    edit_ops = [
        EditOperation(
            old_string=e.get("old_string", ""),
            new_string=e.get("new_string", ""),
            replace_all=e.get("replace_all", False),
        )
        for e in edits
    ]

    try:
        new_content, counts = apply_edits(original, edit_ops)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    diff = generate_diff(original, new_content, file_path)
    patch = generate_structured_patch(original, new_content)

    p.write_text(new_content, encoding="utf-8")

    return json.dumps({
        "success": True,
        "file_path": str(p),
        "edits_applied": len(edit_ops),
        "replacements_per_edit": counts,
        "total_replacements": sum(counts),
        "diff": diff,
        "patch": patch,
        "history_path": history_path,
    }, ensure_ascii=False)


@registry.tool(
    name="undo_edit",
    description="撤销最近一次编辑，从历史备份恢复文件。",
)
def undo_edit(file_path: str) -> str:
    p = Path(file_path).expanduser()
    safe_name = str(p).replace("/", "_").replace("\\", "_")

    if not _HISTORY_DIR.exists():
        return json.dumps({"error": "无编辑历史"}, ensure_ascii=False)

    # 找最新的备份
    backups = sorted(_HISTORY_DIR.glob(f"{safe_name}_*.bak"), reverse=True)
    if not backups:
        return json.dumps({"error": f"无 {file_path} 的编辑历史"}, ensure_ascii=False)

    latest = backups[0]
    shutil.copy2(str(latest), str(p))
    latest.unlink()  # 删除已用的备份

    return json.dumps({
        "success": True,
        "file_path": str(p),
        "restored_from": str(latest),
    }, ensure_ascii=False)


@registry.tool(
    name="code_create",
    description="创建新文件并写入内容。如果文件已存在则报错（除非 overwrite=true）。",
)
def code_create(file_path: str, content: str, overwrite: bool = False) -> str:
    p = Path(file_path).expanduser()
    if p.exists() and not overwrite:
        return json.dumps({
            "error": f"文件已存在: {file_path}。使用 overwrite=true 覆盖",
        }, ensure_ascii=False)

    if p.exists():
        _save_history(file_path)

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    lines = content.count("\n") + 1
    return json.dumps({
        "success": True,
        "file_path": str(p),
        "lines": lines,
        "bytes": len(content.encode()),
    }, ensure_ascii=False)
