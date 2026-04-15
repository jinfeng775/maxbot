"""
多 Agent 工具 — 注册到工具系统，让主 Agent 可以派生子 Agent

参考 CC 的 AgentTool 模式
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from maxbot.tools._registry import registry

if TYPE_CHECKING:
    pass


# 这些工具需要在 Agent 运行时动态注入，因为它们需要引用主 Agent 实例
# 这里定义工具 schema，实际 handler 在 agent_loop 中绑定

SUBAGENT_TOOLS = [
    {
        "name": "spawn_agent",
        "description": (
            "派生一个子 Agent 执行特定任务。"
            "子 Agent 拥有独立上下文，执行完后返回结果。"
            "适合：独立的代码分析、文件搜索、数据处理等子任务。"
        ),
        "parameters": {
            "task": {
                "type": "string",
                "description": "给子 Agent 的详细任务描述",
            },
            "description": {
                "type": "string",
                "description": "简短描述（3-5个字）",
            },
            "allowed_tools": {
                "type": "array",
                "description": "限制子 Agent 可用的工具列表，空则不限制",
            },
            "max_iterations": {
                "type": "integer",
                "description": "最大迭代次数（默认 20）",
            },
        },
    },
    {
        "name": "spawn_agents_parallel",
        "description": (
            "同时派生多个子 Agent 并行执行任务。"
            "每个子 Agent 独立工作，最后汇总结果。"
        ),
        "parameters": {
            "tasks": {
                "type": "array",
                "description": '子任务列表，格式: [{"task": "...", "description": "...", "allowed_tools": [...]}]',
            },
        },
    },
    {
        "name": "agent_status",
        "description": "查看所有子 Agent 的执行状态",
        "parameters": {},
    },
]
