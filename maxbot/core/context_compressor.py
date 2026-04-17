"""
上下文压缩器 - 智能压缩策略

优化点:
1. 智能压缩算法
2. 保留重要信息
3. 压缩统计和日志
"""

from dataclasses import dataclass, field
from typing import Any
import logging

from maxbot.core.message_manager import Message

logger = logging.getLogger(__name__)


@dataclass
class CompressStats:
    """压缩统计信息"""
    compress_count: int = 0  # 压缩次数
    total_compressed_messages: int = 0  # 总共压缩的消息数
    total_compressed_tokens: int = 0  # 总共压缩的 tokens 数
    last_compress_time: float = 0  # 上次压缩时间


class ContextCompressor:
    """
    上下文压缩器
    
    功能:
    - 智能压缩策略
    - 保留重要信息
    - 压缩统计和日志
    """
    
    def __init__(
        self,
        max_tokens: int = 128_000,
        compress_at_tokens: int = 80_000,
        compress_ratio: float = 0.5,
    ):
        """
        初始化上下文压缩器
        
        Args:
            max_tokens: 最大 tokens 数量
            compress_at_tokens: 触发压缩的 tokens 阈值
            compress_ratio: 压缩比例（保留的消息比例）
        """
        self.max_tokens = max_tokens
        self.compress_at_tokens = compress_at_tokens
        self.compress_ratio = compress_ratio
        self._stats = CompressStats()
    
    def should_compress(self, current_tokens: int) -> bool:
        """
        判断是否需要压缩
        
        Args:
            current_tokens: 当前 tokens 数量
        
        Returns:
            bool: 是否需要压缩
        """
        return current_tokens > self.compress_at_tokens
    
    def compress(
        self,
        messages: list[Message],
        strategy: str = "smart"
    ) -> tuple[list[Message], dict]:
        """
        压缩上下文
        
        Args:
            messages: 消息列表
            strategy: 压缩策略 ("smart", "simple", "aggressive")
        
        Returns:
            tuple[list[Message], dict]: (压缩后的消息列表, 压缩统计)
        """
        import time
        
        old_count = len(messages)
        old_tokens = sum(m.estimate_tokens() for m in messages)
        
        # 根据策略选择压缩方法
        if strategy == "smart":
            compressed = self._smart_compress(messages)
        elif strategy == "simple":
            compressed = self._simple_compress(messages)
        elif strategy == "aggressive":
            compressed = self._aggressive_compress(messages)
        else:
            compressed = self._smart_compress(messages)
        
        # 计算统计信息
        new_count = len(compressed)
        new_tokens = sum(m.estimate_tokens() for m in compressed)
        
        # 更新统计
        self._stats.compress_count += 1
        self._stats.total_compressed_messages += old_count - new_count
        self._stats.total_compressed_tokens += old_tokens - new_tokens
        self._stats.last_compress_time = time.time()
        
        stats = {
            "strategy": strategy,
            "old_count": old_count,
            "new_count": new_count,
            "compressed_messages": old_count - new_count,
            "old_tokens": old_tokens,
            "new_tokens": new_tokens,
            "compressed_tokens": old_tokens - new_tokens,
            "compress_ratio": (old_tokens - new_tokens) / old_tokens if old_tokens > 0 else 0,
            "total_compress_count": self._stats.compress_count,
        }
        
        # 记录日志
        logger.info(
            f"上下文压缩完成: {old_count} -> {new_count} 条消息, "
            f"{old_tokens} -> {new_tokens} tokens "
            f"({stats['compress_ratio']:.1%} 压缩率)"
        )
        
        return compressed, stats
    
    def _smart_compress(self, messages: list[Message]) -> list[Message]:
        """
        智能压缩策略
        
        策略:
        1. 保留所有系统消息
        2. 保留最近的用户/assistant 对话（保留 50%）
        3. 保留最近的工具调用结果（保留 30%）
        4. 保留重要的消息（基于 metadata）
        """
        # 策略 1: 保留系统消息
        system_messages = [m for m in messages if m.role == "system"]
        
        # 策略 2: 保留最近的用户/assistant 对话
        conversation_messages = [m for m in messages if m.role in ["user", "assistant"]]
        keep_count = max(10, int(len(conversation_messages) * self.compress_ratio))
        recent_conversation = conversation_messages[-keep_count:]
        
        # 策略 3: 保留最近的工具调用结果
        tool_messages = [m for m in messages if m.role == "tool"]
        keep_tool_count = max(5, int(len(tool_messages) * 0.3))
        recent_tools = tool_messages[-keep_tool_count:]
        
        # 策略 4: 保留重要的消息（基于 metadata）
        important_messages = [
            m for m in messages
            if m.metadata.get("important", False) or m.metadata.get("preserve", False)
        ]
        
        # 合并消息（去重）
        all_messages = system_messages + recent_conversation + recent_tools + important_messages
        
        # 去重（基于 id）
        seen_ids = set()
        unique_messages = []
        for msg in all_messages:
            msg_id = id(msg)
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_messages.append(msg)
        
        return unique_messages
    
    def _simple_compress(self, messages: list[Message]) -> list[Message]:
        """
        简单压缩策略
        
        策略:
        1. 保留系统消息
        2. 保留最近的消息
        """
        # 保留系统消息
        system_messages = [m for m in messages if m.role == "system"]
        
        # 保留最近的消息
        keep_count = max(10, int(len(messages) * self.compress_ratio))
        recent_messages = messages[-keep_count:]
        
        # 合并
        return system_messages + recent_messages
    
    def _aggressive_compress(self, messages: list[Message]) -> list[Message]:
        """
        激进压缩策略
        
        策略:
        1. 保留系统消息
        2. 只保留最近 20 条消息
        """
        # 保留系统消息
        system_messages = [m for m in messages if m.role == "system"]
        
        # 只保留最近 20 条消息
        recent_messages = messages[-20:]
        
        # 合并
        return system_messages + recent_messages
    
    def get_stats(self) -> dict:
        """
        获取压缩统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            "compress_count": self._stats.compress_count,
            "total_compressed_messages": self._stats.total_compressed_messages,
            "total_compressed_tokens": self._stats.total_compressed_tokens,
            "last_compress_time": self._stats.last_compress_time,
            "avg_compressed_messages": (
                self._stats.total_compressed_messages / self._stats.compress_count
                if self._stats.compress_count > 0 else 0
            ),
            "avg_compressed_tokens": (
                self._stats.total_compressed_tokens / self._stats.compress_count
                if self._stats.compress_count > 0 else 0
            ),
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats = CompressStats()
    
    def print_stats(self) -> str:
        """
        打印压缩统计信息
        
        Returns:
            str: 格式化的统计信息
        """
        stats = self.get_stats()
        lines = [
            "📊 上下文压缩统计:",
            f"  压缩次数: {stats['compress_count']}",
            f"  总共压缩消息数: {stats['total_compressed_messages']}",
            f"  总共压缩 tokens: {stats['total_compressed_tokens']}",
        ]
        
        if stats['compress_count'] > 0:
            lines.extend([
                f"  平均每次压缩消息数: {stats['avg_compressed_messages']:.1f}",
                f"  平均每次压缩 tokens: {stats['avg_compressed_tokens']:.1f}",
            ])
        
        return "\n".join(lines)
