import tempfile
from pathlib import Path

from maxbot.learning import LearningConfig, LearningLoop, Pattern, PatternValidator
from maxbot.learning.observer import Observation
from datetime import datetime



def _sample_pattern(pattern_type: str = "tool_sequence") -> Pattern:
    return Pattern(
        id=f"{pattern_type}-001",
        name=f"Sample {pattern_type}",
        pattern_type=pattern_type,
        data={
            "signature": f"{pattern_type}:signature",
            "match_context": {
                "event_type": pattern_type,
                "tool_sequence": ["search_files", "read_file", "patch"],
                "error_signature": "pytest failed",
                "error_type": "tool_error",
                "preference_type": "output_language",
                "preference_value": "zh",
            },
            "action": {
                "type": "suggest_resolution" if pattern_type == "error_solution" else "suggest_tool_sequence",
                "sequence": ["search_files", "read_file", "patch"],
                "resolution_steps": ["search_files", "terminal"],
                "resolution_summary": "检查失败测试并重新运行",
                "preference": {"response_language": "zh"},
            },
            "evidence": {
                "occurrence_count": 3,
                "success_rate": 1.0,
                "success_count": 3,
                "failure_count": 0,
            },
            "sequence": ["search_files", "read_file", "patch"],
            "success_rate": 1.0,
            "error_signature": "pytest failed",
            "solution_steps": ["search_files", "terminal"],
            "success_count": 3,
            "failure_count": 0,
            "preference_type": "output_language",
            "preference_value": "zh",
            "frequency": 3,
        },
        occurrence_count=3,
        confidence=0.9,
        extracted_at=datetime.now(),
        tags=[pattern_type],
        description=f"sample {pattern_type}",
    )



def _make_learning_loop(tmpdir: str, **overrides) -> LearningLoop:
    config = LearningConfig(
        store_path=str(Path(tmpdir) / "observations"),
        instincts_db_path=str(Path(tmpdir) / "instincts.db"),
        learning_loop_async=False,
        min_session_length=1,
        min_occurrence_count=2,
        enable_logging=False,
        auto_approve=True,
        **overrides,
    )
    return LearningLoop(config=config)



def test_validator_returns_standard_decision_fields():
    validator = PatternValidator(validation_threshold=0.6)
    result = validator.validate(_sample_pattern())

    payload = result.to_dict()
    assert {"score", "confidence", "reasons", "approved", "rejected"}.issubset(payload)
    assert payload["approved"] is True
    assert payload["rejected"] is False
    assert payload["score"] >= 0.6
    assert isinstance(payload["reasons"], list)



def test_session_learning_pipeline_validates_before_persist(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        learning_loop = _make_learning_loop(tmpdir)
        pattern = _sample_pattern("tool_sequence")
        order: list[str] = []

        monkeypatch.setattr(learning_loop.extractor, "extract_patterns", lambda *args, **kwargs: [pattern])

        original_validate = learning_loop.validator.validate

        def validate_spy(candidate):
            order.append("validate")
            return original_validate(candidate)

        def persist_spy(*args, **kwargs):
            order.append("persist")
            return learning_loop.store.get_instinct(kwargs["pattern_id"])

        monkeypatch.setattr(learning_loop.validator, "validate", validate_spy)
        monkeypatch.setattr(learning_loop.store, "save_instinct", persist_spy)

        learning_loop.on_user_message("session-1", "请分析代码")
        learning_loop.on_session_end("session-1")

        assert order[:2] == ["validate", "persist"]



def test_error_learning_pipeline_uses_validator_before_persist(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        learning_loop = _make_learning_loop(tmpdir, enable_error_tracking=True)
        pattern = _sample_pattern("error_solution")
        order: list[str] = []

        monkeypatch.setattr(learning_loop.extractor, "extract_error_pattern", lambda *args, **kwargs: pattern)

        original_validate = learning_loop.validator.validate

        def validate_spy(candidate):
            order.append("validate")
            return original_validate(candidate)

        def persist_spy(*args, **kwargs):
            order.append("persist")
            return learning_loop.store.get_instinct(kwargs["pattern_id"])

        monkeypatch.setattr(learning_loop.validator, "validate", validate_spy)
        monkeypatch.setattr(learning_loop.store, "save_instinct", persist_spy)

        learning_loop.on_error(
            error="pytest failed: exit code 1",
            context={
                "tool_name": "terminal",
                "resolution": "检查失败测试并重新运行",
                "occurrence_count": 2,
                "fix_success": True,
            },
        )

        assert order[:2] == ["validate", "persist"]
