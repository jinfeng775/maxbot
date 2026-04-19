"""
多 Agent 协作系统 - 协调器

负责协调多个 Worker Agent，分配任务和聚合结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from maxbot.core.agent_loop import AgentConfig
from maxbot.multi_agent.worker import WorkerAgent, WorkerConfig
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
    assigned_worker: str | None = None


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
        self._workers: dict[str, WorkerAgent] = {}
        self._worker_configs: dict[str, WorkerConfig] = {}
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
        worker = WorkerAgent(config=worker_config)

        self._workers[worker_id] = worker
        self._worker_configs[worker_id] = worker_config
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

            worker = self._workers[worker_id]
            execution = worker.execute_task(task.description)

            if execution.get("success"):
                task.result = execution.get("result")
                task.status = "completed"
                logger.info(f"任务完成: {task.id}")
            else:
                task.status = "failed"
                task.error = execution.get("error", "unknown worker error")
                logger.error(f"任务失败: {task.id}, 错误: {task.error}")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"任务失败: {task.id}, 错误: {e}")

    def _check_dependencies(self, task: Task) -> tuple[bool, str | None]:
        """
        检查任务依赖是否满足

        Args:
            task: 任务

        Returns:
            (依赖是否满足, 失败原因)
        """
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task:
                return False, f"依赖任务失败或不存在: {dep_id}"
            if dep_task.status == "failed":
                return False, f"依赖任务失败或不存在: {dep_id}"
            if dep_task.status != "completed":
                return False, None
        return True, None

    def execute_tasks(self) -> dict[str, Any]:
        """
        执行所有任务

        Returns:
            执行结果
        """
        logger.info(f"开始执行 {len(self._task_queue)} 个任务")

        # 按优先级排序
        self._task_queue.sort(key=lambda t: t.priority, reverse=True)

        while True:
            futures = {}
            progress_made = False

            for task in self._task_queue:
                if task.status != "pending":
                    continue

                # 检查依赖
                dependencies_satisfied, dependency_error = self._check_dependencies(task)
                if not dependencies_satisfied:
                    if dependency_error:
                        task.status = "failed"
                        task.error = dependency_error
                        logger.warning(f"{dependency_error}: {task.id}")
                        progress_made = True
                    else:
                        logger.debug(f"任务依赖未满足: {task.id}")
                    continue

                # 分配 Worker
                worker_id = self._assign_worker(task)
                if not worker_id:
                    task.status = "failed"
                    task.error = self._build_no_worker_error(task)
                    logger.warning(f"{task.error}: {task.id}")
                    progress_made = True
                    continue

                task.assigned_worker = worker_id

                # 提交任务
                future = self._executor.submit(self._execute_task, task, worker_id)
                futures[task.id] = future
                progress_made = True

            if not futures:
                if not progress_made:
                    break
                continue

            # 等待当前批次任务完成，再重新扫描依赖任务
            for future in futures.values():
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
                    "worker": task.assigned_worker,
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
        required_capabilities = self._get_required_capabilities(task)

        for worker_id, config in self._worker_configs.items():
            worker_capabilities = set(config.capabilities)
            if all(capability in worker_capabilities for capability in required_capabilities):
                return worker_id

        return None

    def _get_required_capabilities(self, task: Task) -> list[str]:
        """获取任务所需能力列表。"""
        required_capabilities: list[str] = []

        raw_required = task.params.get("required_capabilities", [])
        if isinstance(raw_required, str):
            raw_required = [raw_required]

        for capability in raw_required:
            if capability and capability not in required_capabilities:
                required_capabilities.append(capability)

        if task.agent_type != "worker" and task.agent_type not in required_capabilities:
            required_capabilities.append(task.agent_type)

        return required_capabilities

    def _build_no_worker_error(self, task: Task) -> str:
        """构造没有可用 Worker 时的错误信息。"""
        required_capabilities = self._get_required_capabilities(task)
        if required_capabilities:
            capabilities = ", ".join(required_capabilities)
            return f"没有可用的 Worker 满足任务所需能力: {capabilities}"

        return "没有可用的 Worker 可执行该任务"

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
            "worker_status": {worker_id: worker.get_status() for worker_id, worker in self._workers.items()},
        }

    def shutdown(self):
        """关闭协调器"""
        self._executor.shutdown(wait=True)
        logger.info("协调器已关闭")
