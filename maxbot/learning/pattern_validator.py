"""
验证模块 - 验证模式的有效性

功能：
- 重现性验证
- 价值评估
- 安全性检查
- 最佳实践检查
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List
import re


@dataclass
class ValidationScore:
    """模式验证分数"""
    reproducibility: float = 0.0
    value: float = 0.0
    safety: float = 0.0
    best_practice: float = 0.0
    overall: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reproducibility": self.reproducibility,
            "value": self.value,
            "safety": self.safety,
            "best_practice": self.best_practice,
            "overall": self.overall,
            "details": self.details,
        }


@dataclass
class ValidationResult:
    """验证结果"""
    pattern_id: str
    pattern_name: str
    pattern_type: str
    score: ValidationScore
    passed: bool
    validation_time: datetime
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    approved: bool = False
    rejected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "score": self.score.overall,
            "score_breakdown": self.score.to_dict(),
            "confidence": self.confidence,
            "reasons": self.reasons,
            "approved": self.approved,
            "rejected": self.rejected,
            "passed": self.passed,
            "validation_time": self.validation_time.isoformat(),
            "warnings": self.warnings,
            "errors": self.errors,
        }


class PatternValidator:
    """模式验证器"""

    DANGEROUS_TOOLS = ["patch", "write_file"]
    DANGEROUS_COMMAND_PATTERNS = [
        r"rm\s+-rf",
        r"del\s+/",
        r"format",
        r"drop\s+(database|table)",
    ]

    def __init__(
        self,
        validation_threshold: float = 0.7,
        min_reproducibility: float = 0.5,
        min_value_score: float = 0.5,
        min_safety: float = 0.8,
        min_best_practice: float = 0.5,
    ):
        self.validation_threshold = validation_threshold
        self.min_reproducibility = min_reproducibility
        self.min_value_score = min_value_score
        self.min_safety = min_safety
        self.min_best_practice = min_best_practice

    def validate(self, pattern) -> ValidationResult:
        result = ValidationResult(
            pattern_id=pattern.id,
            pattern_name=pattern.name,
            pattern_type=pattern.pattern_type,
            score=ValidationScore(),
            validation_time=datetime.now(),
            passed=False,
        )

        if pattern.pattern_type == "tool_sequence":
            self._validate_tool_sequence(pattern, result)
        elif pattern.pattern_type == "error_solution":
            self._validate_error_solution(pattern, result)
        elif pattern.pattern_type in {"preference", "user_preference"}:
            self._validate_preference(pattern, result)
        else:
            result.errors.append(f"Unknown pattern type: {pattern.pattern_type}")
            result.reasons.append(f"unsupported pattern type: {pattern.pattern_type}")
            result.rejected = True
            return result

        result.score.overall = self._calculate_overall_score(result.score)
        result.confidence = self._derive_validation_confidence(result)

        threshold_failures = []
        if result.score.reproducibility < self.min_reproducibility:
            threshold_failures.append("reproducibility below threshold")
        if result.score.value < self.min_value_score:
            threshold_failures.append("value below threshold")
        if result.score.safety < self.min_safety:
            threshold_failures.append("safety below threshold")
        if result.score.best_practice < self.min_best_practice:
            threshold_failures.append("best_practice below threshold")
        if result.score.overall < self.validation_threshold:
            threshold_failures.append("overall score below threshold")

        result.reasons.extend(threshold_failures)
        result.reasons.extend(result.warnings)
        result.reasons.extend(result.errors)

        result.passed = len(result.errors) == 0 and not threshold_failures
        result.approved = result.passed
        result.rejected = not result.approved
        return result

    def batch_validate(self, patterns: List) -> List[ValidationResult]:
        return [self.validate(pattern) for pattern in patterns]

    def _validate_tool_sequence(self, pattern, result: ValidationResult):
        sequence = pattern.data.get("sequence") or pattern.data.get("match_context", {}).get("tool_sequence", [])
        success_rate = pattern.data.get("success_rate") or pattern.data.get("evidence", {}).get("success_rate", 0.0)
        occurrence_count = pattern.occurrence_count

        result.score.reproducibility = self._validate_reproducibility(occurrence_count, success_rate)
        result.score.value = self._evaluate_tool_sequence_value(sequence, success_rate)

        safety_result = self._check_tool_sequence_safety(sequence)
        result.score.safety = safety_result["score"]
        result.warnings.extend(safety_result["warnings"])
        result.errors.extend(safety_result["errors"])

        practice_result = self._check_tool_sequence_best_practice(sequence)
        result.score.best_practice = practice_result["score"]
        result.warnings.extend(practice_result["warnings"])

        result.score.details = {
            "sequence_length": len(sequence),
            "success_rate": success_rate,
            "occurrence_count": occurrence_count,
        }

    def _validate_error_solution(self, pattern, result: ValidationResult):
        data = pattern.data
        solution_steps = data.get("solution_steps") or data.get("action", {}).get("resolution_steps", [])
        success_count = data.get("success_count") or data.get("evidence", {}).get("success_count", 0)
        failure_count = data.get("failure_count") or data.get("evidence", {}).get("failure_count", 0)
        occurrence_count = max(pattern.occurrence_count, success_count + failure_count)
        success_rate = data.get("success_rate") or data.get("evidence", {}).get("success_rate")
        if success_rate is None:
            success_rate = success_count / max(occurrence_count, 1)

        result.score.reproducibility = self._validate_reproducibility(occurrence_count, success_rate)
        result.score.value = self._evaluate_error_solution_value(solution_steps, success_rate)

        safety_result = self._check_solution_steps_safety(solution_steps)
        result.score.safety = safety_result["score"]
        result.warnings.extend(safety_result["warnings"])
        result.errors.extend(safety_result["errors"])

        result.score.best_practice = 1.0 if solution_steps else 0.4
        if not solution_steps:
            result.warnings.append("solution steps missing")

        result.score.details = {
            "solution_steps_count": len(solution_steps),
            "success_rate": success_rate,
            "occurrence_count": occurrence_count,
            "error_type": data.get("error_type"),
        }

    def _validate_preference(self, pattern, result: ValidationResult):
        data = pattern.data
        preference_type = data.get("preference_type") or data.get("match_context", {}).get("preference_type", "")
        frequency = data.get("frequency") or data.get("evidence", {}).get("frequency") or data.get("evidence", {}).get("occurrence_count", 0)

        result.score.reproducibility = min(frequency / 10, 1.0)
        result.score.value = self._evaluate_preference_value(preference_type, frequency)
        result.score.safety = 1.0
        result.score.best_practice = 1.0
        result.score.details = {
            "preference_type": preference_type,
            "frequency": frequency,
        }

    def _validate_reproducibility(self, occurrence_count: int, success_rate: float) -> float:
        occurrence_score = min(occurrence_count / 10, 1.0)
        reproducibility = occurrence_score * 0.6 + success_rate * 0.4
        return max(0.0, min(1.0, reproducibility))

    def _evaluate_tool_sequence_value(self, sequence: List[str], success_rate: float) -> float:
        length_bonus = min(len(sequence) / 10, 0.3)
        success_bonus = success_rate * 0.7
        return max(0.0, min(1.0, length_bonus + success_bonus))

    def _evaluate_error_solution_value(self, solution_steps: List[str], success_rate: float) -> float:
        steps_bonus = min(len(solution_steps) / 5, 0.3)
        success_bonus = success_rate * 0.7
        return max(0.0, min(1.0, steps_bonus + success_bonus))

    def _evaluate_preference_value(self, preference_type: str, frequency: int) -> float:
        base = min(frequency / 20, 1.0)
        if preference_type in {"output_language", "communication_style", "command_prefix"}:
            base = min(1.0, base + 0.1)
        return base

    def _check_tool_sequence_safety(self, sequence: List[str]) -> Dict[str, Any]:
        warnings = []
        errors = []
        safety_score = 1.0

        for tool in sequence:
            if tool in self.DANGEROUS_TOOLS:
                warnings.append(f"Sequence contains potentially dangerous tool: {tool}")
                safety_score -= 0.2

        write_count = sequence.count("write_file") + sequence.count("patch")
        if write_count > 2:
            warnings.append(f"Sequence contains multiple write operations: {write_count}")
            safety_score -= 0.2

        return {
            "score": max(0.0, min(1.0, safety_score)),
            "warnings": warnings,
            "errors": errors,
        }

    def _check_solution_steps_safety(self, steps: List[str]) -> Dict[str, Any]:
        warnings = []
        errors = []
        safety_score = 1.0

        for step in steps:
            if step in self.DANGEROUS_TOOLS:
                warnings.append(f"Solution contains potentially dangerous tool: {step}")
                safety_score -= 0.25
            for pattern in self.DANGEROUS_COMMAND_PATTERNS:
                if re.search(pattern, step, flags=re.IGNORECASE):
                    errors.append(f"Dangerous solution step detected: {step}")
                    safety_score = 0.0

        return {
            "score": max(0.0, min(1.0, safety_score)),
            "warnings": warnings,
            "errors": errors,
        }

    def _check_tool_sequence_best_practice(self, sequence: List[str]) -> Dict[str, Any]:
        warnings = []
        practice_score = 1.0
        read_tools = ["search_files", "read_file", "terminal"]
        write_tools = ["write_file", "patch"]

        has_read = any(tool in read_tools for tool in sequence)
        has_write = any(tool in write_tools for tool in sequence)

        if has_write and not has_read:
            warnings.append("Sequence writes without reading first")
            practice_score -= 0.3

        if "terminal" in sequence[1:] and "search_files" not in sequence:
            warnings.append("Terminal usage without prior file search")
            practice_score -= 0.2

        return {
            "score": max(0.0, min(1.0, practice_score)),
            "warnings": warnings,
        }

    def _derive_validation_confidence(self, result: ValidationResult) -> float:
        return max(0.0, min(1.0, result.score.overall * 0.7 + result.score.safety * 0.3))

    def _calculate_overall_score(self, score: ValidationScore) -> float:
        weights = {
            "safety": 0.4,
            "value": 0.3,
            "reproducibility": 0.2,
            "best_practice": 0.1,
        }
        return (
            score.reproducibility * weights["reproducibility"]
            + score.value * weights["value"]
            + score.safety * weights["safety"]
            + score.best_practice * weights["best_practice"]
        )
