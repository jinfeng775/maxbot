"""
多 Agent 编排系统 — 参考 Claude Code AgentTool + coordinator

架构：
- AgentDelegate: 从主 Agent 派生子 Agent
- Coordinator: 任务拆分 → Worker 派发 → 结果合并
- BackgroundAgent: 后台异步执行
- 每个子 Agent 独立消息历史 + 工具子集
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from maxbot.core.agent_loop import Agent, AgentConfig, Message
from maxbot.core.tool_registry import ToolRegistry
from maxbot.multi_agent.coordinator import Coordinator as RuntimeCoordinator
from maxbot.multi_agent.worker import WorkerConfig as RuntimeWorkerConfig

LegacyCoordinator = None  # populated after legacy Coordinator definition


# ── 状态枚举 ──────────────────────────────────────────────

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Agent 任务 ────────────────────────────────────────────

@dataclass
class AgentTask:
    """子 Agent 任务"""
    task_id: str
    description: str
    prompt: str
    status: AgentStatus = AgentStatus.PENDING
    result: str = ""
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    tokens_used: int = 0
    iterations: int = 0
    worker_name: str = ""


# ── Agent 委派器 ──────────────────────────────────────────

class AgentDelegate:
    """
    从主 Agent 派生子 Agent

    用法：
        delegate = AgentDelegate(parent_agent)
        result = delegate.run("帮我分析这个文件的结构")
    """

    def __init__(
        self,
        parent_agent: Agent,
        allowed_tools: list[str] | None = None,
        system_prompt_suffix: str = "",
    ):
        self.parent = parent_agent
        self.allowed_tools = allowed_tools
        self.system_prompt_suffix = system_prompt_suffix
        self.children: list[AgentTask] = []

    def run(
        self,
        task: str,
        description: str = "",
        max_iterations: int = 30,
    ) -> AgentTask:
        """
        同步执行子 Agent

        返回 AgentTask，包含结果或错误
        """
        task_id = str(uuid.uuid4())[:8]
        agent_task = AgentTask(
            task_id=task_id,
            description=description or task[:50],
            prompt=task,
        )
        self.children.append(agent_task)

        agent_task.status = AgentStatus.RUNNING
        agent_task.start_time = time.time()

        try:
            # 构建子 Agent 配置
            child_config = AgentConfig(
                model=self.parent.config.model,
                base_url=self.parent.config.base_url,
                api_key=self.parent.config.api_key,
                max_iterations=max_iterations,
                system_prompt=self._build_system_prompt(),
            )

            # 构建子 Agent 工具注册表（可能限制工具集）
            if self.allowed_tools:
                child_registry = self._build_filtered_registry()
            else:
                child_registry = self.parent.registry

            child_agent = Agent(config=child_config, registry=child_registry)

            # 继承回调
            child_agent.on_tool_start = self.parent.on_tool_start
            child_agent.on_tool_end = self.parent.on_tool_end

            # 执行
            result = child_agent.run(task)

            agent_task.result = result
            agent_task.status = AgentStatus.COMPLETED
            agent_task.iterations = len(child_agent.messages)

        except Exception as e:
            agent_task.error = str(e)
            agent_task.status = AgentStatus.FAILED

        agent_task.end_time = time.time()
        return agent_task

    def run_background(
        self,
        task: str,
        description: str = "",
        max_iterations: int = 30,
        on_complete: Callable[[AgentTask], None] | None = None,
    ) -> AgentTask:
        """异步后台执行子 Agent"""
        task_id = str(uuid.uuid4())[:8]
        agent_task = AgentTask(
            task_id=task_id,
            description=description or task[:50],
            prompt=task,
        )
        self.children.append(agent_task)

        def _run():
            agent_task.status = AgentStatus.RUNNING
            agent_task.start_time = time.time()

            try:
                child_config = AgentConfig(
                    model=self.parent.config.model,
                    base_url=self.parent.config.base_url,
                    api_key=self.parent.config.api_key,
                    max_iterations=max_iterations,
                    system_prompt=self._build_system_prompt(),
                )

                if self.allowed_tools:
                    child_registry = self._build_filtered_registry()
                else:
                    child_registry = getattr(self.parent, "registry", None) or getattr(self.parent, "_registry", None)

                child_agent = Agent(config=child_config, registry=child_registry)
                result = child_agent.run(task)

                agent_task.result = result
                agent_task.status = AgentStatus.COMPLETED
                agent_task.iterations = len(child_agent.messages)

            except Exception as e:
                agent_task.error = str(e)
                agent_task.status = AgentStatus.FAILED

            agent_task.end_time = time.time()

            if on_complete:
                on_complete(agent_task)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return agent_task

    def get_status(self, task_id: str) -> AgentTask | None:
        for t in self.children:
            if t.task_id == task_id:
                return t
        return None

    def _build_system_prompt(self) -> str:
        base = self.parent.config.system_prompt
        if self.system_prompt_suffix:
            return f"{base}\n\n[子 Agent 指令]\n{self.system_prompt_suffix}"
        return base

    def _build_filtered_registry(self) -> ToolRegistry:
        """构建只包含允许工具的注册表"""
        filtered = ToolRegistry()
        parent_registry = getattr(self.parent, "registry", None) or getattr(self.parent, "_registry", None)
        for name in self.allowed_tools:
            tool = parent_registry.get(name) if parent_registry else None
            if tool:
                filtered.register_def(tool)
        return filtered


# ── Coordinator 协调器 ────────────────────────────────────

@dataclass
class SubTask:
    """协调器分配的子任务"""
    name: str
    description: str
    prompt: str
    depends_on: list[str] = field(default_factory=list)
    allowed_tools: list[str] | None = None
    result: str = ""
    status: AgentStatus = AgentStatus.PENDING


class Coordinator:
    """
    Legacy 协调器模式 — 任务拆分 → 并行派发 → 结果合并

    兼容保留：运行时执行主链请优先使用 `RuntimeCoordinator`
    （即 `maxbot.multi_agent.coordinator.Coordinator`）。

    参考 CC coordinator/coordinatorMode.ts

    用法：
        coord = Coordinator(parent_agent)
        result = coord.orchestrate(
            goal="分析项目并生成报告",
            subtasks=[
                SubTask(name="scan", description="扫描项目结构", prompt="..."),
                SubTask(name="deps", description="分析依赖", prompt="...", depends_on=["scan"]),
            ]
        )
    """

    def __init__(self, parent_agent: Agent, max_parallel: int = 3):
        self.parent = parent_agent
        self.max_parallel = max_parallel
        self.delegate = AgentDelegate(parent_agent)
        self.results: dict[str, AgentTask] = {}

    def orchestrate(
        self,
        goal: str,
        subtasks: list[SubTask],
        final_prompt: str | None = None,
    ) -> str:
        """
        执行协调任务

        1. 按依赖关系排序
        2. 并行执行无依赖的任务
        3. 串行执行有依赖的任务（等待依赖完成）
        4. 汇总所有结果
        """
        # 构建任务图
        completed = set()
        pending = {st.name: st for st in subtasks}

        all_results: dict[str, str] = {}

        while pending:
            # 找出所有依赖已满足的任务
            ready = []
            for name, st in pending.items():
                if all(dep in completed for dep in st.depends_on):
                    ready.append(st)

            if not ready:
                # 循环依赖或无法满足
                remaining = list(pending.keys())
                return f"错误：存在循环依赖或无法满足的依赖: {remaining}"

            # 并行执行 ready 的任务（最多 max_parallel 个）
            batch = ready[:self.max_parallel]
            threads = []
            batch_results: dict[str, AgentTask] = {}

            for st in batch:
                # 注入依赖结果到 prompt
                enriched_prompt = self._inject_deps(st, all_results)

                def _run_task(subtask=st, prompt=enriched_prompt):
                    task_result = self.delegate.run(
                        task=prompt,
                        description=subtask.description,
                    )
                    batch_results[subtask.name] = task_result

                t = threading.Thread(target=_run_task, daemon=True)
                t.start()
                threads.append(t)

            # 等待批次完成
            for t in threads:
                t.join()

            # 收集结果
            for name, task in batch_results.items():
                if task.status == AgentStatus.COMPLETED:
                    all_results[name] = task.result
                    completed.add(name)
                else:
                    all_results[name] = f"[失败] {task.error}"
                    completed.add(name)
                del pending[name]

        # 汇总最终结果
        if final_prompt:
            summary_prompt = f"{final_prompt}\n\n--- 子任务结果 ---\n"
        else:
            summary_prompt = f"请根据以下子任务结果，完成目标: {goal}\n\n--- 子任务结果 ---\n"

        for name, result in all_results.items():
            desc = next((st.description for st in subtasks if st.name == name), name)
            summary_prompt += f"\n## {desc} ({name})\n{result}\n"

        # 最终汇总
        final_task = self.delegate.run(
            task=summary_prompt,
            description="汇总结果",
        )

        return final_task.result

    def orchestrate_auto(
        self,
        goal: str,
        num_subtasks: int = 3,
    ) -> str:
        """
        自动拆分任务（让 LLM 决定怎么拆）

        参考 CC 的 coordinator 模式：LLM 驱动任务拆分
        """
        # 先让主 Agent 拆分任务
        split_prompt = f"""
