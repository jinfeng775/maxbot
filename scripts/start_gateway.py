#!/usr/bin/env python3
"""
MaxBot Gateway 启动脚本 — 集成飞书渠道

用法：
    # 设置环境变量
    export XIAOMI_API_KEY="你的key"
    export XIAOMI_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
    export FEISHU_APP_ID="cli_xxx"
    export FEISHU_APP_SECRET="xxx"

    # 启动
    python3 scripts/start_gateway.py

    # 飞书 webhook 地址：
    # http://你的公网IP:8765/feishu/webhook
"""

import asyncio
import json
import os
import sys

# 确保 maxbot 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from fastapi import FastAPI, Request

from maxbot.core import Agent, AgentConfig
from maxbot.core.context import ContextManager
from maxbot.tools import registry
from maxbot.gateway.server import GatewayServer, GatewayConfig
from maxbot.gateway.channels.feishu import FeishuChannel
from maxbot.gateway.channels.base import InboundMessage, OutboundMessage, MessageType


def load_env():
    """从 ~/.hermes/.env 加载环境变量"""
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()

    # ── API 配置 ──────────────────────────────────────────
    api_key = os.environ.get("XIAOMI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("XIAOMI_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("MAXBOT_MODEL", "mimo-v2-pro")
    port = int(os.environ.get("MAXBOT_PORT", "8765"))

    if not api_key:
        print("❌ 请设置 XIAOMI_API_KEY 或 OPENAI_API_KEY")
        sys.exit(1)

    # ── 创建 Gateway ─────────────────────────────────────
    config = GatewayConfig(
        port=port,
        default_model=model,
        default_base_url=base_url,
        default_api_key=api_key,
    )
    server = GatewayServer(config=config, registry=registry)
    app = server.app

    # ── 飞书集成 ─────────────────────────────────────────
    feishu = None
    if os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET"):
        feishu = FeishuChannel()
        print("✅ 飞书渠道已配置")

        @app.on_event("startup")
        async def startup_feishu():
            await feishu.connect()
            print("✅ 飞书已连接")

        @app.on_event("shutdown")
        async def shutdown_feishu():
            await feishu.disconnect()

        # 飞书消息处理
        async def handle_feishu_message(msg: InboundMessage):
            """收到飞书消息 → Agent 处理 → 回复"""
            session_id = f"feishu-{msg.chat_id}"
            session = server.session_manager.get_or_create(session_id)

            # 注入飞书上下文
            context_prefix = ""
            if msg.is_group:
                context_prefix = f"[飞书群消息 from {msg.sender_name}]\n"

            try:
                response = session.agent.chat(context_prefix + msg.content)
                session.message_count += 1

                # 回复飞书
                await feishu.send_message(OutboundMessage(
                    chat_id=msg.chat_id,
                    message_type=MessageType.TEXT,
                    content=response,
                    reply_to=msg.channel_message_id,
                ))
            except Exception as e:
                print(f"❌ 飞书处理失败: {e}")
                await feishu.send_message(OutboundMessage(
                    chat_id=msg.chat_id,
                    content=f"⚠️ 处理出错: {str(e)[:100]}",
                ))

        feishu.on_message_callback(handle_feishu_message)

        # 飞书 webhook 端点
        @app.post("/feishu/webhook")
        async def feishu_webhook(request: Request):
            body = await request.json()
            return await feishu.handle_webhook(body)

    # ── 启动 ─────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════╗
║  🤖 MaxBot Gateway                       ║
╠══════════════════════════════════════════╣
║  模型: {model:<34}║
║  端口: {port:<34}║
║  工具: {len(registry):<34}║
║  飞书: {'✅ 已配置' if feishu else '❌ 未配置':<32}║
╠══════════════════════════════════════════╣
║  API 文档: http://localhost:{port}/docs{' ' * (12 - len(str(port)))}║
║  健康检查: http://localhost:{port}/health{' ' * (10 - len(str(port)))}║
{'║  飞书 Webhook: http://YOUR_IP:{port}/feishu/webhook  ║' if feishu else ''}
╚══════════════════════════════════════════╝
""")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
