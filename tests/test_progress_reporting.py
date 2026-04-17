"""
测试进度汇报功能
"""

import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from maxbot.core.agent_loop import Agent, AgentConfig


def test_progress_reporting():
    """测试进度汇报功能"""
    print("\n" + "=" * 70)
    print("🧪 测试进度汇报功能")
    print("=" * 70)
    
    # 创建配置（设置较短的汇报间隔）
    config = AgentConfig(
        max_iterations=100,
        session_id="test_progress",
    )
    
    # 创建 Agent
    agent = Agent(config=config)
    
    # 设置较短的汇报间隔（5秒）
    agent._progress_report_interval = 5
    
    print(f"✅ Agent 创建成功")
    print(f"✅ 进度汇报间隔: {agent._progress_report_interval} 秒")
    
    # 模拟一些工作
    print("\n📝 模拟工作...")
    
    for i in range(3):
        # 检查是否需要汇报进度
        progress_report = agent._check_and_report_progress()
        
        if progress_report:
            print(f"\n✅ 收到进度汇报:")
            print(f"  {progress_report}")
        else:
            print(f"  {i+1}. 暂无进度汇报")
        
        # 等待 2 秒
        time.sleep(2)
    
    print("\n✅ 测试完成")
    return True


def test_progress_reporting_with_messages():
    """测试带消息的进度汇报"""
    print("\n" + "=" * 70)
    print("🧪 测试带消息的进度汇报")
    print("=" * 70)
    
    # 创建配置
    config = AgentConfig(
        max_iterations=100,
        session_id="test_progress_messages",
    )
    
    # 创建 Agent
    agent = Agent(config=config)
    
    # 设置较短的汇报间隔（3秒）
    agent._progress_report_interval = 3
    
    print(f"✅ Agent 创建成功")
    print(f"✅ 进度汇报间隔: {agent._progress_report_interval} 秒")
    
    # 添加一些消息
    print("\n📝 添加消息...")
    from maxbot.core.message_manager import Message
    agent._message_manager.append(
        Message(
            role="user",
            content="测试消息" * 100
        )
    )
    
    # 检查进度汇报
    progress_report = agent._check_and_report_progress()
    
    if progress_report:
        print(f"\n✅ 收到进度汇报:")
        print(f"  {progress_report}")
    else:
        print(f"  暂无进度汇报（等待间隔...）")
    
    # 等待并再次检查
    print("\n⏳ 等待 4 秒...")
    time.sleep(4)
    
    progress_report = agent._check_and_report_progress()
    
    if progress_report:
        print(f"\n✅ 收到进度汇报:")
        print(f"  {progress_report}")
    else:
        print(f"  ❌ 未收到进度汇报（应该收到了！）")
        return False
    
    print("\n✅ 测试完成")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("🚀 进度汇报功能测试套件")
    print("=" * 70)
    
    tests = [
        ("基本进度汇报", test_progress_reporting),
        ("带消息的进度汇报", test_progress_reporting_with_messages),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            print(f"\n✅ {name}: 通过")
        except Exception as e:
            results.append((name, False))
            print(f"\n❌ {name}: 失败 - {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
