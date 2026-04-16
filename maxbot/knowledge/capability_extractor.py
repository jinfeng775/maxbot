"""
能力提取器 — LLM 驱动的代码分析 & 工具定义生成

核心流程:
1. 从 code_parser 拿到项目结构和函数列表
2. 用 LLM 分析每个函数/类的能力
3. 生成标准化的工具定义（ToolDef 格式）

参考: Claude Code 的 tool_use 模式 — 先理解代码意图，再生成调用契约
"""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from maxbot.knowledge.code_parser import (
    ModuleInfo, ProjectStructure, FunctionInfo, ClassInfo,
    parse_file, scan_project, summarize_structure,
)


@dataclass
class ExtractedCapability:
    """从代码中提取的可复用能力"""
    name: str
    description: str
    source_file: str
    source_function: str
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema properties
    required_params: list[str] = field(default_factory=list)
    return_description: str = ""
    is_async: bool = False
    is_method: bool = False
    class_name: str = ""
    toolset: str = "absorbed"
    tags: list[str] = field(default_factory=list)
    handler_code: str = ""  # 生成的 handler Python 代码
    raw_docstring: str = ""
    confidence: float = 0.0  # LLM 对提取结果的信心
    repo_path: str = ""  # 吸收的代码仓库路径（用于 handler 导入）

    def to_tool_schema(self) -> dict[str, Any]:
        """转为 OpenAI function calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params,
                },
            },
        }

    def fingerprint(self) -> str:
        """唯一指纹，用于去重"""
        key = f"{self.source_file}::{self.source_function}"
        return hashlib.md5(key.encode()).hexdigest()[:12]


# ── LLM Analysis Prompt Templates ───────────────────────────

_SYSTEM_PROMPT = """你是一个代码分析专家。你的任务是分析给定的代码片段，判断它是否可以被复用为一个独立的工具（Tool）。

判断标准：
1. 函数有明确的输入输出
2. 不依赖复杂的全局状态
3. 可以独立调用（不是内部辅助函数）
4. 完成一个有意义的任务

对于每个可复用的函数，你需要生成：
- 工具名称（snake_case，语义清晰）
- 一句话描述
- 参数的 JSON Schema
- 返回值说明
- handler 代码（Python 函数，调用原始函数逻辑）

只提取真正有价值的函数。内部工具函数、getter/setter、测试函数跳过。"""


def _build_analysis_prompt(module: ModuleInfo, project_summary: str = "") -> str:
    """构建代码分析 prompt"""
    parts = [
        f"# 分析文件: {module.file_path}",
        f"语言: {module.language}",
    ]

    if module.docstring:
        parts.append(f"模块文档: {module.docstring[:300]}")

    if module.imports:
        parts.append(f"依赖: {', '.join(module.imports[:20])}")

    if project_summary:
        parts.append(f"\n## 项目上下文\n{project_summary[:2000]}")

    parts.append("\n## 函数列表")

    for func in module.functions:
        if func.name.startswith("_") or func.name.startswith("test_"):
            continue
        params_str = ", ".join(
            f"{p['name']}: {p.get('type', 'any')}" for p in func.params
        )
        parts.append(f"### {func.name}({params_str})")
        if func.return_type:
            parts.append(f"返回: {func.return_type}")
        if func.docstring:
            parts.append(f"文档: {func.docstring[:500]}")
        if func.decorators:
            parts.append(f"装饰器: {', '.join(func.decorators)}")
        parts.append(f"行号: {func.line_start}-{func.line_end}")

    for cls in module.classes:
        if cls.name.startswith("_"):
            continue
        parts.append(f"\n### 类 {cls.name}")
        if cls.bases:
            parts.append(f"继承: {', '.join(cls.bases)}")
        if cls.docstring:
            parts.append(f"文档: {cls.docstring[:300]}")
        for method in cls.methods:
            if method.name.startswith("_"):
                continue
            params_str = ", ".join(
                f"{p['name']}: {p.get('type', 'any')}" for p in method.params
            )
            parts.append(f"  - {method.name}({params_str})")
            if method.docstring:
                parts.append(f"    文档: {method.docstring[:300]}")

    parts.append("""
请以 JSON 数组格式回复，每个元素代表一个可提取的工具：
```json
[
  {
    "tool_name": "descriptive_snake_case_name",
    "description": "一句话描述这个工具做什么",
    "source_function": "原始函数名",
    "source_class": "原始类名（如果是方法）",
    "parameters": {
      "type": "object",
      "properties": {
        "param_name": {"type": "string", "description": "参数说明"}
      },
      "required": ["param_name"]
    },
    "return_description": "返回值说明",
    "handler_code": "def tool_name(param: str) -> str:\\n    # 调用原始逻辑\\n    return json.dumps(result)",
    "tags": ["tag1", "tag2"],
    "confidence": 0.9
  }
]
```

