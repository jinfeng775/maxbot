"""
Claude Code 优化功能测试（完整版）
"""

import pytest
import json
from concurrent.futures import ThreadPoolExecutor

from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache
from maxbot.core.smart_retry import SmartRetry, RetryStrategy, ErrorType


# ============================================================================
# 测试工具依赖分析器
# ============================================================================

def test_tool_dependency_analyzer():
    """测试工具依赖分析器"""
    analyzer = ToolDependencyAnalyzer()
    
    tool_calls = [
        {"function": {"name": "read_file", "arguments": '{"path": "test.py"}'}},
        {"function": {"name": "search_files", "arguments": '{"pattern": "test"}'}},
    ]
    
    dependencies = analyzer.analyze_dependencies(tool_calls)
    assert len(dependencies) == 2


def test_parallel_groups():
    """测试并行分组"""
    analyzer = ToolDependencyAnalyzer()
    
    tool_calls = [
        {"function": {"name": "read_file", "arguments": '{"path": "a.py"}'}},
        {"function": {"name": "read_file", "arguments": '{"path": "b.py"}'}},
        {"function": {"name": "read_file", "arguments": '{"path": "c.py"}'}},
    ]
    
    dependencies = analyzer.analyze_dependencies(tool_calls)
    parallel_groups = analyzer.get_parallel_groups(dependencies)
    
    # 所有工具应该被分配到某个组
    total_tools = sum(len(g) for g in parallel_groups)
    assert total_tools == 3


# ============================================================================
# 测试智能重试机制
# ============================================================================

def test_smart_retry():
    """测试智能重试"""
    retry = SmartRetry(strategy=RetryStrategy(max_attempts=2))
    
    call_count = 0
    
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("connection refused")
        return "success"
    
    result = retry.execute_with_retry(flaky_function)
    assert result == "success"
    assert call_count == 2


def test_error_classification():
    """测试错误分类"""
    retry = SmartRetry()
    
    # 网络错误
    assert retry.classify_error(ConnectionError("connection refused")) == ErrorType.NETWORK
    
    # 超时错误
    assert retry.classify_error(TimeoutError("timed out")) == ErrorType.TIMEOUT
    
    # 速率限制
    assert retry.classify_error(Exception("429 rate limit")) == ErrorType.RATE_LIMIT
    
    # 服务器错误
    assert retry.classify_error(Exception("500 internal server error")) == ErrorType.SERVER_ERROR
    
    # 客户端错误
    assert retry.classify_error(Exception("400 bad request")) == ErrorType.CLIENT_ERROR
    
    # 未知错误
    assert retry.classify_error(Exception("unknown error")) == ErrorType.UNKNOWN


def test_should_retry():
    """测试重试判断"""
    retry = SmartRetry()
    
    # 可重试的错误
    assert retry.should_retry(ConnectionError("connection refused"), 1)
    assert retry.should_retry(TimeoutError("timed out"), 1)
    assert retry.should_retry(Exception("429 rate limit"), 1)
    assert retry.should_retry(Exception("500 internal server error"), 1)
    
    # 不可重试的错误
    assert not retry.should_retry(Exception("400 bad request"), 1)
    assert not retry.should_retry(Exception("404 not found"), 1)
    
    # 超过最大尝试次数
    assert not retry.should_retry(ConnectionError("connection refused"), 4)


def test_execute_with_retry_success():
    """测试成功执行"""
    retry = SmartRetry()
    
    def success_function():
        return "success"
    
    result = retry.execute_with_retry(success_function)
    assert result == "success"


def test_execute_with_retry_flaky():
    """测试不稳定函数（前几次失败）"""
    retry = SmartRetry(strategy=RetryStrategy(max_attempts=3))
    
    call_count = 0
    
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("connection refused")
        return "success"
    
    result = retry.execute_with_retry(flaky_function)
    assert result == "success"
    assert call_count == 2


def test_execute_with_retry_all_fail():
    """测试所有尝试都失败"""
    retry = SmartRetry(strategy=RetryStrategy(max_attempts=2))
    
    def always_fail():
        raise ConnectionError("connection refused")
    
    with pytest.raises(ConnectionError):
        retry.execute_with_retry(always_fail)


# ============================================================================
# 测试增强工具缓存
# ============================================================================

def test_tool_list_cache():
    """测试工具列表缓存"""
    cache = ToolCache(cache_ttl=300)
    
    call_count = 0
    
    def get_tools():
        nonlocal call_count
        call_count += 1
        return [{"name": "tool1"}, {"name": "tool2"}]
    
    # 第一次调用
    tools1 = cache.get_tools(get_tools)
    assert call_count == 1
    assert len(tools1) == 2
    
    # 第二次调用（缓存命中）
    tools2 = cache.get_tools(get_tools)
    assert call_count == 1
    assert len(tools2) == 2
    
    # 强制刷新
    tools3 = cache.get_tools(get_tools, force_refresh=True)
    assert call_count == 2


