"""
Meta-Harness 风格的 Harness 优化器

核心思想：
1. 不是压缩历史为摘要，而是保留完整的执行轨迹
2. 优化器可以访问文件系统，读取所有历史候选者的源代码、执行轨迹和评分
3. 通过分析失败模式，提出针对性的 harness 修改

与 SelfEvolver 的区别：
- SelfEvolver: 基于能力缺口进化，从外部吸收新能力
- HarnessOptimizer: 基于执行轨迹优化，改进内部 harness 配置

用法：
    optimizer = HarnessOptimizer("/path/to/maxbot")
    result = optimizer.optimize(
        llm_client,
        benchmark_tasks=[...],
        max_iterations=10
    )
"""

from __future__ import annotations

import json
import time
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI


@dataclass
class HarnessCandidate:
    """单个 Harness 候选者"""
    iteration: int
    candidate_id: str
    config: dict  # harness 配置（system prompt, tool configs 等）
    source_code: str  # 生成的代码（如果有）
    metrics: dict = field(default_factory=dict)  # 评估指标
    execution_traces: list[dict] = field(default_factory=list)  # 执行轨迹
    score: float = 0.0  # 综合评分
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "candidate_id": self.candidate_id,
            "config": self.config,
            "source_code": self.source_code,
            "metrics": self.metrics,
            "score": self.score,
            "timestamp": self.timestamp,
        }


@dataclass
class OptimizationIteration:
    """单次优化迭代"""
    iteration: int
    candidates: list[HarnessCandidate] = field(default_factory=list)
    best_candidate: HarnessCandidate | None = None
    reasoning: str = ""  # 提议者的推理过程
    changes: list[dict] = field(default_factory=list)  # 建议的修改
    elapsed: float = 0.0


@dataclass
class OptimizationResult:
    """优化结果"""
    iterations: list[OptimizationIteration] = field(default_factory=list)
    best_overall: HarnessCandidate | None = None
    total_elapsed: float = 0.0
    converged: bool = False

    @property
    def best_score(self) -> float:
        return self.best_overall.score if self.best_overall else 0.0

    def summary(self) -> str:
        lines = [
            "## Harness 优化报告",
            f"- 迭代次数: {len(self.iterations)}",
            f"- 最佳评分: {self.best_score:.2%}",
            f"- 总耗时: {self.total_elapsed:.1f}s",
            f"- 是否收敛: {self.converged}",
            "",
            "## 迭代历史",
        ]
        for it in self.iterations:
            best = it.best_candidate
            lines.append(
                f"迭代 {it.iteration}: "
                f"最佳={best.score:.2% if best else 'N/A'}, "
                f"候选数={len(it.candidates)}, "
                f"耗时={it.elapsed:.1f}s"
            )
            if it.reasoning:
                lines.append(f"  推理: {it.reasoning[:200]}...")
        return "\n".join(lines)


