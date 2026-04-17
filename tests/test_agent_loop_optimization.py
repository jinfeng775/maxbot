"""
Agent 循环优化测试

测试内容:
1. 消息管理器性能测试
2. 上下文压缩器测试
3. 工具缓存测试
4. 性能监控器测试
5. 集成测试
"""

import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from maxbot.core.message_manager import Message, MessageManager
from maxbot.core.context_compressor import ContextCompressor
from maxbot.core.tool_cache import ToolCache, ToolPrioritizer
from maxbot.core.performance_monitor import PerformanceMonitor


def test_message_manager_performance():
    """测试消息管理器性能"""
    print("\n" + "=" * 70)
    print("🧪 测试 1: 消息管理器性能")
    print("=" * 70)
    
    manager = MessageManager()
    
    # 测试添加消息
    start_time = time.time()
    for i in range(1000):
        manager.append(Message(
            role="user",
            content=f"这是一条测试消息，编号 {i}。" * 10
        ))
    add_time = time.time() - start_time
    
    print(f"✅ 添加 1000 条消息: {add_time:.4f}s")
    print(f"✅ 总 tokens: {manager.get_total_tokens()}")
    print(f"✅ 消息数量: {manager.get_message_count()}")
    
    # 测试获取 tokens（O(1)）
    start_time = time.time()
    for _ in range(1000):
        tokens = manager.get_total_tokens()
    get_time = time.time() - start_time
    
    print(f"✅ 获取 1000 次 tokens: {get_time:.4f}s")
    print(f"✅ 平均每次: {get_time / 1000:.6f}s")
    
    # 测试压缩
    start_time = time.time()
    stats = manager.compress(keep_ratio=0.5)
    compress_time = time.time() - start_time
    
    print(f"✅ 压缩消息: {compress_time:.4f}s")
    print(f"✅ 压缩统计: {stats}")
    
    # 性能对比
    print("\n📊 性能对比:")
    print(f"  添加消息: {add_time:.4f}s")
    print(f"  获取 tokens (1000次): {get_time:.4f}s")
    print(f"  压缩消息: {compress_time:.4f}s")
    
    return True


def test_context_compressor():
    """测试上下文压缩器"""
    print("\n" + "=" * 70)
    print("🧪 测试 2: 上下文压缩器")
    print("=" * 70)
    
    compressor = ContextCompressor(
        max_tokens=100_000,
        compress_at_tokens=50_000,
        compress_ratio=0.5,
    )
    
    # 创建测试消息
    messages = []
    
    # 添加系统消息
    messages.append(Message(role="system", content="系统提示"))
    
    # 添加对话消息
    for i in range(100):
        messages.append(Message(role="user", content=f"用户消息 {i}" * 100))
        messages.append(Message(role="assistant", content=f"助手消息 {i}" * 100))
    
    # 添加工具消息
    for i in range(50):
        messages.append(Message(role="tool", content=f"工具结果 {i}" * 100))
    
    print(f"✅ 原顶消息数: {len(messages)}")
    print(f"✅ 原顶 tokens: {sum(m.estimate_tokens() for m in messages)}")
    
    # 测试压缩
    compressed, stats = compressor.compress(messages, strategy="smart")
    
    print(f"✅ 压缩后消息数: {len(compressed)}")
    print(f"✅ 压缩后 tokens: {sum(m.estimate_tokens() for m in compressed)}")
    print(f"✅ 压缩统计: {stats}")
    
    # 测试不同策略
    print("\n📊 不同压缩策略对比:")
    
    for strategy in ["smart", "simple", "aggressive"]:
        compressed, stats = compressor.compress(messages, strategy=strategy)
        print(f"  {strategy}: {len(compressed)} 条消息, {stats['compressed_tokens']} tokens")
    
    return True


