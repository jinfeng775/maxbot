#!/usr/bin/env python3
"""
MaxBot 启动脚本 — 集成飞书 WebSocket 长连接

用法：
    cd /root/maxbot
    python3 scripts/start_gateway.py

配置（从 ~/.maxbot/.env 自动加载）：
    MAXBOT_API_KEY
    MAXBOT_BASE_URL
    MAXBOT_MODEL
    FEISHU_APP_ID
    FEISHU_APP_SECRET
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from fastapi import FastAPI, Request

from maxbot.core import Agent, AgentConfig
from maxbot.tools import registry
from maxbot.gateway.server import MaxBotGateway, GatewayConfig
from maxbot.gateway.channels.base import InboundMessage, OutboundMessage, MessageType


def load_env():
    """从 ~/.maxbot/.env 加载环境变量"""
    env_path = os.path.expanduser("~/.maxbot/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()

    api_key = os.environ.get("MAXBOT_API_KEY", "")
    base_url = os.environ.get("MAXBOT_BASE_URL", "")
    model = os.environ.get("MAXBOT_MODEL", "mimo-v2-pro")
    port = int(os.environ.get("MAXBOT_PORT", "8765"))

    if not api_key:
        print("❌ 请设置 MAXBOT_API_KEY")
        sys.exit(1)

    # 创建 Gateway
    agent_config = AgentConfig(
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    
    config = GatewayConfig(
        port=port,
        agent_config=agent_config,
    )
    server = MaxBotGateway(config=config)
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
                session = server._get_agent(session_id)

                # 检查特殊命令
                content = msg.content.strip()
                if content == "/new" or content == "/reset":
                    # 重置会话
                    session.reset()
                    # 从服务器会话列表中删除（如果存在）
                    if session_id in server._sessions:
                        del server._sessions[session_id]
                    await feishu.send_message(OutboundMessage(
                        chat_id=msg.chat_id,
                        message_type=MessageType.TEXT,
                        content="✅ 会话已重置，开始新对话",
                        reply_to=msg.channel_message_id,
                    ))
                    return

                prefix = f"[来自 {msg.sender_name}] " if msg.is_group else ""
                try:
                    response = session.run(prefix + msg.content)

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

    # 微信集成
    weixin = None
    weixin_status = "❌ 未配置"

    try:
        from maxbot.gateway.channels.weixin import WeixinChannel
        weixin_cred_path = Path.home() / ".maxbot" / "weixin" / "weixin_credentials.json"
        has_weixin_env = os.environ.get("WEIXIN_ACCOUNT_ID") and os.environ.get("WEIXIN_TOKEN")
        has_weixin_cred = weixin_cred_path.exists()

        if has_weixin_env or has_weixin_cred:
            weixin = WeixinChannel()
            weixin_status = "✅ 已配置 (长轮询)"

            @app.on_event("startup")
            async def startup_weixin():
                await weixin.connect()
                print("✅ 微信长轮询已启动")

            @app.on_event("shutdown")
            async def shutdown_weixin():
                if weixin:
                    await weixin.disconnect()

            async def handle_weixin_message(msg: InboundMessage):
                """微信消息 → Agent 处理 → 回复"""
                session_id = f"weixin-{msg.chat_id}"
                session = server._get_agent(session_id)

                # 检查特殊命令
                content = msg.content.strip()
                if content == "/new" or content == "/reset":
                    # 重置会话
                    session.reset()
                    # 从服务器会话列表中删除（如果存在）
                    if session_id in server._sessions:
                        del server._sessions[session_id]
                    await weixin.send_message(OutboundMessage(
                        chat_id=msg.chat_id,
                        message_type=MessageType.TEXT,
                        content="✅ 会话已重置，开始新对话",
                    ))
                    return

                prefix = f"[群聊/{msg.sender_name}] " if msg.is_group else ""
                try:
                    response = session.run(prefix + msg.content)

                    await weixin.send_message(OutboundMessage(
                        chat_id=msg.chat_id,
                        message_type=MessageType.TEXT,
                        content=response,
                    ))
                except Exception as e:
                    print(f"❌ 微信处理失败: {e}")
                    try:
                        await weixin.send_message(OutboundMessage(
                            chat_id=msg.chat_id,
                            content=f"⚠️ 处理出错: {str(e)[:100]}",
                        ))
                    except Exception:
                        pass

            weixin.on_message_callback(handle_weixin_message)
    except ImportError as e:
        weixin_status = f"⚠️ 缺少依赖: {e}"
    except Exception as e:
        weixin_status = f"❌ 错误: {e}"

    # 启动
    print(f"""
╔══════════════════════════════════════════╗
║  🤖 MaxBot Gateway                       ║
╠══════════════════════════════════════════╣
║  模型: {model:<34}║
║  端口: {port:<34}║
║  工具: {len(registry):<34}║
║  飞书: {feishu_status:<34}║
║  微信: {weixin_status:<34}║
╠══════════════════════════════════════════╣
║  API 文档: http://localhost:{port}/docs{' ' * (12 - len(str(port)))}║
╚══════════════════════════════════════════╝
""")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

    # 使用 server.run() 启动
    # server.run()


if __name__ == "__main__":
    main()
