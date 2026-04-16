"""
自我改进器 — 自动分析、生成补丁、测试、应用

核心循环:
1. 分析自身代码 → 发现问题
2. 为每个问题生成补丁
3. 应用补丁 → 跑测试
4. 测试通过 → 保留；测试失败 → 回滚
5. 记录改进历史

用法:
    improver = SelfImprover("/path/to/maxbot")
    result = improver.run(llm_client)
    print(result.summary())
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.self_analyzer import analyze_self, Issue, AnalysisReport
from maxbot.knowledge.patch_generator import generate_patch, validate_patch, Patch


@dataclass
class ImprovementAttempt:
    """单次改进尝试"""
    issue: Issue
    patch: Patch | None = None
    applied: bool = False
    test_passed: bool | None = None
    test_output: str = ""
    rolled_back: bool = False
    error: str = ""
    elapsed: float = 0.0


@dataclass
class ImprovementResult:
    """改进结果"""
    project_root: str
    report: AnalysisReport | None = None
    attempts: list[ImprovementAttempt] = field(default_factory=list)
    total_elapsed: float = 0.0

    @property
    def applied_count(self) -> int:
        return sum(1 for a in self.attempts if a.applied and a.test_passed and not a.rolled_back)

    @property
    def failed_count(self) -> int:
        return sum(1 for a in self.attempts if a.rolled_back)

    def summary(self) -> str:
        lines = [
            f"## 自我改进报告",
            f"- 发现问题: {self.report.total_count if self.report else 0}",
            f"- 尝试修复: {len(self.attempts)}",
            f"- 成功应用: {self.applied_count}",
            f"- 回滚: {self.failed_count}",
            f"- 耗时: {self.total_elapsed:.1f}s",
        ]
        for a in self.attempts:
            status = "✅" if (a.applied and a.test_passed and not a.rolled_back) else "❌"
            lines.append(f"- {status} {a.issue.title}" + (f" — {a.error}" if a.error else ""))
        return "\n".join(lines)


class SelfImprover:
    """
    自我改进器

    用法:
        improver = SelfImprover(project_root="/root/maxbot")
        result = improver.run(llm_client)
    """

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self._history_file = self.root / ".maxbot_improvements.jsonl"

    def run(
        self,
        llm_client: Any,
        model: str = "gpt-4o-mini",
        test_cmd: str = "python -m pytest tests/ -q --tb=short",
        auto_apply: bool = True,
        max_fixes: int = 5,
        focus: str | None = None,
    ) -> ImprovementResult:
        """
        执行一轮自我改进

        Args:
            llm_client: LLM 客户端
            model: 模型
            test_cmd: 测试命令
            auto_apply: 是否自动应用（False 则只报告）
            max_fixes: 单轮最大修复数
            focus: 聚焦维度
        """
        start = time.time()
        result = ImprovementResult(project_root=str(self.root))

        # 1. 分析
        result.report = analyze_self(self.root, llm_client, model, focus=focus)
        if not result.report.issues:
            result.total_elapsed = time.time() - start
            return result

        # 2. 确保当前状态可回滚（需要 git clean state）
        if not self._is_git_clean():
            result.total_elapsed = time.time() - start
            return result

        # 3. 逐个尝试修复
        for issue in result.report.issues[:max_fixes]:
            attempt = self._try_fix_issue(issue, llm_client, model, test_cmd, auto_apply)
            result.attempts.append(attempt)

        result.total_elapsed = time.time() - start

        # 4. 记录历史
        self._save_history(result)

        return result

    def run_single(
        self,
        issue: Issue,
        llm_client: Any,
        model: str = "gpt-4o-mini",
        test_cmd: str = "python -m pytest tests/ -q --tb=short",
    ) -> ImprovementAttempt:
        """修复单个问题"""
        return self._try_fix_issue(issue, llm_client, model, test_cmd, auto_apply=True)

    def _try_fix_issue(
        self,
        issue: Issue,
        llm_client: Any,
        model: str,
        test_cmd: str,
        auto_apply: bool,
    ) -> ImprovementAttempt:
        """尝试修复单个问题"""
        start = time.time()
        attempt = ImprovementAttempt(issue=issue)

        try:
            # 生成补丁
            attempt.patch = generate_patch(issue, self.root, llm_client, model)
            if not attempt.patch.is_valid():
                attempt.error = "未生成有效补丁"
                attempt.elapsed = time.time() - start
                return attempt

            # 验证补丁
            can_apply, reason = validate_patch(attempt.patch, self.root)
            if not can_apply:
                attempt.error = f"补丁验证失败: {reason}"
                attempt.elapsed = time.time() - start
                return attempt

            if not auto_apply:
                attempt.elapsed = time.time() - start
                return attempt

            # 应用补丁
            applied = self._apply_patch(attempt.patch)
            if not applied:
                attempt.error = "补丁应用失败"
                attempt.elapsed = time.time() - start
                return attempt
            attempt.applied = True

            # 跑测试
            passed, output = self._run_tests(test_cmd)
            attempt.test_passed = passed
            attempt.test_output = output

            if not passed:
                # 回滚
                self._rollback()
                attempt.rolled_back = True
                attempt.error = f"测试失败，已回滚"

        except Exception as e:
            attempt.error = str(e)
            if attempt.applied:
                self._rollback()
                attempt.rolled_back = True

        attempt.elapsed = time.time() - start
        return attempt

    def _is_git_clean(self) -> bool:
        """检查 git 工作区是否干净"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and not result.stdout.strip()
        except Exception:
            return False

    def _apply_patch(self, patch: Patch) -> bool:
        """应用补丁"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch.diff)
            patch_file = f.name

        try:
            result = subprocess.run(
                ["git", "apply", patch_file],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
        finally:
            Path(patch_file).unlink(missing_ok=True)

    def _rollback(self) -> bool:
        """回滚所有未提交的更改"""
        try:
            subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=str(self.root),
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=str(self.root),
                capture_output=True,
                timeout=10,
            )
            return True
        except Exception:
            return False

    def _run_tests(self, test_cmd: str) -> tuple[bool, str]:
        """运行测试"""
        try:
            result = subprocess.run(
                test_cmd.split(),
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            return passed, output[-2000:]  # 只保留最后 2000 字符
        except subprocess.TimeoutExpired:
            return False, "测试超时 (120s)"
        except Exception as e:
            return False, str(e)

    def _save_history(self, result: ImprovementResult):
        """追加改进历史"""
        try:
            with open(self._history_file, "a") as f:
                for attempt in result.attempts:
                    record = {
                        "timestamp": time.time(),
                        "issue": attempt.issue.title,
                        "category": attempt.issue.category,
                        "applied": attempt.applied,
                        "test_passed": attempt.test_passed,
                        "rolled_back": attempt.rolled_back,
                        "error": attempt.error,
                        "elapsed": round(attempt.elapsed, 2),
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def get_history(self) -> list[dict]:
        """读取改进历史"""
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
