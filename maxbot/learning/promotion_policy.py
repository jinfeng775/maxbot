from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PromotionDecision:
    target: str
    reason: str
    payload: dict[str, Any] | None = None


class PromotionPolicy:
    def decide(self, *, artifact_type: str, artifact: dict[str, Any]) -> PromotionDecision:
        if artifact_type == "user_preference":
            frequency = artifact.get("frequency", 0)
            stability = artifact.get("stability", 0.0)
            if frequency >= 3 and stability >= 0.8:
                return PromotionDecision(
                    target="memory",
                    reason="stable_user_preference",
                    payload={
                        "key": artifact.get("key"),
                        "value": artifact.get("value"),
                    },
                )
            return PromotionDecision(target="ignore", reason="insufficient_signal")

        if artifact_type == "validated_pattern":
            pattern = artifact.get("pattern")
            validation = artifact.get("validation")
            if not pattern or not validation:
                return PromotionDecision(target="ignore", reason="insufficient_signal")

            overall = getattr(validation.score, "overall", 0.0)
            occurrence_count = getattr(pattern, "occurrence_count", 0)
            confidence = getattr(pattern, "confidence", 0.0)
            if overall >= 0.7 and occurrence_count >= 3 and confidence >= 0.7:
                return PromotionDecision(
                    target="instinct",
                    reason="validated_repeated_pattern",
                    payload={
                        "pattern_id": pattern.id,
                        "pattern_type": pattern.pattern_type,
                    },
                )
            return PromotionDecision(target="ignore", reason="insufficient_signal")

        return PromotionDecision(target="ignore", reason="unsupported_artifact_type")
