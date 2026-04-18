# Agent Loop 集成 - _call_tool 方法修改

## 修改说明

在 `maxbot/core/agent_loop.py` 文件中，找到 `_call_tool` 方法（约第 384-406 行），替换为以下代码：

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
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"工具参数 JSON 解析失败: {arguments[:200]}")
            arguments = {}
    
    # 内置 memory 工具
    if function_name == "memory":
        return self._call_memory_tool(arguments)
    
    # 检查缓存
    cached_result = self._tool_cache.get_cached_result(function_name, arguments)
    if cached_result is not None:
        logger.debug(f"工具缓存命中: {function_name}")
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

## 集成检查清单

- [ ] 步骤 1: 添加导入（已完成 ✅）
- [ ] 步骤 2: 添加配置（已完成 ✅）
- [ ] 步骤 3: 初始化组件（已完成 ✅）
- [ ] 步骤 4: 修改 _call_tool 方法（进行中...）
- [ ] 步骤 5: 修改 run 方法
- [ ] 步骤 6: 添加统计方法

## 注意事项

1. **导入检查**: 确保以下导入已添加（第 9-28 行之后）：
```python
from concurrent.futures import ThreadPoolExecutor
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache as EnhancedToolCache
from maxbot.core.smart_retry import SmartRetry
```

2. **组件初始化检查**: 确保以下组件已在 `__init__` 中初始化：
```python
# 优化：工具缓存（使用增强版）
self._tool_cache = EnhancedToolCache(
    cache_ttl=300,  # 工具列表缓存 TTL: 5 分钟
    result_cache_ttl=60,  # 结果缓存 TTL: 1 分钟
    max_result_cache_size=1000,  # 最大结果缓存条目数
)

# 优化：智能重试
self._smart_retry = SmartRetry()

# 优化：工具依赖分析器
self._dep_analyzer = ToolDependencyAnalyzer()
```

3. **配置检查**: 确保 `AgentConfig` 中添加了优化配置项：
```python
# 优化配置
enable_tool_cache: bool | None = None
enable_smart_retry: bool | None = None
enable_parallel_execution: bool | None = None
tool_cache_ttl: int | None = None
max_result_cache_size: int | None = None
```
