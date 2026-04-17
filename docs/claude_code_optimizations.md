# Claude Code 优化实现文档

本文档说明了从 Claude Code 学到的优化功能在 MaxBot 中的实现。

---

## 📋 已实现的优化

### 1. 并行工具执行

**文件**: `maxbot/core/tool_dependency_analyzer.py`

**功能**:
- 分析工具调用之间的依赖关系
- 自动检测可以并行执行的工具
- 生成执行拓扑顺序

**使用示例**:
```python
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer

analyzer = ToolDependencyAnalyzer()

# 分析工具调用依赖
dependencies = analyzer.analyze_dependencies(tool_calls)

# 获取并行执行组
parallel_groups = analyzer.get_parallel_groups(dependencies)
# [[0, 2], [1, 3], [4]]  # 第1组：工具0和2可并行，第2组：工具1和3可并行

# 按组执行
for group in parallel_groups:
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(
            lambda i: execute_tool(tool_calls[i]),
            group
        ))
```

**原理**:
1. 提取每个工具的输入/输出键
2. 分析工具间的数据流依赖
3. 生成拓扑排序的执行组
4. 同组内的工具可以并行执行

---

### 2. 工具结果缓存

**文件**: `maxbot/core/tool_cache_enhanced.py`

**功能**:
- 缓存工具调用结果
- 自动缓存失效管理
- 缓存命中率统计
- 参数规范化

**使用示例**:
```python
from maxbot.core.tool_cache_enhanced import ToolCache

cache = ToolCache(
    cache_ttl=300,              # 工具列表缓存 TTL: 5 分钟
    result_cache_ttl=60,         # 结果缓存 TTL: 1 分钟
    max_result_cache_size=1000,  # 最大缓存条目数
)

# 检查缓存
cached_result = cache.get_cached_result("read_file", {"path": "test.py"})
if cached_result is not None:
    return cached_result

# 执行工具
result = execute_tool("read_file", {"path": "test.py"})

# 缓存结果
cache.cache_result("read_file", {"path": "test.py"}, result)

# 查看统计
print(cache.print_usage_stats())
print(cache.print_cache_stats())
```

**缓存统计示例**:
```
📊 工具使用统计:

  read_file:
    调用次数: 100
    平均耗时: 0.0234s
    总耗时: 2.3400s
    缓存命中: 75
    缓存未命中: 25
    缓存命中率: 75.00%

📊 缓存统计:
  结果缓存大小: 150/1000
  结果缓存 TTL: 60s
  缓存命中: 75
  缓存未命中: 25
  缓存命中率: 75.00%
```

---

### 3. 智能重试机制

**文件**: `maxbot/core/smart_retry.py`

**功能**:
- 自动识别错误类型
- 基于错误类型的重试策略
- 指数退避重试
- 自定义错误处理器

**使用示例**:
```python
from maxbot.core.smart_retry import SmartRetry, RetryStrategy, ErrorType

# 自定义重试策略
strategy = RetryStrategy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    backoff_multiplier=2.0,
    retryable_errors=[
        ErrorType.NETWORK,
        ErrorType.TIMEOUT,
        ErrorType.RATE_LIMIT,
        ErrorType.SERVER_ERROR,
    ],
)

retry = SmartRetry(strategy)

# 添加自定义处理器
def handle_rate_limit(error, attempt, *args, **kwargs):
    # 从错误消息中提取重试时间
    import re
    retry_match = re.search(r"retry.*after.*(\d+)", str(error))
    if retry_match:
        return {"retry_after": int(retry_match.group(1))}

retry.add_custom_handler(ErrorType.RATE_LIMIT, handle_rate_limit)

# 执行函数并自动重试
result = retry.execute_with_retry(
    lambda: call_tool("web_search", {"query": "test"})
)
```

**错误类型分类**:
| 错误类型 | 检测模式 | 是否重试 |
|----------|----------|----------|
| NETWORK | connection refused/reset/unreachable | ✅ |
| TIMEOUT | timeout/timed out | ✅ |
| RATE_LIMIT | 429/rate limit/quota exceeded | ✅ |
| SERVER_ERROR | 5xx/internal server error | ✅ |
| CLIENT_ERROR | 4xx/bad request/unauthorized | ❌ |
| PARSE_ERROR | json decode/parse error | ❌ |
| UNKNOWN | 其他 | ❌ |

---

## 🔧 集成到 Agent Loop

### 修改 `maxbot/core/agent_loop.py`

在 `__init__` 方法中初始化优化组件：

