from maxbot.evals.trace_store import TraceStore


def test_trace_store_latest_returns_most_recent_trace(tmp_path):
    store = TraceStore(tmp_path / "traces")

    first_id = store.write_trace({"task_id": "task-1", "session_id": "session-1"})
    second_id = store.write_trace({"task_id": "task-2", "session_id": "session-1"})

    latest = store.latest()

    assert latest["trace_id"] == second_id
    assert latest["task_id"] == "task-2"
    assert store.read_trace(first_id)["task_id"] == "task-1"
