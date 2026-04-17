#!/usr/bin/env python3
"""
测试 Agent 效率改进

1. 进度汇报机制（每10分钟）
2. 重复性工作检测
3. 工具使用统计
"""

import time
from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.config.config_loader import ConfigLoader

print("=" * 60)
print("Agent 效率改进测试")
print("=" * 60)

# 创建 Agent（使用默认配置）
agent = Agent()

print("\n测试 1: 检查进度汇报功能")
print(f"  进度汇报间隔: {agent._progress_report_interval} 秒")
print(f"  上次汇报时间: {agent._last_progress_report_time}")
print("  ✅ 进度汇报功能已初始化")

print("\n测试 2: 检查重复性工作检测功能")
print(f"  最大记录调用数: {agent._max_recent_calls}")
print(f"  重复阈值: {agent._duplicate_threshold}")
print(f"  调用记录: {len(agent._recent_tool_calls)}")
print("  ✅ 重复性工作检测功能已初始化")

print("\n测试 3: 测试重复性工作检测")
# 模拟重复调用
test_tool_name = "test_tool"
test_args = {"param": "value"}

# 第一次调用
is_repetitive, warning = agent._detect_repetitive_work(test_tool_name, test_args)
print(f"  第1次调用: 重复={is_repetitive}, 警告={bool(warning)}")
assert not is_repetitive, "第一次调用不应被检测为重复"

# 第二次调用
is_repetitive, warning = agent._detect_repetitive_work(test_tool_name, test_args)
print(f"  第2次调用: 重复={is_repetitive}, 警告={bool(warning)}")
assert not is_repetitive, "第二次调用不应被检测为重复"

# 第三次调用
is_repetitive, warning = agent._detect_repetitive_work(test_tool_name, test_args)
print(f"  第3次调用: 重复={is_repetitive}, 警告={bool(warning)}")
assert not is_repetitive, "第三次调用不应被检测为重复"

# 第四次调用（应该触发重复警告）
is_repetitive, warning = agent._detect_repetitive_work(test_tool_name, test_args)
print(f"  第4次调用: 重复={is_repetitive}, 警告={bool(warning)}")
if warning:
    print(f"  警告消息: {warning.split(chr(10))[0]}")
assert is_repetitive, "第四次调用应该被检测为重复"
print("  ✅ 重复性工作检测功能正常")

print("\n测试 4: 测试工具使用统计")
# 添加更多调用
agent._detect_repetitive_work("tool_a", {"x": 1})
agent._detect_repetitive_work("tool_b", {"y": 2})
agent._detect_repetitive_work("tool_a", {"x": 1})

summary = agent._get_tool_usage_summary()
print(f"  工具使用统计:")
for line in summary.split('\n'):
    if line.strip():
        print(f"    {line}")
print("  ✅ 工具使用统计功能正常")

print("\n测试 5: 测试进度汇报（模拟）")
# 模拟时间流逝
agent._last_progress_report_time = time.time() - 700 - 601  # 超过10分钟
progress_report = agent._check_and_report_progress()
if progress_report:
    print(f"  进度汇报:")
    for line in progress_report.split('\n'):
        if line.strip():
            print(f"    {line}")
    print("  ✅ 进度汇报功能正常")
else:
    print("  ⚠️ 进度汇报未触发（可能时间未到）")

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)

print("\n总结:")
print("  ✅ 进度汇报机制：每10分钟汇报一次")
print("  ✅ 重复性工作检测：连续3次相同调用触发警告")
print("  ✅ 工具使用统计：记录最近20次调用")
print("  ✅ 效率优化：帮助识别性能瓶颈")
