from datetime import datetime

from maxbot.learning.pattern_extractor import Pattern
from maxbot.learning.pattern_validator import ValidationResult, ValidationScore


def _tool_sequence_pattern() -> Pattern:
    return Pattern(
        id="pattern-tool-1",
        name="High confidence tool sequence",
        pattern_type="tool_sequence",
        data={
            "sequence": ["search_files", "read_file", "patch"],
            "success_rate": 0.95,
            "match_context": {"tool_sequence": ["search_files", "read_file", "patch"]},
            "evidence": {"success_rate": 0.95, "occurrence_count": 5},
        },
        occurrence_count=5,
        confidence=0.92,
        extracted_at=datetime.now(),
        tags=["tool_sequence"],
        description="A reliable file-analysis workflow",
    )


def _validation_result(pattern: Pattern, overall: float = 0.91) -> ValidationResult:
    return ValidationResult(
        pattern_id=pattern.id,
        pattern_name=pattern.name,
        pattern_type=pattern.pattern_type,
        score=ValidationScore(
            reproducibility=0.9,
            value=0.9,
            safety=0.95,
            best_practice=0.9,
            overall=overall,
            details={"occurrence_count": pattern.occurrence_count},
        ),
        passed=True,
        validation_time=datetime.now(),
        confidence=0.9,
        approved=True,
        rejected=False,
    )


def test_promotion_policy_routes_user_preference_to_memory():
    from maxbot.learning.promotion_policy import PromotionPolicy

    policy = PromotionPolicy()

    decision = policy.decide(
        artifact_type="user_preference",
        artifact={
            "key": "preferred_language",
            "value": "zh-CN",
            "frequency": 4,
            "stability": 0.95,
        },
    )

    assert decision.target == "memory"
    assert decision.reason == "stable_user_preference"


def test_promotion_policy_routes_validated_repeated_pattern_to_instinct():
    from maxbot.learning.promotion_policy import PromotionPolicy

    policy = PromotionPolicy()
    pattern = _tool_sequence_pattern()
    validation = _validation_result(pattern)

    decision = policy.decide(
        artifact_type="validated_pattern",
        artifact={"pattern": pattern, "validation": validation},
    )

    assert decision.target == "instinct"
    assert decision.reason == "validated_repeated_pattern"


def test_promotion_policy_rejects_low_signal_artifact():
    from maxbot.learning.promotion_policy import PromotionPolicy

    policy = PromotionPolicy()

    decision = policy.decide(
        artifact_type="validated_pattern",
        artifact={
            "pattern": Pattern(
                id="pattern-low",
                name="Low signal pattern",
                pattern_type="tool_sequence",
                data={"sequence": ["search_files"]},
                occurrence_count=1,
                confidence=0.4,
                extracted_at=datetime.now(),
            ),
            "validation": _validation_result(_tool_sequence_pattern(), overall=0.2),
        },
    )

    assert decision.target == "ignore"
    assert decision.reason == "insufficient_signal"
