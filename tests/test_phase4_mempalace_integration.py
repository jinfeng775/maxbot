from pathlib import Path
from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig, Message
from maxbot.config.config_loader import SessionConfig, load_config
from maxbot.core.memory import Memory
from maxbot.sessions import SessionStore



def test_agent_config_supports_mempalace_fields():
    config = AgentConfig(mempalace_enabled=True, mempalace_path="/tmp/palace", mempalace_wing="proj-a")

    assert config.mempalace_enabled is True
    assert config.mempalace_path == "/tmp/palace"
    assert config.mempalace_wing == "proj-a"



def test_load_config_supports_mempalace_fields(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
session:
  mempalace_enabled: true
  mempalace_path: /tmp/palace
  mempalace_wing: proj-a
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_file)
    assert config.session.mempalace_enabled is True
    assert config.session.mempalace_path == "/tmp/palace"
    assert config.session.mempalace_wing == "proj-a"



def test_default_config_keeps_mempalace_disabled_by_default():
    default_config_path = Path(__file__).resolve().parent.parent / "maxbot" / "config" / "default_config.yaml"

    config = load_config(default_config_path)

    assert SessionConfig().mempalace_enabled is False
    assert config.session.mempalace_enabled is False



def test_agent_builds_dedicated_mempalace_prompt_section(monkeypatch, tmp_path):
    from maxbot.memory.mempalace_adapter import MemPalaceAdapter

    config = AgentConfig(
        api_key="test-key",
        memory_enabled=True,
        mempalace_enabled=True,
        mempalace_path="/tmp/palace",
        mempalace_wing="proj-a",
        system_prompt="你是 MaxBot",
        skills_enabled=False,
        session_id="s1",
    )
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    monkeypatch.setattr(MemPalaceAdapter, "is_available", lambda self: True)
    monkeypatch.setattr(MemPalaceAdapter, "wake_up", lambda self, wing=None: "MemPalace wakeup")
    monkeypatch.setattr(
        MemPalaceAdapter,
        "search",
        lambda self, query, wing=None, limit=5: [
            {"content": "mempalace result 1"},
            {"content": "mempalace result 2"},
        ],
    )

    memory = Memory(path=tmp_path / "memory.db")
    memory.set("proj_rule", "use FastAPI", scope="project", project_id="proj-a")

    agent = Agent(config=config, memory=memory)
    agent.messages = [Message(role="user", content="继续项目", metadata={"project_id": "proj-a"})]

    prompt = agent._get_enhanced_system_prompt("继续项目")
    assert "相关记忆" in prompt
    assert "use FastAPI" in prompt
    assert "外部记忆宫殿召回" in prompt
    assert "MemPalace wakeup" in prompt
    assert "mempalace result 1" in prompt
    assert "不是当前会话逐字记录" in prompt



def test_build_memory_context_only_contains_internal_memory(monkeypatch, tmp_path):
    from maxbot.memory.mempalace_adapter import MemPalaceAdapter

    config = AgentConfig(
        api_key="test-key",
        memory_enabled=True,
        mempalace_enabled=True,
        mempalace_path="/tmp/palace",
        mempalace_wing="proj-a",
        system_prompt="你是 MaxBot",
        skills_enabled=False,
        session_id="s1",
    )
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    monkeypatch.setattr(MemPalaceAdapter, "is_available", lambda self: True)
    monkeypatch.setattr(MemPalaceAdapter, "wake_up", lambda self, wing=None: "MemPalace wakeup")
    monkeypatch.setattr(
        MemPalaceAdapter,
        "search",
        lambda self, query, wing=None, limit=5: [{"content": "mempalace result 1"}],
    )

    memory = Memory(path=tmp_path / "memory.db")
    memory.set("proj_rule", "use FastAPI", scope="project", project_id="proj-a")

    agent = Agent(config=config, memory=memory)
    agent.messages = [Message(role="user", content="继续项目", metadata={"project_id": "proj-a"})]

    context = agent._build_memory_context()

    assert "use FastAPI" in context
    assert "MemPalace wakeup" not in context
    assert "mempalace result 1" not in context



def test_session_recall_queries_use_session_store_before_mempalace(monkeypatch, tmp_path):
    from maxbot.memory.mempalace_adapter import MemPalaceAdapter

    store = SessionStore(path=tmp_path / "sessions.db")
    store.create("s1", title="端口决策", metadata={"project_id": "proj-a", "user_id": "u1"})
    store.save_messages(
        "s1",
        [
            {"role": "user", "content": "我们决定网关走 8765 端口", "metadata": {"project_id": "proj-a", "user_id": "u1"}},
            {"role": "assistant", "content": "好，端口定为 8765", "metadata": {"project_id": "proj-a", "user_id": "u1"}},
        ],
        metadata={"project_id": "proj-a", "user_id": "u1", "conversation_turns": 2},
    )

    config = AgentConfig(
        api_key="test-key",
        memory_enabled=True,
        mempalace_enabled=True,
        mempalace_path="/tmp/palace",
        mempalace_wing="proj-a",
        system_prompt="你是 MaxBot",
        skills_enabled=False,
        session_id="s1",
        session_store=store,
    )
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    monkeypatch.setattr(MemPalaceAdapter, "is_available", lambda self: True)
    monkeypatch.setattr(MemPalaceAdapter, "wake_up", lambda self, wing=None: "old mempalace wakeup")
    monkeypatch.setattr(
        MemPalaceAdapter,
        "search",
        lambda self, query, wing=None, limit=5: [{"content": "stale mempalace note"}],
    )

    agent = Agent(config=config)
    prompt = agent._get_enhanced_system_prompt("我们上次聊到哪了？")

    assert "相关会话历史" in prompt
    assert "8765" in prompt
    assert "SessionStore" in prompt
    assert "若外部记忆宫殿与会话历史冲突，以 SessionStore 为准" in prompt
    assert "外部记忆宫殿召回" in prompt



def test_agent_skips_mempalace_when_unavailable(monkeypatch):
    from maxbot.memory.mempalace_adapter import MemPalaceAdapter

    config = AgentConfig(
        api_key="test-key",
        memory_enabled=True,
        mempalace_enabled=True,
        mempalace_path="/tmp/palace",
        system_prompt="你是 MaxBot",
        skills_enabled=False,
    )
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    monkeypatch.setattr(MemPalaceAdapter, "is_available", lambda self: False)

    agent = Agent(config=config)
    prompt = agent._get_enhanced_system_prompt("继续")
    assert "外部记忆宫殿召回" not in prompt
