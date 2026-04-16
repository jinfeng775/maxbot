"""
自我评估器 — 识别 MaxBot 的能力缺口

不是找 bug，而是回答：
"我能做什么？不能做什么？上次失败的任务是什么？哪里需要进化？"

评估维度：
1. 任务失败分析 — 从历史记录看哪些任务搞不定
2. 能力清单盘点 — 当前有多少工具/技能，覆盖了哪些领域
3. 对标差距 — 和 Hermes/Claude Code/OpenClaw 比缺什么
4. 用户行为分析 — 用户反复问什么但我做不到
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CapabilityGap:
    """能力缺口"""
    domain: str            # 领域：code_editing, web_browsing, data_analysis, etc.
    description: str       # 缺什么能力
    evidence: str          # 为什么认为缺这个（失败记录/用户反馈/对标差距）
    priority: str          # critical, high, medium, low
    suggested_solution: str = ""  # 建议怎么补
    source: str = ""       # 哪里发现的（failure_history / user_pattern / benchmark）


@dataclass
class CapabilityInventory:
    """当前能力清单"""
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    toolsets: list[str] = field(default_factory=list)
    domains_covered: list[str] = field(default_factory=list)


@dataclass
class SelfAssessment:
    """自我评估报告"""
    inventory: CapabilityInventory = field(default_factory=CapabilityInventory)
    gaps: list[CapabilityGap] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    summary: str = ""

    def top_gaps(self, n: int = 5) -> list[CapabilityGap]:
        """返回优先级最高的 N 个缺口"""
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(self.gaps, key=lambda g: priority_order.get(g.priority, 9))[:n]


# ── 评估 prompt ────────────────────────────────────────────

_ASSESSMENT_PROMPT = """你是 MaxBot 的自我进化评估引擎。

你的任务不是找 bug，而是分析 MaxBot **缺什么能力**，找到真正的进化方向。

输入包含：
1. 当前能力清单（工具/技能/模块）
2. 任务失败历史（哪些任务搞不定）
3. 用户交互模式（用户反复问什么）
4. 对标分析（Hermes/Claude Code/OpenClaw 的能力对比）

你需要输出 JSON 数组，每个元素是一个能力缺口：
```json
[
  {
    "domain": "能力领域",
    "description": "缺什么能力",
    "evidence": "证据（从输入数据中引用）",
    "priority": "critical|high|medium|low",
    "suggested_solution": "建议怎么补（吸收哪个项目？生成什么工具？）",
    "source": "failure_history|user_pattern|benchmark"
  }
]
```

