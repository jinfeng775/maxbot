# Agent Loop 集成优化 - 补丁说明

## 修改 1：添加导入

在 `maxbot/core/agent_loop.py` 文件开头，第 9-28 行之后添加：

```python
from concurrent.futures import ThreadPoolExecutor
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache as EnhancedToolCache
from maxbot.core.smart_retry import SmartRetry
```

## 修改 2：在 AgentConfig 中添加优化配置

在 `AgentConfig` 类中，第 74 行之后添加：

```python
    # 优化配置
    enable_tool_cache: bool | None = None
    enable_smart_retry: bool | None = None
    enable_parallel_execution: bool | None = None
    tool_cache_ttl: int | None = None
    max_result_cache_size: int | None = None
```

## 修改 3：在 Agent.__init__ 中初始化优化组件

在 `Agent.__init__` 方法中，找到第 239 行的 `self._tool_cache = ToolCache(cache_ttl=300)`，替换为：

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

## 修改 4：修改 _call_tool 方法

找到 `_call_tool` 方法（约第 384 行），替换整个方法：

```python
    def _call_tool(self, tool_call: dict[str, Any]) -> str:
        """
        调用工具（带优化）
        
        优化项：
        - 工具结果缓存
（避免重复调用）
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

## 修改 5：在 run 方法中添加并行工具执行

找到 `run` 方法中处理工具调用的部分（约第 609-653 行），替换为：

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
            
            # 继续对话（让 LLM 处理工具结果）
            logger.debug("继续对话处理工具结果")
            return self.run("")  # 递归调用
```

## 修改 6：添加优化统计方法

在 `Agent` 类末尾（`reset` 方法之后）添加：

```python
    def get_optimization_stats(self) -> dict[str, Any]:
        """
        获取优化统计信息
        
        Returns:
            dict: 优化统计信息
        """
        return {
            "tool_cache": self._tool_cache.get_cache_stats(),
            "usage_stats": self._tool_cache.get_usage_stats(),
        }
    
    def print_optimization_stats(self) -> str:
        """
        打印优化统计信息
        
        Returns:
            str: 格式化的统计信息
        """
        lines = [
            "📊 优化统计:\n",
            self._tool_cache.print_cache_stats(),
            "\n",
            self._tool_cache.print_usage_stats(),
        ]
        return "\n".join(lines)
```

## 验证修改

修改完成后，运行以下命令验证：

```bash
# 运行测试
python3 -m pytest tests/test_claude_code_optimizations.py -v

# 运行现有测试
python3 -m pytest tests/test_agent.py -v

# 检查代码
python3 -m pytest tests/ -v
```

## 性能测试

创建性能测试文件 `tests/test_optimization_performance.py`：

```python
import time
from maxbot.core import Agent, AgentConfig

def test_parallel_execution_performance():
    """测试并行执行性能"""
    config = AgentConfig()
    agent = Agent(config=config)
    
    # 模拟 3 个工具调用
    tool_calls = [
        {"function": {"name": "read_file", "arguments": '{"path": "a.py"}'}},
        {"function": {"name": "read_file", "arguments": '{"path": "b.py"}'}},
        {"function": {"name": "read_file", "arguments": '{"path": "c.py"}'}},
    ]
    
    start = time.time()
    # ... 执行工具调用 ...
    end = time.time()
    
    print(f"耗时: {end - start:.2f}s")

def test_cache_performance():
    """测试缓存性能"""
    config = AgentConfig()
    agent = Agent(config=config)
    
    # 第一次调用（缓存未命中）
    start1 = time.time()
    result1 = agent._call_tool({
        "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}
    })
    end1 = time.time()
    
    # 第二次调用（缓存命中）
    start2 = time.time()
    result2 = agent._call_tool({
        "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}
    })
    end2 = time.time()
    
    print(f"第一次: {end1 - start1:.4f}s")
    print(f"第二次（缓存）: {end2 - start2:.4f}s")
    print(f"加速比: {(end1 - start1) / (end2 - start2):.1f}x")
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
