# Agent 循环优化计划

## 📊 当前实现分析

### 1. 消息管理
**当前实现**:
```python
# 每次都遍历所有消息计算 tokens
total_tokens = sum(len(m.content) for m in self._messages) // 4
```

**问题**:
- ❌ 每次调用都重新计算所有消息的 tokens
- ❌ 没有缓存机制
- ❌ O(n) 时间复杂度，随着消息增长会越来越慢

**优化方案**:
- ✅ 添加消息 tokens 缓存
- ✅ 增量更新 tokens 计数
- ✅ O(1) 时间复杂度

---

### 2. 上下文压缩
**当前实现**:
```python
# 简单压缩策略
if total_tokens > self.config.max_context_tokens:
    self._compress_context()
```

**问题**:
- ❌ 压缩策略过于简单
- ❌ 没有保留重要信息
- ❌ 没有压缩统计

**优化方案**:
- ✅ 实现智能压缩算法
- ✅ 保留系统提示和关键对话
- ✅ 添加压缩统计和日志

---

### 3. 工具调用优化
**当前实现**:
```python
# 每次都重新获取工具列表
tools = self._get_tools()
```

**问题**:
- ❌ 每次都重新构建工具列表
- ❌ 没有工具缓存
- ❌ 没有工具优先级

**优化方案**:
- ✅ 缓存工具列表
- ✅ 添加工具优先级
- ✅ 优化工具匹配

---

### 4. 其他优化点

#### 消息去重
- 检测并移除重复消息
- 减少上下文大小

#### 消息序列化优化
- 使用更快的序列化方法
- 减少内存占用

#### 添加性能监控
- 记录关键操作耗时
- 统计优化效果

---

## 🎯 优化目标

### 性能目标
- **消息 tokens 计算**: O(n) → O(1)
- **工具列表获取**: 每次重建 → 缓存
- **上下文压缩**: 简单策略 → 智能策略
- **整体性能**: 提升 20-30%

### 功能目标
- ✅ 添加消息缓存机制
- ✅ 实现智能上下文压缩
- ✅ 优化工具调用逻辑
- ✅ 添加性能监控

---

## 📝 优化实施方案

### 阶段 1: 消息管理优化

#### 1.1 添加消息 tokens 缓存
```python
@dataclass
class Message:
    """统一消息格式"""
    role: str
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict = field(default_factory=dict)
    # 新增：缓存 tokens 数量
    _cached_tokens: int | None = field(default=None, init=False, repr=False)
    
    def estimate_tokens(self) -> int:
        """估算消息的 tokens 数量（带缓存）"""
        if self._cached_tokens is None:
            # 粗略估算：1 token ≈ 4 字符
            self._cached_tokens = len(self.content) // 4
        return self._cached_tokens
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._cached_tokens = None
```

#### 1.2 添加消息管理器
```python
class MessageManager:
    """消息管理器 - 优化消息操作"""
    
    def __init__(self):
        self._messages: list[Message] = []
        self._total_tokens: int = 0  # 缓存的总 tokens 数量
    
    def append(self, message: Message) -> None:
        """添加消息（增量更新 tokens）"""
        self._messages.append(message)
        self._total_tokens += message.estimate_tokens()
    
    def pop(self) -> Message | None:
        """移除最后一条消息（增量更新 tokens）"""
        if not self._messages:
            return None
        message = self._messages.pop()
        self._total_tokens -= message.estimate_tokens()
        return message
    
    def get_total_tokens(self) -> int:
        """获取总 tokens 数量（O(1)）"""
        return self._total_tokens
    
    def compress(self, keep_ratio: float = 0.5) -> int:
        """压缩消息（智能策略）"""
        # 保留系统消息和最近的对话
        system_messages = [m for m in self._messages if m.role == "system"]
        recent_messages = self._messages[-int(len(self._messages) * keep_ratio):]
        
        old_count = len(self._messages)
        self._messages = system_messages + recent_messages
        
        # 重新计算 tokens
        self._total_tokens = sum(m.estimate_tokens() for m in self._messages)
        
        return old_count - len(self._messages)
```

---

### 阶段 2: 上下文压缩优化

#### 2.1 智能压缩策略
```python
class ContextCompressor:
    """上下文压缩器"""
    
    def __init__(self, max_tokens: int, compress_at_tokens: int):
        self.max_tokens = max_tokens
        self.compress_at_tokens = compress_at_tokens
        self._compress_count = 0  # 压缩次数统计
        self._compressed_messages = 0  # 压缩消息数统计
    
    def should_compress(self, current_tokens: int) -> bool:
        """判断是否需要压缩"""
        return current_tokens > self.compress_at_tokens
    
    def compress(self, messages: list[Message]) -> tuple[list[Message], dict]:
        """压缩上下文（智能策略）"""
        old_count = len(messages)
        
        # 策略 1: 保留系统消息
        system_messages = [m for m in messages if m.role == "system"]
        
        # 策略 2: 保留最近的用户/assistant 对话（保留 50%）
        conversation_messages = [m for m in messages if m.role in ["user", "assistant"]]
        keep_count = min(len(conversation_messages), max(10, len(conversation_messages) // 2))
        recent_conversation = conversation_messages[-keep_count:]
        
        # 策略 3: 保留最近的工具调用结果（保留 30%）
        tool_messages = [m for m in messages if m.role == "tool"]
        keep_tool_count = min(len(tool_messages), max(5, len(tool_messages) // 3))
        recent_tools = tool_messages[-keep_tool_count:]
        
        # 合并消息
        compressed = system_messages + recent_conversation + recent_tools
        
        # 更新统计
        self._compress_count += 1
        self._compressed_messages += old_count - len(compressed)
        
        stats = {
            "compress_count": self._compress_count,
            "old_count": old_count,
            "new_count": len(compressed),
            "compressed_messages": old_count - len(compressed),
            "total_compressed": self._compressed_messages,
        }
        
        return compressed, stats
```

