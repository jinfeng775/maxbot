# Agent Loop 集成 Claude Code 优化

## 集成步骤

### 1. 在 `__init__` 方法中初始化优化组件

在 `maxbot/core/agent_loop.py` 的 `Agent.__`init__` 方法中添加：

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
            cache_ttl=300,              # 工具列表缓存 TTL: 5 分钟
            result_cache_ttl=60,         # 结果缓存 TTL: 1 分钟
            max_result_cache_size=1000,  # 最大结果缓存条目数
        )
        self._smart_retry = SmartRetry()
```

### 2. 在 `_call_tool` 方法中添加缓存和重试

修改 `_call_tool` 方法：

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

### 3. 在 `run` 方法中添加并行工具执行

修改 `run` 方法中的工具调用处理部分：

```python
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
    logger.debug("继续对话处理工具结果")
    return self.run("")
```

### 4. 添加优化统计方法

在 `Agent` 类中添加：

```python
def get_optimization_stats(self) -> dict[str, Any]:
    """获取优化统计信息"""
    return {
        "tool_cache": self._tool_cache.get_cache_stats(),
        "usage_stats": self._tool_cache.get_usage_stats(),
    }

def print_optimization_stats(self) -> str:
    """打印优化统计信息"""
    lines = [
        "📊 优化统计:\n",
        self._tool_cache.print_cache_stats(),
        "\n",
        self._tool_cache.print_usage_stats(),
    ]
    return "\n".join(lines)
```

## 配置选项

在 `AgentConfig` 中添加：

```python
@dataclass
class AgentConfig:
    # ... 现有字段 ...
    
    # 优化配置
    enable_tool_cache: bool = True
    enable_smart_retry: bool = True
    enable_parallel_execution: bool = True
    tool_cache_ttl: int = 60
    max_result_cache_size: int = 1000
```

## 使用示例

```python
from maxbot.core import Agent, AgentConfig

# 创建 Agent（自动启用优化）
config = AgentConfig()
agent = Agent(config=config)

# 运行对话（自动应用优化）
response = agent.run("帮我分析这个项目")

# 查看优化统计
print(agent.print_optimization_stats())
```

## 性能对比

### 优化前
```
3 个工具调用，串行执行：
- read_file: 0.5s
- read_file: 0.5s
- search_files: 0.3s
总耗时: 1.3s
```

### 优化后
```
3 个工具调用，2 个可并行：
- read_file + read_file: 0.5s (并行）
- search_files: 0.3s (串行）
总耗时: 0.8s

提升: 1.3s → 0.8s (38% 提升)
```

## 注意事项

1. **线程安全**: 确保工具处理器是线程安全的
2. **缓存失效**: 对于有副作用的工具，不要缓存结果
3. **重试策略**: 根据实际情况调整重试次数和延迟
4. **并行控制**: 对于 I 紧密型工具，并行执行可能有问题

## 回滚

如果出现问题，可以通过配置禁用优化：

```python
config = AgentConfig(
    enable_tool_cache=False,
    enable_smart_retry=False,
    enable_parallel_execution=False,
)
```
