"""
进化审批委员会 — 多维度子代理独立评估

每个评审员是独立的子 AI：
- 有自己的 system prompt（视角）
- 有自己的上下文（只看自己该看的东西）
- 独立输出 verdict（approve / reject / revise）
- 互不干扰

最终投票决定是否进化。

评审维度：
1. 🔍 能力审查员 — 改进是否真的带来了新能力？
2. 🔒 安全审查员 — 新代码有没有安全隐患？
3. 🏗️ 架构审查员 — 改进是否符合整体架构设计？
4. 🧪 质量审查员 — 代码质量是否达标？
5. 🎯 用户价值审查员 — 对用户有实际价值吗？
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"  # 需要修改后重新提交


@dataclass
class ReviewOpinion:
    """单个审查员的意见"""
    reviewer: str            # 审查员身份
    perspective: str         # 审查角度
    verdict: Verdict
    score: float             # 0.0 - 1.0
    reasoning: str           # 理由
    suggestions: list[str] = field(default_factory=list)  # 修改建议（revise 时）
    confidence: float = 0.0  # 对自己判断的信心


@dataclass
class ReviewBoardResult:
    """委员会投票结果"""
    opinions: list[ReviewOpinion] = field(default_factory=list)
    final_verdict: Verdict = Verdict.REJECT
    approval_score: float = 0.0
    summary: str = ""

    @property
    def approve_count(self) -> int:
        return sum(1 for o in self.opinions if o.verdict == Verdict.APPROVE)

    @property
    def reject_count(self) -> int:
        return sum(1 for o in self.opinions if o.verdict == Verdict.REJECT)

    @property
    def revise_count(self) -> int:
        return sum(1 for o in self.opinions if o.verdict == Verdict.REVISE)

    def text_report(self) -> str:
        lines = [
            "## 进化审批报告",
            f"- 总分: {self.approval_score:.1%}",
            f"- 结论: {self.final_verdict.value}",
            f"- 通过: {self.approve_count} | 否决: {self.reject_count} | 修改: {self.revise_count}",
            "",
        ]
        for o in self.opinions:
            icon = {"approve": "✅", "reject": "❌", "revise": "🔄"}[o.verdict.value]
            lines.append(f"### {icon} {o.reviewer}（{o.perspective}）")
            lines.append(f"评分: {o.score:.0%} | 信心: {o.confidence:.0%}")
            lines.append(f"{o.reasoning}")
            if o.suggestions:
                lines.append("修改建议:")
                for s in o.suggestions:
                    lines.append(f"  - {s}")
            lines.append("")
        return "\n".join(lines)


# ── 评审员定义 ──────────────────────────────────────────────

_REVIEWERS = [
    {
        "id": "capability",
        "name": "能力审查员",
        "perspective": "新能力验证",
        "prompt": """你是能力审查员。你只关心一件事：这个改进是否真的给 MaxBot 带来了**新能力**？

评判标准：
- 改进前 vs 改进后，MaxBot 能做的事情是否变多了？
- 这个新能力是否有实际使用场景？
- 能力是否足够独立（可以作为工具/技能被调用）？
- 是否和已有能力重复？

输出 JSON:
{
  "verdict": "approve|reject|revise",
  "score": 0.0-1.0,
  "reasoning": "你的判断理由",
  "suggestions": ["修改建议"],
  "confidence": 0.0-1.0
}""",
    },
    {
        "id": "security",
        "name": "安全审查员",
        "perspective": "安全风险",
        "prompt": """你是安全审查员。你只关心安全。

检查项：
- 新代码是否有命令注入风险？
- 是否有文件系统越权？
- 是否引入了不安全的依赖？
- 是否有数据泄露风险？
- 沙箱隔离是否足够？

输出 JSON:
{
  "verdict": "approve|reject|revise",
  "score": 0.0-1.0,
  "reasoning": "你的判断理由",
  "suggestions": ["安全改进建议"],
  "confidence": 0.0-1.0
}""",
    },
    {
        "id": "architecture",
        "name": "架构审查员",
        "perspective": "架构一致性",
        "prompt": """你是架构审查员。你关心 MaxBot 的整体架构是否健康。

