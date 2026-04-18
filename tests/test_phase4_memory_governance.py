from datetime import datetime, timedelta

from maxbot.core.memory import Memory



def test_memory_delete_low_importance_entries(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    memory.set("keep", "high", importance=0.9)
    memory.set("drop", "low", importance=0.1)

    deleted = memory.cleanup_entries(min_importance=0.2)

    assert deleted == 1
    assert memory.get("keep") == "high"
    assert memory.get("drop") is None



def test_memory_cleanup_expired_session_entries(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    memory.set("s1", "session note", scope="session", session_id="abc")
    memory.set("g1", "global note", scope="global")

    memory._conn.execute(
        "UPDATE memory SET updated_at = ? WHERE key = ?",
        ((datetime.now() - timedelta(days=10)).timestamp(), "s1"),
    )
    memory._conn.commit()

    deleted = memory.cleanup_entries(session_ttl_days=1)

    assert deleted == 1
    assert memory.get("s1") is None
    assert memory.get("g1") == "global note"



def test_memory_deduplicates_same_value_within_scope(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    memory.set("a", "same", scope="project", project_id="p1")
    memory.set("b", "same", scope="project", project_id="p1")

    merged = memory.merge_duplicates()

    assert merged == 1
    entries = memory.list_all(scope="project", project_id="p1")
    assert len(entries) == 1



def test_memory_keeps_duplicates_across_different_scope(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    memory.set("a", "same", scope="project", project_id="p1")
    memory.set("b", "same", scope="project", project_id="p2")

    merged = memory.merge_duplicates()

    assert merged == 0
    assert len(memory.list_all(scope="project")) == 2
