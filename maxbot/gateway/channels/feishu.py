"""
飞书（Feishu/Lark）渠道适配器

飞书机器人工作流程：
1. 飞书通过事件订阅把消息推送到我们的 webhook
2. 我们处理消息，通过飞书 API 回复

需要配置：
- FEISHU_APP_ID
- FEISHU_APP_SECRET
- FEISHU_VERIFICATION_TOKEN（事件验证 token）
- FEISHU_ENCRYPT_KEY（可选，消息加密 key）
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import httpx

from maxbot.gateway.channels.base import (
    ChannelAdapter,
    InboundMessage,
    MessageType,
    OutboundMessage,
)


class FeishuChannel(ChannelAdapter):
    """
    飞书机器人渠道适配器

    用法：
        channel = FeishuChannel(
            app_id="cli_xxx",
            app_secret="xxx",
        )
        await channel.connect()

        # 在 FastAPI 中挂载 webhook
        @app.post("/feishu/webhook")
        async def feishu_webhook(request: Request):
            return await channel.handle_webhook(await request.json())
    """

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
        verification_token: str | None = None,
        encrypt_key: str | None = None,
    ):
        self._app_id = app_id or os.getenv("FEISHU_APP_ID", "")
        self._app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "")
        self._verification_token = verification_token or os.getenv("FEISHU_VERIFICATION_TOKEN", "")
        self._encrypt_key = encrypt_key or os.getenv("FEISHU_ENCRYPT_KEY", "")
        self._tenant_access_token: str = ""
        self._token_expires: float = 0
        self._http: httpx.AsyncClient | None = None
        self._message_callback = None

    @property
    def name(self) -> str:
        return "feishu"

    @property
    def display_name(self) -> str:
        return "飞书"

    @property
    def capabilities(self) -> list[str]:
        return ["text", "image", "file", "interactive_card"]

    async def connect(self) -> bool:
        if not self._app_id or not self._app_secret:
            raise ValueError("飞书 App ID / Secret 未设置")
        self._http = httpx.AsyncClient(timeout=30)
        await self._refresh_token()
        return True

    async def disconnect(self):
        if self._http:
            await self._http.aclose()
            self._http = None

    async def send_message(self, message: OutboundMessage) -> bool:
        """
        发送消息到飞书

        message.chat_id 格式：
        - 用户 open_id: ou_xxx（私聊）
        - 群 chat_id: oc_xxx（群聊）
        """
        if not self._http:
            return False

        token = await self._get_token()

        if message.message_type == MessageType.TEXT:
            return await self._send_text(token, message.chat_id, message.content, message.reply_to)
        elif message.message_type == MessageType.IMAGE:
            return await self._send_image(token, message.chat_id, message.media_path)

        # 默认当文本发
        return await self._send_text(token, message.chat_id, message.content, message.reply_to)

    async def handle_webhook(self, event: dict) -> dict:
        """
        处理飞书 webhook 事件

        返回响应（飞书要求返回 JSON）
        """
        # 1. URL 验证 challenge
        if "challenge" in event:
            return {"challenge": event["challenge"]}

        # 2. 事件去重（header.event_id）
        header = event.get("header", {})
        event_type = header.get("event_type", "")

        # 3. 处理消息事件
        if event_type == "im.message.receive_v1":
            msg = await self._parse_message_event(event)
            if msg and self._message_callback:
                await self._message_callback(msg)

        return {"code": 0}

    def on_message_callback(self, callback):
        """注册消息回调"""
        self._message_callback = callback

    # ── 内部方法 ──────────────────────────────────────────

    async def _refresh_token(self):
        """获取 tenant_access_token"""
        if not self._http:
            return

        resp = await self._http.post(
            f"{self.BASE_URL}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self._app_id,
                "app_secret": self._app_secret,
            },
        )
        data = resp.json()
        if data.get("code") == 0:
            self._tenant_access_token = data["tenant_access_token"]
            self._token_expires = time.time() + data.get("expire", 7200) - 60
        else:
            raise ValueError(f"飞书认证失败: {data}")

    async def _get_token(self) -> str:
        if time.time() >= self._token_expires:
            await self._refresh_token()
        return self._tenant_access_token

    async def _send_text(
        self,
        token: str,
        receive_id: str,
        text: str,
        message_id: str | None = None,
    ) -> bool:
        """发送文本消息"""
        if not self._http:
            return False

        # 判断 receive_id 类型
        id_type = "open_id" if receive_id.startswith("ou_") else "chat_id"

        body: dict[str, Any] = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }

        try:
            resp = await self._http.post(
                f"{self.BASE_URL}/im/v1/messages?receive_id_type={id_type}",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
            data = resp.json()
            return data.get("code") == 0
        except Exception as e:
            print(f"❌ 飞书发送失败: {e}")
            return False

    async def _send_image(self, token: str, receive_id: str, image_path: str) -> bool:
        """发送图片（需先上传获取 image_key）"""
        # TODO: 实现图片上传 + 发送
        return await self._send_text(token, receive_id, f"[图片: {image_path}]")

    async def _parse_message_event(self, event: dict) -> InboundMessage | None:
        """解析飞书消息事件为 InboundMessage"""
        try:
            event_data = event.get("event", {})
            message_data = event_data.get("message", {})
            sender_data = event_data.get("sender", {}).get("sender_id", {})

            msg_type = message_data.get("message_type", "text")
            content_str = message_data.get("content", "{}")
            try:
                content = json.loads(content_str)
            except json.JSONDecodeError:
                content = {"text": content_str}

            msg = InboundMessage(
                channel="feishu",
                channel_message_id=message_data.get("message_id", ""),
                chat_id=sender_data.get("open_id", ""),
                sender_id=sender_data.get("open_id", ""),
                sender_name=sender_data.get("open_id", ""),  # 需要额外 API 获取昵称
                content=content.get("text", ""),
                is_group=message_data.get("chat_type") == "group",
                raw=event,
            )

            # 群聊时 chat_id 用群 ID
            if msg.is_group:
                msg.chat_id = message_data.get("chat_id", "")

            if msg_type == "text":
                msg.message_type = MessageType.TEXT
            elif msg_type == "image":
                msg.message_type = MessageType.IMAGE
                msg.content = content.get("image_key", "")
            elif msg_type == "file":
                msg.message_type = MessageType.FILE
                msg.content = content.get("file_key", "")
            elif msg_type == "audio":
                msg.message_type = MessageType.AUDIO
            else:
                msg.message_type = MessageType.TEXT
                msg.content = content.get("text", json.dumps(content, ensure_ascii=False))

            return msg

        except Exception as e:
            print(f"⚠️ 飞书消息解析失败: {e}")
            return None