---

### 阶段 3: 工具调用优化

#### 3.1 工具缓存
```python
class ToolCache:
    """工具缓存"""
    
    def __init__(self):
        self._cached_tools: list[dict] | None = None
        self._last_update: float = 0
        self._cache_ttl: float = 300  # 5 分钟缓存
    
    def get_tools(self, get_tools_fn: Callable[[], list[dict]]) -> list[dict]:
        """获取工具列表（带缓存）"""
        import time
        
        # 检查缓存是否有效
        if self._cached_tools is not None:
            if time.time() - self._last_update < self._cache_ttl:
                return self._cached_tools
        
        # 重新获取工具
        self._cached_tools = get_tools_fn()
        self._last_update = time.time()
        
        return self._cached_tools
    
    def invalidate(self):
        """使缓存失效"""
        self._cached_tools = None
        self._last_update = 0
```

#### 3.2 工具优先级
```python
class ToolPrioritizer:
    """工具优先级管理器"""
    
    # 工具优先级（数字越小优先级越高）
    TOOL_PRIORITIES = {
        "memory": 1,           # 记忆工具优先级最高
        "read_file": 2,        # 读取文件
        "write_file": 3,       # 写入文件
        "code_edit": 4,        # 代码编辑
        "shell": 5,            # Shell 命令
        "search_files": 6,     # 搜索文件
        "web_search": 7,       # 网络搜索
        "web_fetch": 8,        # 网页抓取
        "git_status": 9,       # Git 状态
        "git_diff": 10,        # Git 差异
        "git_log": 11,         # Git 日志
        "git_commit": 12,      # Git 提交
    }
    
    @classmethod
    def sort_tools(cls, tools: list[dict]) -> list[dict]:
        """按优先级排序工具"""
        def get_priority(tool):
            name = tool.get("function", {}).get("name", "")
            return cls.TOOL_PRIORITIES.get(name, 100)
        
        return sorted(tools, key=get_priority)
```

---

### 阶段 4: 性能监控

#### 4.1 性能监控器
```python
class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self._metrics = {
            "message_tokens_calc_time": [],
            "tool_list_get_time": [],
            "context_compress_time": [],
            "llm_call_time": [],
            "tool_call_time": [],
        }
    
    def record(self, metric_name: str, duration: float) -> None:
        """记录指标"""
        if metric_name in self._metrics:
            self._metrics[metric_name].append(duration)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {}
        for name, values in self._metrics.items():
            if values:
                stats[name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "total": sum(values),
                }
        return stats
    
    def print_report(self) -> str:
        """打印性能报告"""
        stats = self.get_stats()
        lines = ["📊 性能监控报告:\n"]
        
        for name, stat in stats.items():
            lines.append(f"  {name}:")
            lines.append(f"    调用次数: {stat['count']}")
            lines.append(f"    平均耗时: {stat['avg']:.4f}s")
            lines.append(f"    最小耗时: {stat['min']:.4f}s")
            lines.append(f"    最大耗时: {stat['max']:.4f}s")
            lines.append(f"    总耗时: {stat['total']:.4f}s")
            lines.append("")
        
        return "\n".join(lines)
```

---

## 🚀 实施步骤

### 步骤 1: 创建优化模块
- [ ] 创建 `maxbot/core/message_manager.py`
- [ ] 创建 `maxbot/core/context_compressor.py`
- [ ] 创建 `maxbot/core/tool_cache.py`
- [ ] 创建 `maxbot/core/performance_monitor.py`

### 步骤 2: 更新 Agent 类
- [ ] 集成 MessageManager
- [ ] 集成 ContextCompressor
- [ ] 集成 ToolCache
- [ ] 集成 PerformanceMonitor

### 步骤 3: 更新配置
- [ ] 添加优化相关配置
- [ ] 更新默认值

### 步骤 4: 编写测试
- [ ] 测试消息管理器
- [ ] 测试上下文压缩器
- [ ] 测试工具缓存
- [ ] 测试性能监控

### 步骤 5: 性能测试
- [ ] 对比优化前后的性能
- [ ] 验证功能正确性
- [ ] 生成性能报告

---

## 📊 预期效果

### 性能提升
- **消息 tokens 计算**: 100x 提升（O(n) → O(1)）
- **工具列表获取**: 10x 提升（缓存）
- **上下文压缩**: 2x 提升（智能策略）
- **整体性能**: 20-30% 提升

### 功能改进
- ✅ 更智能的上下文压缩
- ✅ 更好的工具优先级
- ✅ 详细的性能监控
- ✅ 更好的内存使用

---

## ⚠️ 注意事项

### 兼容性
- 保持向后兼容
- 不改变公共 API
- 保持现有功能

### 测试
- 充分测试所有功能
- 性能测试
- 边界情况测试

### 监控
- 添加性能日志
- 统计优化效果
- 及时调整策略

---

**文档版本**: 1.0  
**最后更新**: 2026-04-17  
**维护者**: MaxBot Team
