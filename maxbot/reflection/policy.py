from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReflectionDecision:
    enabled: bool
    reason: str
    max_revisions: int


class ReflectionPolicy:
    def __init__(
        self,
        *,
        enabled: bool,
        max_revisions: int,
        min_output_chars: int,
        high_risk_tool_threshold: int,
        apply_to_task_types: list[str] | None = None,
    ):
        self.enabled = enabled
        self.max_revisions = max_revisions
        self.min_output_chars = min_output_chars
        self.high_risk_tool_threshold = high_risk_tool_threshold
        self.apply_to_task_types = apply_to_task_types or ["default"]

    def should_reflect(
        self,
        *,
        task_type: str,
        output_text: str,
        tool_calls: int,
        metadata: dict | None = None,
    ) -> ReflectionDecision:
        metadata = metadata or {}

        if not self.enabled:
            return ReflectionDecision(False, "reflection_disabled", self.max_revisions)

        if task_type not in self.apply_to_task_types:
            return ReflectionDecision(False, "task_type_not_enabled", self.max_revisions)

        if len((output_text or "").strip()) < self.min_output_chars:
            return ReflectionDecision(False, "output_too_short", self.max_revisions)

        risk_level = metadata.get("risk_level")
        if tool_calls >= self.high_risk_tool_threshold:
            return ReflectionDecision(True, "high_risk_tool_usage", self.max_revisions)

        if risk_level in {"high", "critical"}:
            return ReflectionDecision(True, "high_risk_level", self.max_revisions)

        return ReflectionDecision(False, "policy_not_triggered", self.max_revisions)
