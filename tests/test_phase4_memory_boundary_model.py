from maxbot.core.memory import Memory
from maxbot.learning.instinct_store import InstinctStore


def test_memory_entry_defaults_support_scope_and_metadata(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set("user_name", "张三", category="user")
    entries = mem.list_all()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.scope == "global"
    assert entry.source == "manual"
    assert entry.tags == []
    assert entry.importance == 0.5
    assert entry.session_id is None
    assert entry.project_id is None
    assert entry.user_id is None



def test_memory_set_accepts_scope_source_tags_importance(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set(
        "project_stack",
        "FastAPI + SQLite",
        category="memory",
        scope="project",
        source="agent",
        tags=["tech-stack", "backend"],
        importance=0.9,
        project_id="p1",
        user_id="u1",
        session_id="s1",
    )

    entry = mem.list_all()[0]
    assert entry.scope == "project"
    assert entry.source == "agent"
    assert entry.tags == ["tech-stack", "backend"]
    assert entry.importance == 0.9
    assert entry.project_id == "p1"
    assert entry.user_id == "u1"
    assert entry.session_id == "s1"



def test_memory_list_all_can_filter_by_scope_and_project(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set("a", "global fact", scope="global")
    mem.set("b", "project fact", scope="project", project_id="p1")
    mem.set("c", "other project fact", scope="project", project_id="p2")

    entries = mem.list_all(scope="project", project_id="p1")
    assert [e.key for e in entries] == ["b"]



def test_memory_search_can_filter_by_scope_and_user(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set("lang1", "zh-CN", scope="user", user_id="u1")
    mem.set("lang2", "en-US", scope="user", user_id="u2")

    entries = mem.search("CN", scope="user", user_id="u1")
    assert [e.key for e in entries] == ["lang1"]



def test_memory_stores_facts_not_strategy_steps(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")
    mem.set("user_language", "zh-CN", scope="user", user_id="u1")
    entry = mem.list_all()[0]
    assert entry.scope == "user"
    assert entry.value == "zh-CN"



def test_instinct_store_remains_separate_from_memory_store(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")
    store = InstinctStore(db_path=str(tmp_path / "instincts.db"))

    mem.set("user_language", "zh-CN", scope="user")
    instincts = store.get_all_instincts(enabled_only=False)
    assert instincts == []
