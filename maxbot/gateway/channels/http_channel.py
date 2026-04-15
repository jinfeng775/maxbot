"""
HTTP API 渠道 — 通用 HTTP 回调适配器

支持通过 HTTP webhook 接收消息，通过 API 发送消息。
可作为任何渠道的通用基础。
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from maxbot.gateway.channels.base import (
    ChannelAdapter,
    InboundMessage,
    MessageType,
    OutboundMessage,
)


class HttpChannel(ChannelAdapter):
    """
    HTTP 渠道适配器

    用法：
        channel = HttpChannel(name="webhook")
        # 通过 Gateway API 接收/发送消息
    """

    def __init__(self, name: str = "http", display_name: str = "HTTP API"):
        self._name = name
        self._display = display_name
        self._connected = False
        self._message_queue: list[InboundMessage] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display

    @property
    def capabilities(self) -> list[str]:
        return ["text", "image", "file"]

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self):
        self._connected = False

    async def send_message(self, message: OutboundMessage) -> bool:
        # HTTP 渠道的发送通过 Gateway API 完成
        # 这里只是记录
        return True

    def enqueue_message(self, message: InboundMessage):
        """手动入队消息（用于 webhook 回调）"""
        self._message_queue.append(message)

    async def receive_stream(self) -> AsyncIterator[InboundMessage]:
        import asyncio
        while self._connected:
            if self._message_queue:
                yield self._message_queue.pop(0)
            else:
                await asyncio.sleep(0.1)
