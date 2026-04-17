"""
测试 AgentConfig 配置加载
"""

import sys
from pathlib import Path

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.core.agent_loop import AgentConfig
from maxbot.config.config_loader import load_config


def test_default_config():
    """测试默认配置"""
    print("=" * 70)
    print("测试 1: 默认配置")
    print("=" * 70)

    config = AgentConfig()

    print(f"✅ AgentConfig 创建成功")
    print(f"\n配置值:")
    print(f"   模型: {config.model}")
    print(f"   提供商: {config.provider}")
    print(f"   温度: {config.temperature}")
    print(f"   最大迭代次数: {config.max_iterations}")
    print(f"   最大轮询次数: {config.max_conversation_turns}")
    print(f"   记忆启用: {config.memory_enabled}")
    print(f"   自动保存: {config.auto_save}")
    print(f"   最大 Token: {config.max_context_tokens}")
    print(f"   压缩阈值: {config.compress_at_tokens}")

    # 验证默认值
    assert config.model is not None
    assert config.provider is not None
    assert config.temperature is not None
    assert config.max_iterations is not None
    assert config.max_conversation_turns is not None
    assert config.memory_enabled is not None
    assert config.auto_save is not None
    assert config.max_context_tokens is not None
    assert config.compress_at_tokens is not None

    print("\n✅ 所有默认值验证通过\n")


def test_custom_config():
    """测试自定义配置"""
    print("=" * 70)
    print("测试 2: 自定义配置")
    print("=" * 70)

    config = AgentConfig(
        model="custom-model",
        provider="anthropic",
        temperature=0.9,
        max_conversation_turns=100,
    )

    print(f"✅ AgentConfig 创建成功")
    print(f"\n自定义配置值:")
    print(f"   模型: {config.model}")
    print(f"   提供商: {config.provider}")
    print(f"   温度: {config.temperature}")
    print(f"   最大轮询次数: {config.max_conversation_turns}")

    # 验证自定义值
    assert config.model == "custom-model"
    assert config.provider == "anthropic"
    assert config.temperature == 0.9
    assert config.max_conversation_turns == 100

    print("\n✅ 自定义值验证通过\n")


def test_partial_config():
    """测试部分配置"""
    print("=" * 70)
    print("测试 3: 部分配置")
    print("=" * 70)

    config = AgentConfig(
        model="partial-model",
        max_conversation_turns=200,
    )

    print(f"✅ AgentConfig 创建成功")
    print(f"\n配置值:")
    print(f"   模型（自定义）: {config.model}")
    print(f"   最大轮询次数（自定义）: {config.max_conversation_turns}")
    print(f"   提供商（从配置文件）: {config.provider}")
    print(f"   温度（从配置文件）: {config.temperature}")

    # 验证
    assert config.model == "partial-model"
    assert config.max_conversation_turns == 200
    assert config.provider is not None  # 从配置文件加载
    assert config.temperature is not None  # 从配置文件加载

    print("\n✅ 部分配置验证通过\n")


def test_system_prompt():
    """测试系统提示"""
    print("=" * 70)
    print("测试 4: 系统提示")
    print("=" * 70)

    config = AgentConfig()

    print(f"✅ AgentConfig 创建成功")
    print(f"\n系统提示:")
    print(f"   长度: {len(config.system_prompt)} 字符")
    print(f"   前 100 字符: {config.system_prompt[:100]}...")

    # 验证
    assert config.system_prompt is not None
    assert len(config.system_prompt) > 0
    assert "MaxBot" in config.system_prompt

    print("\n✅ 系统提示验证通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AgentConfig 配置测试")
    print("=" * 70 + "\n")

    test_default_config()
    test_custom_config()
    test_partial_config()
    test_system_prompt()

    print("=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)
