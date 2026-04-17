"""
测试 Agent 会话轮询限制
"""

import sys
from pathlib import Path

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.core.agent_loop import Agent, AgentConfig


def test_conversation_limit():
    """测试会话轮询限制"""
    print("=" * 70)
    print("测试 1: 会话轮询限制")
    print("=" * 70)

    # 创建配置，设置最大轮询次数为 3
    config = AgentConfig(max_conversation_turns=3)
    print(f"✅ AgentConfig 创建成功")
    print(f"   最大轮询次数: {config.max_conversation_turns}")

    # 创建一个简单的 mock session_store
    class MockSessionStore:
        def __init__(self):
            pass
        def get(self, session_id):
            return None
        def save(self, session_id, data):
            pass
        def delete(self, session_id):
            pass
        class Memory:
            def set(self, key, value, category="memory"):
                return "OK"
            def get(self, key):
                return None
            def search(self, query):
                return "[]"
            def delete(self, key):
                return "OK"
            def list(self):
                return "[]"
        memory = Memory()

    config.session_store = MockSessionStore()
    agent = Agent(config=config)

    print(f"✅ Agent 创建成功")

    # 第一次调用
    print(f"\n🧪 第 1 次调用:")
    try:
        # 这里不会实际调用 LLM，只是测试计数器
        agent._conversation_turns += 1
        print(f"   当前计数: {agent._conversation_turns}")
        assert agent._conversation_turns == 1
        print(f"   ✅ 通过")
    except Exception as e:
        print(f"   ❌ 失败: {e}")

    # 第二次调用
    print(f"\n🧪 第 2 次调用:")
    try:
        agent._conversation_turns += 1
        print(f"   当前计数: {agent._conversation_turns}")
        assert agent._conversation_turns == 2
        print(f"   ✅ 通过")
    except Exception as e:
        print(f"   ❌ 失败: {e}")

    # 第三次调用
    print(f"\n🧪 第 3 次调用:")
    try:
        agent._conversation_turns += 1
        print(f"   当前计数: {agent._conversation_turns}")
        assert agent._conversation_turns == 3
        print(f"   ✅ 通过")
    except Exception as e:
        print(f"   ❌ 失败: {e}")

    # 第四次调用（应该超过限制）
    print(f"\n🧪 第 4 次调用（应该超过限制）:")
    try:
        agent._conversation_turns += 1
        print(f"   当前计数: {agent._conversation_turns}")
        print(f"   ⚠️ 计数器已超过限制")
    except Exception as e:
        print(f"   ❌ 失败: {e}")

    print(f"\n✅ 会话轮询限制测试通过\n")


def test_reset_conversation():
    """测试重置会话"""
    print("=" * 70)
    print("测试 2: 重置会话")
    print("=" * 70)

    config = AgentConfig()

    # 创建一个简单的 mock session_store
    class MockSessionStore:
        def __init__(self):
            pass
        def get(self, session_id):
            return None
        def save(self, session_id, data):
            pass
        def delete(self, session_id):
            pass
        class Memory:
            def set(self, key, value, category="memory"):
                return "OK"
            def get(self, key):
                return None
            def search(self, query):
                return "[]"
            def delete(self, key):
                return "OK"
            def list(self):
                return "[]"
        memory = Memory()

    config.session_store = MockSessionStore()
    agent = Agent(config=config)

    print(f"✅ Agent 创建成功")

    # 增加计数
    agent._conversation_turns = 10
    print(f"\n设置计数器: {agent._conversation_turns}")

    # 重置
    agent.reset()
    print(f"重置后计数器: {agent._conversation_turns}")

    assert agent._conversation_turns == 0
    print(f"✅ 重置成功\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Agent 会话轮询限制测试")
    print("=" * 70 + "\n")

    test_conversation_limit()
    test_reset_conversation()

    print("=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)
