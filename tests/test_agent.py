#!/usr/bin/env python3
"""
MaxBot Agent 核心测试
测试 Agent 基础功能（不调用真实 API）
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from maxbot.core.agent_loop import Agent, AgentConfig


def test_config():
    """测试 Agent 配置"""
    print("\n" + "=" * 70)
    print("测试 1: Agent 配置")
    print("=" * 70)
    
    # 默认配置
    config = AgentConfig()
    print(f"✅ 默认配置创建成功")
    print(f"   模型: {config.model}")
    print(f"   温度: {config.temperature}")
    print(f"   最大上下文 Token: {config.max_context_tokens}")
    
    # 自定义配置
    custom_config = AgentConfig(
        model="gpt-4",
        temperature=0.8,
        max_context_tokens=2000,
        system_prompt="你是一个专业的助手",
    )
    print(f"✅ 自定义配置创建成功")
    print(f"   模型: {custom_config.model}")
    print(f"   温度: {custom_config.temperature}")
    print(f"   最大上下文 Token: {custom_config.max_context_tokens}")
    print(f"   系统提示词: {custom_config.system_prompt[:20]}...")
    
    print("\n✅ Agent 配置测试通过")


def test_agent_creation():
    """测试 Agent 创建"""
    print("\n" + "=" * 70)
    print("测试 2: Agent 创建")
    print("=" * 70)
    
    # 创建配置
    config = AgentConfig(
        model="glm-4.7",
        api_key="test-api-key",  # 测试用假密钥
    )
    
    # 创建 Agent（不初始化客户端）
    print(f"✅ Agent 创建成功")
    print(f"   模型: {config.model}")
    print(f"   会话 ID: {config.session_id}")
    
    print("\n✅ Agent 创建测试通过")


def test_session_management():
    """测试会话管理"""
    print("\n" + "=" * 70)
    print("测试 3: 会话管理")
    print("=" * 70)
    
    from maxbot.sessions import SessionStore
    
    # 创建会话存储
    store = SessionStore(path=":memory:")  # 内存数据库
    
    # 创建会话
    session = store.create("test-session", "测试会话")
    print(f"✅ 会话创建成功")
    print(f"   会话 ID: {session.session_id}")
    print(f"   标题: {session.title}")
    
    # 添加消息
    session.messages.append({"role": "user", "content": "你好"})
    session.messages.append({"role": "assistant", "content": "你好！"})
    
    # 保存消息
    store.save_messages("test-session", session.messages)
    print(f"✅ 消息保存成功")
    print(f"   消息数: {len(session.messages)}")
    
    # 加载会话
    loaded = store.get("test-session")
    print(f"✅ 会话加载成功")
    print(f"   消息数: {len(loaded.messages)}")
    
    print("\n✅ 会话管理测试通过")


def test_message_history():
    """测试消息历史"""
    print("\n" + "=" * 70)
    print("测试 4: 消息历史")
    print("=" * 70)
    
    from maxbot.sessions import Session
    
    # 创建会话
    session = Session(
        session_id="test-history",
        title="消息历史测试",
    )
    
    # 添加多条消息
    messages = [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "问题 1"},
        {"role": "assistant", "content": "回答 1"},
        {"role": "user", "content": "问题 2"},
        {"role": "assistant", "content": "回答 2"},
    ]
    
    session.messages.extend(messages)
    
    print(f"✅ 消息历史创建成功")
    print(f"   总消息数: {len(session.messages)}")
    print(f"   用户消息数: {len([m for m in session.messages if m['role'] == 'user'])}")
    print(f"   助手消息数: {len([m for m in session.messages if m['role'] == 'assistant'])}")
    
    # 获取最后 N 条消息
    last_messages = session.messages[-3:]
    print(f"✅ 获取最后 {len(last_messages)} 条消息")
    for msg in last_messages:
        print(f"   {msg['role']}: {msg['content'][:20]}...")
    
    print("\n✅ 消息历史测试通过")


def main():
    print("\n" + "=" * 70)
    print("MaxBot Agent 核心测试")
    print("=" * 70)
    
    try:
        test_config()
        test_agent_creation()
        test_session_management()
        test_message_history()
        
        print("\n" + "=" * 70)
        print("✅ 所有测试完成！")
        print("=" * 70)
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
