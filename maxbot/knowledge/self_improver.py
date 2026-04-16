"""
自我进化器 — 能力进化的核心循环

真正的能力进化，不是修 bug：

1. 自我评估 → 发现能力缺口
2. 知识吸收 → 从代码仓库获取新能力
3. 提交审批 → 多维度子代理独立评审
4. 进化注册 → 审批通过后注册为工具/技能

用法:
    improver = SelfEvolver("/root/maxbot")
    result = improver.evolve(llm_client)
    print(result.summary())
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.self_analyzer import (
    assess, SelfAssessment, CapabilityGap, CapabilityInventory,
)
from maxbot.knowledge.code_parser import scan_project
from maxbot.knowledge.capability_extractor import extract_from_repo, ExtractedCapability
from maxbot.knowledge.skill_factory import SkillFactory, GeneratedSkill
from maxbot.knowledge.sandbox_validator import batch_validate, ValidationResult
from maxbot.knowledge.auto_register import AutoRegister, RegistrationResult
from maxbot.knowledge.review_board import (
    ReviewBoard, ReviewBoardResult, Verdict, ReviewOpinion,
)


@dataclass
class EvolutionAttempt:
    """单次进化尝试"""
    gap: CapabilityGap
    absorbed_from: str = ""           # 从哪里吸收的知识
    capabilities: list[ExtractedCapability] = field(default_factory=list)
    validations: list[ValidationResult] = field(default_factory=list)
    review: ReviewBoardResult | None = None
    registered: list[RegistrationResult] = field(default_factory=list)
    evolved: bool = False             # 最终是否成功进化
    error: str = ""
    elapsed: float = 0.0


@dataclass
class EvolutionResult:
    """进化结果"""
    assessment: SelfAssessment | None = None
    attempts: list[EvolutionAttempt] = field(default_factory=list)
    total_elapsed: float = 0.0

    @property
    def evolved_count(self) -> int:
        return sum(1 for a in self.attempts if a.evolved)

    @property
    def rejected_count(self) -> int:
        return sum(1 for a in self.attempts if a.review and a.review.final_verdict == Verdict.REJECT)

    def summary(self) -> str:
        lines = [
            "## 进化报告",
            f"- 发现缺口: {len(self.assessment.gaps) if self.assessment else 0}",
            f"- 尝试进化: {len(self.attempts)}",
            f"- 成功进化: {self.evolved_count}",
            f"- 被否决: {self.rejected_count}",
            f"- 耗时: {self.total_elapsed:.1f}s",
        ]
        for a in self.attempts:
            status = "🧬" if a.evolved else "❌" if a.review and a.review.final_verdict == Verdict.REJECT else "🔄"
            review_info = ""
            if a.review:
                review_info = f" [{a.review.approval_score:.0%}, {a.review.final_verdict.value}]"
            lines.append(f"- {status} {a.gap.domain}: {a.gap.description}{review_info}")
            if a.error:
                lines.append(f"  错误: {a.error}")
        return "\n".join(lines)


class SelfEvolver:
    """
    自我进化器

    用法:
        evolver = SelfEvolver(project_root="/root/maxbot")
        result = evolver.evolve(llm_client, knowledge_repos=["/path/to/repo"])
    """

    def __init__(
        self,
        project_root: str | Path,
        tool_registry: Any = None,
        skill_manager: Any = None,
    ):
        self.root = Path(project_root)
        self._registry = tool_registry
        self._skill_manager = skill_manager
        self._skill_factory = SkillFactory(
            output_dir=self.root / ".maxbot_absorbed_skills"
        )
        self._auto_register = AutoRegister(tool_registry=tool_registry)
        self._history_file = self.root / ".maxbot_evolution.jsonl"

    def evolve(
        self,
        llm_client: Any,
        model: str = "gpt-4o-mini",
        knowledge_repos: list[str] | None = None,
        max_evolutions: int = 3,
        approval_threshold: float = 0.6,
        quorum: int = 3,
        failure_history: list[dict] | None = None,
        user_patterns: list[dict] | None = None,
    ) -> EvolutionResult:
        """
        执行一轮进化

        Args:
            llm_client: LLM 客户端
            model: 模型
            knowledge_repos: 可吸收的知识源（本地仓库路径列表）
            max_evolutions: 单轮最大进化数
            approval_threshold: 审批通过分数阈值
            quorum: 最少通过票数
            failure_history: 任务失败历史
            user_patterns: 用户交互模式
        """
        start = time.time()
        result = EvolutionResult()

        # 1. 自我评估
        result.assessment = assess(
            tool_registry=self._registry,
            skill_manager=self._skill_manager,
            failure_history=failure_history,
            user_patterns=user_patterns,
            llm_client=llm_client,
            model=model,
        )

        if not result.assessment.gaps:
            result.total_elapsed = time.time() - start
            return result

        # 2. 审批委员会
        board = ReviewBoard(
            llm_client=llm_client,
            model=model,
            quorum=quorum,
            approval_threshold=approval_threshold,
        )

        # 3. 逐个缺口尝试进化
        repos = knowledge_repos or []
        for gap in result.assessment.top_gaps(max_evolutions):
            attempt = self._evolve_gap(gap, board, repos, llm_client, model)
            result.attempts.append(attempt)

        result.total_elapsed = time.time() - start
        self._save_history(result)

        return result

    def evolve_single_gap(
        self,
        gap: CapabilityGap,
        knowledge_repo: str | Path,
        llm_client: Any,
        model: str = "gpt-4o-mini",
        approval_threshold: float = 0.6,
    ) -> EvolutionAttempt:
        """进化单个缺口"""
        board = ReviewBoard(
            llm_client=llm_client,
            model=model,
            approval_threshold=approval_threshold,
        )
        return self._evolve_gap(gap, board, [str(knowledge_repo)], llm_client, model)

    def _evolve_gap(
        self,
        gap: CapabilityGap,
        board: ReviewBoard,
        repos: list[str],
        llm_client: Any,
        model: str,
    ) -> EvolutionAttempt:
        """尝试填补单个能力缺口"""
        start = time.time()
        attempt = EvolutionAttempt(gap=gap)

        try:
            # Step 1: 找到合适的知识源
            source_repo = self._find_knowledge_source(gap, repos)
            if not source_repo:
                attempt.error = f"未找到匹配的知识源（需要: {gap.domain}）"
                attempt.elapsed = time.time() - start
                return attempt

            attempt.absorbed_from = source_repo

            # Step 2: 吸收知识
            attempt.capabilities = extract_from_repo(source_repo)
            if not attempt.capabilities:
                attempt.error = "知识源未提取到可用能力"
                attempt.elapsed = time.time() - start
                return attempt

            # Step 3: 安全验证
            attempt.validations = batch_validate(attempt.capabilities)

            # Step 4: 构建提案，提交审批委员会
            proposal = self._build_proposal(gap, attempt)
            attempt.review = board.review(proposal)

            # Step 5: 根据审批结果决定
            if attempt.review.final_verdict == Verdict.APPROVE:
                # 进化！注册为工具
                attempt.registered = self._auto_register.register_validated(
                    attempt.validations,
                    toolset=f"evolved_{gap.domain}",
                )
                attempt.evolved = any(r.success for r in attempt.registered)

                # 生成技能
                valid_caps = [
                    attempt.capabilities[i]
                    for i, v in enumerate(attempt.validations)
                    if v.is_valid and i < len(attempt.capabilities)
                ]
                if valid_caps:
                    self._skill_factory.generate(valid_caps)

            elif attempt.review.final_verdict == Verdict.REVISE:
                attempt.error = "委员会要求修改，暂不自动修订"

        except Exception as e:
            attempt.error = str(e)

        attempt.elapsed = time.time() - start
        return attempt

    def _find_knowledge_source(
        self,
        gap: CapabilityGap,
        repos: list[str],
    ) -> str | None:
        """为缺口找到合适的知识源"""
        if not repos:
            return None

        # 如果缺口有建议方案，尝试匹配
        suggestion = gap.suggested_solution.lower()
        domain = gap.domain.lower()

        for repo in repos:
            repo_lower = repo.lower()
            # 简单关键词匹配
            if domain in repo_lower or any(
                kw in repo_lower for kw in domain.split("_")
            ):
                return repo
            if suggestion and any(
                kw in repo_lower for kw in suggestion.split()[:3]
            ):
                return repo

        # 没有精确匹配，返回第一个（让 LLM 决定吸收什么）
        return repos[0] if repos else None

    def _build_proposal(
        self,
        gap: CapabilityGap,
        attempt: EvolutionAttempt,
    ) -> dict[str, Any]:
        """构建审批提案"""
        changes = []
        new_capabilities = []

        for cap in attempt.capabilities[:5]:  # 最多展示 5 个
            changes.append({
                "file": cap.source_file,
                "description": f"吸收 {cap.source_function}: {cap.description}",
                "new_code": cap.handler_code[:500] if cap.handler_code else "",
            })
            new_capabilities.append(f"{cap.name}: {cap.description}")

        # 测试结果
        test_results = {
            "passed": sum(1 for v in attempt.validations if v.is_valid),
            "failed": sum(1 for v in attempt.validations if not v.is_valid),
            "output": "\n".join(
                v.test_output[:200]
                for v in attempt.validations
                if v.test_output
            )[:1000],
        }

        return {
            "gap": gap,
            "changes": changes,
            "new_capabilities": new_capabilities,
            "test_results": test_results,
        }

    def get_history(self) -> list[dict]:
        """读取进化历史"""
        if not self._history_file.exists():
            return []
        records = []
        for line in self._history_file.read_text().splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
        return records

    def _save_history(self, result: EvolutionResult):
        """追加进化历史"""
        try:
            with open(self._history_file, "a") as f:
                for attempt in result.attempts:
                    record = {
                        "timestamp": time.time(),
                        "gap_domain": attempt.gap.domain,
                        "gap_description": attempt.gap.description,
                        "absorbed_from": attempt.absorbed_from,
                        "capabilities_count": len(attempt.capabilities),
                        "review_score": attempt.review.approval_score if attempt.review else 0,
                        "review_verdict": attempt.review.final_verdict.value if attempt.review else "none",
                        "evolved": attempt.evolved,
                        "error": attempt.error,
                        "elapsed": round(attempt.elapsed, 2),
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass
