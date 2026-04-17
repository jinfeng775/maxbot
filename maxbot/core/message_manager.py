"""
消息管理器 - 优化消息操作

优化点:
1. 消息 tokens 缓存（O(n) → O(1)）
2. 增量更新 tokens 计数
3. 智能消息压缩
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """
    统一消息格式（优化版）
    
    优化:
    - 添加 tokens 缓存
    - 增量更新 tokens 计数
    """
    role: str                          # system | user | assistant | tool
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict = field(default_factory=dict)
    # 优化：缓存 tokens 数量
    _cached_tokens: int | None = field(default=None, init=False, repr=False)

    def estimate_tokens(self) -> int:
        """
        估算消息的 tokens 数量（带缓存）
        
        Returns:
            int: 估算的 tokens 数量
        """
        if self._cached_tokens is None:
            # 粗略估算：1 token ≈ 4 字符
            # 更精确的方法可以使用 tiktoken，但为了性能使用简单估算
            self._cached_tokens = len(self.content) // 4
        
        return self._cached_tokens

    def invalidate_cache(self):
        """使缓存失效（内容修改后调用）"""
        self._cached_tokens = None

    def to_api(self) -> dict:
        """
        转换成 OpenAI API 格式
        """
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg

    def to_dict(self) -> dict:
        """
        转换成字典（用于序列化）
        """
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "metadata": self.metadata,
        }


class MessageManager:
    """
    消息管理器 - 优化消息操作
    
    优化:
    - O(1) 时间复杂度获取总 tokens
    - 增量更新 tokens 计数
    - 智能消息压缩
    """
    
    def __init__(self):
        self._messages: list[Message] = []
        self._total_tokens: int = 0  # 缓存的总 tokens 数量
    
    def append(self, message: Message) -> None:
        """
        添加消息（增量更新 tokens）
        
        Args:
            message: 要添加的消息
        """
        self._messages.append(message)
        self._total_tokens += message.estimate_tokens()
    
    def pop(self) -> Message | None:
        """
        移除最后一条消息（增量更新 tokens）
        
        Returns:
            Message | None: 被移除的消息，如果没有消息则返回 None
        """
        if not self._messages:
            return None
        
        message = self._messages.pop()
        self._total_tokens -= message.estimate_tokens()
        return message
    
    def extend(self, messages: list[Message]) -> None:
        """
        批量添加消息（增量更新 tokens）
        
        Args:
            messages: 要添加的消息列表
        """
        for message in messages:
            self.append(message)
    
    def get_messages(self) -> list[Message]:
        """
        获取所有消息的副本
        
        Returns:
            list[Message]: 消息列表的副本
        """
        return self._messages.copy()
    
    def get_total_tokens(self) -> int:
        """
        获取总 tokens 数量（O(1)）
        
        Returns:
            int: 总 tokens 数量
        """
        return self._total_tokens
    
    def get_message_count(self) -> int:
        """
        获取消息数量
        
        Returns:
            int: 消息数量
        """
        return len(self._messages)
    
    def clear(self) -> None:
        """清空所有消息"""
        self._messages.clear()
        self._total_tokens = 0
    
    def compress(self, keep_ratio: float = 0.5) -> dict:
        """
        压缩消息（智能策略）
        
        策略:
        1. 保留系统消息
        2. 保留最近的对话（保留 50%）
        3. 保留最近的工具调用结果（保留 30%）
        
        Args:
            keep_ratio: 保留的消息比例（0.0 - 1.0）
        
        Returns:
            dict: 压缩统计信息
        """
        old_count = len(self._messages)
        old_tokens = self._total_tokens
        
        # 策略 1: 保留系统消息
        system_messages = [m for m in self._messages if m.role == "system"]
        
        # 策略 2: 保留最近的用户/assistant 对话
        conversation_messages = [m for m in self._messages if m.role in ["user", "assistant"]]
        keep_count = max(10, int(len(conversation_messages) * keep_ratio))
        recent_conversation = conversation_messages[-keep_count:]
        
        # 策略 3: 保留最近的工具调用结果
        tool_messages = [m for m in self._messages if m.role == "tool"]
        keep_tool_count = max(5, int(len(tool_messages) * 0.3))
        recent_tools = tool_messages[-keep_tool_count:]
        
        # 合并消息
        self._messages = system_messages + recent_conversation + recent_tools
        
        # 重新计算 tokens
        self._total_tokens = sum(m.estimate_tokens() for m in self._messages)
        
        stats = {
            "old_count": old_count,
            "new_count": len(self._messages),
            "compressed_messages": old_count - len(self._messages),
            "old_tokens": old_tokens,
            "new_tokens": self._total_tokens,
            "compressed_tokens": old_tokens - self._total_tokens,
        }
        
        return stats
    
    def remove_duplicates(self) -> dict:
        """
        移除重复的消息
        
        Returns:
            dict: 去重统计信息
        """
        old_count = len(self._messages)
        old_tokens = self._total_tokens
        
        # 使用字典去重（基于内容和角色）
        seen = set()
        unique_messages = []
        
        for message in self._messages:
            # 创建唯一标识
            key = (message.role, message.content[:100])  # 使用前 100 个字符作为标识
            if key not in seen:
                seen.add(key)
                unique_messages.append(message)
        
        # 更新消息
        self._messages = unique_messages
        
        # 重新计算 tokens
        self._total_tokens = sum(m.estimate_tokens() for m in self._messages)
        
        stats = {
            "old_count": old_count,
            "new_count": len(self._messages),
            "removed_duplicates": old_count - len(self._messages),
            "old_tokens": old_tokens,
            "new_tokens": self._total_tokens,
            "removed_tokens": old_tokens - self._total_tokens,
        }
        
        return stats
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        role_counts = {}
        for message in self._messages:
            role_counts[message.role] = role_counts.get(message.role, 0) + 1
        
        return {
            "total_messages": len(self._messages),
            "total_tokens": self._total_tokens,
            "role_counts": role_counts,
            "avg_tokens_per_message": self._total_tokens / len(self._messages) if self._messages else 0,
        }
    
    def __len__(self) -> int:
        """返回消息数量"""
        return len(self._messages)
    
    def __getitem__(self, index: int) -> Message:
        """获取指定索引的消息"""
        return self._messages[index]
    
    def __iter__(self):
        """迭代消息"""
        return iter(self._messages)