只输出 JSON。只报告真实的能力缺口，不要编造。重点是"能做什么"而不是"代码有什么问题"。"""


def assess(
    tool_registry: Any = None,
    skill_manager: Any = None,
    failure_history: list[dict] | None = None,
    user_patterns: list[dict] | None = None,
    benchmark_file: str | Path | None = None,
    llm_client: Any = None,
    model: str = "gpt-4o-mini",
) -> SelfAssessment:
    """
    执行自我评估

    Args:
        tool_registry: 工具注册表（盘点当前工具）
        skill_manager: 技能管理器（盘点当前技能）
        failure_history: 失败任务记录 [{"task": ..., "error": ..., "timestamp": ...}]
        user_patterns: 用户交互模式 [{"pattern": ..., "frequency": ...}]
        benchmark_file: 对标文件路径（Hermes/CC/OC 的能力清单）
        llm_client: LLM 客户端
        model: 模型名
    """
    assessment = SelfAssessment()

    # 1. 盘点当前能力
    assessment.inventory = _build_inventory(tool_registry, skill_manager)

    # 2. 如果没有 LLM，返回基础评估
    if not llm_client:
        assessment.summary = _basic_summary(assessment.inventory)
        return assessment

    # 3. 构建上下文
    context = _build_context(
        assessment.inventory,
        failure_history or [],
        user_patterns or [],
        benchmark_file,
    )

    # 4. LLM 评估
    try:
        response = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ASSESSMENT_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content

        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            items = json.loads(json_match.group(0))
            for item in items:
                assessment.gaps.append(CapabilityGap(
                    domain=item.get("domain", "unknown"),
                    description=item.get("description", ""),
                    evidence=item.get("evidence", ""),
                    priority=item.get("priority", "medium"),
                    suggested_solution=item.get("suggested_solution", ""),
                    source=item.get("source", ""),
                ))

        assessment.summary = f"当前 {len(assessment.inventory.tools)} 个工具，发现 {len(assessment.gaps)} 个能力缺口"

    except Exception as e:
        assessment.summary = f"评估失败: {e}"

    return assessment


def _build_inventory(tool_registry: Any, skill_manager: Any) -> CapabilityInventory:
    """盘点当前能力"""
    inventory = CapabilityInventory()

    if tool_registry:
        try:
            tools = tool_registry.list_tools()
            inventory.tools = [t.name for t in tools]
            inventory.toolsets = list(set(t.toolset for t in tools))
        except Exception:
            pass

    if skill_manager:
        try:
            skills = skill_manager.list_skills()
            inventory.skills = [s.name for s in skills]
        except Exception:
            pass

    # 根据工具名推断覆盖领域
    tool_names = set(inventory.tools)
    domain_map = {
        "file": ["read_file", "write_file", "search_files", "patch_file"],
        "shell": ["shell", "exec_python"],
        "git": ["git_status", "git_diff", "git_log", "git_commit"],
        "web": ["web_search", "web_fetch"],
        "code_editing": ["code_edit", "code_edit_multi"],
        "notebook": ["notebook_read", "notebook_edit"],
        "multi_agent": ["spawn_agent", "spawn_agents_parallel"],
        "knowledge": ["knowledge_absorb"],
    }
    for domain, domain_tools in domain_map.items():
        if tool_names & set(domain_tools):
            inventory.domains_covered.append(domain)

    return inventory


def _build_context(
    inventory: CapabilityInventory,
    failure_history: list[dict],
    user_patterns: list[dict],
    benchmark_file: str | Path | None,
) -> str:
    """构建 LLM 评估上下文"""
    parts = ["# MaxBot 自我评估\n"]

    # 当前能力
    parts.append("## 当前能力清单")
    parts.append(f"工具 ({len(inventory.tools)}): {', '.join(inventory.tools[:30])}")
    parts.append(f"技能 ({len(inventory.skills)}): {', '.join(inventory.skills[:20])}")
    parts.append(f"工具集: {', '.join(inventory.toolsets)}")
    parts.append(f"覆盖领域: {', '.join(inventory.domains_covered)}")

    # 失败历史
    if failure_history:
        parts.append("\n## 任务失败历史")
        for f in failure_history[-20:]:  # 最近 20 条
            parts.append(f"- [{f.get('timestamp', '?')}] {f.get('task', '?')} → {f.get('error', '?')}")

    # 用户模式
    if user_patterns:
        parts.append("\n## 用户交互模式")
        for p in user_patterns[:20]:
            parts.append(f"- {p.get('pattern', '?')} (出现 {p.get('frequency', '?')} 次)")

    # 对标
    if benchmark_file:
        benchmark_path = Path(benchmark_file)
        if benchmark_path.is_file():
            try:
                content = benchmark_path.read_text(encoding="utf-8")[:5000]
                parts.append(f"\n## 对标能力清单\n{content}")
            except Exception:
                pass

    return "\n".join(parts)


def _basic_summary(inventory: CapabilityInventory) -> str:
    """无 LLM 时的基础摘要"""
    return (
        f"当前 {len(inventory.tools)} 个工具，{len(inventory.skills)} 个技能，"
        f"覆盖 {len(inventory.domains_covered)} 个领域"
    )
