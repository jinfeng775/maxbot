"""
Jupyter Notebook 编辑工具 — 参考 Claude Code NotebookEditTool

支持：
- 读取 .ipynb 文件
- 编辑指定 cell
- 插入/删除 cell
- 列出 cell 信息
"""

from __future__ import annotations

import json
from pathlib import Path

from maxbot.tools._registry import registry


def _load_notebook(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_notebook(path: Path, nb: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)


@registry.tool(
    name="notebook_read",
    description="读取 Jupyter Notebook (.ipynb) 文件，列出所有 cell 信息",
)
def notebook_read(file_path: str, cell_index: int | None = None) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    nb = _load_notebook(p)
    cells = nb.get("cells", [])

    if cell_index is not None:
        if cell_index < 0 or cell_index >= len(cells):
            return json.dumps({"error": f"cell_index {cell_index} 超出范围 (0-{len(cells)-1})"})
        cell = cells[cell_index]
        source = "".join(cell.get("source", []))
        return json.dumps({
            "cell_index": cell_index,
            "cell_type": cell.get("cell_type", "code"),
            "source": source,
            "outputs_count": len(cell.get("outputs", [])) if cell.get("cell_type") == "code" else 0,
        }, ensure_ascii=False)

    # 列出所有 cell
    cell_info = []
    for i, cell in enumerate(cells):
        source = "".join(cell.get("source", []))
        cell_info.append({
            "index": i,
            "type": cell.get("cell_type", "code"),
            "lines": source.count("\n") + 1,
            "preview": source[:80].replace("\n", "\\n"),
        })

    return json.dumps({
        "file_path": str(p),
        "kernel": nb.get("metadata", {}).get("kernelspec", {}).get("name", "unknown"),
        "total_cells": len(cells),
        "cells": cell_info,
    }, ensure_ascii=False)


@registry.tool(
    name="notebook_edit_cell",
    description="编辑 Jupyter Notebook 中指定 cell 的内容",
)
def notebook_edit_cell(file_path: str, cell_index: int, new_source: str) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    nb = _load_notebook(p)
    cells = nb.get("cells", [])

    if cell_index < 0 or cell_index >= len(cells):
        return json.dumps({"error": f"cell_index {cell_index} 超出范围 (0-{len(cells)-1})"})

    cell = cells[cell_index]
    old_source = "".join(cell.get("source", []))

    # notebook 的 source 是字符串数组
    cell["source"] = new_source.split("\n")
    # 每行后面加 \n，最后一行不加
    cell["source"] = [line + "\n" for i, line in enumerate(cell["source"])]
    if cell["source"]:
        cell["source"][-1] = cell["source"][-1].rstrip("\n")

    # 清空 outputs
    if cell.get("cell_type") == "code":
        cell["outputs"] = []
        cell["execution_count"] = None

    _save_notebook(p, nb)

    return json.dumps({
        "success": True,
        "file_path": str(p),
        "cell_index": cell_index,
        "old_lines": old_source.count("\n") + 1,
        "new_lines": new_source.count("\n") + 1,
    }, ensure_ascii=False)


@registry.tool(
    name="notebook_insert_cell",
    description="在 Jupyter Notebook 的指定位置插入新 cell",
)
def notebook_insert_cell(
    file_path: str,
    cell_type: str = "code",
    source: str = "",
    insert_after: int = -1,
) -> str:
    """
    insert_after: 在此 cell 索引之后插入。-1 表示插入到最前面。
    """
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    nb = _load_notebook(p)
    cells = nb.get("cells", [])

    new_cell = {
        "cell_type": cell_type,
        "source": [line + "\n" for line in source.split("\n")],
        "metadata": {},
    }
    if cell_type == "code":
        new_cell["outputs"] = []
        new_cell["execution_count"] = None

    insert_pos = insert_after + 1
    cells.insert(insert_pos, new_cell)

    _save_notebook(p, nb)

    return json.dumps({
        "success": True,
        "file_path": str(p),
        "inserted_at": insert_pos,
        "cell_type": cell_type,
        "total_cells": len(cells),
    }, ensure_ascii=False)


@registry.tool(
    name="notebook_delete_cell",
    description="删除 Jupyter Notebook 中指定的 cell",
)
def notebook_delete_cell(file_path: str, cell_index: int) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    nb = _load_notebook(p)
    cells = nb.get("cells", [])

    if cell_index < 0 or cell_index >= len(cells):
        return json.dumps({"error": f"cell_index {cell_index} 超出范围 (0-{len(cells)-1})"})

    removed = cells.pop(cell_index)
    _save_notebook(p, nb)

    return json.dumps({
        "success": True,
        "file_path": str(p),
        "removed_cell_index": cell_index,
        "removed_type": removed.get("cell_type", "unknown"),
        "remaining_cells": len(cells),
    }, ensure_ascii=False)
