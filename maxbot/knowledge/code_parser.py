"""
代码解析引擎 — 多语言 AST 解析 & 项目结构扫描

支持语言:
- Python: stdlib ast 模块（精确）
- JavaScript / TypeScript: 正则启发式
- Go: 正则启发式
- Rust: 正则启发式

参考: Claude Code FileEditTool 的代码理解能力
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FunctionInfo:
    """函数/方法信息"""
    name: str
    params: list[dict[str, str]] = field(default_factory=list)  # [{name, type, default}]
    return_type: str = ""
    docstring: str = ""
    is_async: bool = False
    is_method: bool = False
    line_start: int = 0
    line_end: int = 0
    decorators: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    bases: list[str] = field(default_factory=list)
    docstring: str = ""
    methods: list[FunctionInfo] = field(default_factory=list)
    line_start: int = 0
    decorators: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """模块信息"""
    file_path: str
    language: str
    docstring: str = ""
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


@dataclass
class ProjectStructure:
    """项目结构"""
    root: str
    languages: dict[str, int] = field(default_factory=dict)  # language -> file count
    modules: list[ModuleInfo] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)  # main files
    dependencies: dict[str, list[str]] = field(default_factory=dict)  # file -> imports
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0


# ── Language Detection ──────────────────────────────────────

_LANG_EXT_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

_ENTRY_POINT_FILES = {
    "main.py", "app.py", "server.py", "cli.py", "__main__.py", "run.py", "manage.py",
    "main.js", "index.js", "app.js", "server.js", "cli.js",
    "main.ts", "index.ts", "app.ts", "server.ts", "cli.ts",
    "main.go", "cmd.go",
    "main.rs", "lib.rs",
}

_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache", "vendor",
    "target", ".next", ".nuxt", ".maxbot_sandbox",
}


def detect_language(file_path: Path) -> str | None:
    """根据文件扩展名检测语言"""
    return _LANG_EXT_MAP.get(file_path.suffix.lower())


# ── Python Parser (ast) ─────────────────────────────────────

def _parse_python(source: str, file_path: str = "") -> ModuleInfo:
    """用 ast 模块精确解析 Python 文件"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ModuleInfo(file_path=file_path, language="python")

    docstring = ast.get_docstring(tree) or ""
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    imports: list[str] = []
    entry_points: list[str] = []

    for node in ast.iter_child_nodes(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

        # Top-level functions
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = _python_func_info(node)
            functions.append(func)

        # Classes
        elif isinstance(node, ast.ClassDef):
            cls = _python_class_info(node)
            classes.append(cls)

    # Entry point detection
    fname = Path(file_path).name if file_path else ""
    if fname in _ENTRY_POINT_FILES:
        entry_points.append(fname)
    # Check for if __name__ == "__main__"
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Compare):
                if (isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
                        and len(node.test.comparators) == 1
                        and isinstance(node.test.comparators[0], ast.Constant)
                        and node.test.comparators[0].value == "__main__"):
                    entry_points.append("__main__")
                    break

    return ModuleInfo(
        file_path=file_path,
        language="python",
        docstring=docstring,
        functions=functions,
        classes=classes,
        imports=imports,
        entry_points=entry_points,
    )


def _python_func_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
    """从 AST 节点提取函数信息"""
    params = []
    defaults_offset = len(node.args.args) - len(node.args.defaults)
    for i, arg in enumerate(node.args.args):
        if arg.arg in ("self", "cls"):
            continue
        p: dict[str, str] = {"name": arg.arg}
        if arg.annotation:
            try:
                p["type"] = ast.unparse(arg.annotation)
            except Exception:
                p["type"] = ""
        default_idx = i - defaults_offset
        if default_idx >= 0 and default_idx < len(node.args.defaults):
            try:
                p["default"] = ast.unparse(node.args.defaults[default_idx])
            except Exception:
                pass
        params.append(p)

    return_type = ""
    if node.returns:
        try:
            return_type = ast.unparse(node.returns)
        except Exception:
            pass

    decorators = []
    for dec in node.decorator_list:
        try:
            decorators.append(ast.unparse(dec))
        except Exception:
            pass

    return FunctionInfo(
        name=node.name,
        params=params,
        return_type=return_type,
        docstring=ast.get_docstring(node) or "",
        is_async=isinstance(node, ast.AsyncFunctionDef),
        is_method=False,  # set by caller if inside class
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        decorators=decorators,
    )


