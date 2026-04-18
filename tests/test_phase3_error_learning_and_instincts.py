import tempfile
from pathlib import Path

from maxbot.learning import LearningConfig, LearningLoop



def _make_learning_loop(tmpdir: str, **overrides) -> LearningLoop:
    config = LearningConfig(
        store_path=str(Path(tmpdir) / "observations"),
        instincts_db_path=str(Path(tmpdir) / "instincts.db"),
        learning_loop_async=False,
        min_session_length=1,
        min_occurrence_count=2,
        enable_logging=False,
        auto_approve=True,
        enable_error_tracking=True,
        auto_apply_threshold=0.75,
        **overrides,
    )
    return LearningLoop(config=config)



def test_error_learning_classifies_error_and_reuses_solution():
    with tempfile.TemporaryDirectory() as tmpdir:
        learning_loop = _make_learning_loop(tmpdir)

        learning_loop.on_error(
            error="ValidationError: schema mismatch on field title",
            context={
                "user_message": "修复 schema 错误",
                "tool_name": "terminal",
                "tool_args": {"command": "pytest -q"},
                "resolution": "更新 schema 定义并重新运行验证",
                "fix_success": True,
                "occurrence_count": 2,
                "error_type": "validation_error",
            },
        )

        instincts = learning_loop.store.get_all_instincts(enabled_only=False)
        assert len(instincts) == 1
        instinct = instincts[0]
        assert instinct.pattern_type == "error_solution"
        assert instinct.pattern_data["error_type"] == "validation_error"
        assert instinct.pattern_data["resolution_summary"] == "更新 schema 定义并重新运行验证"

        matches = learning_loop.applier.find_matching_instincts(
            {
                "recent_error": "ValidationError: schema mismatch on field author",
                "error_type": "validation_error",
                "tool_name": "terminal",
            },
            instincts,
        )
        assert matches
        assert matches[0].suggested_action["type"] == "suggest_resolution"
        assert matches[0].confidence_tier in {"high", "medium"}
        assert matches[0].trigger_mode in {"auto_apply", "suggest"}



def test_low_signal_error_is_rejected_and_not_persisted():
    with tempfile.TemporaryDirectory() as tmpdir:
        learning_loop = _make_learning_loop(tmpdir)

        learning_loop.on_error(
            error="random transient failure",
            context={
                "tool_name": "terminal",
                "tool_args": {"command": "pytest -q"},
            },
        )

        instincts = learning_loop.store.get_all_instincts(enabled_only=False)
        assert instincts == []
