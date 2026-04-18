"""
模式提取模块 - 从观察记录中识别可复用的模式

功能：
- 提取工具使用序列模式
- 提取错误-解决模式
- 提取用户偏好模式
- 支持不同的模式阈值
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import Counter, defaultdict
import hashlib
import re


@dataclass
class Pattern:
    """提取的模式"""
    id: str
    name: str
    pattern_type: str  # tool_sequence, error_solution, user_preference
    data: Dict[str, Any]
    occurrence_count: int
    confidence: float  # 0-1, 置信度
    extracted_at: datetime
    tags: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "pattern_type": self.pattern_type,
            "data": self.data,
            "occurrence_count": self.occurrence_count,
            "confidence": self.confidence,
            "extracted_at": self.extracted_at.isoformat(),
            "tags": self.tags,
            "description": self.description,
        }


class PatternExtractor:
    """模式提取器"""

    def __init__(
        self,
        min_occurrence_count: int = 3,
        pattern_threshold: str = "medium",
    ):
        self.min_occurrence_count = min_occurrence_count
        self.pattern_threshold = pattern_threshold
        self.thresholds = {
            "low": {
                "min_confidence": 0.5,
                "min_sequence_length": 2,
                "min_success_rate": 0.6,
                "min_preference_ratio": 0.6,
            },
            "medium": {
                "min_confidence": 0.7,
                "min_sequence_length": 3,
                "min_success_rate": 0.8,
                "min_preference_ratio": 0.7,
            },
            "high": {
                "min_confidence": 0.85,
                "min_sequence_length": 4,
                "min_success_rate": 0.9,
                "min_preference_ratio": 0.8,
            },
        }

    def aggregate_observations(self, observations: List) -> Dict[str, Any]:
        """聚合 observation，为后续 pattern extraction 提供统一入口。"""
        successful = [obs for obs in observations if obs.success]
        failed = [obs for obs in observations if not obs.success]

        tool_sequences = [
            [tool_call.tool_name for tool_call in obs.tool_calls]
            for obs in successful
            if obs.tool_calls
        ]

        error_events = []
        preference_signals = defaultdict(Counter)
        for obs in observations:
            if obs.context:
                language = obs.context.get("response_language")
                if language:
                    preference_signals["output_language"][language] += 1
                style = obs.context.get("communication_style")
                if style:
                    preference_signals["communication_style"][style] += 1

            if not obs.success and obs.tool_results:
                last_result = obs.tool_results[-1]
                if last_result.error:
                    error_events.append(
                        {
                            "session_id": obs.session_id,
                            "error_signature": self._get_error_signature(last_result.error),
                            "error_message": last_result.error,
                            "tool_name": last_result.tool_name,
                            "observation": obs,
                        }
                    )

        return {
            "total_observations": len(observations),
            "successful_observations": len(successful),
            "failed_observations": len(failed),
            "tool_sequences": tool_sequences,
            "error_events": error_events,
            "preference_signals": {
                key: dict(counter) for key, counter in preference_signals.items()
            },
        }

    def extract_patterns(
        self,
        observations: List,
        enable_tool_sequence: bool = True,
        enable_error_solution: bool = True,
        enable_user_preference: bool = True,
    ) -> List[Pattern]:
        patterns: List[Pattern] = []

        if enable_tool_sequence:
            patterns.extend(self._extract_tool_sequences(observations))

        if enable_error_solution:
            patterns.extend(self._extract_error_solution(observations))

        if enable_user_preference:
            patterns.extend(self._extract_user_preferences(observations))

        patterns.sort(key=lambda pattern: pattern.confidence, reverse=True)
        return patterns

    def extract_error_pattern(self, error: str, context: Optional[Dict[str, Any]] = None) -> Optional[Pattern]:
        """从错误上下文直接提取单个错误模式。"""
        context = dict(context or {})
        resolution = (
            context.get("resolution")
            or context.get("solution")
            or context.get("fix")
            or ""
        )
        occurrence_count = max(
            int(context.get("occurrence_count", self.min_occurrence_count if resolution else 1)),
            1,
        )
        fix_success = bool(context.get("fix_success", bool(resolution)))
        if occurrence_count < self.min_occurrence_count or not resolution:
            return None

        error_signature = self._get_error_signature(error)
        error_type = self._classify_error(error, context)
        solution_steps = context.get("solution_steps") or self._resolution_to_steps(resolution)
        success_count = occurrence_count if fix_success else max(occurrence_count - 1, 0)
        failure_count = 0 if fix_success else 1
        success_rate = success_count / max(success_count + failure_count, 1)
        confidence = min(1.0, 0.45 + occurrence_count * 0.15 + success_rate * 0.25)
        threshold = self.thresholds[self.pattern_threshold]

        if confidence < threshold["min_confidence"]:
            return None

        data = self._build_pattern_payload(
            pattern_type="error_solution",
            signature=f"error_solution:{error_type}:{error_signature}",
            match_context={
                "event_type": "error",
                "error_signature": error_signature,
                "error_type": error_type,
                "tool_name": context.get("tool_name", "unknown"),
            },
            action={
                "type": "suggest_resolution",
                "resolution_steps": solution_steps,
                "resolution_summary": resolution,
            },
            evidence={
                "occurrence_count": occurrence_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
            },
            extra={
                "error": error,
                "error_signature": error_signature,
                "error_type": error_type,
                "resolution": resolution,
                "resolution_summary": resolution,
                "solution_steps": solution_steps,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
                "tool_name": context.get("tool_name", "unknown"),
                "tool_args": context.get("tool_args", {}),
                "tool_result": context.get("tool_result", {}),
                "user_message": context.get("user_message", ""),
                "context": context,
                "fix_success": fix_success,
            },
        )

        return Pattern(
            id=self._generate_pattern_id("error_solution", data["signature"]),
            name=f"Error Solution: {error_type}",
            pattern_type="error_solution",
            data=data,
            occurrence_count=occurrence_count,
            confidence=confidence,
            extracted_at=datetime.now(),
            tags=["error_solution", error_type, context.get("tool_name", "unknown")],
            description=f"Stable solution for {error_type}: {error_signature[:48]}",
        )

    def _extract_tool_sequences(self, observations: List) -> List[Pattern]:
        threshold = self.thresholds[self.pattern_threshold]
        sequence_counter = Counter()
        durations = defaultdict(list)
        totals = defaultdict(int)
        successes = defaultdict(int)

        for obs in observations:
            sequence = [tool_call.tool_name for tool_call in obs.tool_calls]
            if len(sequence) < threshold["min_sequence_length"]:
                continue
            key = tuple(sequence)
            sequence_counter[key] += 1
            totals[key] += 1
            if obs.success:
                successes[key] += 1
            durations[key].append(sum(result.duration for result in obs.tool_results if result.success))

        patterns: List[Pattern] = []
        for sequence, count in sequence_counter.items():
            if count < self.min_occurrence_count:
                continue

            success_rate = successes[sequence] / max(totals[sequence], 1)
            confidence = self._calculate_sequence_confidence(count, success_rate, len(sequence))
            if success_rate < threshold["min_success_rate"] or confidence < threshold["min_confidence"]:
                continue

            avg_duration = sum(durations[sequence]) / len(durations[sequence]) if durations[sequence] else 0.0
            sequence_list = list(sequence)
            data = self._build_pattern_payload(
                pattern_type="tool_sequence",
                signature=f"tool_sequence:{'>'.join(sequence_list)}",
                match_context={
                    "event_type": "tool_sequence",
                    "tool_sequence": sequence_list,
                },
                action={
                    "type": "suggest_tool_sequence",
                    "sequence": sequence_list,
                    "next_tool": sequence_list[-1],
                },
                evidence={
                    "occurrence_count": count,
                    "success_rate": success_rate,
                    "avg_duration": avg_duration,
                },
                extra={
                    "sequence": sequence_list,
                    "avg_duration": avg_duration,
                    "success_rate": success_rate,
                    "occurrence_count": count,
                },
            )
            patterns.append(
                Pattern(
                    id=self._generate_pattern_id("tool_sequence", data["signature"]),
                    name=f"Tool Sequence: {' → '.join(sequence_list)}",
                    pattern_type="tool_sequence",
                    data=data,
                    occurrence_count=count,
                    confidence=confidence,
                    extracted_at=datetime.now(),
                    tags=["tool_sequence", "automation"],
                    description=f"Common tool sequence used {count} times with {success_rate:.1%} success rate",
                )
            )

        return patterns

    def _extract_error_solution(self, observations: List) -> List[Pattern]:
        candidates: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "success_count": 0,
            "failure_count": 0,
            "resolution_counter": Counter(),
            "tool_counter": Counter(),
            "example_error": "",
            "error_type": "runtime_error",
        })

        for index, obs in enumerate(observations[:-1]):
            if obs.success or not obs.tool_results:
                continue

            last_result = obs.tool_results[-1]
            if not last_result.error:
                continue

            next_obs = observations[index + 1]
            if not next_obs.success:
                continue

            error_signature = self._get_error_signature(last_result.error)
            error_type = self._classify_error(last_result.error, obs.context)
            resolution = (
                next_obs.context.get("resolution")
                or obs.context.get("resolution")
                or " → ".join(tool_call.tool_name for tool_call in next_obs.tool_calls)
            )
            key = f"{error_type}:{error_signature}"
            bucket = candidates[key]
            bucket["count"] += 1
            bucket["success_count"] += 1
            bucket["resolution_counter"][resolution] += 1
            bucket["tool_counter"][last_result.tool_name] += 1
            bucket["example_error"] = last_result.error
            bucket["error_type"] = error_type

        patterns: List[Pattern] = []
        threshold = self.thresholds[self.pattern_threshold]
        for key, bucket in candidates.items():
            count = bucket["count"]
            if count < self.min_occurrence_count:
                continue

            resolution, resolution_count = bucket["resolution_counter"].most_common(1)[0]
            error_type, error_signature = key.split(":", 1)
            success_rate = bucket["success_count"] / max(count, 1)
            confidence = min(1.0, 0.45 + resolution_count * 0.15 + success_rate * 0.25)
            if confidence < threshold["min_confidence"]:
                continue

            solution_steps = self._resolution_to_steps(resolution)
            tool_name = bucket["tool_counter"].most_common(1)[0][0] if bucket["tool_counter"] else "unknown"
            data = self._build_pattern_payload(
                pattern_type="error_solution",
                signature=f"error_solution:{error_type}:{error_signature}",
                match_context={
                    "event_type": "error",
                    "error_signature": error_signature,
                    "error_type": error_type,
                    "tool_name": tool_name,
                },
                action={
                    "type": "suggest_resolution",
                    "resolution_steps": solution_steps,
                    "resolution_summary": resolution,
                },
                evidence={
                    "occurrence_count": count,
                    "success_count": bucket["success_count"],
                    "failure_count": bucket["failure_count"],
                    "success_rate": success_rate,
                },
                extra={
                    "error": bucket["example_error"],
                    "error_signature": error_signature,
                    "error_type": error_type,
                    "resolution": resolution,
                    "resolution_summary": resolution,
                    "solution_steps": solution_steps,
                    "success_count": bucket["success_count"],
                    "failure_count": bucket["failure_count"],
                    "success_rate": success_rate,
                    "tool_name": tool_name,
                },
            )
            patterns.append(
                Pattern(
                    id=self._generate_pattern_id("error_solution", data["signature"]),
                    name=f"Error Solution: {error_signature[:50]}",
                    pattern_type="error_solution",
                    data=data,
                    occurrence_count=count,
                    confidence=confidence,
                    extracted_at=datetime.now(),
                    tags=["error_solution", error_type, tool_name],
                    description=f"Solution for '{error_signature[:40]}...' used {count} times",
                )
            )

        return patterns

    def _extract_user_preferences(self, observations: List) -> List[Pattern]:
        threshold = self.thresholds[self.pattern_threshold]
        total = len(observations)
        if total < self.min_occurrence_count:
            return []

        patterns: List[Pattern] = []
        language_counter = Counter()
        style_counter = Counter()
        command_counter = Counter()

        for obs in observations:
            if obs.context.get("response_language"):
                language_counter[obs.context["response_language"]] += 1
            if obs.context.get("communication_style"):
                style_counter[obs.context["communication_style"]] += 1

            words = obs.user_message.strip().split()
            if len(words) >= 2:
                command_counter[f"{words[0]} {words[1]}"] += 1

        patterns.extend(
            self._build_preference_patterns(
                preference_type="output_language",
                counter=language_counter,
                total=total,
                threshold=threshold,
                tag="language",
            )
        )
        patterns.extend(
            self._build_preference_patterns(
                preference_type="interaction_style",
                counter=style_counter,
                total=total,
                threshold=threshold,
                tag="interaction",
            )
        )
        patterns.extend(
            self._build_preference_patterns(
                preference_type="command_prefix",
                counter=command_counter,
                total=total,
                threshold=threshold,
                tag="command",
            )
        )

        return patterns

    def _build_preference_patterns(
        self,
        preference_type: str,
        counter: Counter,
        total: int,
        threshold: Dict[str, float],
        tag: str,
    ) -> List[Pattern]:
        patterns: List[Pattern] = []
        for value, count in counter.items():
            if count < self.min_occurrence_count:
                continue
            ratio = count / max(total, 1)
            confidence = min(1.0, ratio * 0.8 + min(count / 10, 0.2))
            if ratio < threshold["min_preference_ratio"] or confidence < threshold["min_confidence"]:
                continue

            data = self._build_pattern_payload(
                pattern_type="user_preference",
                signature=f"user_preference:{preference_type}:{value}",
                match_context={
                    "event_type": "user_preference",
                    "preference_type": preference_type,
                    "preference_value": value,
                },
                action={
                    "type": "apply_preference",
                    "preference": {preference_type: value},
                },
                evidence={
                    "occurrence_count": count,
                    "frequency": count,
                    "ratio": ratio,
                },
                extra={
                    "preference_type": preference_type,
                    "preference_value": value,
                    "frequency": count,
                },
            )
            patterns.append(
                Pattern(
                    id=self._generate_pattern_id("user_preference", data["signature"]),
                    name=f"User Preference: {preference_type}={value}",
                    pattern_type="user_preference",
                    data=data,
                    occurrence_count=count,
                    confidence=confidence,
                    extracted_at=datetime.now(),
                    tags=["user_preference", tag],
                    description=f"User repeatedly prefers {preference_type}={value}",
                )
            )
        return patterns

    def _build_pattern_payload(
        self,
        *,
        pattern_type: str,
        signature: str,
        match_context: Dict[str, Any],
        action: Dict[str, Any],
        evidence: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "pattern_type": pattern_type,
            "signature": signature,
            "match_context": match_context,
            "action": action,
            "evidence": evidence,
        }
        if extra:
            payload.update(extra)
        return payload

    def _get_error_signature(self, error: str) -> str:
        signature = error[:100].lower()
        signature = re.sub(r"/[^\s]+/", "/.../", signature)
        signature = re.sub(r"\d+", "N", signature)
        signature = re.sub(r"0x[0-9a-f]+", "0x...", signature)
        return signature.strip()

    def _classify_error(self, error: str, context: Optional[Dict[str, Any]] = None) -> str:
        context = context or {}
        explicit_type = context.get("error_type")
        if explicit_type:
            return explicit_type

        lowered = error.lower()
        if context.get("user_correction"):
            return "user_correction"
        if "validation" in lowered or "schema" in lowered:
            return "validation_error"
        if context.get("tool_name"):
            return "tool_error"
        if any(token in lowered for token in ["traceback", "exception", "runtime", "timeout"]):
            return "runtime_error"
        return "runtime_error"

    def _resolution_to_steps(self, resolution: str) -> List[str]:
        if not resolution:
            return []
        if "→" in resolution:
            parts = [part.strip() for part in resolution.split("→")]
        elif "->" in resolution:
            parts = [part.strip() for part in resolution.split("->")]
        elif "，" in resolution:
            parts = [part.strip() for part in resolution.split("，")]
        else:
            parts = [resolution.strip()]
        return [part for part in parts if part]

    def _calculate_sequence_confidence(
        self,
        occurrence_count: int,
        success_rate: float,
        sequence_length: int,
    ) -> float:
        occurrence_ratio = min(
            occurrence_count / max(self.min_occurrence_count, 1),
            1.0,
        )
        success_component = success_rate * 0.4
        length_bonus = min(sequence_length / 30, 0.1)
        confidence = occurrence_ratio * 0.5 + success_component + length_bonus
        return max(0, min(1, confidence))

    def _generate_pattern_id(self, pattern_type: str, key: Any) -> str:
        key_str = str(key)
        hash_val = hashlib.sha256(key_str.encode()).hexdigest()[:12]
        return f"{pattern_type}_{hash_val}"
