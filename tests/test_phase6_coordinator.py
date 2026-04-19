"""Phase 6 regression tests for coordinator.py."""

from __future__ import annotations

from typing import Any

import pytest

import maxbot.multi_agent.coordinator as coordinator_module
from maxbot.core.agent_loop import AgentConfig
from maxbot.multi_agent.coordinator import Coordinator, WorkerConfig


class FakeAgent:
    """Small fake agent used to keep worker-backed tests deterministic."""

    def __init__(self, config: Any = None, registry: Any = None):
        self.config = config
        self.registry = registry

    def run(self, description: str) -> str:
        return f"processed:{description}"

    def reset(self):
        return None


class FakeWorkerAgent:
    """WorkerAgent stub to verify coordinator executes through worker.py."""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.current_task: str | None = None
        self.task_count = 0

    def execute_task(self, task_description: str) -> dict[str, Any]:
        self.current_task = task_description
        self.task_count += 1
        return {
            "success": True,
            "result": f"worker:{self.config.name}:{task_description}",
            "task_count": self.task_count,
            "worker": self.config.name,
            "current_task": self.current_task,
            "is_busy": False,
        }

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.config.name,
            "capabilities": self.config.capabilities,
            "current_task": self.current_task,
            "task_count": self.task_count,
            "is_busy": False,
        }


@pytest.fixture
def coordinator(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(coordinator_module, "WorkerAgent", FakeWorkerAgent)
    coord = Coordinator(max_workers=2)
    try:
        yield coord
    finally:
        coord.shutdown()


@pytest.fixture(autouse=True)
def stub_worker_agent_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("maxbot.multi_agent.worker.Agent", FakeAgent)


def _register_worker(coord: Coordinator, name: str, capabilities: list[str]) -> str:
    return coord.register_worker(
        WorkerConfig(
            name=name,
            agent_config=AgentConfig(skills_enabled=False),
            capabilities=capabilities,
        )
    )


def test_coordinator_and_worker_share_same_worker_config_class():
    from maxbot.multi_agent.worker import WorkerConfig as WorkerModuleConfig

    assert WorkerConfig is WorkerModuleConfig


@pytest.mark.parametrize(
    ("agent_type", "params", "expected_worker"),
    [
        ("analysis", None, "analysis-worker"),
        ("worker", {"required_capabilities": ["analysis"]}, "analysis-worker"),
    ],
)
def test_routes_tasks_to_workers_with_matching_capabilities(
    coordinator: Coordinator,
    agent_type: str,
    params: dict[str, Any] | None,
    expected_worker: str,
):
    _register_worker(coordinator, "code-worker", ["code"])
    _register_worker(coordinator, "analysis-worker", ["analysis"])

    task_id = coordinator.create_task(
        description="Analyze the project",
        agent_type=agent_type,
        params=params,
    )

    results = coordinator.execute_tasks()

    assert results["tasks"][task_id]["status"] == "completed"
    assert results["tasks"][task_id]["worker"] == expected_worker


def test_execute_tasks_rescans_pending_tasks_after_dependencies_complete(
    coordinator: Coordinator,
):
    _register_worker(coordinator, "general-worker", ["general"])

    first_task_id = coordinator.create_task(
        description="Prepare the source material",
        priority=0,
    )
    dependent_task_id = coordinator.create_task(
        description="Write the final report",
        priority=1,
        dependencies=[first_task_id],
    )

    results = coordinator.execute_tasks()

    assert results["completed"] == 2
    assert results["failed"] == 0
    assert results["tasks"][first_task_id]["status"] == "completed"
    assert results["tasks"][dependent_task_id]["status"] == "completed"


def test_marks_dependent_tasks_failed_when_prerequisite_fails(coordinator: Coordinator):
    dependent_task_id = coordinator.create_task(
        description="Downstream task",
        dependencies=["missing-task-id"],
    )

    results = coordinator.execute_tasks()
    task_result = results["tasks"][dependent_task_id]

    assert task_result["status"] == "failed"
    assert "依赖任务失败或不存在" in task_result["error"]


def test_aggregated_results_include_assigned_worker(coordinator: Coordinator):
    _register_worker(coordinator, "general-worker", ["general"])

    task_id = coordinator.create_task(description="Handle a general task")

    results = coordinator.execute_tasks()
    task_result = results["tasks"][task_id]

    assert "worker" in task_result
    assert task_result["worker"] == "general-worker"


def test_fails_task_when_no_worker_matches_required_capabilities(
    coordinator: Coordinator,
):
    _register_worker(coordinator, "code-worker", ["code"])

    task_id = coordinator.create_task(
        description="Review the system design",
        params={"required_capabilities": ["analysis"]},
    )

    results = coordinator.execute_tasks()
    task_result = results["tasks"][task_id]

    assert results["completed"] == 0
    assert results["failed"] == 1
    assert task_result["status"] == "failed"
    assert task_result["worker"] is None
    assert "analysis" in task_result["error"]


def test_coordinator_executes_tasks_through_worker_agent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(coordinator_module, "WorkerAgent", FakeWorkerAgent)
    coord = Coordinator(max_workers=1)
    try:
        _register_worker(coord, "worker-a", ["general"])
        task_id = coord.create_task(description="Execute via worker agent")

        results = coord.execute_tasks()
        task_result = results["tasks"][task_id]

        assert task_result["status"] == "completed"
        assert task_result["worker"] == "worker-a"
        assert task_result["result"] == "worker:worker-a:Execute via worker agent"
    finally:
        coord.shutdown()
