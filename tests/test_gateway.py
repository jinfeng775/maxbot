"""
测试网关系统
"""

import sys
from pathlib import Path
import os

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.gateway.server import MaxBotGateway, GatewayConfig, create_gateway
from maxbot.core.agent_loop import AgentConfig


def test_gateway_creation():
    """测试网关创建"""
    print("=" * 70)
    print("测试 1: 网关创建")
    print("=" * 70)

    # 创建网关配置
    config = GatewayConfig(
        host="127.0.0.1",
        port=8888,
        agent_config=AgentConfig(skills_enabled=False),
        coordinator_enabled=False,
    )

    # 创建网关
    gateway = MaxBotGateway(config)
    print(f"✅ 网关创建成功")
    print(f"   监听地址: {config.host}:{config.port}")
    print(f"   协调器启用: {config.coordinator_enabled}")

    print(f"\n✅ 网关创建测试通过\n")


def test_gateway_with_coordinator():
    """测试带协调器的网关"""
    print("=" * 70)
    print("测试 2: 带协调器的网关")
    print("=" * 70)

    # 创建网关配置
    config = GatewayConfig(
        host="127.0.0.1",
        port=8889,
        agent_config=AgentConfig(skills_enabled=False),
        coordinator_enabled=True,
        max_workers=2,
    )

    # 创建网关
    gateway = MaxBotGateway(config)
    print(f"✅ 网关创建成功")
    print(f"   监听地址: {config.host}:{config.port}")
    print(f"  协调器启用: {config.coordinator_enabled}")
    print(f"   最大 Worker 数: {config.max_workers}")

    print(f"\n✅ 带协调器的网关测试通过\n")


def test_create_gateway_function():
    """测试便捷函数"""
    print("=" * 70)
    print("测试 3: 便捷函数")
    print("=" * 70)

    # 使用便捷函数创建网关
    gateway = create_gateway(
        host="127.0.0.1",
        port=8890,
        agent_config=AgentConfig(skills_enabled=False),
        coordinator_enabled=False,
    )

    print(f"✅ 网关创建成功（使用便捷函数）")
    print(f"   配置: {gateway.config.host}:{gateway.config.port}")

    print(f"\n✅ 便捷函数测试通过\n")


def test_gateway_config():
    """测试网关配置"""
    print("=" * 70)
    print("测试 4: 网关配置")
    print("=" * 70)

    # 测试默认配置
    config = GatewayConfig()
    print(f"✅ 默认配置创建成功")
    print(f"   主机: {config.host}")
    print(f"   端口: {config.port}")
    print(f"   协调器启用: {config.coordinator_enabled}")
    print(f"   最大 Worker 数: {config.max_workers}")

    # 测试自定义配置
    config = GatewayConfig(
        host="0.0.0.0",
        port=9000,
        coordinator_enabled=True,
        max_workers=8,
    )
    print(f"\n✅ 自定义配置创建成功")
    print(f"   主机: {config.host}")
    print(f"   端口: {config.port}")
    print(f"   协调器启用: {config.coordinator_enabled}")
    print(f"   最大 Worker 数: {config.max_workers}")

    print(f"\n✅ 网关配置测试通过\n")


def test_api_models():
    """测试 API 模型"""
    print("=" * 70)
    print("测试 5: API 模型")
    print("=" * 70)

    from maxbot.gateway.server import MessageRequest, MessageResponse, TaskRequest, TaskResponse

    # 测试消息请求
    request = MessageRequest(
        message="你好",
        session_id="test-session",
        skills_enabled=True,
    )
    print(f"✅ MessageRequest 创建成功")
    print(f"   消息: {request.message}")
    print(f"   会话 ID: {request.session_id}")
    print(f"   技能启用: {request.skills_enabled}")

    # 测试消息响应
    response = MessageResponse(
        success=True,
        response="你好！",
        session_id="test-session",
    )
    print(f"\n✅ MessageResponse 创建成功")
    print(f"   成功: {response.success}")
    print(f"   响应: {response.response}")
    print(f"   会话 ID: {response.session_id}")

    # 测试任务请求
    task_request = TaskRequest(
        description="分析代码",
        agent_type="worker",
        priority=1,
    )
    print(f"\n✅ TaskRequest 创建成功")
    print(f"   描述: {task_request.description}")
    print(f"   Agent 类型: {task_request.agent_type}")
    print(f"   优先级: {task_request.priority}")

    # 测试任务响应
    task_response = TaskResponse(
        success=True,
        task_id="task-123",
    )
    print(f"\n✅ TaskResponse 创建成功")
    print(f"   成功: {task_response.success}")
    print(f"   任务 ID: {task_response.task_id}")

    print(f"\n✅ API 模型测试通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("网关系统测试")
    print("=" * 70 + "\n")

    test_gateway_creation()
    test_gateway_with_coordinator()
    test_create_gateway_function()
    test_gateway_config()
    test_api_models()

    print("=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)
