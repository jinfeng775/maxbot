import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from maxbot.learning import LearningConfig, LearningLoop, Pattern
from maxbot.learning.instinct_store import InstinctStore



def _wait_for(predicate, timeout: float = 3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not satisfied before timeout")



def _sample_error_pattern() -> Pattern:
    return Pattern(
        id="error-solution-async",
        name="Async Error Solution",
        pattern_type="error_solution",
        data={
            "signature": "error_solution:pytest failed",
            "match_context": {
                "event_type": "error",
                "error_signature": "pytest failed",
                "error_type": "tool_error",
                "tool_name": "terminal",
            },
            "action": {
                "type": "suggest_resolution",
                "resolution_steps": ["search_files", "terminal"],
                "resolution_summary": "检查失败测试并重新运行",
            },
            "evidence": {
                "occurrence_count": 2,
                "success_count": 2,
                "failure_count": 0,
                "success_rate": 1.0,
            },
            "error_signature": "pytest failed",
            "error_type": "tool_error",
            "solution_steps": ["search_files", "terminal"],
            "success_count": 2,
            "failure_count": 0,
            "tool_name": "terminal",
        },
        occurrence_count=2,
        confidence=0.88,
        extracted_at=datetime.now(),
        tags=["error_solution"],
        description="async error solution",
    )



def _make_async_loop(tmpdir: str, **overrides) -> LearningLoop:
    config = LearningConfig(
        store_path=str(Path(tmpdir) / "observations"),
        instincts_db_path=str(Path(tmpdir) / "instincts.db"),
        learning_loop_async=True,
        min_session_length=1,
        min_occurrence_count=2,
        enable_logging=False,
        auto_approve=True,
        enable_error_tracking=True,
        async_retry_limit=2,
        async_retry_backoff=0.01,
        async_worker_count=2,
        **overrides,
    )
    return LearningLoop(config=config)



def test_async_worker_retries_failed_tasks_and_recovers(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        learning_loop = _make_async_loop(tmpdir)
        attempts = {"count": 0}

        def flaky_extract(error: str, context: dict):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("temporary failure")
            return _sample_error_pattern()

        monkeypatch.setattr(learning_loop.extractor, "extract_error_pattern", flaky_extract)

        learning_loop.on_error(
            error="pytest failed: exit code 1",
            context={
                "tool_name": "terminal",
                "resolution": "检查失败测试并重新运行",
                "occurrence_count": 2,
                "fix_success": True,
            },
        )

        _wait_for(lambda: learning_loop.store.get_statistics()["total_count"] == 1)
        assert attempts["count"] == 2
        learning_loop.shutdown()



def test_async_worker_deduplicates_duplicate_tasks(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        learning_loop = _make_async_loop(tmpdir)
        calls = {"count": 0}

        def counting_extract(error: str, context: dict):
            calls["count"] += 1
            return _sample_error_pattern()

        monkeypatch.setattr(learning_loop.extractor, "extract_error_pattern", counting_extract)

        payload = {
            "tool_name": "terminal",
            "resolution": "检查失败测试并重新运行",
            "occurrence_count": 2,
            "fix_success": True,
        }
        learning_loop.on_error(error="pytest failed: exit code 1", context=payload)
        learning_loop.on_error(error="pytest failed: exit code 1", context=payload)
        learning_loop.on_error(error="pytest failed: exit code 1", context=payload)

        _wait_for(lambda: learning_loop.store.get_statistics()["total_count"] == 1)
        assert calls["count"] == 1
        learning_loop.shutdown()



def test_instinct_store_merges_duplicates_and_invalidates_low_quality_patterns():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = InstinctStore(db_path=str(Path(tmpdir) / "instincts.db"))
        pattern_data = {
            "signature": "tool_sequence:search>read>patch",
            "match_context": {"event_type": "tool_sequence", "tool_sequence": ["search_files", "read_file", "patch"]},
            "action": {"type": "suggest_tool_sequence", "sequence": ["search_files", "read_file", "patch"]},
            "evidence": {"occurrence_count": 3, "success_rate": 1.0},
            "sequence": ["search_files", "read_file", "patch"],
            "success_rate": 1.0,
        }

        first = store.save_instinct(
            pattern_id="tool-seq-1",
            name="Sequence 1",
            pattern_type="tool_sequence",
            pattern_data=pattern_data,
            validation_score={"overall": 0.92},
        )
        second = store.save_instinct(
            pattern_id="tool-seq-2",
            name="Sequence 2",
            pattern_type="tool_sequence",
            pattern_data=pattern_data,
            validation_score={"overall": 0.95},
        )

        instincts = store.get_all_instincts(enabled_only=False)
        assert len(instincts) == 1
        assert second.id == first.id

        for _ in range(3):
            store.record_instinct_usage(first.id, success=False)

        degraded = store.get_instinct(first.id)
        assert degraded.quality_state == "invalidated"
        assert degraded.enabled is False

        stale_date = (datetime.now() - timedelta(days=365)).isoformat()
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE instincts SET created_at = ?, updated_at = ?, last_used_at = ?, invalidated_at = ? WHERE id = ?",
                (stale_date, stale_date, stale_date, stale_date, first.id),
            )
            conn.commit()

        deleted = store.cleanup_old_instincts(days=30, max_count=10)
        assert deleted == 1
        assert store.get_statistics()["total_count"] == 0