评判标准：
- 改进是否符合 MaxBot 的模块化设计？
- 是否破坏了现有的依赖关系？
- 是否引入了不必要的耦合？
- 接口设计是否一致？
- 是否遵循了"工具注册表"模式？

MaxBot 架构核心：
- core/: 引擎（agent_loop, tool_registry, memory, context）
- tools/: 工具实现，通过 registry 自动注册
- knowledge/: 知识吸收 + 自我改进
- gateway/: 多平台网关
- multi_agent/: 子 Agent 编排

输出 JSON:
{
  "verdict": "approve|reject|revise",
  "score": 0.0-1.0,
  "reasoning": "你的判断理由",
  "suggestions": ["架构改进建议"],
  "confidence": 0.0-1.0
}""",
    },
    {
        "id": "quality",
        "name": "质量审查员",
        "perspective": "代码质量",
        "prompt": """你是代码质量审查员。

检查项：
- 命名是否清晰？
- 是否有重复代码？
- 错误处理是否完善？
- 测试覆盖是否足够？
- 文档是否齐全？
- 代码风格是否一致？

输出 JSON:
{
  "verdict": "approve|reject|revise",
  "score": 0.0-1.0,
  "reasoning": "你的判断理由",
  "suggestions": ["质量改进建议"],
  "confidence": 0.0-1.0
}""",
    },
    {
        "id": "user_value",
        "name": "用户价值审查员",
        "perspective": "用户实际价值",
        "prompt": """你是用户价值审查员。你只关心一件事：这个改进对**用户**有没有实际价值？

评判标准：
- 用户会用到这个能力吗？
- 是否解决了真实痛点？
- 使用门槛是否合理？
- 性价比如何（复杂度 vs 收益）？