class HarnessOptimizer:
    """
    Meta-Harness 风格的优化器

    核心特性：
    1. 文件系统接口：所有历史候选者的完整信息都存储在文件系统中
    2. 执行轨迹保留：不压缩历史，保留完整的执行日志
    3. 诊断驱动：通过分析失败模式提出针对性修改
    """

    def __init__(
        self,
        project_root: str | Path,
        work_dir: str | Path | None = None,
    ):
        self.root = Path(project_root)
        self.work_dir = Path(work_dir or self.root / ".maxbot_harness_opt")
        self.work_dir.mkdir(parents=True=True, exist_ok=True)

        # 创建文件系统结构
        self._setup_filesystem()

        # 当前最佳 harness
        self._current_harness: HarnessCandidate | None = None

    def _setup_filesystem(self):
        """设置文件系统结构"""
        dirs = [
            self.work_dir / "candidates",  # 所有候选者
            self.work_dir / "traces",      # 执行轨迹
            self.work_dir / "metrics",      # 评估指标
            self.work_dir / "proposals",    # 提议记录
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def optimize(
        self,
        llm_client: OpenAI,
        benchmark_tasks: list[dict],
        max_iterations: int = 10,
        candidates_per_iter: int = 2,
        initial_harness: dict | None = None,
        evaluation_fn: Callable | None = None,
        convergence_threshold: float = 0.01,
    ) -> OptimizationResult:
        """
        执行优化循环

        Args:
            llm_client: LLM 客户端
            benchmark_tasks: 基准测试任务列表
            max_iterations: 最大迭代次数
            candidates_per_iter: 每次迭代生成的候选者数量
            initial_harness: 初始 harness 配置
            evaluation_fn: 评估函数 (harness_config, tasks) -> dict
            convergence_threshold: 收敛阈值（评分改进小于此值时停止）
        """
        start = time.time()
        result = OptimizationResult()

        # 初始化当前 harness
        if initial_harness:
            self._current_harness = HarnessCandidate(
                iteration=0,
                candidate_id="initial",
                config=initial_harness,
                source_code="",
                timestamp=datetime.now().isoformat(),
            )
            # 评估初始 harness
            if evaluation_fn:
                metrics = evaluation_fn(initial_harness, benchmark_tasks)
                self._current_harness.metrics = metrics
                self._current_harness.score = metrics.get("score", 0.0)
                self._save_candidate(self._current_harness)

        # 优化循环
        for iteration in range(1, max_iterations + 1):
            iter_start = time.time()
            iter_result = OptimizationIteration(iteration=iteration)

            # 1. 提议新的 harness 候选者
            candidates = self._propose_candidates(
                llm_client,
                iteration,
                candidates_per_iter,
            )
            iter_result.candidates = candidates

            # 2. 评估候选者
            for candidate in candidates:
                if evaluation_fn:
                    metrics = evaluation_fn(candidate.config, benchmark_tasks)
                    candidate.metrics = metrics
                    candidate.score = metrics.get("score", 0.0)
                    candidate.timestamp = datetime.now().isoformat()

                    # 保存候选者和轨迹
                    self._save_candidate(candidate)
                    self._save_traces(candidate, metrics.get("traces", []))

            # 3. 选择最佳候选者
            best = max(candidates, key=lambda c: c.score) if candidates else None
            iter_result.best_candidate = best

            # 4. 更新当前最佳
            if best and (not self._current_harness or best.score > self._current_harness.score):
                improvement = best.score - (self._current_harness.score if self._current_harness else 0)
                iter_result.reasoning = f"改进 {improvement:.2%}"

                # 检查收敛
                if improvement < convergence_threshold:
                    result.converged = True
                    iter_result.reasoning += " (已收敛)"

                self._current_harness = best

            # 5. 记录提案推理
            if best:
                iter_result.reasoning = self._extract_reasoning(best)

            iter_result.elapsed = time.time() - iter_start
            result.iterations.append(iter_result)

            # 检查是否提前停止
            if result.converged:
                break

        result.best_overall = self._current_harness
        result.total_elapsed = time.time() - start

        # 保存最终结果
        self._save_result(result)

        return result

    def _propose_candidates(
        self,
        llm_client: OpenAI,
        iteration: int,
        count: int,
    ) -> list[HarnessCandidate]:
        """
        提议新的 harness 候选者

        这是 Meta-Harness 的核心：提案者可以访问文件系统，
        读取所有历史候选者的完整信息
        """
        candidates = []

        for i in range(count):
            # 构建提案提示
            prompt = self._build_proposal_prompt(iteration, i)

            # 调用 LLM 生成提案
            response = llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """你是 MaxBot Harness 优化器。你的任务是分析历史执行轨迹，
提出改进 harness 配置的方案。你可以通过文件系统访问所有历史候选者的完整信息。

请以 JSON 格式返回提案：
{
    "reasoning": "你的推理过程",
    "changes": [{"field": "system_prompt", "new_value": "..."}, ...],
    "new_config": {...}
}"""
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

            content = response.choices[0].message.content or ""

            # 解析提案
            try:
                # 提取 JSON 部分
                import re
                json_match = re.search(r'\{[^}]*"reasoning"[^}]*\}', content, re.DOTALL)
                if json_match:
                    proposal = json.loads(json_match.group())
                else:
                    proposal = json.loads(content)

                # 创建候选者
                base_config = self._current_harness.config if self._current_harness else {}
                new_config = proposal.get("new_config", base_config.copy())

                candidate = HarnessCandidate(
                    iteration=iteration,
                    candidate_id=f"iter{iteration}_cand{i}",
                    config=new_config,
                    source_code=content,
                    timestamp=datetime.now().isoformat(),
                )
                candidates.append(candidate)

                # 保存提案
                self._save_proposal(iteration, i, proposal)

            except (json.JSONDecodeError, KeyError) as e:
                print(f"解析提案失败: {e}")
                continue

        return candidates

    def _build_proposal_prompt(self, iteration: int, candidate_idx: int) -> str:
        """构建提案提示"""
        lines = [
            f"# 优化迭代 {iteration} - 候选者 {candidate_idx}",
            "",
            "## 当前最佳 Harness",
        ]

        if self._current_harness:
            lines.append(f"评分: {self._current_harness.score:.2%}")
            lines.append(f"配置: {json.dumps(self._current_harness.config, indent=2, ensure_ascii=False)}")
        else:
            lines.append("（无初始 harness）")

        lines.extend([
            "",
            "## 历史候选者",
            f"文件系统路径: {self.work_dir / 'candidates'}",
            "你可以使用以下工具探索历史：",
            "- cat: 读取候选者配置",
            "- ls: 列出所有候选者",
            "- grep: 搜索特定模式",
            "",
            "## 执行轨迹",
            f"文件系统路径: {self.work_dir / 'traces'}",
            "分析失败模式，提出针对性改进。",
            "",
            "## 任务",
            "基于历史执行轨迹，提出改进 harness 配置的方案。",
            "重点关注：",
            "1. 系统提示词的优化",
            "2. 工具定义的改进",
            "3. 上下文管理策略",
            "4. 错误处理机制",
        ])

        return "\n".join(lines)

    def _extract_reasoning(self, candidate: HarnessCandidate) -> str:
        """从候选者源代码中提取推理"""
        try:
            import re
            json_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', candidate.source_code)
            if json_match:
                return json_match.group(1)
        except Exception:
            pass
        return ""

    def _save_candidate(self, candidate: HarnessCandidate):
        """保存候选者到文件系统"""
        path = self.work_dir / "candidates" / f"{candidate.candidate_id}.json"
        path.write_text(json.dumps(candidate.to_dict(), indent=2, ensure_ascii=False))

    def _save_traces(self, candidate: HarnessCandidate, traces: list[dict]):
        """保存执行轨迹"""
        path = self.work_dir / "traces" / f"{candidate.candidate_id}.jsonl"
        with open(path, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    def _save_proposal(self, iteration: int, candidate_idx: int, proposal: dict):
        """保存提案"""
        path = self.work_dir / "proposals" / f"iter{iteration}_cand{candidate_idx}.json"
        path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False))

    def _save_result(self, result: OptimizationResult):
        """保存优化结果"""
        path = self.work_dir / "optimization_result.json"
        data = {
            "iterations_count": len(result.iterations),
            "best_score": result.best_score,
            "total_elapsed": result.total_elapsed,
            "converged": result.converged,
            "best_candidate": result.best_overall.to_dict() if result.best_overall else None,
            "summary": result.summary(),
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_history(self) -> list[dict]:
        """获取优化历史"""
        candidates_dir = self.work_dir / "candidates"
        history = []

        for path in sorted(candidates_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                history.append(data)
            except Exception:
                continue

        return history

    def get_best_harness(self) -> HarnessCandidate | None:
        """获取最佳 harness"""
        return self._current_harness

    def reset(self):
        """重置优化器"""
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
            self.work_dir.mkdir(parents=True=True)
            self._setup_filesystem()
        self._current_harness = None
