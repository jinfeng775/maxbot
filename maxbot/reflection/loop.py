from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from maxbot.reflection.policy import ReflectionDecision


@dataclass
class ReflectionResult:
    final_output: str
    revision_count: int = 0
    reflection_applied: bool = False
    critiques: list[dict[str, Any]] = field(default_factory=list)
    stopped_reason: str = "accepted"


class ReflectionLoop:
    def __init__(self, *, critic: Any, max_revisions: int = 1):
        self.critic = critic
        self.max_revisions = max_revisions

    def run(
        self,
        *,
        draft: str,
        decision: ReflectionDecision,
        revise_fn: Callable[[str, str], str],
        context: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        if not decision.enabled:
            return ReflectionResult(
                final_output=draft,
                revision_count=0,
                reflection_applied=False,
                critiques=[],
                stopped_reason="skipped",
            )

        current = draft
        critiques: list[dict[str, Any]] = []
        revisions = 0
        max_revisions = min(decision.max_revisions, self.max_revisions)
        stopped_reason = "accepted"

        while True:
            critique = self.critic.critique(current, context or {})
            critiques.append(critique)
            if not critique.get("revise"):
                stopped_reason = "accepted"
                break
            if revisions >= max_revisions:
                stopped_reason = "max_revisions_reached"
                break

            feedback = critique.get("feedback", "")
            current = revise_fn(current, feedback)
            revisions += 1

        return ReflectionResult(
            final_output=current,
            revision_count=revisions,
            reflection_applied=True,
            critiques=critiques,
            stopped_reason=stopped_reason,
        )
