# Agent Loop 集成优化 - _call_tool 方法

## 当前 _call_tool 方法（第 384-406 行）

```python
def _call_tool(self, tool_call: dict[str, Any]) -> str:
    """
    调用工具
    """
    function_name = tool_call.get("function", {}).get("name")
    arguments = tool_call.get("function", {}).get("arguments", {})

    # arguments 可能是 JSON 字符串（来自 API），需要解析为 dict
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"工具参数 JSON 解析失败: {arguments[:200]}")
            arguments = {}

    # 内置
    if function_name == "memory":
        return self._call_memory_tool(arguments)

    # 注册表中的工具
    if self._registry:
        return self._registry.call(function_name, arguments)

    logger.error(f"未找到工具: {function_name}")
    return json.dumps({"error": f"未找到工具: {function_name}"}, ensure_ascii=False)
```

## 优化后的 _call_tool 方法

```python
def _call_tool(self, tool_call: dict[str, Any]) -> str:
    """
    调用工具（带优化）
    
    优化项：
    - 工具结果缓存（避免重复调用）
    - 智能重试（网络错误自动重试）
    - 使用统计（记录调用次数和耗时）
    """
    function_name = tool_call.get("function", {}).get("name")
    arguments = tool_call.get("function", {}).get("arguments", {})

    # arguments 可能是 JSON 字符串（来自 API），需要解析为 dict
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except (json.loadsError, ValueError):
            logger.warning(f"工具参数 JSON 解析失败: {arguments[:200]}")
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

## 集成步骤

1. 找到 `maxbot/core/agent_loop.py` 文件的第 384-406 行
2. 将整个 `_call_tool` 方法替换为优化版本
3. 确保以下导入已添加（第 9-28 行）：
   ```python
   from concurrent.futures import ThreadPoolExecutor
   from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
   from maxbot.core.tool_cache_enhanced import ToolCache as EnhancedToolCache
   from maxbot.core.smart_retry import SmartRetry
   ```

4. 确保以下组件已在 `__init__` 中初始化（第 239-248 行）：
   ```python
   # 优化：工具缓存（使用增强版）
   self._tool_cache = EnhancedToolCache(
       cache_ttl=300,
       result_cache_ttl=60,
       max_result_cache_size=1000,
   )
   
   # 优化：智能重试
   self._smart_retry = SmartRetry()
   
   # 优化：工具依赖分析器
   self._dep_analyzer = ToolDependencyAnalyzer()
   ```

## 测试

修改完成后，运行测试验证：

```bash
# 测试优化功能
python3 -m pytest tests/test_claude_code_optimizations.py -v

# 测试 Agent
python3 -m pytest tests/test_agent.py -v

# 测试所有测试
python3 -m pytest tests/ -v
```

## 注意事项

1. **线程安全**: 确保工具处理器是线程安全的
2. **缓存失效**: 对于有副作用的工具，不要缓存结果
3. **重试策略**: 根据实际情况调整重试次数和延迟
4. **并行控制**: 对于 I/O 密集型工具，并行执行可能有问题

## 回滚

如果出现问题，可以通过配置禁用优化：

```python
config = AgentConfig(
    enable_tool_cache=False,
    enable_smart_retry=False,
    enable_parallel_execution=False,
)
```
