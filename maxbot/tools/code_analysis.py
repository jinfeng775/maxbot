"""
代码分析工具 — AST 解析、函数/类提取、依赖分析

使用 Python 标准库 ast 模块 + tree-sitter（多语言）
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from maxbot.tools._registry import registry


# ── Python AST 分析 ───────────────────────────────────────

@registry.tool(
    name="analyze_python",
    description="分析 Python 文件结构：函数、类、导入、全局变量",
)
def analyze_python(file_path: str) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    try:
        source = p.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(p))
    except SyntaxError as e:
        return json.dumps({"error": f"语法错误: {e}"})

    result = {
        "file_path": str(p),
        "lines": source.count("\n") + 1,
        "imports": [],
        "classes": [],
        "functions": [],
        "global_vars": [],
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append({
                    "type": "import",
                    "module": alias.name,
                    "as": alias.asname,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                result["imports"].append({
                    "type": "from",
                    "module": node.module or "",
                    "name": alias.name,
                    "as": alias.asname,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in item.args.args if a.arg != "self"]
                    methods.append({
                        "name": item.name,
                        "args": args,
                        "line": item.lineno,
                        "is_async": isinstance(item, ast.AsyncFunctionDef),
                        "is_private": item.name.startswith("_"),
                    })
            result["classes"].append({
                "name": node.name,
                "bases": [ast.unparse(b) for b in node.bases],
                "methods": methods,
                "line": node.lineno,
                "line_end": getattr(node, "end_lineno", node.lineno),
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            result["functions"].append({
                "name": node.name,
                "args": args,
                "line": node.lineno,
                "line_end": getattr(node, "end_lineno", node.lineno),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "is_private": node.name.startswith("_"),
                "decorators": [ast.unparse(d) for d in node.decorator_list],
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result["global_vars"].append({
                        "name": target.id,
                        "line": node.lineno,
                    })

    return json.dumps(result, ensure_ascii=False)


# ── 通用代码分析 ──────────────────────────────────────────

@registry.tool(
    name="analyze_code",
    description="通用代码分析：行数统计、函数/类概览、导入依赖（支持任意语言的简单启发式）",
)
def analyze_code(file_path: str) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    # Python 用 AST
    if p.suffix == ".py":
        return analyze_python(file_path)

    # 其他语言用启发式分析
    source = p.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()

    result = {
        "file_path": str(p),
        "language": _guess_language(p.suffix),
        "total_lines": len(lines),
        "code_lines": sum(1 for l in lines if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("#")),
        "comment_lines": sum(1 for l in lines if l.strip().startswith("//") or l.strip().startswith("#")),
        "blank_lines": sum(1 for l in lines if not l.strip()),
    }

    # 通用正则提取
    funcs = []
    classes = []

    # JavaScript/TypeScript
    if p.suffix in (".js", ".ts", ".tsx", ".jsx"):
        for i, line in enumerate(lines, 1):
            m = re.match(r"^(export\s+)?(async\s+)?function\s+(\w+)", line)
            if m:
                funcs.append({"name": m.group(3), "line": i, "async": bool(m.group(2))})
            m = re.match(r"^(export\s+)?(default\s+)?class\s+(\w+)", line)
            if m:
                classes.append({"name": m.group(3), "line": i})
            m = re.match(r"^\s+(async\s+)?(\w+)\s*\(", line)
            if m and m.group(2) not in ("if", "for", "while", "switch", "return", "import", "export", "const", "let", "var"):
                funcs.append({"name": m.group(2), "line": i, "async": bool(m.group(1))})

    # Go
    elif p.suffix == ".go":
        for i, line in enumerate(lines, 1):
            m = re.match(r"^func\s+(\(.*?\)\s+)?(\w+)\(", line)
            if m:
                funcs.append({"name": m.group(2), "line": i})
            m = re.match(r"^type\s+(\w+)\s+struct", line)
            if m:
                classes.append({"name": m.group(1), "line": i})

    # Rust
    elif p.suffix == ".rs":
        for i, line in enumerate(lines, 1):
            m = re.match(r"^(pub\s+)?(async\s+)?fn\s+(\w+)", line)
            if m:
                funcs.append({"name": m.group(3), "line": i, "async": bool(m.group(2))})
            m = re.match(r"^(pub\s+)?struct\s+(\w+)", line)
            if m:
                classes.append({"name": m.group(2), "line": i})
            m = re.match(r"^(pub\s+)?enum\s+(\w+)", line)
            if m:
                classes.append({"name": m.group(2), "line": i, "type": "enum"})

    result["functions"] = funcs
    result["classes"] = classes

    return json.dumps(result, ensure_ascii=False)


def _guess_language(ext: str) -> str:
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".jsx": "javascript",
        ".go": "go", ".rs": "rust", ".rb": "ruby",
        ".java": "java", ".c": "c", ".cpp": "cpp",
        ".cs": "csharp", ".php": "php", ".swift": "swift",
        ".kt": "kotlin", ".scala": "scala", ".sh": "shell",
    }
    return lang_map.get(ext, "unknown")


# ── 项目结构分析 ──────────────────────────────────────────

@registry.tool(
    name="analyze_project",
    description="分析项目结构：目录树、文件统计、主要语言",
)
def analyze_project(project_path: str = ".", max_depth: int = 3) -> str:
    base = Path(project_path).expanduser()
    if not base.is_dir():
        return json.dumps({"error": f"目录不存在: {project_path}"})

    file_stats: dict[str, int] = {}
    total_files = 0
    total_lines = 0
    dir_tree = []

    for p in sorted(base.rglob("*")):
        if any(part.startswith(".") for part in p.parts):
            continue
        if any(part in ("__pycache__", "node_modules", "venv", ".git") for part in p.parts):
            continue

        rel = p.relative_to(base)
        depth = len(rel.parts)

        if depth > max_depth:
            continue

        if p.is_dir():
            dir_tree.append({"type": "dir", "path": str(rel), "depth": depth})
        else:
            ext = p.suffix
            file_stats[ext] = file_stats.get(ext, 0) + 1
            total_files += 1
            try:
                lines = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                total_lines += lines
            except Exception:
                pass
            dir_tree.append({"type": "file", "path": str(rel), "ext": ext, "depth": depth})

    # 主要语言排序
    top_langs = sorted(file_stats.items(), key=lambda x: -x[1])

    return json.dumps({
        "project_path": str(base),
        "total_files": total_files,
        "total_lines": total_lines,
        "languages": [{"ext": ext, "count": count} for ext, count in top_langs[:10]],
        "tree": dir_tree[:200],
    }, ensure_ascii=False)


# ── 函数详细分析 ──────────────────────────────────────────

@registry.tool(
    name="get_function",
    description="获取 Python 文件中指定函数的完整源码和信息",
)
def get_function(file_path: str, function_name: str) -> str:
    p = Path(file_path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"文件不存在: {file_path}"})

    source = p.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return json.dumps({"error": f"语法错误: {e}"})

    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)
            func_source = "\n".join(lines[start:end])
            args = [a.arg for a in node.args.args]

            return json.dumps({
                "name": node.name,
                "file_path": str(p),
                "line_start": node.lineno,
                "line_end": end,
                "args": args,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "decorators": [ast.unparse(d) for d in node.decorator_list],
                "source": func_source,
            }, ensure_ascii=False)

    return json.dumps({"error": f"未找到函数: {function_name}"}, ensure_ascii=False)
