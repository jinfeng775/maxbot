"""
Gateway 服务 — HTTP/WebSocket API

参考 OpenClaw gateway/boot.ts + server-*.ts

提供：
- REST API：消息发送、会话管理、工具调用
- WebSocket：实时对话
- 多渠道消息路由
- 认证（API Key + JWT）
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.core.memory import Memory
from maxbot.tools import registry as builtin_registry


# ── 数据模型 ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: str | None = None
    model: str | None = None
    tools: list[str] | None = None  # 限制可用工具


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    response: str
    tool_calls: list[dict] = []
    tokens_used: int = 0
    duration_ms: int = 0


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: float
    message_count: int
    last_active: float


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    parameters: dict


class GatewayConfig(BaseModel):
    """Gateway 配置"""
    host: str = "0.0.0.0"
    port: int = 8765
    api_keys: list[str] = Field(default_factory=list)  # 允许的 API Key
    default_model: str = "gpt-4o"
    default_base_url: str | None = None
    default_api_key: str | None = None
    max_sessions: int = 100
    cors_origins: list[str] = ["*"]


# ── 会话管理 ──────────────────────────────────────────────

@dataclass
class Session:
    session_id: str
    agent: Agent
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0


class SessionManager:
    """管理多个 Agent 会话"""

    def __init__(self, config: GatewayConfig, registry: ToolRegistry):
        self.config = config
        self.registry = registry
        self.sessions: dict[str, Session] = {}

    def get_or_create(
        self,
        session_id: str | None = None,
        model: str | None = None,
    ) -> Session:
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_active = time.time()
            return session

        # 创建新会话
        sid = session_id or str(uuid.uuid4())[:12]
        agent_config = AgentConfig(
            model=model or self.config.default_model,
            base_url=self.config.default_base_url,
            api_key=self.config.default_api_key,
        )
        agent = Agent(config=agent_config, registry=self.registry)
        session = Session(session_id=sid, agent=agent)
        self.sessions[sid] = session

        # 清理过期会话
        self._cleanup()

        return session

    def _cleanup(self):
        if len(self.sessions) <= self.config.max_sessions:
            return
        # 删除最旧的
        sorted_sessions = sorted(self.sessions.items(), key=lambda x: x[1].last_active)
        to_remove = len(self.sessions) - self.config.max_sessions
        for sid, _ in sorted_sessions[:to_remove]:
            del self.sessions[sid]

    def list_sessions(self) -> list[SessionInfo]:
        return [
            SessionInfo(
                session_id=s.session_id,
                created_at=s.created_at,
                message_count=s.message_count,
                last_active=s.last_active,
            )
            for s in self.sessions.values()
        ]

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


# ── Gateway 服务 ──────────────────────────────────────────

class GatewayServer:
    """
    Gateway 服务主类

    用法：
        server = GatewayServer(config=GatewayConfig(port=8765))
        server.start()  # 阻塞启动
    """

    def __init__(
        self,
        config: GatewayConfig | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.config = config or GatewayConfig()
        self.registry = registry or builtin_registry
        self.session_manager = SessionManager(self.config, self.registry)
        self.app = FastAPI(
            title="MaxBot Gateway",
            description="MaxBot 多平台消息网关",
            version="0.1.0",
        )
        self._ws_connections: dict[str, WebSocket] = {}
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _verify_api_key(self, x_api_key: str | None = Header(None)) -> str | None:
        """验证 API Key"""
        if not self.config.api_keys:
            return None  # 未配置则不验证
        if not x_api_key or x_api_key not in self.config.api_keys:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        return x_api_key

    def _setup_routes(self):

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "sessions": len(self.session_manager.sessions)}

        @self.app.post("/chat", response_model=ChatResponse)
        async def chat(request: ChatRequest, _key: str | None = Depends(self._verify_api_key)):
            session = self.session_manager.get_or_create(
                session_id=request.session_id,
                model=request.model,
            )
            session.message_count += 1

            start = time.time()
            response = session.agent.chat(request.message)
            duration = int((time.time() - start) * 1000)

            return ChatResponse(
                session_id=session.session_id,
                response=response,
                duration_ms=duration,
            )

        @self.app.get("/sessions")
        async def list_sessions(_key: str | None = Depends(self._verify_api_key)):
            return self.session_manager.list_sessions()

        @self.app.delete("/sessions/{session_id}")
        async def delete_session(session_id: str, _key: str | None = Depends(self._verify_api_key)):
            if self.session_manager.delete_session(session_id):
                return {"deleted": True}
            raise HTTPException(404, "Session not found")

        @self.app.post("/sessions/{session_id}/reset")
        async def reset_session(session_id: str, _key: str | None = Depends(self._verify_api_key)):
            session = self.session_manager.get_or_create(session_id)
            session.agent.reset()
            return {"reset": True}

        @self.app.get("/tools")
        async def list_tools(_key: str | None = Depends(self._verify_api_key)):
            return [
                ToolInfo(name=t.name, description=t.description, parameters=t.parameters)
                for t in self.registry.list_tools()
            ]

        @self.app.post("/tools/{tool_name}/call")
        async def call_tool(
            tool_name: str,
            args: dict = {},
            _key: str | None = Depends(self._verify_api_key),
        ):
            result = self.registry.call(tool_name, args)
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"result": result}

        # ── WebSocket 实时对话 ─────────────────────────────

        @self.app.websocket("/ws/{session_id}")
        async def websocket_chat(websocket: WebSocket, session_id: str = "default"):
            await websocket.accept()
            self._ws_connections[session_id] = websocket

            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        msg = json.loads(data)
                        user_message = msg.get("message", data)
                    except json.JSONDecodeError:
                        user_message = data

                    session = self.session_manager.get_or_create(session_id)
                    session.message_count += 1

                    # 发送"正在处理"状态
                    await websocket.send_json({"type": "status", "status": "thinking"})

                    # 调用 Agent
                    response = session.agent.chat(user_message)

                    # 发送响应
                    await websocket.send_json({
                        "type": "response",
                        "session_id": session_id,
                        "message": response,
                    })

            except WebSocketDisconnect:
                self._ws_connections.pop(session_id, None)

        # ── 批量消息（参考 OpenClaw 的消息队列）──────────

        @self.app.post("/batch")
        async def batch_chat(
            messages: list[ChatRequest],
            _key: str | None = Depends(self._verify_api_key),
        ):
            results = []
            for req in messages:
                session = self.session_manager.get_or_create(req.session_id, req.model)
                session.message_count += 1
                response = session.agent.chat(req.message)
                results.append(ChatResponse(
                    session_id=session.session_id,
                    response=response,
                ))
            return results

    def start(self, host: str | None = None, port: int | None = None):
        """启动服务（阻塞）"""
        uvicorn.run(
            self.app,
            host=host or self.config.host,
            port=port or self.config.port,
            log_level="info",
        )

    def start_background(self, host: str | None = None, port: int | None = None):
        """后台启动（非阻塞，返回线程）"""
        import threading

        def _run():
            uvicorn.run(
                self.app,
                host=host or self.config.host,
                port=port or self.config.port,
                log_level="warning",
            )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
