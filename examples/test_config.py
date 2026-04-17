"""
测试配置文件功能

演示:
1. 从默认配置加载
2. 从自定义配置文件加载
3. 环境变量覆盖
4. AgentConfig 使用配置
"""

from pathlib import Path
import sys
import os

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.config.config_loader import load_config, get_config
from maxbot.core.agent_loop import Agent, AgentConfig

print("=" * 70)
print("测试配置文件功能")
print("=" * 70)

# 测试 1: 从默认配置加载
print("\n📋 测试 1: 从默认配置加载")
print("-" * 70)

config = load_config()
print(f"✅ 配置加载成功")
print(f"\n模型配置:")
print(f"   名称: {config.model.name}")
print(f"   提供商: {config.model.provider}")
print(f"   温度: {config.model.temperature}")
print(f"\n会话配置:")
print(f"   最大轮询次数: {config.session.max_conversation_turns}")
print(f"   记忆启用: {config.session.memory_enabled}")
print(f"   自动保存: {config.session.auto_save}")
print(f"\n迭代配置:")
print(f"   最大迭代次数: {config.iteration.max_iterations}")
print(f"\n上下文配置:")
print(f"   最大 Token: {config.context.max_tokens}")
print(f"   压缩阈值: {config.context.compress_at_tokens}")

# 测试 2: AgentConfig 使用配置
print("\n" + "=" * 70)
print("📋 测试 2: AgentConfig 使用配置")
print("-" * 70)

agent_config = AgentConfig()
print(f"✅ AgentConfig 创建成功（自动从配置文件加载）")
print(f"\nAgentConfig 配置:")
print(f"   模型: {agent_config.model}")
print(f"   提供商: {agent_config.provider}")
print(f"   温度: {agent_config.temperature}")
print(f"   最大迭代次数: {agent_config.max_iterations}")
print(f"   最大轮询次数: {agent_config.max_conversation_turns}")
print(f"   记忆启用: {agent_config.memory_enabled}")
print(f"   最大 Token: {agent_config.max_context_tokens}")

# 测试 3: 自定义配置文件
print("\n" + "=" * 70)
print("📋 测试 3: 自定义配置文件")
print("-" * 70)

# 创建自定义配置文件
custom_config_path = Path("/tmp/test_maxbot_config.yaml")
custom_config_content = """
# 自定义配置
model:
  name: "gpt-4"
  temperature: 0.9

session:
  max_conversation_turns: 100

iteration:
  max_iterations: 100
"""

custom_config_path.write_text(custom_config_content, encoding="utf-8")
print(f"✅ 创建自定义配置文件: {custom_config_path}")

# 从自定义配置加载
custom_config = load_config(config_path=custom_config_path)
print(f"✅ 从自定义配置加载成功")
print(f"\n自定义配置:")
print(f"   模型: {custom_config.model.name}")
print(f"   温度: {custom_config.model.temperature}")
print(f"   最大轮询次数: {custom_config.session.max_conversation_turns}")
print(f"   最大迭代次数: {custom_config.iteration.max_iterations}")

# 测试 4: 环境变量覆盖
print("\n" + "=" * 70)
print("📋 测试 4: 环境变量覆盖")
print("-" * 70)

# 设置环境变量
os.environ["MAXBOT_MODEL"] = "claude-3-opus"
os.environ["MAXBOT_MAX_CONVERSATION_TURNS"] = "200"
os.environ["MAXBOT_TEMPERATURE"] = "0.5"
print(f"✅ 设置环境变量:")
print(f"   MAXBOT_MODEL=claude-3-opus")
print(f"   MAXBOT_MAX_CONVERSATION_TURNS=200")
print(f"   MAXBOT_TEMPERATURE=0.5")

# 重新加载配置（环境变量会覆盖）
env_config = load_config()
print(f"\n✅ 配置加载成功（环境变量已覆盖）")
print(f"\n环境变量覆盖后的配置:")
print(f"   模型: {env_config.model.name}")
print(f"   温度: {env_config.model.temperature}")
print(f"   最大轮询次数: {env_config.session.max_conversation_turns}")

# 清理环境变量
del os.environ["MAXBOT_MODEL"]
del os.environ["MAXBOT_MAX_CONVERSATION_TURNS"]
del os.environ["MAXBOT_TEMPERATURE"]

# 测试 5: AgentConfig 优先级
print("\n" + "=" * 70)
print("📋 测试 5: AgentConfig 优先级")
print("-" * 70)

# 优先级：AgentConfig 参数 > 配置文件 > 默认值
agent_config_custom = AgentConfig(
    model="custom-model",
    max_conversation_turns=300,
)
print(f"✅ 创建自定义 AgentConfig")
print(f"\nAgentConfig 优先级测试:")
print(f"   模型（自定义）: {agent_config_custom.model}")
print(f"   最大轮询次数（自定义）: {agent_config_custom.max_conversation_turns}")
print(f"   温度（从配置文件）: {agent_config_custom.temperature}")
print(f"   记忆启用（从配置文件）: {agent_config_custom.memory_enabled}")

print("\n" + "=" * 70)
print("✅ 所有测试完成！")
print("=" * 70)

# 清理
custom_config_path.unlink()
print(f"\n🧹 清理临时文件")