def _python_class_info(node: ast.ClassDef) -> ClassInfo:
    """从 AST 节点提取类信息"""
    bases = []
    for base in node.bases:
        try:
            bases.append(ast.unparse(base))
        except Exception:
            pass

    decorators = []
    for dec in node.decorator_list:
        try:
            decorators.append(ast.unparse(dec))
        except Exception:
            pass

    methods = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = _python_func_info(item)
            func.is_method = True
            methods.append(func)

    return ClassInfo(
        name=node.name,
        bases=bases,
        docstring=ast.get_docstring(node) or "",
        methods=methods,
        line_start=node.lineno,
        decorators=decorators,
    )


# ── JavaScript / TypeScript Parser (regex) ──────────────────

_RE_JS_FUNC = re.compile(
    r'(?:(?:export)\s+)?(?:(?:async)\s+)?(?:function)\s+(\w+)\s*\(([^)]*)\)',
    re.MULTILINE,
)
_RE_JS_ARROW = re.compile(
    r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
    re.MULTILINE,
)
_RE_JS_CLASS = re.compile(
    r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
    re.MULTILINE,
)
_RE_JS_DOC = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)
_RE_JS_METHOD = re.compile(
    r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{',
    re.MULTILINE,
)
_RE_TS_TYPE = re.compile(r'(\w+)\s*:\s*([A-Za-z_<>\[\]|]+)')


def _parse_js_ts(source: str, file_path: str = "", language: str = "javascript") -> ModuleInfo:
    """正则解析 JS/TS 文件"""
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    exports: list[str] = []
    imports: list[str] = []

    # Extract imports
    for m in re.finditer(r'(?:import\s+.*?from\s+["\']([^"\']+)["\']|require\s*\(\s*["\']([^"\']+)["\'])', source):
        imports.append(m.group(1) or m.group(2))

    # Extract exports
    for m in re.finditer(r'export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)', source):
        exports.append(m.group(1))

    # Functions (declaration style)
    for m in _RE_JS_FUNC.finditer(source):
        name = m.group(1)
        raw_params = m.group(2)
        params = _parse_js_params(raw_params, language)
        line = source[:m.start()].count('\n') + 1
        docstring = _find_docstring_before(source, m.start())
        functions.append(FunctionInfo(
            name=name, params=params, docstring=docstring,
            is_async="async" in source[max(0, m.start()-20):m.start()+10],
            line_start=line,
        ))

    # Arrow functions
    for m in _RE_JS_ARROW.finditer(source):
        name = m.group(1)
        raw_params = m.group(2)
        params = _parse_js_params(raw_params, language)
        line = source[:m.start()].count('\n') + 1
        docstring = _find_docstring_before(source, m.start())
        functions.append(FunctionInfo(
            name=name, params=params, docstring=docstring,
            is_async="async" in m.group(0),
            line_start=line,
        ))

    # Classes
    for m in _RE_JS_CLASS.finditer(source):
        cls_name = m.group(1)
        base = m.group(2) or ""
        line = source[:m.start()].count('\n') + 1
        docstring = _find_docstring_before(source, m.start())
        # Find methods within class body (rough)
        methods = []
        classes.append(ClassInfo(
            name=cls_name,
            bases=[base] if base else [],
            docstring=docstring,
            methods=methods,
            line_start=line,
        ))

    # Entry points
    entry_points = []
    fname = Path(file_path).name if file_path else ""
    if fname in _ENTRY_POINT_FILES:
        entry_points.append(fname)

    return ModuleInfo(
        file_path=file_path,
        language=language,
        functions=functions,
        classes=classes,
        imports=imports,
        exports=exports,
        entry_points=entry_points,
    )


def _parse_js_params(raw: str, language: str) -> list[dict[str, str]]:
    """解析 JS/TS 参数字符串"""
    if not raw.strip():
        return []
    params = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        # Handle destructuring, rest params
        if part.startswith("{") or part.startswith("[") or part.startswith("..."):
            params.append({"name": part.lstrip("...").strip()})
            continue
        # TypeScript typed params: name: type
        if ":" in part and language == "typescript":
            name, _, type_str = part.partition(":")
            default = ""
            if "=" in type_str:
                type_str, _, default = type_str.partition("=")
            p: dict[str, str] = {"name": name.strip(), "type": type_str.strip()}
            if default:
                p["default"] = default.strip()
            params.append(p)
        elif "=" in part:
            name, _, default = part.partition("=")
            params.append({"name": name.strip(), "default": default.strip()})
        else:
            params.append({"name": part})
    return params


def _find_docstring_before(source: str, pos: int) -> str:
    """查找位置之前的 JSDoc 注释"""
    before = source[:pos]
    matches = list(_RE_JS_DOC.finditer(before))
    if matches:
        last = matches[-1]
        return last.group(1).strip().replace(" * ", " ").replace(" *", "")
    return ""


# ── Go Parser (regex) ──────────────────────────────────────

_RE_GO_FUNC = re.compile(
    r'func\s+(?:\(([^)]+)\)\s+)?(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]*)\)|([\w.*\[\]]+))?',
    re.MULTILINE,
)
_RE_GO_DOC = re.compile(r'//\s*(.*)', re.MULTILINE)


def _parse_go(source: str, file_path: str = "") -> ModuleInfo:
    """正则解析 Go 文件"""
    functions: list[FunctionInfo] = []
    imports: list[str] = []

    # Extract imports
    import_block = re.search(r'import\s*\((.*?)\)', source, re.DOTALL)
    if import_block:
        for m in re.finditer(r'"([^"]+)"', import_block.group(1)):
            imports.append(m.group(1))
    for m in re.finditer(r'import\s+"([^"]+)"', source):
        if m.group(1) not in imports:
            imports.append(m.group(1))

    # Extract functions
    for m in _RE_GO_FUNC.finditer(source):
        receiver = m.group(1)  # method receiver
        name = m.group(2)
        raw_params = m.group(3)
        return_type = (m.group(4) or m.group(5) or "").strip()

        params = []
        if raw_params.strip():
            for part in raw_params.split(","):
                part = part.strip()
                if not part:
                    continue
                tokens = part.split()
                if len(tokens) >= 2:
                    params.append({"name": tokens[0], "type": " ".join(tokens[1:])})
                else:
                    params.append({"name": tokens[0]})

        line = source[:m.start()].count('\n') + 1
        # Docstring: consecutive // lines before func
        docstring = _find_go_docstring(source, m.start())

        functions.append(FunctionInfo(
            name=name,
            params=params,
            return_type=return_type,
            docstring=docstring,
            is_method=bool(receiver),
            line_start=line,
        ))

    entry_points = []
    fname = Path(file_path).name if file_path else ""
    if fname in _ENTRY_POINT_FILES:
        entry_points.append(fname)
    if "func main()" in source:
        entry_points.append("main()")

    return ModuleInfo(
        file_path=file_path,
        language="go",
        functions=functions,
        imports=imports,
        entry_points=entry_points,
    )


def _find_go_docstring(source: str, pos: int) -> str:
    """提取 Go 函数前的 // 注释"""
    before = source[:pos].rstrip()
    lines = before.split("\n")
    doc_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("//"):
            doc_lines.insert(0, stripped[2:].strip())
        elif stripped == "":
            continue
        else:
            break
    return "\n".join(doc_lines)


# ── Rust Parser (regex) ─────────────────────────────────────

_RE_RUST_FN = re.compile(
    r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)(?:<[^>]*>)?\s*\(([^)]*)\)\s*(?:->\s*([^\s{]+))?',
    re.MULTILINE,
)
_RE_RUST_STRUCT = re.compile(
    r'(?:pub\s+)?struct\s+(\w+)',
    re.MULTILINE,
)
_RE_RUST_IMPL = re.compile(
    r'impl(?:<[^>]*>)?\s+(\w+)',
    re.MULTILINE,
)
_RE_RUST_DOC = re.compile(r'///\s*(.*)', re.MULTILINE)