def test_result_cache():
    """测试工具结果缓存"""
    cache = ToolCache(result_cache_ttl=60)
    
    # 第一次调用（缓存未命中）
    result1 = cache.get_cached_result("read_file", {"path": "test.py"})
    assert result1 is None
    
    # 缓存结果
    cache.cache_result("read_file", {"path": "test.py"}, "file content")
    
    # 第二次调用（缓存命中）
    result2 = cache.get_cached_result("read_file", {"path": "test.py"})
    assert result2 == "file content"
    
    # 不同参数（缓存未命中）
    result3 = cache.get_cached_result("read_file", {"path": "other.py"})
    assert result3 is None


def test_cache_key_generation():
    """测试缓存键生成"""
    cache = ToolCache()
    
    # 相同参数生成相同的键
    key1 = cache._make_cache_key("test_tool", {"arg1": "value1", "arg2": "value2"})
    key2 = cache._make_cache_key("test_tool", {"arg2": "value2", "arg1": "value1"})
    assert key1 == key2
    
    # 不同参数生成不同的键
    key3 = cache._make_cache_key("test_tool", {"arg1": "other"})
    assert key1 != key3


def test_cache_stats():
    """测试缓存统计"""
    cache = ToolCache(result_cache_ttl=60)
    
    # 缓存一些结果
    cache.cache_result("tool1", {"arg": "value1"}, "result1")
    cache.cache_result("tool2", {"arg": "value2"}, "result2")
    
    # 获取缓存
    cache.get_cached_result("tool1", {"arg": "value1"})  # 命中
    cache.get_cached_result("tool1", {"arg": "value1"})  # 命中
    cache.get_cached_result("tool2", {"arg": "value2"})  # 命中
    cache.get_cached_result("tool3", {"arg": "value3"})  # 未命中
    
    stats = cache.get_cache_stats()
    assert stats["result_cache_size"] == 2
    assert stats["result_cache_hits"] == 3
    assert stats["result_cache_misses"] == 1
    assert stats["result_cache_hit_rate"] == 0.75


def test_usage_stats():
    """测试使用统计"""
    cache = ToolCache()
    
    # 记录使用
    cache.record_usage("tool1", 0.1)
    cache.record_usage("tool1", 0.2)
    cache.record_usage("tool2", 0.3)
    
    stats = cache.get_usage_stats()
    
    assert stats["tool1"]["call_count"] == 2
    assert stats["tool1"]["total_time"] == 0.3
    # 不精确比较浮点数
    assert 0.14 < stats["tool1"]["avg_time"] < 0.16
    
    assert stats["tool2"]["call_count"] == 1
    assert stats["tool2"]["total"] == 0.3
    assert stats["tool2"]["avg_time"] == 0.3


def test_cache_invalidation():
    """测试缓存失效"""
    cache = ToolCache(cache_ttl=300)
    
    def get_tools():
        return [{"name": "tool1"}]
    
    # 缓存工具列表
    cache.get_tools(get_tools)
    
    # 使缓存失效
    cache.invalidate()
    
    # 再次调用应该重新获取
    cache.get_tools(get_tools)
    
    # 使结果缓存失效
    cache.cache_result("tool1", {}, "result")
    cache.invalidate_result_cache()
    
    # 缓存应该被清除
    assert cache.get_cached_result("tool1", {}) is None


def test_max_cache_size():
    """测试最大缓存大小"""
    cache = ToolCache(max_result_cache_size=3)
    
    # 添加 4 个缓存条目
    cache.cache_result("tool1", {}, "result1")
    cache.cache_result("tool2", {}, "result2")
    cache.cache_result("tool3", {}, "result3")
    cache.cache_result("tool4", {}, "result4")
    
    # 缓存大小应该不超过最大值
    stats = cache.get_cache_stats()
    assert stats["result_cache_size"] <= 3


# ============================================================================
# 集成测试
# ============================================================================

def test_parallel_execution_with_dependency_analysis():
    """测试结合依赖分析的并行执行"""
    analyzer = ToolDependencyAnalyzer()
    
    # 模拟工具调用
    tool_calls = [
        {"function": {"name": "read_file", "arguments": '{"path": "a.py"}'}},
        {"function": {"name": "read_file", "arguments": '{"path": "b.py"}'}},
        {"function": {"name": "read_file", "arguments": '{"path": "c.py"}'}},
    ]
    
    dependencies = analyzer.analyze_dependencies(tool_calls)
    parallel_groups = analyzer.get_parallel_groups(dependencies)
    
    # 所有工具应该被分配到某个组
    total_tools = sum(len(g) for g in parallel_groups)
    assert total_tools == 3


def test_cache_with_retry():
    """测试缓存和重试结合"""
    cache = ToolCache(result_cache_ttl=60)
    retry = SmartRetry(strategy=RetryStrategy(max_attempts=2))
    
    call_count = 0
    
    def flaky_tool_call():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("connection refused")
        return "success"
    
    # 第一次调用：失败后重试，成功后缓存
    result1 = retry.execute_with_retry(flaky_tool_call)
    assert result1 == "success"
    cache.cache_result("flaky_tool", {}, result1)
    
    # 第二次调用：从缓存获取
    result2 = cache.get_cached_result("flaky_tool", {})
    assert result2 == "success"
    
    assert call_count == 2  # 只执行了一次（第二次从缓存）


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
