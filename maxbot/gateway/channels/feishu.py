"""
飞书（Feishu/Lark）渠道适配器 — WebSocket 长连接模式

使用 lark_oapi SDK，机器人主动连接飞书，不需要公网 webhook。
只需要 App ID + App Secret。

用法：
    channel = FeishuChannel(app_id="cli_xxx", app_secret="xxx")
    await channel.connect()  # 启动 WebSocket 长连接
    await channel.send_message(OutboundMessage(chat_id="ou_xxx", content="你好"))
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Any, Callable

from maxbot.gateway.channels.base import (
    ChannelAdapter,
    InboundMessage,
    MessageType,
    OutboundMessage,
)

# lark_oapi SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
    )
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
    from lark_oapi.ws import Client as FeishuWSClient
    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False


class FeishuChannel(ChannelAdapter):
    """
    飞书渠道 — WebSocket 长连接模式

    只需要 App ID + App Secret，不需要公网 IP。
    """

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
    ):
        if not LARK_AVAILABLE:
            raise ImportError("需要安装 lark_oapi: pip install lark-oapi")

        self._app_id = app_id or os.getenv("FEISHU_APP_ID", "")
        self._app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "")
        self._ws_client: Any = None
        self._event_handler: Any = None
        self._message_callback: Callable | None = None
        self._user_name_cache: dict[str, str] = {}
        # 线程安全的消息队列
        self._message_queue: asyncio.Queue[InboundMessage] | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None

        self._verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "").strip()
        self._encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "").strip()

        # 构建 lark client
        self._client = lark.Client.builder() \
            .app_id(self._app_id) \
            .app_secret(self._app_secret) \
            .log_level(lark.LogLevel.WARNING) \
            .build()

    @property
    def name(self) -> str:
        return "feishu"

    @property
    def display_name(self) -> str:
        return "飞书"

    @property
    def capabilities(self) -> list[str]:
        return ["text", "image", "file", "audio", "interactive_card"]

    async def connect(self) -> bool:
        """启动 WebSocket 长连接"""
        if not self._app_id or not self._app_secret:
            raise ValueError("飞书 App ID / Secret 未设置")

        # 保存主事件循环引用
        self._main_loop = asyncio.get_running_loop()
        self._message_queue = asyncio.Queue()

        # 创建事件处理器
        self._event_handler = EventDispatcherHandler.builder(
            self._encrypt_key,
            self._verification_token,
        ) \
            .register_p2_im_message_receive_v1(self._on_receive_message) \
            .build()

        # 创建 WebSocket 客户端
        self._ws_client = FeishuWSClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=self._event_handler,
            log_level=lark.LogLevel.WARNING,
        )

        # 在后台线程启动 WebSocket
        t = threading.Thread(target=self._ws_client.start, daemon=True)
        t.start()

        return True

    async def disconnect(self):
        # lark_oapi WS client 没有 stop()，线程会随进程结束
        self._ws_client = None

    async def send_message(self, message: OutboundMessage) -> bool:
        """发送消息到飞书"""
        chat_id = message.chat_id

        # 判断是回复还是新消息
        if message.reply_to:
            return await self._reply_message(message.reply_to, message.content)
        else:
            return await self._create_message(chat_id, message.content)

    def on_message_callback(self, callback: Callable):
        """注册消息回调"""
        self._message_callback = callback

    async def receive_stream(self):
        """消息接收流（从队列中获取）"""
        if not self._message_queue:
            return
        while True:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    # ── 内部方法 ──────────────────────────────────────────

    def _on_receive_message(self, ctx: Any, event: Any):
        """
        收到飞书消息的回调（在 lark 后台线程中同步调用）

        使用 call_soon_threadsafe 安全地调度到主事件循环
        """
        try:
            msg_data = event.event.message
            sender_id = event.event.sender.sender_id.open_id
            chat_type = msg_data.chat_type  # "p2p" or "group"
            msg_type = msg_data.message_type  # "text", "image", etc.
            message_id = msg_data.message_id
            chat_id = msg_data.chat_id

            # 解析内容
            try:
                content = json.loads(msg_data.content)
            except (json.JSONDecodeError, TypeError):
                content = {"text": str(msg_data.content)}

            # 提取文本
            text = ""
            if msg_type == "text":
                text = content.get("text", "")
            elif msg_type == "image":
                text = content.get("image_key", "[图片]")
            elif msg_type == "audio":
                text = content.get("file_key", "[语音]")
            elif msg_type == "file":
                text = content.get("file_key", "[文件]")
            else:
                text = json.dumps(content, ensure_ascii=False)

            # 构建 InboundMessage
            inbound = InboundMessage(
                channel="feishu",
                channel_message_id=message_id,
                chat_id=sender_id if chat_type == "p2p" else chat_id,
                sender_id=sender_id,
                sender_name=self._get_user_name(sender_id),
                content=text,
                is_group=chat_type == "group",
                raw={"event": event.event.model_dump() if hasattr(event.event, "model_dump") else {}},
            )

            if msg_type == "text":
                inbound.message_type = MessageType.TEXT
            elif msg_type == "image":
                inbound.message_type = MessageType.IMAGE
            elif msg_type in ("audio", "opus"):
                inbound.message_type = MessageType.AUDIO
            elif msg_type == "file":
                inbound.message_type = MessageType.FILE
            else:
                inbound.message_type = MessageType.TEXT

            # 线程安全地调度到主事件循环
            if self._main_loop and self._main_loop.is_running():
                if self._message_callback:
                    self._main_loop.call_soon_threadsafe(
                        self._schedule_callback, inbound
                    )
                if self._message_queue:
                    self._main_loop.call_soon_threadsafe(
                        self._message_queue.put_nowait, inbound
                    )

        except Exception as e:
            print(f"❌ 飞书消息处理失败: {e}")
            import traceback
            traceback.print_exc()

    def _schedule_callback(self, inbound: InboundMessage):
        """在主事件循环中安全地调度回调"""
        if self._message_callback and self._main_loop:
            asyncio.ensure_future(self._message_callback(inbound), loop=self._main_loop)

    def _get_user_name(self, open_id: str) -> str:
        """获取用户名（缓存）"""
        if open_id in self._user_name_cache:
            return self._user_name_cache[open_id]
        short = open_id[-8:] if len(open_id) > 8 else open_id
        return f"user_{short}"

    def _create_message(self, receive_id: str, text: str) -> bool:
        """发送新消息"""
        try:
            # 判断 ID 类型
            id_type = "open_id" if receive_id.startswith("ou_") else "chat_id"

            req = CreateMessageRequest.builder() \
                .receive_id_type(id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type("text")
                    .content(json.dumps({"text": text}))
                    .build()
                ).build()

            resp = self._client.im.v1.message.create(req)
            return resp.success()
        except Exception as e:
            print(f"❌ 飞书发送失败: {e}")
            return False

    def _reply_message(self, message_id: str, text: str) -> bool:
        """回复消息"""
        try:
            req = ReplyMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .msg_type("text")
                    .content(json.dumps({"text": text}))
                    .build()
                ).build()

            resp = self._client.im.v1.message.reply(req)
            return resp.success()
        except Exception as e:
            print(f"❌ 飞书回复失败: {e}")
            return False
