"""
上下文管理器 — 窗口压缩、摘要、token 估算

参考来源：
- Hermes: context_compressor.py — 自动上下文压缩
- Claude Code: services/compact/ — 上下文压缩
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from maxbot.core.agent_loop import Message


@dataclass
class ContextStats:
    total_messages: int = 0
    system_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    tool_messages: int = 0
    estimated_tokens: int = 0


class ContextManager:
    """
    上下文管理

    功能：
    - token 估算（简单启发式，1 中文字 ≈ 2 token）
    - 消息压缩（保留 system + 最近 N 轮）
    - 历史摘要
    """

    def __init__(self, max_messages: int = 100, max_tokens: int = 128_000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数"""
        # 英文：~4 chars per token
        # 中文：~1.5 chars per token
        # 混合：取保守值
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        other_chars = len(text) - ascii_chars
        return ascii_chars // 4 + int(other_chars * 0.6) + 1

    def get_stats(self, messages: list[Message]) -> ContextStats:
        stats = ContextStats(total_messages=len(messages))
        for m in messages:
            if m.role == "system":
                stats.system_messages += 1
            elif m.role == "user":
                stats.user_messages += 1
            elif m.role == "assistant":
                stats.assistant_messages += 1
            elif m.role == "tool":
                stats.tool_messages += 1
            stats.estimated_tokens += self.estimate_tokens(m.content)
        return stats

    def compress(self, messages: list[Message], keep_recent: int = 20) -> list[Message]:
        """
        压缩消息历史

        策略：
        1. 保留所有 system 消息
        2. 保留最近 keep_recent 条非 system 消息
        3. 在中间插入一条摘要消息
        """
        if len(messages) <= keep_recent + 1:
            return messages

        # 分离 system 和非 system
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        if len(non_system) <= keep_recent:
            return messages

        # 被压缩的部分
        to_compress = non_system[: -keep_recent]
        kept = non_system[-keep_recent:]

        # 生成摘要
        summary = self._summarize(to_compress)

        return system_msgs + [Message(role="user", content=f"[历史摘要]\n{summary}")] + kept

    def _summarize(self, messages: list[Message]) -> str:
        """生成简单摘要（不含 LLM 调用）"""
        topics = []
        tool_uses = []
        for m in messages:
            if m.role == "user" and len(m.content) > 10:
                topics.append(m.content[:80])
            elif m.role == "assistant" and m.tool_calls:
                for tc in m.tool_calls:
                    fname = tc.get("function", {}).get("name", "?")
                    tool_uses.append(fname)
            elif m.role == "tool":
                tool_uses.append(f"→{m.name}")

        parts = []
        if topics:
            parts.append(f"讨论话题: {'; '.join(topics[:5])}")
        if tool_uses:
            parts.append(f"使用工具: {', '.join(set(tool_uses))}")

        return "\n".join(parts) if parts else "（无重要历史）"
