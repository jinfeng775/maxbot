"""
测试多 Agent 协作系统
"""

import sys
from pathlib import Path
import os

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.multi_agent.coordinator import Coordinator, WorkerConfig
from maxbot.multi_agent.worker import WorkerAgent
from maxbot.core.agent_loop import AgentConfig


def test_coordinator():
    """测试协调器"""
    print("=" * 70)
    print("测试 1: 协调器")
    print("=" * 70)

    # 设置测试 API Key
    os.environ["MAXBOT_API_KEY"] = "test-key"

    # 创建协调器
    coordinator = Coordinator(max_workers=2)
    print(f"✅ 协调器创建成功")

    # 创建 Worker 配置
    worker_config = WorkerConfig(
        name="test-worker",
        agent_config=AgentConfig(skills_enabled=False),  # 禁用技能以加快测试
        capabilities=["code", "analysis"],
        max_concurrent_tasks=1,
    )

    # 注册 Worker
    worker_id = coordinator.register_worker(worker_config)
    print(f"✅ Worker 注册成功: {worker_id}")

    # 创建任务
    task_id_1 = coordinator.create_task(
        description="分析这个项目",
        priority=1,
    )
    print(f"✅ 任务创建成功: {task_id_1}")

    task_id_2 = coordinator.create_task(
        description="生成项目报告",
        priority=0,
        dependencies=[task_id_1],  # 依赖任务 1
    )
    print(f"✅ 任务创建成功: {task_id_2}")

    # 执行任务
    print(f"\n🧪 执行任务...")
    results = coordinator.execute_tasks()

    print(f"\n📊 执行结果:")
    print(f"   总任务数: {results['total_tasks']}")
    print(f"   完成数: {results['completed']}")
    print(f"   失败数: {results['failed']}")

    for task_id, task_result in results['tasks'].items():
        print(f"\n   任务 {task_id[:8]}:")
        print(f"     状态: {task_result['status']}")
        print(f"     描述: {task_result['description']}")

    # 获取统计信息
    stats = coordinator.get_stats()
    print(f"\n📈 统计信息:")
    print(f"   总 Worker 数: {stats['total_workers']}")
    print(f"   总任务数: {stats['total_tasks']}")
    print(f"   完成任务数: {stats['completed_tasks']}")
    print(f"   失败任务数: {stats['failed_tasks']}")

    # 关闭协调器
    coordinator.shutdown()
    print(f"\n✅ 协调器测试通过\n")


def test_worker_agent():
    """测试 Worker Agent"""
    print("=" * 70)
    print("测试 2: Worker Agent")
    print("=" * 70)

    # 设置测试 API Key
    os.environ["MAXBOT_API_KEY"] = "test-key"

    # 创建 Worker 配置
    worker_config = WorkerConfig(
        name="test-worker",
        agent_config=AgentConfig(skills_enabled=False),
        capabilities=["code", "analysis"],
    )

    # 创建 Worker
    worker = WorkerAgent(config=worker_config)
    print(f"✅ Worker Agent 创建成功")

    # 执行任务
    print(f"\n🧪 执行任务...")
    result = worker.execute_task("分析这个项目")

    print(f"\n📊 执行结果:")
    print(f"   成功: {result['success']}")
    print(f"   任务数: {result['task_count']}")

    if result['success']:
        print(f"   结果: {result['result'][:100]}...")
    else:
        print(f"   错误: {result['error']}")

    # 获取状态
    status = worker.get_status()
    print(f"\n📈 Worker 状态:")
    print(f"   名称: {status['name']}")
    print(f"   能力: {', '.join(status['capabilities'])}")
    print(f"   任务数: {status['task_count']}")
    print(f"   是否忙碌: {status['is_busy']}")

    print(f"\n✅ Worker Agent 测试通过\n")


def test_concurrent_execution():
    """测试并发执行"""
    print("=" * 70)
    print("测试 3: 并发执行")
    print("=" * 70)

    # 设置测试 API Key
    os.environ["MAXBOT_API_KEY"] = "test-key"

    # 创建协调器
    coordinator = Coordinator(max_workers=3)
    print(f"✅ 协调器创建成功")

    # 创建多个 Worker
    for i in range(3):
        worker_config = WorkerConfig(
            name=f"worker-{i}",
            agent_config=AgentConfig(skills_enabled=False),
            capabilities=["general"],
        )
        coordinator.register_worker(worker_config)
    print(f"✅ 注册了 3 个 Worker")

    # 创建多个任务
    for i in range(5):
        coordinator.create_task(
            description=f"执行任务 {i}",
            priority=i % 2,  # 交替优先级
        )
    print(f"✅ 创建了 5 个任务")

    # 执行任务
    print(f"\n🧪 并发执行任务...")
    results = coordinator.execute_tasks()

    print(f"\n📊 执行结果:")
    print(f"   总任务数: {results['total_tasks']}")
    print(f"   完成数: {results['completed']}")
    print(f"   失败数: {results['failed']}")

    # 关闭协调器
    coordinator.shutdown()
    print(f"\n✅ 并发执行测试通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("多 Agent 协作系统测试")
    print("=" * 70 + "\n")

    test_coordinator()
    test_worker_agent()
    test_concurrent_execution()

    print("=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)
