"""
Telegram Bot 渠道适配器 — 使用 aiohttp 异步轮询

通过 Telegram Bot API 收发消息，不阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from maxbot.gateway.channels.base import (
    ChannelAdapter,
    InboundMessage,
    MessageType,
    OutboundMessage,
)


class TelegramChannel(ChannelAdapter):
    """
    Telegram Bot 渠道

    用法：
        channel = TelegramChannel(bot_token="123456:ABC-DEF...")
        await channel.connect()
        await channel.send_message(OutboundMessage(chat_id="12345", content="Hello!"))
    """

    def __init__(self, bot_token: str | None = None):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("需要安装 aiohttp: pip install aiohttp")

        self._token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._api_base = f"https://api.telegram.org/bot{self._token}"
        self._connected = False
        self._offset = 0
        self._poll_task: asyncio.Task | None = None
        self._message_queue: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def display_name(self) -> str:
        return "Telegram"

    @property
    def capabilities(self) -> list[str]:
        return ["text", "image", "audio", "video", "file", "commands"]

    async def connect(self) -> bool:
        if not self._token:
            raise ValueError("Telegram bot token 未设置")
        self._session = aiohttp.ClientSession()
        self._connected = True
        # 启动轮询
        self._poll_task = asyncio.create_task(self._poll_loop())
        return True

    async def disconnect(self):
        self._connected = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()

    async def send_message(self, message: OutboundMessage) -> bool:
        url = f"{self._api_base}/sendMessage"
        payload = {
            "chat_id": message.chat_id,
            "text": message.content,
        }
        if message.reply_to:
            payload["reply_to_message_id"] = message.reply_to

        try:
            async with self._session.post(url, json=payload) as resp:
                result = await resp.json()
                return result.get("ok", False)
        except Exception as e:
            print(f"❌ Telegram 发送失败: {e}")
            return False

    async def receive_stream(self) -> AsyncIterator[InboundMessage]:
        while self._connected:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    async def _poll_loop(self):
        """长轮询接收消息（异步，不阻塞）"""
        while self._connected:
            try:
                url = f"{self._api_base}/getUpdates"
                params = {"offset": self._offset, "timeout": 30}
                async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=35)) as resp:
                    data = await resp.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        msg = self._parse_update(update)
                        if msg:
                            await self._message_queue.put(msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._connected:
                    print(f"⚠️ Telegram 轮询错误: {e}")
                await asyncio.sleep(1)

    def _parse_update(self, update: dict) -> InboundMessage | None:
        """解析 Telegram update 为 InboundMessage"""
        if "message" not in update:
            return None

        tg_msg = update["message"]
        chat = tg_msg.get("chat", {})
        sender = tg_msg.get("from", {})

        msg = InboundMessage(
            channel="telegram",
            channel_message_id=str(tg_msg.get("message_id", "")),
            chat_id=str(chat.get("id", "")),
            sender_id=str(sender.get("id", "")),
            sender_name=sender.get("first_name", ""),
            is_group=chat.get("type") in ("group", "supergroup"),
            raw=tg_msg,
        )

        if "text" in tg_msg:
            msg.message_type = MessageType.TEXT
            msg.content = tg_msg["text"]
        elif "photo" in tg_msg:
            msg.message_type = MessageType.IMAGE
            msg.content = tg_msg.get("caption", "")
        elif "voice" in tg_msg:
            msg.message_type = MessageType.AUDIO
            msg.content = tg_msg.get("caption", "")
        elif "document" in tg_msg:
            msg.message_type = MessageType.FILE
            msg.content = tg_msg.get("caption", "")

        return msg