def _parse_rust(source: str, file_path: str = "") -> ModuleInfo:
    """正则解析 Rust 文件"""
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    imports: list[str] = []
    exports: list[str] = []

    # use statements
    for m in re.finditer(r'use\s+([\w:]+)', source):
        imports.append(m.group(1))

    # pub items = exports
    for m in re.finditer(r'pub\s+(?:fn|struct|enum|trait|type)\s+(\w+)', source):
        exports.append(m.group(1))

    # Functions
    for m in _RE_RUST_FN.finditer(source):
        name = m.group(1)
        raw_params = m.group(2)
        return_type = m.group(3) or ""

        params = []
        if raw_params.strip():
            for part in raw_params.split(","):
                part = part.strip()
                if not part or part == "self" or part == "&self" or part == "&mut self":
                    continue
                if ":" in part:
                    pname, _, ptype = part.partition(":")
                    params.append({"name": pname.strip(), "type": ptype.strip()})
                else:
                    params.append({"name": part})

        line = source[:m.start()].count('\n') + 1
        docstring = _find_rust_docstring(source, m.start())
        is_async = "async fn" in source[max(0, m.start()-10):m.start()+10]

        functions.append(FunctionInfo(
            name=name,
            params=params,
            return_type=return_type.strip(),
            docstring=docstring,
            is_async=is_async,
            line_start=line,
        ))

    # Structs
    for m in _RE_RUST_STRUCT.finditer(source):
        struct_name = m.group(1)
        line = source[:m.start()].count('\n') + 1
        docstring = _find_rust_docstring(source, m.start())
        classes.append(ClassInfo(
            name=struct_name,
            docstring=docstring,
            line_start=line,
        ))

    entry_points = []
    fname = Path(file_path).name if file_path else ""
    if fname in _ENTRY_POINT_FILES:
        entry_points.append(fname)
    if "fn main()" in source:
        entry_points.append("fn main()")

    return ModuleInfo(
        file_path=file_path,
        language="rust",
        functions=functions,
        classes=classes,
        imports=imports,
        exports=exports,
        entry_points=entry_points,
    )


