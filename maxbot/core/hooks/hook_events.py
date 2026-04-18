"""
Hook 事件定义

参考 ECC hooks.json 的事件系统
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


class HookEvent(str, Enum):
    """Hook 事件类型（参考 ECC hooks.json）
    
    ECC hooks.json 包含以下事件类型：
    - PreToolUse: 工具调用前
    - PostToolUse: 工具调用后
    - SessionStart: 会话开始
    - SessionEnd: 会话结束
    - PreCompact: 压缩前
    - PostCompact: 压缩后
    - Error: 错误发生
    """
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_COMPACT = "pre_compact"
    POST_COMPACT = "post_compact"
    ERROR = "error"


@dataclass
class HookContext:
    """钩子执行上下文
    
    包含钩子执行所需的所有上下文信息
    """
    event: HookEvent
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.tool_args is None:
            self.tool_args = {}
        if self.metadata is None:
            self.metadata = {}
