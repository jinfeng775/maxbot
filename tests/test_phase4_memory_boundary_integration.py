from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.sessions import SessionStore



def test_session_store_preserves_project_and_user_metadata(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.db")
    session = store.create("s1", title="demo")

    session.metadata["project_id"] = "proj-1"
    session.metadata["user_id"] = "user-1"

    store.save_messages("s1", [{"role": "user", "content": "hi"}], metadata=session.metadata)
    loaded = store.get("s1")

    assert loaded.metadata["project_id"] == "proj-1"
    assert loaded.metadata["user_id"] == "user-1"



def test_memory_tool_forwards_scope_metadata_fields(monkeypatch):
    store = MagicMock()
    store.memory = MagicMock()

    config = AgentConfig(api_key="test-key", auto_save=False, session_store=store)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    agent = Agent(config=config)

    agent._call_memory_tool({
        "action": "set",
        "key": "project_stack",
        "value": "FastAPI",
        "category": "memory",
        "scope": "project",
        "source": "agent",
        "tags": ["backend"],
        "importance": 0.8,
        "project_id": "p1",
        "user_id": "u1",
        "session_id": "s1",
    })

    store.memory.set.assert_called_once()
    kwargs = store.memory.set.call_args.kwargs
    assert kwargs["scope"] == "project"
    assert kwargs["project_id"] == "p1"
    assert kwargs["user_id"] == "u1"
    assert kwargs["session_id"] == "s1"



def test_agent_save_session_persists_context_metadata(monkeypatch):
    store = MagicMock()
    store.get.return_value = None
    store.memory = MagicMock()

    config = AgentConfig(api_key="test-key", auto_save=True, session_id="s1", session_store=store)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    agent = Agent(config=config)
    agent._conversation_turns = 3

    agent._save_session()

    assert store.save_messages.called
    kwargs = store.save_messages.call_args.kwargs
    assert "metadata" in kwargs
    assert kwargs["metadata"]["conversation_turns"] == 3
