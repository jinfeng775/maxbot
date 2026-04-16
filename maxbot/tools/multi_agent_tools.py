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


def set_parent_agent(agent: Agent):
    """设置父 Agent 引用（Gateway 启动时调用）"""
    _parent_agent_ref[0] = agent


def _get_parent() -> Agent:
    agent = _parent_agent_ref[0]
    if agent is None:
        raise RuntimeError("父 Agent 未设置，请先调用 set_parent_agent()")
    return agent


@registry.tool(
    name="spawn_agent",
    description="派生一个子 Agent 执行特定任务。子 Agent 有独立上下文，执行完后返回结果。",
)
def spawn_agent(
    task: str,
    description: str = "",
    max_iterations: int = 20,
) -> str:
    parent = _get_parent()

    task_id = str(uuid.uuid4())[:8]

    try:
        child_config = AgentConfig(
            model=parent.config.model,
            base_url=parent.config.base_url,
            api_key=parent.config.api_key,
            max_iterations=max_iterations,
            system_prompt=f"{parent.config.system_prompt}\n\n[子任务指令]\n{description or task[:50]}",
        )
        child_agent = Agent(config=child_config, registry=parent.registry)
        result = child_agent.chat(task)

        return json.dumps({
            "success": True,
            "task_id": task_id,
            "description": description or task[:50],
            "result": result,
            "iterations": len(child_agent.messages),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "task_id": task_id,
            "error": str(e),
        }, ensure_ascii=False)


@registry.tool(
    name="spawn_agents_parallel",
    description="同时派生多个子 Agent 并行执行任务。每个子 Agent 独立工作，最后汇总结果。",
)
def spawn_agents_parallel(tasks_json: str) -> str:
    """
    tasks_json: JSON 数组，格式:
    [{"task": "...", "description": "...", "max_iterations": 20}, ...]
    """
    parent = _get_parent()

    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "tasks_json 必须是有效的 JSON 数组"}, ensure_ascii=False)

    results = {}
    threads = []
    lock = threading.Lock()

    def _run_subtask(task_def: dict):
        task_id = str(uuid.uuid4())[:8]
        try:
            child_config = AgentConfig(
                model=parent.config.model,
                base_url=parent.config.base_url,
                api_key=parent.config.api_key,
                max_iterations=task_def.get("max_iterations", 20),
                system_prompt=f"{parent.config.system_prompt}\n\n[子任务] {task_def.get('description', '')}",
            )
            child_agent = Agent(config=child_config, registry=parent.registry)
            result = child_agent.chat(task_def.get("task", ""))
            with lock:
                results[task_id] = {
                    "success": True,
                    "description": task_def.get("description", task_def.get("task", "")[:50]),
                    "result": result,
                }
        except Exception as e:
            with lock:
                results[task_id] = {
                    "success": False,
                    "description": task_def.get("description", ""),
                    "error": str(e),
                }

    for t in tasks[:5]:  # 最多 5 个并行
        th = threading.Thread(target=_run_subtask, args=(t,), daemon=True)
        th.start()
        threads.append(th)

    for th in threads:
        th.join(timeout=300)

    return json.dumps({
        "total": len(results),
        "results": results,
    }, ensure_ascii=False)
