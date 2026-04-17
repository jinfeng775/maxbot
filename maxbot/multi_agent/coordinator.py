"""
多 Agent 协作系统 - 协调器

负责协调多个 Worker Agent，分配任务和聚合结果
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.utils.logger import get_logger

# 获取协调器日志器
logger = get_logger("coordinator")


@dataclass
class Task:
    """任务定义"""
    id: str
    description: str
    agent_type: str = "worker"
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str | None = None


@dataclass
class WorkerConfig:
    """Worker 配置"""
    name: str
    agent_config: AgentConfig
    capabilities: list[str] = field(default_factory=list)
    max_concurrent_tasks: int = 1


class Coordinator:
    """
    多 Agent 协调器

    功能：
    - 任务分配
    - 结果聚合
    - 并发执行
    - 依赖管理
    """

    def __init__(self, max_workers: int = 4):
        """
        初始化协调器

        Args:
            max_workers: 最大并发 Worker 数
        """
        self.max_workers = max_workers
        self._workers: dict[str, tuple[Agent, WorkerConfig]] = {}
        self._tasks: dict[str, Task] = {}
        self._task_queue: list[Task] = []
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        logger.info(f"协调器初始化成功，最大 Worker 数: {max_workers}")

    def register_worker(self, worker_config: WorkerConfig) -> str:
        """
        注册 Worker

        Args:
            worker_config: Worker 配置

        Returns:
            Worker ID
        """
        worker_id = worker_config.name

        # 创建 Agent
        agent = Agent(config=worker_config.agent_config)

        self._workers[worker_id] = (agent, worker_config)
        logger.info(f"Worker 注册成功: {worker_id}")

        return worker_id

    def create_task(
        self,
        description: str,
        agent_type: str = "worker",
        priority: int = 0,
        dependencies: list[str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """
        创建任务

        Args:
            description: 任务描述
            agent_type: Agent 类型
            priority: 优先级
            dependencies: 依赖的任务 ID
            params: 任务参数

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())

        task = Task(
            id=task_id,
            description=description,
            agent_type=agent_type,
            priority=priority,
            dependencies=dependencies or [],
            params=params or {},
        )

        self._tasks[task_id] = task
        self._task_queue.append(task)

        logger.debug(f"任务创建成功: {task_id}")

        return task_id

    def _execute_task(self, task: Task, worker_id: str) -> None:
        """
        执行任务

        Args:
            task: 任务
            worker_id: Worker ID
        """
        try:
            task.status = "running"
            logger.info(f"开始执行任务: {task.id}, Worker: {worker_id}")

            agent, worker_config = self._workers[worker_id]

            # 执行任务
            result = agent.run(task.description)

            task.result = result
            task.status = "completed"

            logger.info(f"任务完成: {task.id}")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"任务失败: {task.id}, 错误: {e}")

    def _check_dependencies(self, task: Task) -> bool:
        """
        检查任务依赖是否满足

        Args:
            task: 任务

        Returns:
            是否满足依赖
        """
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != "completed":
                return False
        return True

    def execute_tasks(self) -> dict[str, Any]:
        """
        执行所有任务

        Returns:
            执行结果
        """
        logger.info(f"开始执行 {len(self._task_queue)} 个任务")

        # 按优先级排序
        self._task_queue.sort(key=lambda t: t.priority, reverse=True)

        # 执行任务
        futures = {}
        for task in self._task_queue:
            if task.status != "pending":
                continue

            # 检查依赖
            if not self._check_dependencies(task):
                logger.debug(f"任务依赖未满足: {task.id}")
                continue

            # 分配 Worker
            worker_id = self._assign_worker(task)
            if not worker_id:
                logger.warning(f"没有可用的 Worker: {task.id}")
                continue

            # 提交任务
            future = self._executor.submit(self._execute_task, task, worker_id)
            futures[task.id] = future

        # 等待所有任务完成
        for task_id, future in futures.items():
            future.result()

        # 聚合结果
        results = {
            "total_tasks": len(self._tasks),
            "completed": sum(1 for t in self._tasks.values() if t.status == "completed"),
            "failed": sum(1 for t in self._tasks.values() if t.status == "failed"),
            "tasks": {
                task_id: {
                    "description": task.description,
                    "status": task.status,
                    "result": task.result,
                    "error": task.error,
                }
                for task_id, task in self._tasks.items()
            },
        }

        logger.info(f"任务执行完成: {results['completed']}/{results['total_tasks']}")

        return results

    def _assign_worker(self, task: Task) -> str | None:
        """
        分配 Worker

        Args:
            task: 任务

        Returns:
            Worker ID
        """
        # 简单策略：随机选择一个 Worker
        # TODO: 实现更智能的分配策略
        for worker_id, (agent, config) in self._workers.items():
            return worker_id

        return None

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息
        """
        return {
            "total_workers": len(self._workers),
            "total_tasks": len(self._tasks),
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == "pending"),
            "running_tasks": sum(1 for t in self._tasks.values() if t.status == "running"),
            "completed_tasks": sum(1 for t in self._tasks.values() if t.status == "completed"),
            "failed_tasks": sum(1 for t in self._tasks.values() if t.status == "failed"),
        }

    def shutdown(self):
        """关闭协调器"""
        self._executor.shutdown(wait=True)
        logger.info("协调器已关闭")
