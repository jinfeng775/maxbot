from datetime import datetime

from maxbot.learning.pattern_extractor import Pattern
from maxbot.learning.pattern_validator import ValidationResult, ValidationScore


def _pattern(pattern_type: str, name: str, occurrence_count: int = 4, confidence: float = 0.9) -> Pattern:
    return Pattern(
        id=f"pattern-{pattern_type}",
        name=name,
        pattern_type=pattern_type,
        data={
            "sequence": ["search_files", "read_file", "patch"],
            "success_rate": 0.95,
            "match_context": {"tool_sequence": ["search_files", "read_file", "patch"]},
            "evidence": {"success_rate": 0.95, "occurrence_count": occurrence_count},
        },
        occurrence_count=occurrence_count,
        confidence=confidence,
        extracted_at=datetime.now(),
        description="reusable workflow",
        tags=[pattern_type],
    )


def _validation(pattern: Pattern, overall: float = 0.9) -> ValidationResult:
    return ValidationResult(
        pattern_id=pattern.id,
        pattern_name=pattern.name,
        pattern_type=pattern.pattern_type,
        score=ValidationScore(
            reproducibility=overall,
            value=overall,
            safety=overall,
            best_practice=overall,
            overall=overall,
            details={},
        ),
        passed=True,
        validation_time=datetime.now(),
        confidence=overall,
        approved=True,
        rejected=False,
    )


def test_boundary_routes_stable_fact_to_memory():
    from maxbot.learning.promotion_policy import PromotionPolicy

    policy = PromotionPolicy()
    decision = policy.decide(
        artifact_type="user_preference",
        artifact={"key": "timezone", "value": "Asia/Shanghai", "frequency": 3, "stability": 0.9},
    )

    assert decision.target == "memory"


def test_boundary_routes_pattern_to_instinct_before_skill():
    from maxbot.learning.promotion_policy import PromotionPolicy

    policy = PromotionPolicy()
    pattern = _pattern("tool_sequence", "Repeatable analysis workflow")
    validation = _validation(pattern)

    decision = policy.decide(
        artifact_type="validated_pattern",
        artifact={"pattern": pattern, "validation": validation},
    )

    assert decision.target == "instinct"


def test_boundary_routes_structured_workflow_to_skill_draft():
    from maxbot.knowledge.skill_distiller import SkillDistiller

    distiller = SkillDistiller()
    pattern = _pattern("tool_sequence", "Repeatable analysis workflow", occurrence_count=6, confidence=0.95)
    validation = _validation(pattern, overall=0.94)

    draft = distiller.distill(pattern=pattern, validation=validation)

    assert draft is not None
    assert draft["name"] == "repeatable-analysis-workflow"
    assert draft["source_pattern_id"] == pattern.id
    assert "steps" in draft and len(draft["steps"]) >= 3