如果没有值得提取的函数，返回空数组 []。
只返回 JSON，不要有其他文字。""")

    return "\n".join(parts)


# ── Heuristic (No-LLM) Extraction ──────────────────────────

def extract_capabilities_heuristic(
    module: ModuleInfo,
    min_docstring_len: int = 20,
    repo_path: str = "",
) -> list[ExtractedCapability]:
    """
    基于启发式规则提取能力（不需要 LLM）

    规则:
    - 函数有 docstring（≥ min_docstring_len 字符）
    - 不是私有函数（不以 _ 开头）
    - 不是测试函数
    - 至少有 1 个参数（纯副作用函数跳过）
    """
    capabilities = []

    for func in module.functions:
        if func.name.startswith("_") or func.name.startswith("test_"):
            continue
        if len(func.docstring) < min_docstring_len:
            continue

        # Build parameters schema
        properties = {}
        required = []
        for p in func.params:
            pname = p["name"]
            ptype = p.get("type", "str")
            json_type = _python_type_to_json(ptype)
            prop: dict[str, Any] = {"type": json_type}
            if "default" in p:
                prop["default"] = p["default"]
            else:
                required.append(pname)
            properties[pname] = prop

        # Generate handler code
        handler = _generate_handler_code(func, module, repo_path)

        cap = ExtractedCapability(
            name=f"{Path(module.file_path).stem}_{func.name}",
            description=func.docstring.split("\n")[0][:200],
            source_file=module.file_path,
            source_function=func.name,
            parameters=properties,
            required_params=required,
            is_async=func.is_async,
            raw_docstring=func.docstring,
            handler_code=handler,
            confidence=0.6,  # heuristic — lower confidence
            tags=[module.language, "auto-extracted"],
            repo_path=repo_path,
        )
        capabilities.append(cap)

    # Also extract class methods with docstrings
    for cls in module.classes:
        for method in cls.methods:
            if method.name.startswith("_") or method.name.startswith("test_"):
                continue
            if len(method.docstring) < min_docstring_len:
                continue

            properties = {}
            required = []
            for p in method.params:
                pname = p["name"]
                ptype = p.get("type", "str")
                json_type = _python_type_to_json(ptype)
                prop = {"type": json_type}
                if "default" in p:
                    prop["default"] = p["default"]
                else:
                    required.append(pname)
                properties[pname] = prop

            handler = _generate_method_handler_code(method, cls, module, repo_path)

            cap = ExtractedCapability(
                name=f"{Path(module.file_path).stem}_{cls.name.lower()}_{method.name}",
                description=method.docstring.split("\n")[0][:200],
                source_file=module.file_path,
                source_function=f"{cls.name}.{method.name}",
                class_name=cls.name,
                parameters=properties,
                required_params=required,
                is_method=True,
                is_async=method.is_async,
                raw_docstring=method.docstring,
                handler_code=handler,
                confidence=0.5,
                tags=[module.language, "auto-extracted", "method"],
                repo_path=repo_path,
            )
            capabilities.append(cap)

    return capabilities


def _python_type_to_json(py_type: str) -> str:
    """Python 类型字符串 → JSON Schema 类型"""
    mapping = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "List": "array",
        "dict": "object",
        "Dict": "object",
        "tuple": "array",
        "set": "array",
        "Any": "string",
        "Optional": "string",
    }
    # Strip generics like List[str] → List
    base = py_type.split("[")[0].strip()
    return mapping.get(base, "string")


def _generate_handler_code(func: FunctionInfo, module: ModuleInfo, repo_path: str = "") -> str:
    """生成工具 handler Python 代码 — 真正可执行的版本"""
    # 构建参数签名
    params_sig = ", ".join(
        f"{p['name']}: {p.get('type', 'str')}" if p.get("type") else p["name"]
        for p in func.params
    )

    # 构建函数调用参数
    params_call = ", ".join(
        f"{p['name']}={p['name']}" if p.get("type") else p["name"]
        for p in func.params
    )

    # 模块文件路径
    module_file = module.file_path
    mod_name = Path(module_file).stem
    func_name = func.name

    # 导入路径处理
    import_block = ""
    if repo_path:
        import_block = f"""
    # Add absorbed repo to path
    import sys
    _repo = {repo_path!r}
    if _repo not in sys.path:
        sys.path.insert(0, _repo)"""

    return f'''def {func_name}__tool({params_sig}) -> str:
    """Auto-generated: {module_file}::{func_name}"""
    import json
    try:{import_block}
        from {mod_name} import {func_name} as _fn
        result = _fn({params_call})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({{"error": str(e), "tool": "{func_name}__tool"}}, ensure_ascii=False)'''


def _generate_method_handler_code(method: FunctionInfo, cls: ClassInfo, module: ModuleInfo, repo_path: str = "") -> str:
    """生成类方法的 handler 代码 — 真正可执行的版本"""
    params_sig = ", ".join(
        f"{p['name']}: {p.get('type', 'str')}" if p.get("type") else p["name"]
        for p in method.params
    )
    params_call = ", ".join(
        f"{p['name']}={p['name']}" if p.get("type") else p["name"]
        for p in method.params
    )

    module_file = module.file_path
    mod_name = Path(module_file).stem
    cls_name = cls.name
    method_name = method.name

    import_block = ""
    if repo_path:
        import_block = f"""
    # Add absorbed repo to path
    import sys
    _repo = {repo_path!r}
    if _repo not in sys.path:
        sys.path.insert(0, _repo)"""

    return f'''def {cls_name.lower()}_{method_name}__tool({params_sig}) -> str:
    """Auto-generated: {module_file}::{cls_name}.{method_name}"""
    import json
    try:{import_block}
        from {mod_name} import {cls_name}
        _obj = {cls_name}()
        result = _obj.{method_name}({params_call})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({{"error": str(e), "tool": "{cls_name.lower()}_{method_name}__tool"}}, ensure_ascii=False)'''


# ── Batch Extraction ────────────────────────────────────────

def extract_from_repo(
    repo_path: str | Path,
    languages: list[str] | None = None,
    use_llm: bool = False,
    llm_client: Any = None,
    max_modules_for_llm: int = 20,
    min_docstring_len: int = 20,
) -> list[ExtractedCapability]:
    """
    从代码仓库批量提取能力

    Args:
        repo_path: 仓库路径
        languages: 限制语言（None = 全部）
        use_llm: 是否用 LLM 分析（默认用启发式）
        llm_client: LLM 客户端（OpenAI 兼容）
        max_modules_for_llm: LLM 最大分析模块数
    """
    structure = scan_project(repo_path)
    if not structure.modules:
        return []

    all_capabilities: list[ExtractedCapability] = []

    for module in structure.modules:
        if languages and module.language not in languages:
            continue

        if use_llm and llm_client and len(all_capabilities) < max_modules_for_llm:
            # LLM analysis for high-value modules
            caps = _extract_with_llm(module, structure, llm_client)
            all_capabilities.extend(caps)
        else:
            # Heuristic fallback
            caps = extract_capabilities_heuristic(module, min_docstring_len, repo_path=str(repo_path))
            all_capabilities.extend(caps)

    # Deduplicate by fingerprint
    seen: set[str] = set()
    unique: list[ExtractedCapability] = []
    for cap in all_capabilities:
        fp = cap.fingerprint()
        if fp not in seen:
            seen.add(fp)
            unique.append(cap)

    return unique


def _extract_with_llm(
    module: ModuleInfo,
    structure: ProjectStructure,
    llm_client: Any,
) -> list[ExtractedCapability]:
    """用 LLM 分析单个模块"""
    summary = summarize_structure(structure)[:1000]
    prompt = _build_analysis_prompt(module, summary)

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content

        # Parse JSON from response
        # Try to find JSON array in the response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            return []

        items = json.loads(json_match.group(0))
        capabilities = []

        for item in items:
            cap = ExtractedCapability(
                name=item.get("tool_name", ""),
                description=item.get("description", ""),
                source_file=module.file_path,
                source_function=item.get("source_function", ""),
                class_name=item.get("source_class", ""),
                parameters=item.get("parameters", {}).get("properties", {}),
                required_params=item.get("parameters", {}).get("required", []),
                return_description=item.get("return_description", ""),
                is_method=bool(item.get("source_class")),
                handler_code=item.get("handler_code", ""),
                raw_docstring="",
                confidence=item.get("confidence", 0.8),
                tags=item.get("tags", [module.language, "llm-extracted"]),
            )
            if cap.name:  # Skip empty entries
                capabilities.append(cap)

        return capabilities

    except Exception as e:
        # Fallback to heuristic on LLM failure
        return extract_capabilities_heuristic(module)
