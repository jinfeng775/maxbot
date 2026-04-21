from pathlib import Path
from unittest.mock import MagicMock

from maxbot.memory.mempalace_adapter import MemPalaceAdapter
from maxbot.core.agent_loop import Agent, AgentConfig, Message



def test_mempalace_adapter_unavailable_without_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    adapter = MemPalaceAdapter()
    assert adapter.is_available() is False



def test_mempalace_adapter_search_parses_cli_output(monkeypatch):
    class Result:
        returncode = 0
        stdout = "result line 1\nresult line 2"
        stderr = ""

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mempalace")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())

    adapter = MemPalaceAdapter(palace_path="/tmp/palace")
    results = adapter.search("auth decision", wing="proj-a", limit=2)

    assert len(results) == 2
    assert results[0]["content"] == "result line 1"
    assert results[1]["content"] == "result line 2"



def test_mempalace_adapter_mine_returns_text(monkeypatch):
    class Result:
        returncode = 0
        stdout = "mined 3 memories"
        stderr = ""

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mempalace")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())

    adapter = MemPalaceAdapter(palace_path="/tmp/palace")
    assert adapter.mine(wing="proj-a", source="notes.md") == "mined 3 memories"



def test_mempalace_adapter_wakeup_returns_text(monkeypatch):
    class Result:
        returncode = 0
        stdout = "wake up context"
        stderr = ""

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mempalace")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())

    adapter = MemPalaceAdapter(palace_path="/tmp/palace")
    assert adapter.wake_up(wing="proj-a") == "wake up context"



def test_mempalace_adapter_returns_empty_search_on_failure(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mempalace")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())

    adapter = MemPalaceAdapter(palace_path="/tmp/palace")
    assert adapter.search("auth") == []



def test_mempalace_adapter_returns_empty_mine_on_failure(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mempalace")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())

    adapter = MemPalaceAdapter(palace_path="/tmp/palace")
    assert adapter.mine(wing="proj-a") == ""



def test_mempalace_adapter_store_session_falls_back_to_cli_mine_when_python_api_missing(monkeypatch, tmp_path):
    recorded = {}

    class Result:
        returncode = 0
        stdout = "mined 1 memories"
        stderr = ""

    def fake_run(command, capture_output, text, timeout):
        recorded["command"] = command
        source_path = command[2]
        recorded["source_path"] = source_path
        export_files = list(Path(source_path).glob("*.jsonl"))
        assert export_files
        recorded["file_content"] = export_files[0].read_text(encoding="utf-8")
        return Result()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mempalace")
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("maxbot.memory.mempalace_adapter._MEMPALACE_AVAILABLE", False)
    monkeypatch.setattr("maxbot.memory.mempalace_adapter.os.path.exists", lambda path: False)

    adapter = MemPalaceAdapter(palace_path=str(tmp_path / "palace"))
    ok = adapter.store_session(
        messages=[
            {"role": "user", "content": "我们决定用 8765 端口"},
            {"role": "assistant", "content": "好的，记下来了"},
        ],
        session_id="sess-1",
        wing="proj-a",
        room="u1",
    )

    assert ok is True
    assert recorded["command"][0] == "mempalace"
    assert recorded["command"][1] == "mine"
    assert "--mode" in recorded["command"]
    assert "convos" in recorded["command"]
    assert "8765" in recorded["file_content"]



def test_agent_save_session_uses_mempalace_cli_fallback(monkeypatch, tmp_path):
    captured = {}

    def fake_store_session(self, messages, session_id, wing="conversations", room="general"):
        captured["messages"] = messages
        captured["session_id"] = session_id
        captured["wing"] = wing
        captured["room"] = room
        return True

    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    monkeypatch.setattr(MemPalaceAdapter, "is_available", lambda self: True)
    monkeypatch.setattr(MemPalaceAdapter, "store_session", fake_store_session)

    config = AgentConfig(
        api_key="test-key",
        memory_enabled=True,
        mempalace_enabled=True,
        mempalace_path=str(tmp_path / "palace"),
        session_id="s1",
        auto_save=True,
        system_prompt="你是 MaxBot",
        skills_enabled=False,
    )
    agent = Agent(config=config)
    agent.messages = [
        Message(role="user", content="继续排查", metadata={"project_id": "proj-a", "user_id": "u1"}),
        Message(role="assistant", content="收到"),
    ]

    assert agent.save_session() is True
    assert captured["session_id"] == "s1"
    assert captured["wing"] == "proj-a"
    assert captured["room"] == "u1"
    assert captured["messages"][0]["content"] == "继续排查"
