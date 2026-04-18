from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig, Message
from maxbot.sessions import SessionStore



def _make_agent(monkeypatch, store, *, session_id="s1", auto_save=False):
    config = AgentConfig(
        api_key="test-key",
        auto_save=auto_save,
        session_id=session_id,
        memory_enabled=True,
        system_prompt="你是 MaxBot",
        skills_enabled=False,
        session_store=store,
    )
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    return Agent(config=config)



def test_reloaded_agent_injects_context_from_all_memory_scopes(monkeypatch, tmp_path):
    store = SessionStore(path=tmp_path / "sessions.db")
    store.memory.set("session_note", "current ticket: fix auth", scope="session", session_id="s1")
    store.memory.set("project_stack", "FastAPI", scope="project", project_id="p1")
    store.memory.set("user_lang", "zh-CN", scope="user", user_id="u1")
    store.memory.set("global_rule", "write tests first", scope="global")

    agent = _make_agent(monkeypatch, store, session_id="s1", auto_save=True)
    agent.messages = [
        Message(role="user", content="继续这个项目", metadata={"project_id": "p1", "user_id": "u1"})
    ]
    assert agent.save_session() is True

    reloaded = _make_agent(monkeypatch, store, session_id="s1")
    prompt = reloaded._get_enhanced_system_prompt("继续这个项目")

    assert "current ticket: fix auth" in prompt
    assert "FastAPI" in prompt
    assert "zh-CN" in prompt
    assert "write tests first" in prompt



def test_memory_context_deduplicates_values_and_prioritizes_nearer_scopes(monkeypatch, tmp_path):
    store = SessionStore(path=tmp_path / "sessions.db")
    store.memory.set("g_shared", "shared fact", scope="global")
    store.memory.set("p_shared", "shared fact", scope="project", project_id="p1")
    store.memory.set("user_pref", "reply in Chinese", scope="user", user_id="u1")
    store.memory.set("global_style", "keep answers compact", scope="global")
    store.memory.set("session_focus", "focus on bug #42", scope="session", session_id="s1")

    agent = _make_agent(monkeypatch, store, session_id="s1")
    agent.messages = [
        Message(role="user", content="继续排查", metadata={"project_id": "p1", "user_id": "u1"})
    ]

    context = agent._build_memory_context()

    assert context.count("shared fact") == 1
    assert context.index("focus on bug #42") < context.index("shared fact")
    assert context.index("shared fact") < context.index("reply in Chinese")
    assert context.index("reply in Chinese") < context.index("keep answers compact")
