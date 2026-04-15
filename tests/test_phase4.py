"""Phase 4 测试 — Gateway 多平台"""

import json
import pytest
from fastapi.testclient import TestClient

from maxbot.core.tool_registry import ToolRegistry
from maxbot.gateway.server import GatewayServer, GatewayConfig, ChatRequest
from maxbot.gateway.channels import (
    ChannelRegistry,
    HttpChannel,
    InboundMessage,
    MessageType,
    OutboundMessage,
)


# ── 测试用 registry ───────────────────────────────────────

def _make_test_registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.tool(name="echo", description="回显测试工具")
    def echo(text: str) -> str:
        return json.dumps({"echo": text})

    @reg.tool(name="add", description="加法测试工具")
    def add(a: int, b: int) -> str:
        return json.dumps({"result": a + b})

    return reg


# ── Gateway 服务测试 ──────────────────────────────────────

class TestGatewayServer:
    def test_health(self):
        server = GatewayServer(registry=_make_test_registry())
        client = TestClient(server.app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_list_tools(self):
        server = GatewayServer(registry=_make_test_registry())
        client = TestClient(server.app)
        resp = client.get("/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "echo" in names
        assert "add" in names

    def test_call_tool(self):
        server = GatewayServer(registry=_make_test_registry())
        client = TestClient(server.app)
        resp = client.post("/tools/echo/call", json={"text": "hello"})
        assert resp.status_code == 200
        assert resp.json()["echo"] == "hello"

    def test_call_tool_invalid(self):
        server = GatewayServer(registry=_make_test_registry())
        client = TestClient(server.app)
        resp = client.post("/tools/nonexistent/call", json={})
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_sessions_list(self):
        server = GatewayServer(registry=_make_test_registry())
        client = TestClient(server.app)
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_session_create_and_reset(self):
        server = GatewayServer(registry=_make_test_registry())
        client = TestClient(server.app)

        # 创建会话（通过 chat 调用）
        # 注意：没有真实 API，chat 会失败，但 session 应该被创建
        # 我们直接操作 session manager
        session = server.session_manager.get_or_create("test-session")
        assert session.session_id == "test-session"

        # 重置
        resp = client.post("/sessions/test-session/reset")
        assert resp.status_code == 200

        # 删除
        resp = client.delete("/sessions/test-session")
        assert resp.status_code == 200

    def test_api_key_auth(self):
        config = GatewayConfig(api_keys=["secret-key-123"])
        server = GatewayServer(config=config, registry=_make_test_registry())
        client = TestClient(server.app)

        # 无 key → 401
        resp = client.get("/tools")
        assert resp.status_code == 401

        # 错误 key → 401
        resp = client.get("/tools", headers={"X-Api-Key": "wrong"})
        assert resp.status_code == 401

        # 正确 key → 200
        resp = client.get("/tools", headers={"X-Api-Key": "secret-key-123"})
        assert resp.status_code == 200

    def test_health_no_auth(self):
        """health 端点不需要认证"""
        config = GatewayConfig(api_keys=["secret"])
        server = GatewayServer(config=config, registry=_make_test_registry())
        client = TestClient(server.app)
        resp = client.get("/health")
        assert resp.status_code == 200


# ── 渠道注册表测试 ────────────────────────────────────────

class TestChannelRegistry:
    def test_register_and_list(self):
        reg = ChannelRegistry()
        http = HttpChannel(name="web")
        reg.register(http)
        assert "web" in reg.list_channels()
        assert reg.get("web") is http

    def test_get_missing(self):
        reg = ChannelRegistry()
        assert reg.get("nonexistent") is None


# ── HTTP 渠道测试 ─────────────────────────────────────────

class TestHttpChannel:
    def test_properties(self):
        ch = HttpChannel(name="test", display_name="测试渠道")
        assert ch.name == "test"
        assert ch.display_name == "测试渠道"
        assert "text" in ch.capabilities

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        ch = HttpChannel()
        assert await ch.connect() is True
        await ch.disconnect()


# ── 数据模型测试 ──────────────────────────────────────────

class TestModels:
    def test_inbound_message(self):
        msg = InboundMessage(
            channel="test",
            chat_id="123",
            sender_id="456",
            message_type=MessageType.TEXT,
            content="hello",
        )
        assert msg.channel == "test"
        assert msg.is_group is False

    def test_outbound_message(self):
        msg = OutboundMessage(
            chat_id="123",
            content="reply",
            reply_to="msg-456",
        )
        assert msg.reply_to == "msg-456"

    def test_chat_request(self):
        req = ChatRequest(message="hello", session_id="s1")
        assert req.message == "hello"
        assert req.session_id == "s1"
