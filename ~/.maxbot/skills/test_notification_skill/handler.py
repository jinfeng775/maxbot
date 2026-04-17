"""
Auto-generated handler for: test_notification_skill
Source: examples/test_notification.py::test_function
"""


def handle_test_notification_skill(args, agent):
    '''
    测试技能生成通知

    Args:
        args: 包含 message 的字典
        agent: Agent 实例

    Returns:
        str: 测试结果
    '''
    message = args.get("message", "Hello!")
    return f"✅ 测试成功: {message}"

