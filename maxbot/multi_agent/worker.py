"""
多 Agent 协作系统 - Worker Agent

Worker Agent 是执行具体任务的 Agent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.utils.logger import get_logger

# 获取 Worker 日志器
logger = get_logger("worker")


@dataclass
class WorkerConfig:
    """Worker 配置"""
    name: str
    agent_config: AgentConfig
    capabilities: list[str] = field(default_factory=list)
    max_concurrent_tasks: int = 1


class WorkerAgent:
    """
    Worker Agent

    功能：
    - 执行具体任务
    - 报告进度
    - 处理错误
    """

    def __init__(self, config: WorkerConfig):
        """
        初始化 Worker

        Args:
            config: Worker 配置
        """
        self.config = config
        self.agent = Agent(config=config.agent_config)
        self.current_task: str | None = None
        self.task_count = 0

        logger.info(f"Worker Agent 初始化成功: {config.name}")

    def execute_task(self, task_description: str) -> dict[str, Any]:
        """
        执行任务

        Args:
            task_description: 任务描述

        Returns:
            执行结果
        """
        self.current_task = task_description
        self.task_count += 1

        logger.info(f"开始执行任务 #{self.task_count}: {task_description}")

        try:
            # 执行任务
            result = self.agent.run(task_description)

            logger.info(f"任务执行成功: {task_description}")

            return {
                "success": True,
                "result": result,
                "task_count": self.task_count,
            }

        except Exception as e:
            logger.error(f"任务执行失败: {task_description}, 错误: {e}")

            return {
                "success": False,
                "error": str(e),
                "task_count": self.task_count,
            }

    def get_status(self) -> dict[str, Any]:
        """
        获取 Worker 状态

        Returns:
            状态信息
        """
        return {
            "name": self.config.name,
            "capabilities": self.config.capabilities,
            "current_task": self.current_task,
            "task_count": self.task_count,
            "is_busy": self.current_task is not None,
        }

    def reset(self):
        """重置 Worker"""
        self.current_task = None
        self.task_count = 0
        self.agent.reset()

        logger.info(f"Worker 重置: {self.config.name}")
