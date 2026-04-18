"""
应用模块 - 在类似场景中自动应用学到的技能

功能：
- 场景匹配
- 本能选择
- 自动执行
- 结果反馈
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import difflib


@dataclass
class MatchResult:
    """匹配结果"""
    instinct_id: str
    instinct_name: str
    match_score: float
    match_type: str
    suggested_action: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    confidence_tier: str = "low"
    trigger_mode: str = "record"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instinct_id": self.instinct_id,
            "instinct_name": self.instinct_name,
            "match_score": self.match_score,
            "match_type": self.match_type,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
            "confidence_tier": self.confidence_tier,
            "trigger_mode": self.trigger_mode,
        }


@dataclass
class ApplicationResult:
    """应用结果"""
    success: bool
    instinct_id: str
    instinct_name: str
    match_result: MatchResult
    applied_at: datetime
    execution_time: float = 0.0
    error: Optional[str] = None
    user_confirmed: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "instinct_id": self.instinct_id,
            "instinct_name": self.instinct_name,
            "match_result": self.match_result.to_dict(),
            "applied_at": self.applied_at.isoformat(),
            "execution_time": self.execution_time,
            "error": self.error,
            "user_confirmed": self.user_confirmed,
        }


class InstinctApplier:
    """本能应用器"""

    def __init__(
        self,
        auto_apply_threshold: float = 0.9,
        require_user_confirmation: bool = True,
    ):
        self.auto_apply_threshold = auto_apply_threshold
        self.require_user_confirmation = require_user_confirmation
        self.tool_executor: Optional[Callable] = None

    def set_tool_executor(self, executor: Callable):
        self.tool_executor = executor

    def find_matching_instincts(
        self,
        context: Dict[str, Any],
        instincts: List,
        top_k: int = 5,
    ) -> List[MatchResult]:
        results: List[MatchResult] = []
        for instinct in instincts:
            if not instinct.enabled or instinct.quality_state == "invalidated":
                continue

            candidates = [
                match for match in [
                    self._match_exact(context, instinct),
                    self._match_fuzzy(context, instinct),
                    self._match_semantic(context, instinct),
                ]
                if match is not None
            ]
            if not candidates:
                continue

            best = max(candidates, key=lambda item: item.match_score)
            best.confidence = self._calculate_confidence(best, instinct)
            best.confidence_tier = self._classify_confidence(best.confidence)
            best.trigger_mode = self._determine_trigger_mode(best.confidence_tier)
            results.append(best)

        results.sort(key=lambda item: item.confidence, reverse=True)
        return results[:top_k]

    def apply_instinct(
        self,
        match_result: MatchResult,
        instinct,
        require_confirmation: Optional[bool] = None,
    ) -> ApplicationResult:
        start_time = datetime.now()
        should_confirm = (
            require_confirmation
            if require_confirmation is not None
            else self.require_user_confirmation
        )

        if match_result.trigger_mode == "auto_apply":
            should_confirm = False
        elif match_result.trigger_mode == "record":
            should_confirm = True

        if should_confirm:
            return ApplicationResult(
                success=False,
                instinct_id=instinct.id,
                instinct_name=instinct.name,
                match_result=match_result,
                applied_at=datetime.now(),
                user_confirmed=None,
            )

        try:
            self._execute_instinct(instinct)
            execution_time = (datetime.now() - start_time).total_seconds()
            return ApplicationResult(
                success=True,
                instinct_id=instinct.id,
                instinct_name=instinct.name,
                match_result=match_result,
                applied_at=datetime.now(),
                execution_time=execution_time,
                user_confirmed=True,
            )
        except Exception as exc:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ApplicationResult(
                success=False,
                instinct_id=instinct.id,
                instinct_name=instinct.name,
                match_result=match_result,
                applied_at=datetime.now(),
                execution_time=execution_time,
                error=str(exc),
                user_confirmed=True,
            )

    def _match_exact(self, context: Dict[str, Any], instinct) -> Optional[MatchResult]:
        match_context = instinct.pattern_data.get("match_context", {})

        if instinct.pattern_type == "tool_sequence":
            sequence = instinct.pattern_data.get("sequence") or match_context.get("tool_sequence", [])
            current_sequence = context.get("recent_tool_calls", [])
            if current_sequence == sequence:
                return MatchResult(
                    instinct_id=instinct.id,
                    instinct_name=instinct.name,
                    match_score=1.0,
                    match_type="exact",
                    suggested_action=instinct.pattern_data.get("action"),
                )
            if len(current_sequence) >= len(sequence) - 1 and current_sequence[: len(sequence) - 1] == sequence[: len(sequence) - 1]:
                return MatchResult(
                    instinct_id=instinct.id,
                    instinct_name=instinct.name,
                    match_score=0.9,
                    match_type="exact",
                    suggested_action=instinct.pattern_data.get("action"),
                )

        if instinct.pattern_type == "error_solution":
            error_signature = instinct.pattern_data.get("error_signature") or match_context.get("error_signature", "")
            current_error = context.get("recent_error", "")
            same_type = not match_context.get("error_type") or match_context.get("error_type") == context.get("error_type")
            if same_type and self._error_signatures_match(error_signature, current_error):
                return MatchResult(
                    instinct_id=instinct.id,
                    instinct_name=instinct.name,
                    match_score=1.0,
                    match_type="exact",
                    suggested_action=instinct.pattern_data.get("action"),
                )

        if instinct.pattern_type == "user_preference":
            preference_type = instinct.pattern_data.get("preference_type") or match_context.get("preference_type")
            preference_value = instinct.pattern_data.get("preference_value") or match_context.get("preference_value")
            if preference_type == "output_language" and context.get("response_language") == preference_value:
                return MatchResult(
                    instinct_id=instinct.id,
                    instinct_name=instinct.name,
                    match_score=1.0,
                    match_type="exact",
                    suggested_action=instinct.pattern_data.get("action"),
                )

        return None

    def _match_fuzzy(self, context: Dict[str, Any], instinct) -> Optional[MatchResult]:
        user_message = context.get("user_message", "").lower()
        match_context = instinct.pattern_data.get("match_context", {})

        if instinct.pattern_type == "user_preference":
            preference_type = instinct.pattern_data.get("preference_type") or match_context.get("preference_type", "")
            preference_value = instinct.pattern_data.get("preference_value") or match_context.get("preference_value", "")
            if preference_type == "command_prefix" and user_message.startswith(str(preference_value).lower()):
                return MatchResult(
                    instinct_id=instinct.id,
                    instinct_name=instinct.name,
                    match_score=0.82,
                    match_type="fuzzy",
                    suggested_action=instinct.pattern_data.get("action"),
                )
            if preference_type == "interaction_style" and context.get("communication_style") == preference_value:
                return MatchResult(
                    instinct_id=instinct.id,
                    instinct_name=instinct.name,
                    match_score=0.8,
                    match_type="fuzzy",
                    suggested_action=instinct.pattern_data.get("action"),
                )

        if instinct.pattern_type == "error_solution":
            candidate_type = match_context.get("error_type")
            current_type = context.get("error_type")
            if candidate_type and current_type and candidate_type == current_type:
                similarity = difflib.SequenceMatcher(
                    None,
                    (context.get("recent_error", "") or "").lower(),
                    (instinct.pattern_data.get("error") or instinct.description).lower(),
                ).ratio()
                if similarity >= 0.45:
                    return MatchResult(
                        instinct_id=instinct.id,
                        instinct_name=instinct.name,
                        match_score=similarity,
                        match_type="fuzzy",
                        suggested_action=instinct.pattern_data.get("action"),
                    )

        return None

    def _match_semantic(self, context: Dict[str, Any], instinct) -> Optional[MatchResult]:
        user_message = context.get("user_message", "")
        description = instinct.description.lower()
        similarity = difflib.SequenceMatcher(None, user_message.lower(), description).ratio()
        if similarity >= 0.5:
            return MatchResult(
                instinct_id=instinct.id,
                instinct_name=instinct.name,
                match_score=similarity * 0.7,
                match_type="semantic",
                suggested_action=instinct.pattern_data.get("action"),
            )
        return None

    def _error_signatures_match(self, sig1: str, sig2: str) -> bool:
        sig1 = (sig1 or "").lower()
        sig2 = (sig2 or "").lower()
        return bool(sig1 and sig2 and (sig1 in sig2 or sig2 in sig1))

    def _calculate_confidence(self, match_result: MatchResult, instinct) -> float:
        match_score = match_result.match_score
        success_rate = instinct.success_rate
        match_weights = {
            "exact": 0.7,
            "fuzzy": 0.55,
            "semantic": 0.35,
        }
        quality_bonus = {
            "active": 0.15,
            "degraded": -0.1,
            "invalidated": -0.4,
        }.get(getattr(instinct, "quality_state", "active"), 0.0)

        confidence = (
            match_score * match_weights.get(match_result.match_type, 0.3)
            + success_rate * 0.3
            + quality_bonus
        )
        return max(0.0, min(1.0, confidence))

    def _classify_confidence(self, confidence: float) -> str:
        if confidence >= self.auto_apply_threshold:
            return "high"
        if confidence >= max(0.45, self.auto_apply_threshold - 0.2):
            return "medium"
        return "low"

    def _determine_trigger_mode(self, confidence_tier: str) -> str:
        if confidence_tier == "high":
            return "auto_apply"
        if confidence_tier == "medium":
            return "suggest"
        return "record"

    def _execute_instinct(self, instinct) -> Dict[str, Any]:
        if instinct.pattern_type == "tool_sequence":
            return self._execute_tool_sequence(instinct)
        if instinct.pattern_type == "error_solution":
            return self._execute_error_solution(instinct)
        if instinct.pattern_type == "user_preference":
            return self._execute_preference(instinct)
        raise ValueError(f"Unknown instinct type: {instinct.pattern_type}")

    def _execute_tool_sequence(self, instinct) -> Dict[str, Any]:
        sequence = instinct.pattern_data.get("sequence", [])
        results = []
        for tool_name in sequence:
            if self.tool_executor:
                results.append(self.tool_executor(tool_name, {}))
            else:
                results.append({"tool": tool_name, "action": "suggested"})
        return {"results": results}

    def _execute_error_solution(self, instinct) -> Dict[str, Any]:
        steps = instinct.pattern_data.get("solution_steps") or instinct.pattern_data.get("action", {}).get("resolution_steps", [])
        results = []
        for step in steps:
            if self.tool_executor:
                results.append(self.tool_executor(step, {}))
            else:
                results.append({"step": step, "action": "suggested"})
        return {"results": results}

    def _execute_preference(self, instinct) -> Dict[str, Any]:
        preference_type = instinct.pattern_data.get("preference_type", "")
        preference_value = instinct.pattern_data.get("preference_value", "")
        return {
            "preference_type": preference_type,
            "preference_value": preference_value,
            "action": "applied",
        }
