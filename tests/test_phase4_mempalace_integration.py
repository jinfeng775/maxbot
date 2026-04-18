from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig, Message
from maxbot.config.config_loader import load_config



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



def test_agent_builds_memory_context_with_mempalace_results(monkeypatch, tmp_path):
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

    agent = Agent(config=config)
    agent.messages = [Message(role="user", content="继续项目", metadata={"project_id": "proj-a"})]

    context = agent._build_memory_context()
    assert "MemPalace wakeup" in context
    assert "mempalace result 1" in context
    assert "mempalace result 2" in context



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
    context = agent._build_memory_context()
    assert "MemPalace" not in context
