"""Phase 3-8 集成测试 — 学习系统接入 Agent 主循环"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.core.hooks import HookEvent, HookContext


class DummyResponse:
    def __init__(self, content="完成", tool_calls=None):
        self.choices = [MagicMock(message=MagicMock(content=content, tool_calls=tool_calls or []))]


def _make_registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.tool(name="echo", description="回显")
    def echo(text: str) -> str:
        return f'{{"echo": "{text}"}}'

    return reg


def _make_agent(tmp_path: Path) -> Agent:
    config = AgentConfig(
        model="gpt-4o",
        base_url="http://localhost:99999/v1",
        api_key="test-key",
        session_id="phase3-session",
        memory_db_path=str(tmp_path / "session.db"),
        auto_save=False,
    )
    return Agent(config=config, registry=_make_registry())


def test_agent_triggers_session_start_and_end_hooks(monkeypatch, tmp_path):
    agent = _make_agent(tmp_path)

    events = []

    def record_hook(context: HookContext):
        events.append(context.event)

    agent._hook_manager.register(HookEvent.SESSION_START, record_hook)
    agent._hook_manager.register(HookEvent.SESSION_END, record_hook)

    monkeypatch.setattr(
        agent._client.chat.completions,
        "create",
        lambda **kwargs: DummyResponse(content="ok")
    )

    result = agent.run("你好")

    assert result == "ok"
    assert HookEvent.SESSION_START in events

    agent.reset()
    assert HookEvent.SESSION_END in events


def test_agent_triggers_error_hook_on_llm_failure(monkeypatch, tmp_path):
    agent = _make_agent(tmp_path)

    captured = []

    def record_error(context: HookContext):
        captured.append(context.metadata.get("error"))

    agent._hook_manager.register(HookEvent.ERROR, record_error)

    def raise_error(**kwargs):
        raise RuntimeError("llm boom")

    monkeypatch.setattr(agent._client.chat.completions, "create", raise_error)

    with pytest.raises(RuntimeError, match="llm boom"):
        agent.run("触发错误")

    assert any("llm boom" in str(err) for err in captured)
