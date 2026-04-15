#!/usr/bin/env python3
"""
MaxBot 启动脚本 — 集成飞书 WebSocket 长连接

用法：
    cd /root/maxbot
    python3 scripts/start_gateway.py

配置（从 ~/.hermes/.env 自动加载）：
    XIAOMI_API_KEY / OPENAI_API_KEY
    XIAOMI_BASE_URL / OPENAI_BASE_URL
    FEISHU_APP_ID
    FEISHU_APP_SECRET
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from fastapi import FastAPI, Request

from maxbot.core import Agent, AgentConfig
from maxbot.tools import registry
from maxbot.gateway.server import GatewayServer, GatewayConfig
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

    api_key = os.environ.get("XIAOMI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("XIAOMI_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("MAXBOT_MODEL", "mimo-v2-pro")
    port = int(os.environ.get("MAXBOT_PORT", "8765"))

    if not api_key:
        print("❌ 请设置 XIAOMI_API_KEY 或 OPENAI_API_KEY")
        sys.exit(1)

    # 创建 Gateway
    config = GatewayConfig(
        port=port,
        default_model=model,
        default_base_url=base_url,
        default_api_key=api_key,
    )
    server = GatewayServer(config=config, registry=registry)
    app = server.app

    # 飞书集成
    feishu = None
    feishu_status = "❌ 未配置"

    try:
        from maxbot.gateway.channels.feishu import FeishuChannel
        if os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET"):
            feishu = FeishuChannel()
            feishu_status = "✅ 已配置 (WebSocket)"

            @app.on_event("startup")
            async def startup_feishu():
                await feishu.connect()
                print("✅ 飞书 WebSocket 长连接已建立")

            @app.on_event("shutdown")
            async def shutdown_feishu():
                if feishu:
                    await feishu.disconnect()

            async def handle_feishu_message(msg: InboundMessage):
                """飞书消息 → Agent 处理 → 回复"""
                session_id = f"feishu-{msg.chat_id}"
                session = server.session_manager.get_or_create(session_id)

                prefix = f"[来自 {msg.sender_name}] " if msg.is_group else ""
                try:
                    response = session.agent.chat(prefix + msg.content)
                    session.message_count += 1

                    await feishu.send_message(OutboundMessage(
                        chat_id=msg.chat_id,
                        message_type=MessageType.TEXT,
                        content=response,
                        reply_to=msg.channel_message_id,
                    ))
                except Exception as e:
                    print(f"❌ 飞书处理失败: {e}")
                    try:
                        await feishu.send_message(OutboundMessage(
                            chat_id=msg.chat_id,
                            content=f"⚠️ 处理出错: {str(e)[:100]}",
                        ))
                    except Exception:
                        pass

            feishu.on_message_callback(handle_feishu_message)
    except ImportError:
        feishu_status = "⚠️ 缺少 lark-oapi（pip install lark-oapi）"
    except Exception as e:
        feishu_status = f"❌ 错误: {e}"

    # 启动
    print(f"""
╔══════════════════════════════════════════╗
║  🤖 MaxBot Gateway                       ║
╠══════════════════════════════════════════╣
║  模型: {model:<34}║
║  端口: {port:<34}║
║  工具: {len(registry):<34}║
║  飞书: {feishu_status:<34}║
╠══════════════════════════════════════════╣
║  API 文档: http://localhost:{port}/docs{' ' * (12 - len(str(port)))}║
╚══════════════════════════════════════════╝
""")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
