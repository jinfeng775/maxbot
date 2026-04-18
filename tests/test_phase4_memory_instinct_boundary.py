from maxbot.core.memory import Memory
from maxbot.learning.instinct_store import InstinctStore



def test_memory_facts_do_not_create_instinct_records(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    instincts = InstinctStore(db_path=str(tmp_path / "instincts.db"))

    memory.set("user_language", "zh-CN", scope="user", user_id="u1")
    memory.set("project_stack", "FastAPI", scope="project", project_id="p1")

    stored = instincts.get_all_instincts(enabled_only=False)
    assert stored == []



def test_instinct_patterns_do_not_appear_in_memory_entries(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    instincts = InstinctStore(db_path=str(tmp_path / "instincts.db"))

    instincts.save_instinct(
        pattern_id="tool-seq-1",
        name="Search then patch",
        pattern_type="tool_sequence",
        pattern_data={
            "signature": "tool_sequence:search>read>patch",
            "match_context": {"event_type": "tool_sequence", "tool_sequence": ["search_files", "read_file", "patch"]},
            "action": {"tool_sequence": ["search_files", "read_file", "patch"]},
            "evidence": {"occurrence_count": 3, "success_rate": 1.0},
        },
        validation_score={"overall": 0.93},
    )

    values = [entry.value for entry in memory.list_all()]
    assert values == []