```python
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache
from maxbot.core.smart_retry import SmartRetry

class Agent:
    def __init__(self, ...):
        # ... 现有代码 ...
        
        # 初始化优化组件
        self._dep_analyzer = ToolDependencyAnalyzer()
        self._tool_cache = ToolCache(
            cache_ttl=300,
            result_cache_ttl=60,
        )
        self._smart_retry = SmartRetry()
```

在 `_call_tool` 方法中添加缓存和重试：

```python
def _call_tool(self, tool_call: dict[str, Any]) -> str:
    """调用工具（带优化）"""
    function_name = tool_call.get("function", {}).get("name")
    arguments = tool_call.get("function", {}).get("arguments", {})
    
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except (json.JSONDecodeError, ValueError):
            arguments = {}
    
    # 内置 memory 工具
    if function_name == "memory":
        return self._call_memory_tool(arguments)
    
    # 检查缓存
    cached_result = self._tool_cache.get_cached_result(function_name, arguments)
    if cached_result is not None:
        return cached_result
    
    # 使用智能重试执行工具
    start_time = time.time()
    
    def execute_tool():
        if self._registry:
            return self._registry.call(function_name, arguments)
        return json.dumps({"error": f"未找到工具: {function_name}"}, ensure_ascii=False)
    
    try:
        result = self._smart_retry.execute_with_retry(execute_tool)
    except Exception as e:
        logger.error(f"工具调用失败: {function_name}, 错误: {e}")
        result = json.dumps({"error": str(e), "tool": function_name}, ensure_ascii=False)
    
    # 记录使用统计
    duration = time.time() - start_time
    self._tool_cache.record_usage(function_name, duration)
    
    # 缓存结果
    self._tool_cache.cache_result(function_name, arguments, result)
    
    return result
```

在 `run` 方法中添加并行工具执行：

```python
def run(self, user_message: str) -> str:
    """运行对话（带并行优化）"""
    # ... 现有代码 ...
    
    # 处理工具调用
    if assistant_message.tool_calls:
        logger.info(f"收到 {len(assistant_message.tool_calls)} 个工具调用")
        
        # 分析依赖关系
        tool_calls_list = [
            {
                "id": tc.id,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in assistant_message.tool_calls
        ]
        
        dependencies = self._dep_analyzer.analyze_dependencies(tool_calls_list)
        parallel_groups = self._dep_analyzer.get_parallel_groups(dependencies)
        
        logger.info(f"并行执行: {[len(g) for g in parallel_groups]} 组")
        
        # 按组并行执行
        all_results = {}
        for group in parallel_groups:
            with ThreadPoolExecutor() as executor:
                group_results = list(executor.map(
                    lambda i: self._call_tool(tool_calls_list[i]),
                    group
                ))
                
                for i, result in zip(group, group_results):
                    tool_call = tool_calls_list[i]
                    all_results[tool_call["id"]] = result
        
        # 保存工具响应
        for tool_call in assistant_message.tool_calls:
            result = all_results[tool_call.id]
            tool_response = Message(
                role="tool",
                content=result,
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
            )
            self._message_manager.append(tool_response)
        
        # 继续对话
        return self.run("")
    
    # ... 现有代码 ...
```

---

## 📊 性能提升预期

| 优化项 | 预期提升 | 适用场景 |
|--------|----------|----------|
| **并行工具执行** | 2-5x | 多个独立工具调用 |
| **工具结果缓存** | 10-100x | 重复工具调用 |
| **智能重试** | 减少 50% 失败率 | 网络/速率限制 |

**综合提升**: 在典型场景下，总体性能可提升 **3-10x**。

---

## 🧪 测试

创建测试文件 `tests/test_claude_code_optimizations.py`:

```python
import pytest
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache
from maxbot.core.smart_retry import SmartRetry, ErrorType

def test_dependency_analysis():
    """测试依赖分析"""
    analyzer = ToolDependencyAnalyzer()
    
    tool_calls = [
        {
            "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}
        },
        {
            "function": {"name": "search_files", "arguments": '{"pattern": "test"}'}
        },
        {
            "function": {"name": "write_file", "arguments": '{"path": "test.py", "content": "..."}'}
        },
    ]
    
    dependencies = analyzer.analyze_dependencies(tool_calls)
    parallel_groups = analyzer.get_parallel_groups(dependencies)
    
    # read_file 和 search_files 可以并行
    assert len(parallel_groups[0]) == 2

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

def test_smart_retry():
    """测试智能重试"""
    retry = SmartRetry()
    
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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## 📝 后续计划

- [ ] 将优化组件集成到 Agent Loop
- [ ] 添加性能基准测试
- [ ] 优化缓存策略（LRU/LFU）
- [ ] 添加工具执行超时控制
- [ ] 实现工具调用链追踪

---

**文档版本**: 1.0  
**最后更新**: 2026-04-17  
**维护者**: MaxBot Team
