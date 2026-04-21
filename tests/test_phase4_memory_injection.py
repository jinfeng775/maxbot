from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig, Message
from maxbot.core.memory import Memory



def _make_agent_with_memory(monkeypatch, tmp_path, *, session_id="s1", project_id=None, user_id=None, auto_save=False):
    config = AgentConfig(
        api_key="test-key",
        auto_save=auto_save,
        session_id=session_id,
        memory_enabled=True,
        system_prompt="你是 MaxBot",
        skills_enabled=False,
    )
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    memory = Memory(path=tmp_path / "memory.db")
    agent = Agent(config=config, memory=memory)
    metadata = {k: v for k, v in {"project_id": project_id, "user_id": user_id}.items() if v}
    agent.messages = [Message(role="user", content="hello", metadata=metadata)]
    if metadata and agent.config.session_store and session_id:
        session = agent.config.session_store.get(session_id)
        if session is None:
            agent.config.session_store.create(session_id, metadata=metadata)
        agent.config.session_store.save_messages(session_id, [msg.to_dict() for msg in agent.messages], metadata=metadata)
    return agent, memory



def test_enhanced_system_prompt_includes_scoped_memory(monkeypatch, tmp_path):
    agent, memory = _make_agent_with_memory(monkeypatch, tmp_path, project_id="p1")
    memory.set("proj_rule", "use FastAPI", scope="project", project_id="p1")
    memory.set("global_rule", "write tests first", scope="global")
    memory.set("other_proj", "use Django", scope="project", project_id="p2")

    prompt = agent._get_enhanced_system_prompt("帮我继续这个项目")

    assert "相关记忆" in prompt
    assert "use FastAPI" in prompt
    assert "use Django" not in prompt



def test_memory_context_filters_scoped_entries(monkeypatch, tmp_path):
    agent, memory = _make_agent_with_memory(monkeypatch, tmp_path, project_id="p1")
    memory.set("proj_a", "A", scope="project", project_id="p1")
    memory.set("proj_b", "B", scope="project", project_id="p2")

    context = agent._build_memory_context()
    assert "A" in context
    assert "B" not in context



def test_memory_export_text_respects_max_chars(tmp_path):
    memory = Memory(path=tmp_path / "memory.db")
    memory.set("a", "x" * 100, scope="global")
    memory.set("b", "y" * 100, scope="global")

    text = memory.export_text(max_chars=120)
    assert len(text) <= 140
    assert "# 持久记忆" in text



def test_auto_extract_memory_stores_remembered_fact(monkeypatch, tmp_path):
    agent, memory = _make_agent_with_memory(monkeypatch, tmp_path, user_id="u1")
    agent.messages = [Message(role="user", content="记住我喜欢 Python", metadata={"user_id": "u1"})]

    agent._auto_extract_memory(user_message=None, response="好的")

    entries = memory.list_all(scope="user", user_id="u1")
    assert len(entries) == 1
    assert "Python" in entries[0].value



def test_auto_extract_memory_ignores_regular_message(monkeypatch, tmp_path):
    agent, memory = _make_agent_with_memory(monkeypatch, tmp_path)
    agent.messages = [Message(role="user", content="今天天气怎么样")]

    agent._auto_extract_memory(user_message=None, response="晴天")

    assert memory.list_all() == []
