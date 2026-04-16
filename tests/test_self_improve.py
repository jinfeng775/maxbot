"""
Phase 6 自我进化 — 测试

覆盖:
- self_analyzer: CapabilityGap, SelfAssessment, 能力盘点
- review_board: Verdict, ReviewOpinion, ReviewBoardResult, 投票逻辑
- self_improver: EvolutionAttempt, SelfEvolver, 进化循环
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ══════════════════════════════════════════════════════════════
# Self Analyzer — 能力缺口分析
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.self_analyzer import (
    CapabilityGap, CapabilityInventory, SelfAssessment, assess,
)


class TestCapabilityGap:
    """能力缺口"""

    def test_create(self):
        gap = CapabilityGap(
            domain="web_browsing",
            description="无法自动化操作网页",
            evidence="用户反复要求操作网页但做不到",
            priority="high",
            suggested_solution="吸收 browser automation 代码",
            source="user_pattern",
        )
        assert gap.domain == "web_browsing"
        assert gap.priority == "high"

    def test_defaults(self):
        gap = CapabilityGap(
            domain="test",
            description="test",
            evidence="test",
            priority="low",
        )
        assert gap.suggested_solution == ""


class TestCapabilityInventory:
    """能力清单"""

    def test_empty(self):
        inv = CapabilityInventory()
        assert len(inv.tools) == 0
        assert len(inv.domains_covered) == 0

    def test_with_tools(self):
        inv = CapabilityInventory(
            tools=["read_file", "write_file", "shell", "web_search"],
            skills=["code-review"],
            toolsets=["builtin", "absorbed"],
            domains_covered=["file", "shell", "web"],
        )
        assert len(inv.tools) == 4


class TestSelfAssessment:
    """自我评估"""

    def test_empty_assessment(self):
        assessment = SelfAssessment()
        assert len(assessment.gaps) == 0
        assert len(assessment.top_gaps(5)) == 0

    def test_top_gaps_by_priority(self):
        assessment = SelfAssessment(
            gaps=[
                CapabilityGap(domain="a", description="a", evidence="a", priority="low"),
                CapabilityGap(domain="b", description="b", evidence="b", priority="critical"),
                CapabilityGap(domain="c", description="c", evidence="c", priority="medium"),
                CapabilityGap(domain="d", description="d", evidence="d", priority="high"),
            ],
        )
        top = assessment.top_gaps(2)
        assert len(top) == 2
        assert top[0].priority == "critical"
        assert top[1].priority == "high"

    def test_inventory_build(self):
        """测试能力盘点（无 LLM）"""
        # 用 mock registry
        mock_registry = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "read_file"
        mock_tool1.toolset = "builtin"
        mock_tool2 = MagicMock()
        mock_tool2.name = "shell"
        mock_tool2.toolset = "builtin"
        mock_tool3 = MagicMock()
        mock_tool3.name = "git_status"
        mock_tool3.toolset = "builtin"
        mock_registry.list_tools.return_value = [mock_tool1, mock_tool2, mock_tool3]

        result = assess(tool_registry=mock_registry)
        assert "read_file" in result.inventory.tools
        assert "shell" in result.inventory.tools
        assert "file" in result.inventory.domains_covered
        assert "shell" in result.inventory.domains_covered
        assert "git" in result.inventory.domains_covered


# ══════════════════════════════════════════════════════════════
# Review Board — 审批委员会
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.review_board import (
    Verdict, ReviewOpinion, ReviewBoardResult, ReviewBoard,
)


class TestVerdict:
    """裁决枚举"""

    def test_values(self):
        assert Verdict.APPROVE.value == "approve"
        assert Verdict.REJECT.value == "reject"
        assert Verdict.REVISE.value == "revise"


class TestReviewOpinion:
    """单个评审意见"""

    def test_create(self):
        opinion = ReviewOpinion(
            reviewer="安全审查员",
            perspective="安全风险",
            verdict=Verdict.APPROVE,
            score=0.85,
            reasoning="代码安全，无注入风险",
            confidence=0.9,
        )
        assert opinion.reviewer == "安全审查员"
        assert opinion.score == 0.85


class TestReviewBoardResult:
    """委员会结果"""

    def test_empty(self):
        result = ReviewBoardResult()
        assert result.approve_count == 0
        assert result.reject_count == 0

    def test_counts(self):
        result = ReviewBoardResult(
            opinions=[
                ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.APPROVE, score=0.8, reasoning="ok", confidence=0.9),
                ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.APPROVE, score=0.7, reasoning="ok", confidence=0.8),
                ReviewOpinion(reviewer="C", perspective="z", verdict=Verdict.REJECT, score=0.3, reasoning="bad", confidence=0.7),
            ],
        )
        assert result.approve_count == 2
        assert result.reject_count == 1

    def test_text_report(self):
        result = ReviewBoardResult(
            opinions=[
                ReviewOpinion(reviewer="能力审查员", perspective="新能力验证", verdict=Verdict.APPROVE, score=0.9, reasoning="带来了新能力", confidence=0.85),
            ],
            approval_score=0.9,
            final_verdict=Verdict.APPROVE,
        )
        text = result.text_report()
        assert "能力审查员" in text
        assert "新能力验证" in text


class TestReviewBoardVoting:
    """投票逻辑（不用 LLM，直接测决策逻辑）"""

    def test_unanimous_approve(self):
        board = ReviewBoard(llm_client=None, quorum=3, approval_threshold=0.6)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.APPROVE, score=0.9, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.APPROVE, score=0.8, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="C", perspective="z", verdict=Verdict.APPROVE, score=0.7, reasoning="", confidence=0.8),
        ]
        score = board._calc_score(opinions)
        verdict = board._decide(opinions, score)
        assert verdict == Verdict.APPROVE

    def test_majority_approve(self):
        board = ReviewBoard(llm_client=None, quorum=3, approval_threshold=0.6)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.APPROVE, score=0.9, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.APPROVE, score=0.8, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="C", perspective="z", verdict=Verdict.REJECT, score=0.3, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="D", perspective="w", verdict=Verdict.APPROVE, score=0.7, reasoning="", confidence=0.8),
        ]
        score = board._calc_score(opinions)
        verdict = board._decide(opinions, score)
        assert verdict == Verdict.APPROVE

    def test_all_reject(self):
        board = ReviewBoard(llm_client=None, quorum=3, approval_threshold=0.6)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.REJECT, score=0.2, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.REJECT, score=0.3, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="C", perspective="z", verdict=Verdict.REJECT, score=0.1, reasoning="", confidence=0.8),
        ]
        score = board._calc_score(opinions)
        verdict = board._decide(opinions, score)
        assert verdict == Verdict.REJECT

    def test_all_revise(self):
        board = ReviewBoard(llm_client=None, quorum=3, approval_threshold=0.6)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.REVISE, score=0.5, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.REVISE, score=0.5, reasoning="", confidence=0.8),
        ]
        score = board._calc_score(opinions)
        verdict = board._decide(opinions, score)
        assert verdict == Verdict.REVISE

    def test_score_below_threshold(self):
        board = ReviewBoard(llm_client=None, quorum=2, approval_threshold=0.7)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.APPROVE, score=0.5, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.APPROVE, score=0.6, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="C", perspective="z", verdict=Verdict.REVISE, score=0.5, reasoning="", confidence=0.8),
        ]
        score = board._calc_score(opinions)
        verdict = board._decide(opinions, score)
        # 2 approve + 1 revise, no reject → REVISE (not enough for approve, but no hard reject)
        assert verdict == Verdict.REVISE

    def test_score_below_threshold_with_reject(self):
        board = ReviewBoard(llm_client=None, quorum=2, approval_threshold=0.7)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.APPROVE, score=0.5, reasoning="", confidence=0.8),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.REJECT, score=0.3, reasoning="", confidence=0.8),
        ]
        score = board._calc_score(opinions)
        verdict = board._decide(opinions, score)
        # 1 approve + 1 reject, quorum not met → REJECT
        assert verdict == Verdict.REJECT

    def test_weighted_score(self):
        board = ReviewBoard(llm_client=None)
        opinions = [
            ReviewOpinion(reviewer="A", perspective="x", verdict=Verdict.APPROVE, score=1.0, reasoning="", confidence=0.9),
            ReviewOpinion(reviewer="B", perspective="y", verdict=Verdict.APPROVE, score=0.2, reasoning="", confidence=0.1),
        ]
        score = board._calc_score(opinions)
        # Weighted: (1.0*0.9 + 0.2*0.1) / (0.9+0.1) = 0.92/1.0 = 0.92
        assert score > 0.85  # High-confidence reviewer dominates


# ══════════════════════════════════════════════════════════════
# Self Evolver — 进化循环
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.self_improver import (
    EvolutionAttempt, EvolutionResult, SelfEvolver,
)


class TestEvolutionResult:
    """进化结果"""

    def test_empty(self):
        result = EvolutionResult()
        assert result.evolved_count == 0
        assert result.rejected_count == 0

    def test_summary(self):
        result = EvolutionResult()
        text = result.summary()
        assert "进化报告" in text

    def test_counts(self):
        result = EvolutionResult(
            assessment=SelfAssessment(
                gaps=[
                    CapabilityGap(domain="a", description="a", evidence="a", priority="high"),
                ],
            ),
            attempts=[
                EvolutionAttempt(
                    gap=CapabilityGap(domain="a", description="a", evidence="a", priority="high"),
                    evolved=True,
                ),
            ],
        )
        assert result.evolved_count == 1


class TestSelfEvolver:
    """自我进化器"""

    def test_no_gaps(self):
        """没有缺口时不进化"""
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = []

        evolver = SelfEvolver(
            project_root="/tmp/nonexistent_maxbot_test",
            tool_registry=mock_registry,
        )
        # 没有 LLM，assess 返回基础评估，没有 gaps
        result = evolver.evolve(llm_client=None)
        assert len(result.attempts) == 0

    def test_history_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            evolver = SelfEvolver(project_root=tmp)
            assert evolver.get_history() == []


class TestEvolutionAttempt:
    """单次进化尝试"""

    def test_default(self):
        gap = CapabilityGap(
            domain="browser",
            description="没有浏览器自动化",
            evidence="用户需要",
            priority="high",
        )
        attempt = EvolutionAttempt(gap=gap)
        assert attempt.evolved is False
        assert len(attempt.capabilities) == 0
        assert attempt.elapsed == 0.0
