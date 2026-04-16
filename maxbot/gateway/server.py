"""
Gateway 服务 — HTTP/WebSocket API

参考 OpenClaw gateway/boot.ts + server-*.ts

提供：
- REST API：消息发送、会话管理、工具调用
- WebSocket：实时对话
- 多渠道消息路由
- 认证（API Key + JWT）
- Session 持久化（SQLite）
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from maxbot.core.agent_loop import Agent, AgentConfig, Message
from maxbot.core.tool_registry import ToolRegistry
from maxbot.core.memory import Memory


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
    default_model: str = "mimo-v2-pro"
    default_base_url: str | None = None
    default_api_key: str | None = None
    max_sessions: int = 100
    cors_origins: list[str] = ["*"]
    session_db_path: str | None = None  # None = 内存模式，否则 SQLite 路径


# ── 会话管理（线程安全）─────────────────────────────────

@dataclass
class Session:
    session_id: str
    agent: Agent
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0


class SessionManager:
    """管理多个 Agent 会话（线程安全 + 可选持久化）"""

    def __init__(self, config: GatewayConfig, registry: ToolRegistry):
        self.config = config
        self.registry = registry
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

        # 可选 SQLite 持久化
        self._db_conn = None
        if config.session_db_path:
            self._init_persistence(config.session_db_path)

    def _init_persistence(self, db_path: str):
        """初始化 SQLite 持久化"""
        import sqlite3
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_conn = sqlite3.connect(str(path), check_same_thread=False)
        self._db_conn.row_factory = sqlite3.Row
        self._db_conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at REAL,
                last_active REAL,
                message_count INTEGER DEFAULT 0,
                messages TEXT DEFAULT '[]'
            );
        """)
        self._db_conn.commit()

    def get_or_create(
        self,
        session_id: str | None = None,
        model: str | None = None,
    ) -> Session:
        with self._lock:
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                session.last_active = time.time()
                # 移动到末尾（LRU）
                self._sessions.move_to_end(session_id)
                return session

            # 创建新会话
            sid = session_id or str(uuid.uuid4())[:12]
            agent_config = AgentConfig(
                model=model or self.config.default_model,
                base_url=self.config.default_base_url,
                api_key=self.config.default_api_key,
            )
            agent = Agent(config=agent_config, registry=self.registry)

            # 从数据库恢复历史（如果有）
            if self._db_conn:
                row = self._db_conn.execute(
                    "SELECT messages FROM sessions WHERE session_id = ?", (sid,)
                ).fetchone()
                if row:
                    try:
                        saved_msgs = json.loads(row["messages"])
                        # 恢复消息（保持 OpenAI API 格式，在 Agent 内部存储）
                        for m in saved_msgs:
                            restored = Message(
                                role=m.get("role", "user"),
                                content=m.get("content", ""),
                                tool_calls=m.get("tool_calls", []),
                                tool_call_id=m.get("tool_call_id"),
                                name=m.get("name"),
                            )
                            agent.messages.append(restored)
                    except Exception:
                        pass

            session = Session(session_id=sid, agent=agent)
            self._sessions[sid] = session
            self._cleanup()
            return session

    def _cleanup(self):
        """清理最旧的会话"""
        if len(self._sessions) <= self.config.max_sessions:
            return
        to_remove = len(self._sessions) - self.config.max_sessions
        for _ in range(to_remove):
            sid, session = self._sessions.popitem(last=False)
            # 持久化到数据库
            self._persist_session(session)

    def _persist_session(self, session: Session):
        """保存会话到数据库"""
        if not self._db_conn:
            return
        try:
            msgs_json = json.dumps(
                [m.to_api() if hasattr(m, "to_api") else m for m in session.agent.messages],
                ensure_ascii=False,
            )
            self._db_conn.execute("""
                INSERT OR REPLACE INTO sessions (session_id, created_at, last_active, message_count, messages)
                VALUES (?, ?, ?, ?, ?)
            """, (session.session_id, session.created_at, session.last_active, session.message_count, msgs_json))
            self._db_conn.commit()
        except Exception:
            pass

    def persist_all(self):
        """持久化所有会话"""
        with self._lock:
            for session in self._sessions.values():
                self._persist_session(session)

    def list_sessions(self) -> list[SessionInfo]:
        with self._lock:
            return [
                SessionInfo(
                    session_id=s.session_id,
                    created_at=s.created_at,
                    message_count=s.message_count,
                    last_active=s.last_active,
                )
                for s in self._sessions.values()
            ]

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                self._persist_session(session)
                return True
            return False

    def __len__(self) -> int:
        return len(self._sessions)


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
        self.registry = registry or ToolRegistry()
        self.session_manager = SessionManager(self.config, self.registry)
        self.app = FastAPI(
            title="MaxBot Gateway",
            description="MaxBot 多平台消息网关",
            version="0.1.0",
        )
        self._ws_connections: dict[str, WebSocket] = {}
        self._setup_middleware()
        self._setup_routes()

        # 进程退出时持久化
        import atexit
        atexit.register(self.session_manager.persist_all)

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
            return {"status": "ok", "sessions": len(self.session_manager)}

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

                    # 调用 Agent（在线程池中运行同步代码）
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(None, session.agent.chat, user_message)

                    # 发送响应
                    await websocket.send_json({
                        "type": "response",
                        "session_id": session_id,
                        "message": response,
                    })

            except WebSocketDisconnect:
                self._ws_connections.pop(session_id, None)

        # ── 批量消息 ─────────────────────────────────────

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
