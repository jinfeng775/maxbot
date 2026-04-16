"""
自我分析器 — 扫描 MaxBot 自身代码，识别改进空间

核心思路：把代码扔给 LLM，让它找问题。不要自己写规则引擎。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.code_parser import scan_project, summarize_structure


@dataclass
class Issue:
    """发现的问题"""
    category: str          # bug, performance, missing_feature, code_quality, security
    severity: str          # critical, high, medium, low
    file: str
    line: int | None = None
    title: str = ""
    description: str = ""
    suggestion: str = ""


@dataclass
class AnalysisReport:
    """分析报告"""
    project_root: str
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""
    raw_llm_response: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def total_count(self) -> int:
        return len(self.issues)

    def by_category(self) -> dict[str, list[Issue]]:
        result: dict[str, list[Issue]] = {}
        for issue in self.issues:
            result.setdefault(issue.category, []).append(issue)
        return result

    def text_report(self) -> str:
        lines = [f"# 自我分析报告: {self.project_root}", ""]
        lines.append(f"共发现 {self.total_count} 个问题（其中 {self.critical_count} 个严重）")
        lines.append("")

        for cat, issues in self.by_category().items():
            lines.append(f"## {cat}")
            for i in sorted(issues, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.severity, 9)):
                loc = f"{i.file}" + (f":{i.line}" if i.line else "")
                lines.append(f"- [{i.severity}] {i.title} ({loc})")
                if i.description:
                    lines.append(f"  {i.description}")
                if i.suggestion:
                    lines.append(f"  → {i.suggestion}")
            lines.append("")

        if self.summary:
            lines.append(f"## 总结\n{self.summary}")

        return "\n".join(lines)


# ── 自分析 prompt ──────────────────────────────────────────

_SYSTEM_PROMPT = """你是 MaxBot 的自我分析引擎。你的任务是分析 MaxBot 的源代码，找出可以改进的地方。

分析维度：
1. **Bug/风险** — 潜在的逻辑错误、边界情况未处理
2. **性能** — 不必要的计算、可以优化的循环、内存泄漏风险
3. **缺失功能** — 对比同类项目（Hermes, Claude Code, OpenClaw）缺少的能力
4. **代码质量** — 重复代码、命名不清晰、复杂度过高
5. **安全** — 输入验证不足、权限控制缺失

输出格式：严格 JSON 数组，每个元素：
```json
{
  "category": "bug|performance|missing_feature|code_quality|security",
  "severity": "critical|high|medium|low",
  "file": "相对路径",
  "line": 123,
  "title": "一句话标题",
  "description": "问题描述",
  "suggestion": "改进建议"
}
```

只输出 JSON，不要有其他文字。只报告真实问题，不要编造。"""


def analyze_self(
    project_root: str | Path,
    llm_client: Any,
    model: str = "gpt-4o-mini",
    focus: str | None = None,
) -> AnalysisReport:
    """
    分析 MaxBot 自身代码

    Args:
        project_root: MaxBot 项目根目录
        llm_client: OpenAI 兼容的 LLM 客户端
        model: 使用的模型
        focus: 可选的聚焦维度（bug/performance/missing_feature/code_quality/security）
    """
    root = Path(project_root)

    # 1. 扫描项目结构
    structure = scan_project(root)
    project_summary = summarize_structure(structure)

    # 2. 读取关键文件内容（按重要性取前 N 个文件）
    key_files = _select_key_files(structure.modules, max_files=15)
    code_context = _build_code_context(key_files, root)

    # 3. 构建 prompt
    user_prompt = f"# MaxBot 项目结构\n\n{project_summary}\n\n# 关键源码\n\n{code_context}"
    if focus:
        user_prompt += f"\n\n# 本次分析聚焦：{focus}"

    # 4. 调用 LLM
    report = AnalysisReport(project_root=str(root))

    try:
        response = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        report.raw_llm_response = content

        # 解析 JSON
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            items = json.loads(json_match.group(0))
            for item in items:
                report.issues.append(Issue(
                    category=item.get("category", "code_quality"),
                    severity=item.get("severity", "medium"),
                    file=item.get("file", ""),
                    line=item.get("line"),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion", ""),
                ))

        report.summary = f"扫描了 {len(structure.modules)} 个文件，{structure.total_functions} 个函数"

    except Exception as e:
        report.summary = f"分析失败: {e}"

    return report


def _select_key_files(modules: list, max_files: int = 15) -> list:
    """选关键文件（核心模块优先，跳过测试和 __pycache__）"""
    priority_prefixes = ["core/", "knowledge/", "tools/", "gateway/", "multi_agent/"]
    key = []
    rest = []

    for mod in modules:
        if any(mod.file_path.startswith(p) for p in priority_prefixes):
            key.append(mod)
        elif not mod.file_path.startswith("tests/"):
            rest.append(mod)

    return (key + rest)[:max_files]


def _build_code_context(modules: list, root: Path, max_chars: int = 30000) -> str:
    """构建代码上下文（读取文件内容）"""
    parts = []
    total = 0

    for mod in modules:
        filepath = root / mod.file_path
        if not filepath.is_file():
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue

        # 截断过长文件
        if len(content) > 3000:
            content = content[:3000] + "\n# ... truncated"

        block = f"## {mod.file_path}\n```python\n{content}\n```\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)

    return "\n".join(parts)
