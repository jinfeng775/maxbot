from maxbot.memory.mempalace_adapter import MemPalaceAdapter



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
