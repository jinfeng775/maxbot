"""Phase 3 测试 — 多 Agent 编排"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.multi_agent import (
    AgentDelegate,
    AgentStatus,
    AgentTask,
    Coordinator,
    SubTask,
    WorkerPool,
)


# ── 测试用模拟 Agent ──────────────────────────────────────

def _make_mock_registry() -> ToolRegistry:
    """创建带简单工具的注册表（不依赖 API）"""
    reg = ToolRegistry()

    @reg.tool(name="echo", description="回显")
    def echo(text: str) -> str:
        return json.dumps({"echo": text})

    @reg.tool(name="add", description="加法")
    def add(a: int, b: int) -> str:
        return json.dumps({"result": a + b})

    return reg


def _make_agent(registry: ToolRegistry | None = None) -> Agent:
    config = AgentConfig(
        model="gpt-4o",
        base_url="http://localhost:99999/v1",  # 无效地址，测试不会真正调用
        api_key="test-key",
    )
    return Agent(config=config, registry=registry or _make_mock_registry())


# ── AgentTask 测试 ────────────────────────────────────────

class TestAgentTask:
    def test_task_creation(self):
        task = AgentTask(
            task_id="test-1",
            description="测试任务",
            prompt="执行这个任务",
        )
        assert task.task_id == "test-1"
        assert task.status == AgentStatus.PENDING
        assert task.result == ""

    def test_task_status_transitions(self):
        task = AgentTask(task_id="t1", description="", prompt="")
        assert task.status == AgentStatus.PENDING
        task.status = AgentStatus.RUNNING
        assert task.status == AgentStatus.RUNNING
        task.status = AgentStatus.COMPLETED
        assert task.status == AgentStatus.COMPLETED


# ── AgentDelegate 测试 ────────────────────────────────────

class TestAgentDelegate:
    def test_delegate_creation(self):
        parent = _make_agent()
        delegate = AgentDelegate(parent)
        assert delegate.parent is parent
        assert delegate.children == []

    def test_delegate_with_allowed_tools(self):
        parent = _make_agent()
        delegate = AgentDelegate(parent, allowed_tools=["echo"])
        child_reg = delegate._build_filtered_registry()
        assert child_reg.get("echo") is not None
        assert child_reg.get("add") is None

    def test_delegate_system_prompt(self):
        parent = _make_agent()
        delegate = AgentDelegate(
            parent,
            system_prompt_suffix="你是一个代码分析专家",
        )
        prompt = delegate._build_system_prompt()
        assert "代码分析专家" in prompt

    def test_filtered_registry(self):
        parent = _make_agent()
        delegate = AgentDelegate(parent, allowed_tools=["echo"])
        filtered = delegate._build_filtered_registry()
        assert len(filtered) == 1
        assert filtered.get("echo") is not None


# ── Coordinator 测试 ──────────────────────────────────────

class TestCoordinator:
    def test_coordinator_creation(self):
        parent = _make_agent()
        coord = Coordinator(parent)
        assert coord.parent is parent
        assert coord.max_parallel == 3

    def test_inject_deps(self):
        parent = _make_agent()
        coord = Coordinator(parent)

        subtask = SubTask(
            name="step2",
            description="第二步",
            prompt="继续处理",
            depends_on=["step1"],
        )

        all_results = {"step1": "第一步的结果"}
        enriched = coord._inject_deps(subtask, all_results)

        assert "第一步的结果" in enriched
        assert "继续处理" in enriched

    def test_no_deps(self):
        parent = _make_agent()
        coord = Coordinator(parent)

        subtask = SubTask(
            name="step1",
            description="第一步",
            prompt="开始处理",
        )

        enriched = coord._inject_deps(subtask, {})
        assert enriched == "开始处理"


# ── WorkerPool 测试 ───────────────────────────────────────

class TestWorkerPool:
    def test_pool_creation(self):
        parent = _make_agent()
        pool = WorkerPool(parent, pool_size=2)
        assert pool.parent is parent
        assert pool.workers == {}
        assert pool.tasks == {}

    def test_summary_empty(self):
        parent = _make_agent()
        pool = WorkerPool(parent)
        assert pool.get_summary() == ""


# ── 工具注册测试 ──────────────────────────────────────────

class TestMultiAgentTools:
    def test_tools_defined(self):
        from maxbot.multi_agent.tools import SUBAGENT_TOOLS
        assert len(SUBAGENT_TOOLS) == 3
        names = [t["name"] for t in SUBAGENT_TOOLS]
        assert "spawn_agent" in names
        assert "spawn_agents_parallel" in names
        assert "agent_status" in names

    def test_spawn_agent_schema(self):
        from maxbot.multi_agent.tools import SUBAGENT_TOOLS
        spawn = next(t for t in SUBAGENT_TOOLS if t["name"] == "spawn_agent")
        assert "task" in spawn["parameters"]
        assert "description" in spawn["parameters"]
        assert "allowed_tools" in spawn["parameters"]


# ── 子任务依赖图测试 ──────────────────────────────────────

class TestDependencyGraph:
    def test_sequential_deps(self):
        """A → B → C 顺序依赖"""
        tasks = [
            SubTask(name="A", description="第一步", prompt="do A"),
            SubTask(name="B", description="第二步", prompt="do B", depends_on=["A"]),
            SubTask(name="C", description="第三步", prompt="do C", depends_on=["B"]),
        ]
        # 验证依赖链
        assert tasks[2].depends_on == ["B"]
        assert tasks[1].depends_on == ["A"]
        assert tasks[0].depends_on == []

    def test_parallel_deps(self):
        """A, B 并行 → C 汇总"""
        tasks = [
            SubTask(name="A", description="并行1", prompt="do A"),
            SubTask(name="B", description="并行2", prompt="do B"),
            SubTask(name="C", description="汇总", prompt="do C", depends_on=["A", "B"]),
        ]
        # A 和 B 无依赖，可以并行
        assert tasks[0].depends_on == []
        assert tasks[1].depends_on == []
        assert set(tasks[2].depends_on) == {"A", "B"}

    def test_diamond_deps(self):
        """
        A → B
        A → C
        B, C → D
        """
        tasks = [
            SubTask(name="A", description="起点", prompt="do A"),
            SubTask(name="B", description="分支1", prompt="do B", depends_on=["A"]),
            SubTask(name="C", description="分支2", prompt="do C", depends_on=["A"]),
            SubTask(name="D", description="汇合", prompt="do D", depends_on=["B", "C"]),
        ]
        assert tasks[0].depends_on == []
        assert tasks[1].depends_on == ["A"]
        assert tasks[2].depends_on == ["A"]
        assert set(tasks[3].depends_on) == {"B", "C"}
