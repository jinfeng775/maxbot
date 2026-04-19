"""
多 Agent 工具 — 注册 spawn_agent 等工具到 registry

让主 Agent 可以在对话中派生子 Agent。
"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.tools._registry import registry


# 全局引用，由 Gateway 在启动时注入当前 Agent
_parent_agent_ref: list[Agent | None] = [None]
_spawned_tasks: dict[str, dict[str, Any]] = {}
_spawned_tasks_lock = threading.Lock()
_UNSET = object()


def _execute_agent(agent: Agent, task: str) -> str:
    runner = getattr(agent, "run", None)
    if callable(runner):
        return runner(task)

    chatter = getattr(agent, "chat", None)
    if callable(chatter):
        return chatter(task)

    raise AttributeError("child agent does not expose run() or chat()")


def set_parent_agent(agent: Agent):
    """设置父 Agent 引用（Gateway 启动时调用）"""
    _parent_agent_ref[0] = agent


def _get_parent() -> Agent:
    agent = _parent_agent_ref[0]
    if agent is None:
        raise RuntimeError("父 Agent 未设置，请先调用 set_parent_agent()")
    return agent


def _get_parent_registry(parent: Agent):
    return getattr(parent, "registry", None) or getattr(parent, "_registry", None)


def _build_child_registry(parent: Agent, allowed_tools: list | object = _UNSET):
    parent_registry = _get_parent_registry(parent)
    if allowed_tools is _UNSET or allowed_tools is None or parent_registry is None:
        return parent_registry

    filtered = ToolRegistry()
    for name in allowed_tools:
        tool = parent_registry.get(name)
        if tool:
            filtered.register_def(tool)
    return filtered


def _record_task(
    task_id: str,
    *,
    description: str,
    status: str,
    result: str | None = None,
    error: str | None = None,
    allowed_tools: list | None = None,
    mode: str,
):
    with _spawned_tasks_lock:
        _spawned_tasks[task_id] = {
            "description": description,
            "status": status,
            "result": result,
            "error": error,
            "allowed_tools": allowed_tools or [],
            "mode": mode,
        }


@registry.tool(
    name="spawn_agent",
    description="派生一个子 Agent 执行特定任务。子 Agent 有独立上下文，执行完后返回结果。",
)
def spawn_agent(
    task: str,
    description: str = "",
    allowed_tools: list = None,
    max_iterations: int = 20,
) -> str:
    parent = _get_parent()

    task_id = str(uuid.uuid4())[:8]
    task_desc = description or task[:50]

    try:
        child_config = AgentConfig(
            model=parent.config.model,
            base_url=parent.config.base_url,
            api_key=parent.config.api_key,
            max_iterations=max_iterations,
            system_prompt=f"{parent.config.system_prompt}\n\n[子任务指令]\n{task_desc}",
        )
        child_registry = _build_child_registry(parent, allowed_tools)
        child_agent = Agent(config=child_config, registry=child_registry)
        result = _execute_agent(child_agent, task)

        _record_task(
            task_id,
            description=task_desc,
            status="completed",
            result=result,
            allowed_tools=allowed_tools,
            mode="single",
        )

        return json.dumps({
            "success": True,
            "task_id": task_id,
            "description": task_desc,
            "result": result,
            "iterations": len(child_agent.messages),
            "allowed_tools": allowed_tools or [],
        }, ensure_ascii=False)
    except Exception as e:
        _record_task(
            task_id,
            description=task_desc,
            status="failed",
            error=str(e),
            allowed_tools=allowed_tools,
            mode="single",
        )
        return json.dumps({
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "allowed_tools": allowed_tools or [],
        }, ensure_ascii=False)


@registry.tool(
    name="spawn_agents_parallel",
    description="同时派生多个子 Agent 并行执行任务。每个子 Agent 独立工作，最后汇总结果。",
)
def spawn_agents_parallel(tasks: list) -> str:
    parent = _get_parent()

    if isinstance(tasks, str):
        try:
            tasks = json.loads(tasks)
        except json.JSONDecodeError:
            return json.dumps({"error": "tasks 必须是有效的 JSON 数组"}, ensure_ascii=False)

    if not isinstance(tasks, list):
        return json.dumps({"error": "tasks 必须是数组"}, ensure_ascii=False)

    results = {}
    threads = []
    lock = threading.Lock()

    def _run_subtask(task_def: dict):
        task_id = str(uuid.uuid4())[:8]
        description = task_def.get("description", task_def.get("task", "")[:50])
        allowed_tools = task_def.get("allowed_tools", _UNSET)
        try:
            child_config = AgentConfig(
                model=parent.config.model,
                base_url=parent.config.base_url,
                api_key=parent.config.api_key,
                max_iterations=task_def.get("max_iterations", 20),
                system_prompt=f"{parent.config.system_prompt}\n\n[子任务] {description}",
            )
            child_registry = _build_child_registry(parent, allowed_tools)
            child_agent = Agent(config=child_config, registry=child_registry)
            result = _execute_agent(child_agent, task_def.get("task", ""))
            payload = {
                "success": True,
                "description": description,
                "result": result,
                "allowed_tools": [] if allowed_tools is _UNSET else (allowed_tools or []),
            }
            _record_task(
                task_id,
                description=description,
                status="completed",
                result=result,
                allowed_tools=[] if allowed_tools is _UNSET else allowed_tools,
                mode="parallel",
            )
        except Exception as e:
            payload = {
                "success": False,
                "description": description,
                "error": str(e),
                "allowed_tools": [] if allowed_tools is _UNSET else (allowed_tools or []),
            }
            _record_task(
                task_id,
                description=description,
                status="failed",
                error=str(e),
                allowed_tools=[] if allowed_tools is _UNSET else allowed_tools,
                mode="parallel",
            )

        with lock:
            results[task_id] = payload

    for task_def in tasks[:5]:  # 最多 5 个并行
        th = threading.Thread(target=_run_subtask, args=(task_def,), daemon=True)
        th.start()
        threads.append(th)

    for th in threads:
        th.join(timeout=300)

    return json.dumps({
        "total": len(results),
        "results": results,
    }, ensure_ascii=False)


@registry.tool(
    name="agent_status",
    description="查看所有子 Agent 的执行状态",
)
def agent_status() -> str:
    with _spawned_tasks_lock:
        tasks = dict(_spawned_tasks)

    return json.dumps({
        "total": len(tasks),
        "tasks": tasks,
    }, ensure_ascii=False)
