"""Phase 6 legacy/runtime contract tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from maxbot.core.agent_loop import AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.multi_agent import AgentDelegate, AgentStatus, Coordinator as LegacyCoordinator, SubTask, WorkerPool
from maxbot.multi_agent.coordinator import Coordinator as RuntimeCoordinator, WorkerConfig
from maxbot.tools import multi_agent_tools


class FakeChildAgent:
    created: list["FakeChildAgent"] = []

    def __init__(self, config=None, registry=None):
        self.config = config
        self.registry = registry
        self.messages: list[dict] = []
        FakeChildAgent.created.append(self)

    def run(self, task: str) -> str:
        self.messages.append({"role": "assistant", "content": task})
        return f"handled-run:{task}"

    def reset(self):
        return None


@pytest.fixture(autouse=True)
def reset_tool_state():
    FakeChildAgent.created.clear()
    multi_agent_tools._parent_agent_ref[0] = None
    multi_agent_tools._spawned_tasks.clear()
    yield
    FakeChildAgent.created.clear()
    multi_agent_tools._parent_agent_ref[0] = None
    multi_agent_tools._spawned_tasks.clear()


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.tool(name="echo", description="echo")
    def echo(text: str) -> str:
        return text

    return registry


def _make_parent() -> SimpleNamespace:
    return SimpleNamespace(
        config=AgentConfig(
            model="test-model",
            base_url="http://localhost:99999/v1",
            api_key="test-key",
            system_prompt="system prompt",
            skills_enabled=False,
        ),
        registry=_make_registry(),
        on_tool_start=None,
        on_tool_end=None,
        reset=lambda: None,
        run=lambda prompt: '[{"name":"scan","description":"scan repo","prompt":"scan prompt"}]',
    )


def test_legacy_agent_delegate_executes_with_run_path(monkeypatch: pytest.MonkeyPatch):
    parent = _make_parent()
    monkeypatch.setattr("maxbot.multi_agent.Agent", FakeChildAgent)

    delegate = AgentDelegate(parent, allowed_tools=["echo"])
    result = delegate.run("analyze repo", description="analysis")

    assert result.status == AgentStatus.COMPLETED
    assert result.result == "handled-run:analyze repo"
    child = FakeChildAgent.created[0]
    assert child.registry.get("echo") is not None


def test_legacy_coordinator_orchestrate_returns_summary_from_dependency_graph(monkeypatch: pytest.MonkeyPatch):
    parent = _make_parent()
    monkeypatch.setattr("maxbot.multi_agent.Agent", FakeChildAgent)

    coordinator = LegacyCoordinator(parent, max_parallel=2)
    summary = coordinator.orchestrate(
        goal="summarize work",
        subtasks=[
            SubTask(name="scan", description="scan repo", prompt="scan prompt"),
            SubTask(name="report", description="write report", prompt="report prompt", depends_on=["scan"]),
        ],
    )

    assert summary.startswith("handled-run:")
    assert "scan repo" in summary
    assert "write report" in summary


def test_legacy_coordinator_auto_mode_uses_parent_run(monkeypatch: pytest.MonkeyPatch):
    parent = _make_parent()
    monkeypatch.setattr("maxbot.multi_agent.Agent", FakeChildAgent)

    coordinator = LegacyCoordinator(parent, max_parallel=1)
    summary = coordinator.orchestrate_auto(goal="summarize work", num_subtasks=1)

    assert summary.startswith("handled-run:")
    assert "scan repo" in summary


def test_worker_pool_summary_tracks_background_task(monkeypatch: pytest.MonkeyPatch):
    parent = _make_parent()
    monkeypatch.setattr("maxbot.multi_agent.Agent", FakeChildAgent)

    pool = WorkerPool(parent, pool_size=1)
    task_id = pool.submit("worker-a", "do work", description="background run", allowed_tools=["echo"])
    task = pool.wait(task_id, timeout=5)

    assert task.status == AgentStatus.COMPLETED
    summary = pool.get_summary()
    assert "background run" in summary
    assert "worker-a" in summary


def test_runtime_and_tool_layer_share_subagent_result_shape(monkeypatch: pytest.MonkeyPatch):
    multi_agent_tools.set_parent_agent(_make_parent())
    monkeypatch.setattr(multi_agent_tools, "Agent", FakeChildAgent)

    payload = json.loads(
        multi_agent_tools.spawn_agents_parallel(
            tasks=[{"task": "task a", "description": "parallel a", "allowed_tools": ["echo"]}]
        )
    )

    assert payload["total"] == 1
    only_result = next(iter(payload["results"].values()))
    assert only_result["success"] is True
    assert only_result["description"] == "parallel a"
    assert only_result["allowed_tools"] == ["echo"]
    assert only_result["result"] == "handled-run:task a"


def test_runtime_coordinator_and_legacy_exports_can_coexist():
    runtime = RuntimeCoordinator(max_workers=1)
    try:
        worker_id = runtime.register_worker(
            WorkerConfig(
                name="runtime-worker",
                agent_config=AgentConfig(skills_enabled=False),
                capabilities=["general"],
            )
        )
        task_id = runtime.create_task(description="runtime task")
        results = runtime.execute_tasks()
    finally:
        runtime.shutdown()

    assert worker_id == "runtime-worker"
    assert results["tasks"][task_id]["status"] in {"completed", "failed"}
