"""文件操作工具 — 读、写、搜索、补丁"""

from __future__ import annotations

import os
import re
from pathlib import Path

from maxbot.tools._registry import registry


@registry.tool(name="read_file", description="读取文件内容，支持指定行范围")
def read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    import json
    p = Path(path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {path}"})
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    start = max(0, int(offset) - 1)
    end = min(total, start + int(limit))
    content = "\n".join(f"{i+1}|{line}" for i, line in enumerate(lines[start:end], start=start))
    return json.dumps({"content": content, "total_lines": total, "showing": f"{start+1}-{end}"})


@registry.tool(name="write_file", description="写入文件内容（完全覆盖）")
def write_file(path: str, content: str) -> str:
    import json
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return json.dumps({"success": True, "path": str(p), "bytes": len(content.encode())})


@registry.tool(name="search_files", description="在文件中搜索文本内容（正则）")
def search_files(pattern: str, path: str = ".", file_glob: str = "*.py", limit: int = 50) -> str:
    import json
    base = Path(path).expanduser()
    results = []
    regex = re.compile(pattern)
    for f in sorted(base.rglob(file_glob))[:500]:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append({"file": str(f), "line": i, "text": line.strip()})
                    if len(results) >= limit:
                        return json.dumps({"matches": results, "truncated": True})
        except Exception:
            continue
    return json.dumps({"matches": results, "truncated": False})


@registry.tool(name="patch_file", description="在文件中查找并替换文本")
def patch_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    import json
    p = Path(path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {path}"})
    text = p.read_text(encoding="utf-8")
    if old_string not in text:
        return json.dumps({"error": "未找到目标文本", "old_string": old_string[:100]})
    count = text.count(old_string) if replace_all else 1
    if not replace_all and count > 1:
        return json.dumps({"error": f"找到 {count} 处匹配，请使用 replace_all=true 或提供更精确的上下文"})
    new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    p.write_text(new_text, encoding="utf-8")
    return json.dumps({"success": True, "replacements": count, "path": str(p)})


@registry.tool(name="list_files", description="列出目录下的文件")
def list_files(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
    import json
    base = Path(path).expanduser()
    if not base.is_dir():
        return json.dumps({"error": f"目录不存在: {path}"})
    if recursive:
        files = [str(f.relative_to(base)) for f in base.rglob(pattern) if f.is_file()]
    else:
        files = [str(f.relative_to(base)) for f in base.glob(pattern) if f.is_file()]
    return json.dumps({"path": str(base), "files": sorted(files)[:200], "count": len(files)})