def _find_rust_docstring(source: str, pos: int) -> str:
    """提取 Rust 函数前的 /// 注释"""
    before = source[:pos].rstrip()
    lines = before.split("\n")
    doc_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("///"):
            doc_lines.insert(0, stripped[3:].strip())
        elif stripped == "":
            continue
        else:
            break
    return "\n".join(doc_lines)


# ── Unified Parser ──────────────────────────────────────────

_PARSERS = {
    "python": _parse_python,
    "javascript": lambda s, fp: _parse_js_ts(s, fp, "javascript"),
    "typescript": lambda s, fp: _parse_js_ts(s, fp, "typescript"),
    "go": _parse_go,
    "rust": _parse_rust,
}


def parse_file(file_path: str | Path) -> ModuleInfo | None:
    """解析单个文件"""
    path = Path(file_path)
    if not path.is_file():
        return None

    lang = detect_language(path)
    if lang is None:
        return None

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    parser = _PARSERS.get(lang)
    if not parser:
        return None

    return parser(source, str(path))


def scan_project(root: str | Path, max_files: int = 5000) -> ProjectStructure:
    """扫描整个项目，提取结构信息"""
    root = Path(root)
    if not root.is_dir():
        return ProjectStructure(root=str(root))

    structure = ProjectStructure(root=str(root))
    file_count = 0

    for file_path in root.rglob("*"):
        if file_count >= max_files:
            break
        if not file_path.is_file():
            continue
        # Skip hidden/build dirs
        if any(part in _SKIP_DIRS for part in file_path.parts):
            continue
        if any(part.startswith(".") and part not in (".", "..") for part in file_path.parts):
            continue

        lang = detect_language(file_path)
        if lang is None:
            continue

        structure.languages[lang] = structure.languages.get(lang, 0) + 1

        module = parse_file(file_path)
        if module:
            # Make path relative
            try:
                module.file_path = str(file_path.relative_to(root))
            except ValueError:
                pass
            structure.modules.append(module)
            structure.total_functions += len(module.functions)
            structure.total_classes += len(module.classes)
            # Count lines
            try:
                structure.total_lines += len(file_path.read_text(errors="replace").splitlines())
            except Exception:
                pass
            # Collect entry points
            for ep in module.entry_points:
                structure.entry_points.append(f"{module.file_path}:{ep}")

        file_count += 1

    # Build dependency graph
    for module in structure.modules:
        if module.imports:
            structure.dependencies[module.file_path] = module.imports

    return structure


def summarize_structure(structure: ProjectStructure) -> str:
    """生成项目结构摘要（文本格式）"""
    lines = [
        f"# 项目结构: {structure.root}",
        f"- 语言分布: {json.dumps(structure.languages, ensure_ascii=False)}",
        f"- 文件数: {len(structure.modules)}",
        f"- 总行数: {structure.total_lines}",
        f"- 函数数: {structure.total_functions}",
        f"- 类/结构体数: {structure.total_classes}",
    ]

    if structure.entry_points:
        lines.append(f"- 入口点: {', '.join(structure.entry_points[:10])}")

    # List all functions with docstrings
    lines.append("\n## 可提取的函数")
    for module in structure.modules:
        for func in module.functions:
            if func.docstring and not func.name.startswith("_"):
                params_str = ", ".join(
                    f"{p['name']}: {p.get('type', 'any')}" for p in func.params
                )
                lines.append(f"- `{module.file_path}::{func.name}({params_str})` — {func.docstring[:100]}")
        for cls in module.classes:
            for method in cls.methods:
                if method.docstring and not method.name.startswith("_"):
                    params_str = ", ".join(
                        f"{p['name']}: {p.get('type', 'any')}" for p in method.params
                    )
                    lines.append(f"- `{module.file_path}::{cls.name}.{method.name}({params_str})` — {method.docstring[:100]}")

    return "\n".join(lines)
