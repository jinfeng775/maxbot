"""
Gateway 多平台网关 — 参考 OpenClaw gateway/ + channels/

结构：
- HTTP/WS API 服务（FastAPI）
- 消息路由（chat_id → Agent 实例）
- 渠道适配器基类 + 实现
- 会话管理
- 认证鉴权
"""

from maxbot.gateway.server import MaxBotGateway, create_gateway
from maxbot.gateway.auth import AuthManager

app = None

__all__ = ["MaxBotGateway", "create_gateway", "app", "AuthManager"]
