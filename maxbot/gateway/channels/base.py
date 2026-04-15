"""
渠道适配器 — 参考 OpenClaw channels/plugins/types.plugin.ts

每个渠道适配器实现统一接口，支持：
- 连接/断开
- 接收消息
- 发送消息
- 媒体处理
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    COMMAND = "command"


@dataclass
class InboundMessage:
    """入站消息（从渠道接收）"""
    channel: str                    # 渠道名（weixin/telegram/discord/...）
    channel_message_id: str = ""    # 渠道消息 ID
    chat_id: str = ""               # 聊天/会话 ID
    sender_id: str = ""             # 发送者 ID
    sender_name: str = ""           # 发送者昵称
    message_type: MessageType = MessageType.TEXT
    content: str = ""               # 文本内容
    media_url: str = ""             # 媒体 URL
    media_path: str = ""            # 本地媒体路径
    is_group: bool = False          # 是否群聊
    raw: dict = field(default_factory=dict)  # 原始消息


@dataclass
class OutboundMessage:
    """出站消息（发送到渠道）"""
    chat_id: str = ""
    message_type: MessageType = MessageType.TEXT
    content: str = ""
    media_path: str = ""
    reply_to: str = ""              # 回复的消息 ID
    extra: dict = field(default_factory=dict)


class ChannelAdapter(ABC):
    """
    渠道适配器基类（参考 OpenClaw ChannelPlugin）

    实现一个渠道需要：
    1. 继承 ChannelAdapter
    2. 实现 connect / disconnect
    3. 实现 send_message
    4. 可选：实现 receive_stream（实时接收）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道名称"""
        ...

    @property
    def display_name(self) -> str:
        """人类可读名称"""
        return self.name

    @property
    def capabilities(self) -> list[str]:
        """支持的能力"""
        return ["text"]

    @abstractmethod
    async def connect(self) -> bool:
        """连接到渠道"""
        ...

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        ...

    @abstractmethod
    async def send_message(self, message: OutboundMessage) -> bool:
        """发送消息"""
        ...

    async def receive_stream(self) -> AsyncIterator[InboundMessage]:
        """消息接收流（可选实现）"""
        return
        yield  # type: ignore  # make it a generator

    async def on_message(self, message: InboundMessage) -> OutboundMessage | None:
        """
        处理接收到的消息（可重写）

        默认返回 None（不自动回复）
        """
        return None

    async def handle_media(self, url: str) -> str | None:
        """下载/处理媒体文件（可选）"""
        return None

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"


# ── 渠道注册表 ────────────────────────────────────────────

class ChannelRegistry:
    """渠道注册表"""

    def __init__(self):
        self._channels: dict[str, ChannelAdapter] = {}

    def register(self, channel: ChannelAdapter):
        self._channels[channel.name] = channel

    def get(self, name: str) -> ChannelAdapter | None:
        return self._channels.get(name)

    def list_channels(self) -> list[str]:
        return list(self._channels.keys())

    async def connect_all(self):
        for name, ch in self._channels.items():
            try:
                await ch.connect()
                print(f"✅ 渠道已连接: {name}")
            except Exception as e:
                print(f"❌ 渠道连接失败: {name} — {e}")

    async def disconnect_all(self):
        for ch in self._channels.values():
            try:
                await ch.disconnect()
            except Exception:
                pass

    async def broadcast(self, message: OutboundMessage, channels: list[str] | None = None):
        """广播消息到多个渠道"""
        targets = channels or list(self._channels.keys())
        for name in targets:
            ch = self._channels.get(name)
            if ch:
                try:
                    await ch.send_message(message)
                except Exception as e:
                    print(f"❌ 发送失败 [{name}]: {e}")
