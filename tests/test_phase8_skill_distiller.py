from datetime import datetime

from maxbot.learning.pattern_extractor import Pattern
from maxbot.learning.pattern_validator import ValidationResult, ValidationScore


def test_skill_distiller_generates_skill_draft_from_tool_sequence_pattern():
    from maxbot.knowledge.skill_distiller import SkillDistiller

    pattern = Pattern(
        id="pattern-tool-seq-1",
        name="Repeatable analysis workflow",
        pattern_type="tool_sequence",
        data={
            "sequence": ["search_files", "read_file", "patch"],
            "success_rate": 0.96,
            "match_context": {"tool_sequence": ["search_files", "read_file", "patch"]},
            "evidence": {"success_rate": 0.96, "occurrence_count": 6},
        },
        occurrence_count=6,
        confidence=0.95,
        extracted_at=datetime.now(),
        tags=["tool_sequence", "analysis"],
        description="A repeatable analysis workflow",
    )
    validation = ValidationResult(
        pattern_id=pattern.id,
        pattern_name=pattern.name,
        pattern_type=pattern.pattern_type,
        score=ValidationScore(
            reproducibility=0.95,
            value=0.93,
            safety=0.97,
            best_practice=0.92,
            overall=0.94,
            details={"occurrence_count": 6},
        ),
        passed=True,
        validation_time=datetime.now(),
        confidence=0.94,
        approved=True,
        rejected=False,
    )

    distiller = SkillDistiller()
    draft = distiller.distill(pattern=pattern, validation=validation)

    assert draft is not None
    assert draft["name"] == "repeatable-analysis-workflow"
    assert draft["source_pattern_id"] == pattern.id
    assert draft["pattern_type"] == "tool_sequence"
    assert draft["confidence"] == 0.94
    assert draft["steps"] == [
        "使用 search_files 收集相关文件或匹配项",
        "使用 read_file 深入阅读关键内容",
        "使用 patch 应用最小必要改动",
    ]