请将以下目标拆分为 {num_subtasks} 个子任务。每个子任务需要可以独立执行。

目标：{goal}

请返回 JSON 数组格式：
[
  {{
    "name": "子任务名（英文标识）",
    "description": "子任务描述",
    "prompt": "给子 Agent 的详细指令",
    "depends_on": []  // 依赖的其他子任务名，无依赖则空数组
  }}
]

只返回 JSON，不要其他内容。
"""
        split_response = self.parent.run(split_prompt)

        # 解析子任务
        try:
            # 尝试提取 JSON
            json_str = split_response
            if "```" in split_response:
                # 从代码块提取
                parts = split_response.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("["):
                        json_str = part
                        break

            subtask_dicts = json.loads(json_str)
            subtasks = [
                SubTask(
                    name=st["name"],
                    description=st["description"],
                    prompt=st["prompt"],
                    depends_on=st.get("depends_on", []),
                )
                for st in subtask_dicts
            ]
        except (json.JSONDecodeError, KeyError) as e:
            return f"任务拆分失败: {e}\n拆分结果: {split_response[:500]}"

        # 重置父 Agent 的消息（拆分不应该计入对话）
        self.parent.reset()

        return self.orchestrate(goal, subtasks)

    def _inject_deps(self, subtask: SubTask, all_results: dict[str, str]) -> str:
        """将依赖的子任务结果注入 prompt"""
        if not subtask.depends_on:
            return subtask.prompt

        dep_context = "\n--- 依赖结果 ---\n"
        for dep_name in subtask.depends_on:
            if dep_name in all_results:
                dep_context += f"\n[{dep_name}]:\n{all_results[dep_name]}\n"

        return f"{subtask.prompt}\n{dep_context}"


# ── Worker Pool（轻量级）──────────────────────────────────

class WorkerPool:
    """
    Worker 池 — 管理多个并行 Worker Agent

    参考 CC 的 teammate / worker 概念
    """

    def __init__(self, parent_agent: Agent, pool_size: int = 3):
        self.parent = parent_agent
        self.pool_size = pool_size
        self.workers: dict[str, AgentDelegate] = {}
        self.tasks: dict[str, AgentTask] = {}

    def submit(
        self,
        worker_name: str,
        task: str,
        description: str = "",
        allowed_tools: list[str] | None = None,
    ) -> str:
        """提交任务到指定 Worker（后台执行）"""
        if worker_name not in self.workers:
            self.workers[worker_name] = AgentDelegate(
                self.parent,
                allowed_tools=allowed_tools,
                system_prompt_suffix=f"你是 Worker: {worker_name}",
            )

        delegate = self.workers[worker_name]
        agent_task = delegate.run_background(
            task=task,
            description=description or f"{worker_name}: {task[:40]}",
        )
        agent_task.worker_name = worker_name
        self.tasks[agent_task.task_id] = agent_task

        return agent_task.task_id

    def wait(self, task_id: str, timeout: float = 300) -> AgentTask:
        """等待任务完成"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"未知任务: {task_id}")

        start = time.time()
        while task.status in (AgentStatus.PENDING, AgentStatus.RUNNING):
            if time.time() - start > timeout:
                task.status = AgentStatus.FAILED
                task.error = "超时"
                break
            time.sleep(0.5)

        return task

    def wait_all(self, timeout: float = 300) -> dict[str, AgentTask]:
        """等待所有任务完成"""
        for task_id in list(self.tasks.keys()):
            self.wait(task_id, timeout)
        return dict(self.tasks)

    def get_summary(self) -> str:
        """获取所有任务状态摘要"""
        lines = []
        for tid, task in self.tasks.items():
            duration = ""
            if task.start_time and task.end_time:
                duration = f" ({task.end_time - task.start_time:.1f}s)"
            status_icon = {
                AgentStatus.PENDING: "⏳",
                AgentStatus.RUNNING: "🔄",
                AgentStatus.COMPLETED: "✅",
                AgentStatus.FAILED: "❌",
                AgentStatus.CANCELLED: "🚫",
            }.get(task.status, "?")
            lines.append(f"  {status_icon} [{task.worker_name or tid}] {task.description}{duration}")
        return "\n".join(lines)


LegacyCoordinator = Coordinator

__all__ = [
    "AgentDelegate",
    "AgentStatus",
    "AgentTask",
    "Coordinator",
    "LegacyCoordinator",
    "RuntimeCoordinator",
    "RuntimeWorkerConfig",
    "SubTask",
    "WorkerPool",
]
