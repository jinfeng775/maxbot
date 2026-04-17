"""
Auto-generated handler for: set_conversation_limit
Source: maxbot/core/agent_loop.py::AgentConfig
"""

# Handler for set_conversation_limit

def handle_set_conversation_limit(args, agent):
    '''
    设置或查询会话轮询次数限制

    Args:
        args: 包含 max_turns 和 reset 的字典
        agent: Agent 实例

    Returns:
        str: 操作结果
    '''
    max_turns = args.get("max_turns")
    reset = args.get("reset", False)

    # 查询当前设置
    if max_turns is None and not reset:
        current = agent.config.max_conversation_turns
        current_count = agent._conversation_turns
        return f"当前设置：最大 {current} 次，已使用 {current_count} 次"

    # 重置计数器
    if reset:
        agent._conversation_turns = 0
        return "✅ 会话轮询计数器已重置"

    # 设置新的限制
    if max_turns:
        old_limit = agent.config.max_conversation_turns
        agent.config.max_conversation_turns = max_turns
        return f"✅ 会话轮询限制已更新：{old_limit} → {max_turns}"

    return "❌ 无效的操作参数"

