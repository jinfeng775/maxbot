"""
Claude Code 优化功能测试（简化版）
"""

import pytest
import json
from concurrent.futures import ThreadPoolExecutor

from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache
from maxbot.core.smart_retry import SmartRetry, RetryStrategy, ErrorType


def test_tool_dependency_analyzer():
    """测试工具依赖分析器"""
    analyzer = ToolDependencyAnalyzer()
    
    tool_calls = [
        {"function": {"name": "read_file", "arguments": '{"path": "test.py"}'}},
        {"function": {"name": "search_files", "arguments": '{"pattern": "test"}'}},
    ]
    
    dependencies = analyzer.analyze_dependencies(tool_calls)
    assert len(dependencies) == 2


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


def test_tool_cache():
    """测试工具缓存"""
    cache = ToolCache(result_cache_ttl=60)
    
    # 第一次调用（缓存未命中）
    result1 = cache.get_cached_result("test_tool", {"arg": "value"})
    assert result1 is None
    
    # 缓存结果
    cache.cache_result("test_tool", {"arg": "value"}, "result")
    
    # 第二次调用（缓存命中）
    result2 = cache.get_cached_result("test_tool", {"arg": "value"})
    assert result2 == "result"


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


def test_cache_stats():
    """测试缓存统计"""
    cache = ToolCache(result_cache_ttl=60)
    
    # 缓存一些结果
    cache.cache_result("tool1", {"arg": "value1"}, "result1")
    cache.cache_result("tool2", {"arg": "value2"}, "result2")
    
    # 获取缓存
    cache.get_cached_result("tool1", {"arg": "value1"})
    cache.get_cached_result("tool1", {"arg": "value1"})
    cache.get_cached_result("tool2", {"arg": "value2"})
    cache.get_cached_result("tool3", {"arg": "value3"})
    
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
    assert stats["tool2"]["total_time"] == 0.3
    assert stats["tool2"]["avg_time"] == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
