"""
Hook 自动化系统

参考 ECC hooks.json 的钩子系统实现

使用示例：
```python
from maxbot.core.hooks import HookManager, HookEvent, HookContext, BUILTIN_HOOKS

# 创建钩子管理器
hook_manager = HookManager()
hook_manager.register_many(BUILTIN_HOOKS)

# 触发钩子
await hook_manager.trigger(
    HookEvent.PRE_TOOL_USE,
    HookContext(
        event=HookEvent.PRE_TOOL_USE,
        tool_name="shell",
        tool_args={"command": "ls -la"},
        session_id="session-123"
    )
)
```
"""
from .hook_events import HookEvent, HookContext
from .hook_manager import HookManager
from .builtin_hooks import BUILTIN_HOOKS

__all__ = [
    "HookEvent",
    "HookContext", 
    "HookManager",
    "BUILTIN_HOOKS",
]