输出 JSON:
{
  "verdict": "approve|reject|revise",
  "score": 0.0-1.0,
  "reasoning": "你的判断理由",
  "suggestions": ["提升用户价值的建议"],
  "confidence": 0.0-1.0
}""",
    },
]


# ── 审批委员会 ──────────────────────────────────────────────

class ReviewBoard:
    """
    进化审批委员会

    每个评审员是独立的 LLM 调用，有自己的 system prompt 和上下文。
    互不干扰，独立判断，最后投票。

    用法:
        board = ReviewBoard(llm_client)
        result = board.review(proposal)
        if result.final_verdict == Verdict.APPROVE:
            apply_evolution()
    """

    def __init__(
        self,
        llm_client: Any,
        model: str = "gpt-4o-mini",
        quorum: int = 3,  # 至少需要几个评审员同意
        approval_threshold: float = 0.6,  # 平均分过线
    ):
        self.llm_client = llm_client
        self.model = model
        self.quorum = quorum
        self.approval_threshold = approval_threshold

    def review(
        self,
        proposal: dict[str, Any],
        reviewers: list[dict] | None = None,
        parallel: bool = False,
    ) -> ReviewBoardResult:
        """
        审批一个进化提案

        Args:
            proposal: 提案内容 {
                "gap": CapabilityGap,
                "changes": [{"file": ..., "description": ...}],
                "new_capabilities": [...],
                "test_results": {...},
            }
            reviewers: 自定义评审员（默认用内置 5 个）
            parallel: 是否并行调用 LLM（需要异步支持）

        Returns:
            ReviewBoardResult
        """
        reviewers = reviewers or _REVIEWERS
        result = ReviewBoardResult()

        # 为每个评审员构建独立上下文
        proposal_text = _format_proposal(proposal)

        for reviewer in reviewers:
            opinion = self._ask_reviewer(reviewer, proposal_text)
            result.opinions.append(opinion)

        # 计算最终裁决
        result.approval_score = self._calc_score(result.opinions)
        result.final_verdict = self._decide(result.opinions, result.approval_score)
        result.summary = self._build_summary(result)

        return result

    def _ask_reviewer(self, reviewer: dict, proposal_text: str) -> ReviewOpinion:
        """单个评审员独立评审"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": reviewer["prompt"]},
                    {"role": "user", "content": proposal_text},
                ],
                temperature=0.2,
            )
            content = response.choices[0].message.content

            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return ReviewOpinion(
                    reviewer=reviewer["name"],
                    perspective=reviewer["perspective"],
                    verdict=Verdict(data.get("verdict", "reject")),
                    score=float(data.get("score", 0)),
                    reasoning=data.get("reasoning", ""),
                    suggestions=data.get("suggestions", []),
                    confidence=float(data.get("confidence", 0.5)),
                )

            # LLM 没返回有效 JSON
            return ReviewOpinion(
                reviewer=reviewer["name"],
                perspective=reviewer["perspective"],
                verdict=Verdict.REJECT,
                score=0.0,
                reasoning=f"LLM 响应解析失败: {content[:200]}",
            )

        except Exception as e:
            return ReviewOpinion(
                reviewer=reviewer["name"],
                perspective=reviewer["perspective"],
                verdict=Verdict.REJECT,
                score=0.0,
                reasoning=f"评审异常: {e}",
            )

    def _calc_score(self, opinions: list[ReviewOpinion]) -> float:
        """加权平均分（信心高的评审员权重更大）"""
        if not opinions:
            return 0.0
        total_weight = sum(o.confidence for o in opinions) or len(opinions)
        weighted_sum = sum(o.score * (o.confidence or 0.5) for o in opinions)
        return weighted_sum / total_weight

    def _decide(self, opinions: list[ReviewOpinion], score: float) -> Verdict:
        """最终裁决"""
        approves = sum(1 for o in opinions if o.verdict == Verdict.APPROVE)

        # 全票通过
        if approves == len(opinions):
            return Verdict.APPROVE

        # 多数通过 + 分数达标
        if approves >= self.quorum and score >= self.approval_threshold:
            return Verdict.APPROVE

        # 有人要求修改且没人强烈反对
        rejects = sum(1 for o in opinions if o.verdict == Verdict.REJECT)
        if rejects == 0:
            return Verdict.REVISE

        return Verdict.REJECT

    def _build_summary(self, result: ReviewBoardResult) -> str:
        return (
            f"{result.approve_count}/{len(result.opinions)} 通过，"
            f"平均分 {result.approval_score:.0%}，"
            f"结论: {result.final_verdict.value}"
        )


def _format_proposal(proposal: dict[str, Any]) -> str:
    """格式化提案供评审员阅读"""
    parts = ["# 进化提案\n"]

    if "gap" in proposal:
        gap = proposal["gap"]
        parts.append("## 待填补的能力缺口")
        parts.append(f"- 领域: {gap.domain if hasattr(gap, 'domain') else gap.get('domain', '?')}")
        parts.append(f"- 描述: {gap.description if hasattr(gap, 'description') else gap.get('description', '?')}")
        parts.append(f"- 优先级: {gap.priority if hasattr(gap, 'priority') else gap.get('priority', '?')}")
        parts.append(f"- 建议方案: {gap.suggested_solution if hasattr(gap, 'suggested_solution') else gap.get('suggested_solution', '?')}")

    if "changes" in proposal:
        parts.append("\n## 代码变更")
        for change in proposal["changes"]:
            parts.append(f"### {change.get('file', '?')}")
            parts.append(f"描述: {change.get('description', '?')}")
            if "diff" in change:
                parts.append(f"```diff\n{change['diff'][:2000]}\n```")
            if "new_code" in change:
                parts.append(f"```python\n{change['new_code'][:2000]}\n```")

    if "new_capabilities" in proposal:
        parts.append("\n## 新增能力")
        for cap in proposal["new_capabilities"]:
            parts.append(f"- {cap}")

    if "test_results" in proposal:
        tr = proposal["test_results"]
        parts.append(f"\n## 测试结果")
        parts.append(f"- 通过: {tr.get('passed', '?')}")
        parts.append(f"- 失败: {tr.get('failed', '?')}")
        if tr.get("output"):
            parts.append(f"```\n{tr['output'][:1000]}\n```")

    return "\n".join(parts)
