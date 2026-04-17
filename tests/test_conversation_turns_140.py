#!/usr/bin/env python3
"""
测试会话轮询次数配置（140次）
"""

from maxbot.config.config_loader import SessionConfig, ConfigLoader

print("=" * 60)
print("会话轮询次数配置测试")
print("=" * 60)

# 测试 1: SessionConfig 默认值
print("\n测试 1: SessionConfig 默认值")
session_config = SessionConfig()
print(f"  max_conversation_turns: {session_config.max_conversation_turns}")
assert session_config.max_conversation_turns == 140, "❌ SessionConfig 默认值应该是 140"
print("  ✅ SessionConfig 默认值正确")

# 测试 2: ConfigLoader 加载默认配置
print("\n测试 2: ConfigLoader 加载默认配置")
loader = ConfigLoader()
config = loader.load()
print(f"  session.max_conversation_turns: {config.session.max_conversation_turns}")
assert config.session.max_conversation_turns == 140, "❌ ConfigLoader 加载的默认值应该是 140"
print("  ✅ ConfigLoader 加载默认配置正确")

# 测试 3: 自定义配置
print("\n测试 3: 自定义配置")
custom_config = SessionConfig(max_conversation_turns=200)
print(f"  自定义 max_conversation_turns: {custom_config.max_conversation_turns}")
assert custom_config.max_conversation_turns == 200, "❌ 自定义值应该是 200"
print("  ✅ 自定义配置正确")

# 测试 4: 从字典加载配置
print("\n测试 4: 从字典加载配置")
loader2 = ConfigLoader()
dict_config = loader2.load_from_dict({
    "session": {
        "max_conversation_turns": 300
    }
})
print(f"  从字典加载的 max_conversation_turns: {dict_config.session.max_conversation_turns}")
assert dict_config.session.max_conversation_turns == 300, "❌ 从字典加载的值应该是 300"
print("  ✅ 从字典加载配置正确")

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
print("\n总结:")
print("  - SessionConfig 默认值: 140")
print("  - ConfigLoader 默认配置: 140")
print("  - 支持自定义配置")
print("  - 支持从字典加载配置")
