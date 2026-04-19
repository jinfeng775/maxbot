"""Phase 6 regression tests for runtime multi-agent tools."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import maxbot.tools.multi_agent_tools as multi_agent_tools
from maxbot.core.tool_registry import ToolRegistry
from maxbot.tools._registry import registry as tool_registry


class FakeChildAgent:
    created: list["FakeChildAgent"] = []

    def __init__(self, config=None, registry=None):
        self.config = config
        self.registry = registry
        self.messages: list[dict] = []
        FakeChildAgent.created.append(self)

    def chat(self, task: str) -> str:
        self.messages.append({"role": "assistant", "content": task})
        return f"handled:{task}"


@pytest.fixture(autouse=True)
def reset_multi_agent_tool_state():
    FakeChildAgent.created.clear()
    multi_agent_tools._parent_agent_ref[0] = None
    if hasattr(multi_agent_tools, "_spawned_tasks"):
        multi_agent_tools._spawned_tasks.clear()
    yield
    FakeChildAgent.created.clear()
    multi_agent_tools._parent_agent_ref[0] = None
    if hasattr(multi_agent_tools, "_spawned_tasks"):
        multi_agent_tools._spawned_tasks.clear()


def _make_parent() -> SimpleNamespace:
    registry = ToolRegistry()

    @registry.tool(name="echo", description="echo")
    def echo(text: str) -> str:
        return text

    @registry.tool(name="add", description="add")
    def add(a: int, b: int) -> str:
        return json.dumps({"result": a + b})

    config = SimpleNamespace(
        model="test-model",
        base_url="http://localhost:99999/v1",
        api_key="test-key",
        system_prompt="system prompt",
    )
    return SimpleNamespace(config=config, registry=registry)


class TestRuntimeMultiAgentToolSchemas:
    def test_spawn_agent_runtime_schema_exposes_allowed_tools(self):
        schema = tool_registry.get("spawn_agent").to_schema()["function"]
        assert "allowed_tools" in schema["parameters"]["properties"]

    def test_spawn_agents_parallel_runtime_schema_uses_tasks_array(self):
        schema = tool_registry.get("spawn_agents_parallel").to_schema()["function"]
        props = schema["parameters"]["properties"]
        assert "tasks" in props
        assert "tasks_json" not in props

    def test_agent_status_is_registered_in_runtime_registry(self):
        tool = tool_registry.get("agent_status")
        assert tool is not None


class TestRuntimeMultiAgentToolBehavior:
    def test_spawn_agent_filters_child_registry_by_allowed_tools(self, monkeypatch: pytest.MonkeyPatch):
        multi_agent_tools.set_parent_agent(_make_parent())
        monkeypatch.setattr(multi_agent_tools, "Agent", FakeChildAgent)

        payload = json.loads(
            multi_agent_tools.spawn_agent(
                task="analyze this",
                description="analysis",
                allowed_tools=["echo"],
            )
        )

        child_registry = FakeChildAgent.created[0].registry
        assert payload["success"] is True
        assert child_registry.get("echo") is not None
        assert child_registry.get("add") is None

    def test_spawn_agent_with_empty_allowlist_builds_empty_child_registry(self, monkeypatch: pytest.MonkeyPatch):
        multi_agent_tools.set_parent_agent(_make_parent())
        monkeypatch.setattr(multi_agent_tools, "Agent", FakeChildAgent)

        payload = json.loads(
            multi_agent_tools.spawn_agent(
                task="analyze this",
                description="analysis",
                allowed_tools=[],
            )
        )

        child_registry = FakeChildAgent.created[0].registry
        assert payload["success"] is True
        assert child_registry is not None
        assert len(child_registry) == 0

    def test_spawn_agents_parallel_accepts_tasks_array_and_respects_allowed_tools(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        multi_agent_tools.set_parent_agent(_make_parent())
        monkeypatch.setattr(multi_agent_tools, "Agent", FakeChildAgent)

        payload = json.loads(
            multi_agent_tools.spawn_agents_parallel(
                tasks=[
                    {
                        "task": "run echo",
                        "description": "parallel echo",
                        "allowed_tools": ["echo"],
                    }
                ]
            )
        )

        child_registry = FakeChildAgent.created[0].registry
        assert payload["total"] == 1
        assert child_registry.get("echo") is not None
        assert child_registry.get("add") is None

    def test_agent_status_reports_spawned_tasks(self, monkeypatch: pytest.MonkeyPatch):
        multi_agent_tools.set_parent_agent(_make_parent())
        monkeypatch.setattr(multi_agent_tools, "Agent", FakeChildAgent)

        multi_agent_tools.spawn_agent(task="inspect repo", description="repo scan")
        status = json.loads(multi_agent_tools.agent_status())

        assert status["total"] == 1
        only_task = next(iter(status["tasks"].values()))
        assert only_task["description"] == "repo scan"
        assert only_task["status"] == "completed"
