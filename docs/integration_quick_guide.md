# Agent Loop 集成优化 - 快速指南

## 快速集成

### 1. 添加导入（已完成 ✅）

在 `maxbot/core/agent_loop.py` 第 9-28 行之后添加：

```python
from concurrent.futures import ThreadPoolExecutor
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache as EnhancedToolCache
from maxbot.core.smart_retry import SmartRetry
```

### 2. 添加配置（已完成 ✅）

在 `AgentConfig` 类中添加：

```python
# 优化配置
enable_tool_cache: bool | None = None
enable_smart_retry: bool | None = None
enable_parallel_execution: bool | None = None
tool_cache_ttl: int | None = None
max_result_cache_size: int | None = None
```

### 3. 初始化组件（已完成 ✅）

在 `Agent.__init__` 中：

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

### 4. 修改 _call_tool 方法（待完成）

参考 `docs/agent_loop_integration_patch.md` 中的完整代码

### 5. 修改 run 方法（待完成）

参考 `docs/agent_loop_integration_patch.md` 中的完整代码

---

## 当前状态

| 步骤 | 状态 |
|------|------|
| 1. 添加导入 | ✅ 已完成 |
| 2. 添加配置 | ✅ 已完成 |
| 3. 初始化组件 | ✅ 已完成 |
| 4. 修改 _call_tool | ⏳ 待完成 |
| 5. 修改 run 方法 | ⏳ 待完成 |
| 6. 添加统计方法 | ⏳ 待完成 |

---

## 下一步

继续完成剩余的集成步骤，参考：
- `docs/agent_loop_integration_patch.md` - 详细集成指南
- `docs/agent_loop_integration_guide.md` - 使用说明