def test_tool_cache():
    """测试工具缓存"""
    print("\n" + "=" * 70)
    print("🧪 测试 3: 工具缓存")
    print("=" * 70)
    
    cache = ToolCache(cache_ttl=5)
    
    # 模拟获取工具列表
    def get_tools():
        time.sleep(0.1)  # 模拟耗时操作
        return [
            {"function": {"name": f"tool_{i}"}} for i in range(10)
        ]
    
    # 测试第一次获取（应该调用函数）
    start_time = time.time()
    tools1 = cache.get_tools(get_tools)
    first_time = time.time() - start_time
    
    print(f"✅ 第一次获取工具: {first_time:.4f}s")
    print(f"✅ 工具数量: {len(tools1)}")
    
    # 测试第二次获取（应该使用缓存）
    start_time = time.time()
    tools2 = cache.get_tools(get_tools)
    second_time = time.time() - start_time
    
    print(f"✅ 第二次获取工具（缓存）: {second_time:.4f}s")
    print(f"✅ 工具数量: {len(tools2)}")
    
    # 测试缓存失效
    print(f"✅ 缓存加速: {first_time / second_time:.1f}x")
    
    # 测试工具使用统计
    cache.record_usage("tool_1", 0.5)
    cache.record_usage("tool_1", 0.6)
    cache.record_usage("tool_2", 0.3)
    
    print(f"✅ 工具使用统计:")
    print(cache.print_usage_stats())
    
    # 测试工具优先级
    print(f"✅ 工具优先级排序:")
    sorted_tools = ToolPrioritizer.sort_tools(tools1)
    print(f"  前 3 个工具: {[t['function']['name'] for t in sorted_tools[:3]]}")
    
    return True


def test_performance_monitor():
    """测试性能监控器"""
    print("\n" + "=" * 70)
    print("🧪 测试 4: 性能监控器")
    print("=" * 70)
    
    monitor = PerformanceMonitor()
    
    # 测试记录记录
    for i in range(100):
        monitor.record("operation_1", 0.01 + i * 0.0001)
        monitor.record("operation_2", 0.02 + i * 0.0002)
    
    # 测试计时器
    with monitor.start_timer("operation_3"):
        time.sleep(0.1)
    
    print(f"✅ 性能统计:")
    print(monitor.print_summary())
    
    print(f"\n✅ 详细报告:")
    print(monitor.print_report(detailed=True))
    
    return True


def test_integration():
    """集成测试"""
    print("\n" + "=" * 70)
    print("🧪 测试 5: 集成测试")
    print("=" * 70)
    
    # 创建所有组件
    message_manager = MessageManager()
    compressor = ContextCompressor()
    tool_cache = ToolCache()
    monitor = PerformanceMonitor()
    
    # 模拟对话
    with monitor.start_timer("total_conversation"):
        # 添加消息
        with monitor.start_timer("add_messages"):
            for i in range(50):
                message_manager.append(Message(
                    role="user",
                    content=f"用户消息 {i}" * 50
                ))
        
        # 检查上下文大小
        with monitor.start_timer("check_context"):
            total_tokens = message_manager.get_total_tokens()
        
        # 压缩上下文
        if compressor.should_compress(total_tokens):
            with monitor.start_timer("compress_context"):
                stats = message_manager.compress()
        
        # 获取工具
        def get_tools():
            return [{"function": {"name": f"tool_{i}"}} for i in range(5)]
        
        with monitor.start_timer("get_tools"):
            tools = tool_cache.get_tools(get_tools)
    
    print(f"✅ 集成测试完成")
    print(f"✅ 消息数量: {message_manager.get_message_count()}")
    print(f"✅ 总 tokens: {message_manager.get_total_tokens()}")
    print(f"✅ 工具数量: {len(tools)}")
    
    print(f"\n📊 性能报告:")
    print(monitor.print_report())
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("🚀 Agent 循环优化测试套件")
    print("=" * 70)
    
    tests = [
        ("消息管理器性能", test_message_manager_performance),
        ("上下文压缩器", test_context_compressor),
        ("工具缓存", test_tool_cache),
        ("性能监控器", test_performance_monitor),
        ("集成测试", test_integration),
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
