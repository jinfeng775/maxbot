"""网关系统 - HTTP/WebSocket Gateway 与兼容接口"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.gateway.auth import AuthManager
from maxbot.multi_agent.coordinator import Coordinator
from maxbot.utils.logger import get_logger

logger = get_logger("gateway")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class MessageRequest(ChatRequest):
    skills_enabled: bool = True


class MessageResponse(BaseModel):
    success: bool
    response: str
    session_id: str
    error: str | None = None


class TaskRequest(BaseModel):
    description: str
    agent_type: str = "worker"
    priority: int = 0


class TaskResponse(BaseModel):
    success: bool
    task_id: str
    error: str | None = None


@dataclass
class GatewayConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    agent_config: AgentConfig | None = None
    coordinator_enabled: bool = False
    max_workers: int = 4
    api_keys: list[str] | None = None


class _SessionManagerCompat:
    def __init__(self, gateway: "GatewayServer"):
        self.gateway = gateway

    def get_or_create(self, session_id: str):
        return self.gateway._get_agent(session_id)

    def reset(self, session_id: str) -> bool:
        agent = self.gateway._sessions.get(session_id)
        if not agent:
            return False
        agent.reset()
        return True

    def delete(self, session_id: str) -> bool:
        return self.gateway._delete_session(session_id)


class GatewayServer:
    def __init__(
        self,
        config: GatewayConfig | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.config = config or GatewayConfig()
        self.registry = registry or ToolRegistry()
        self._sessions: dict[str, Agent] = {}
        self._coordinator: Coordinator | None = None
        self.auth_manager = AuthManager()
        for api_key in self.config.api_keys or []:
            self.auth_manager.add_api_key(api_key)
        self.session_manager = _SessionManagerCompat(self)
        self.app = FastAPI(title="MaxBot Gateway", version="1.0.0")

        if self.config.coordinator_enabled:
            self._coordinator = Coordinator(max_workers=self.config.max_workers)
            logger.info("协调器已启用")

        self._register_routes()
        logger.info(f"网关初始化成功: {self.config.host}:{self.config.port}")

    def _require_api_key(self, x_api_key: str | None):
        if not (self.config.api_keys or []):
            return
        if not x_api_key:
            raise HTTPException(status_code=401, detail="缺少 API Key")
        if not self.auth_manager.verify_api_key(x_api_key):
            raise HTTPException(status_code=401, detail="无效的 API Key")

    def _get_agent(self, session_id: str | None) -> Agent:
        sid = session_id or "default-session"
        if sid in self._sessions:
            return self._sessions[sid]
        agent_config = self.config.agent_config or AgentConfig(api_key="test-key", skills_enabled=False)
        if agent_config.api_key is None:
            agent_config.api_key = "test-key"
        agent = Agent(config=agent_config, session_id=sid)
        agent.session_id = sid
        self._sessions[sid] = agent
        return agent

    def _delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def _register_routes(self):
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request, exc):
            logger.error(f"未处理的异常: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": str(exc), "error_type": type(exc).__name__},
            )

        @self.app.get("/")
        async def root():
            return {"name": "MaxBot Gateway", "version": "1.0.0", "status": "running"}

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "name": "MaxBot Gateway"}

        @self.app.get("/tools")
        async def list_tools(x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            return [
                {"name": tool.name, "description": tool.description}
                for tool in self.registry.list_tools()
            ]

        @self.app.post("/tools/{name}/call")
        async def call_tool(name: str, payload: dict[str, Any], x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            try:
                return json.loads(self.registry.call(name, payload))
            except Exception:
                return {"error": f"未知工具: {name}"}

        @self.app.post("/auth/token")
        async def generate_token(request: dict[str, Any]):
            api_key = request.get("api_key")
            ttl = request.get("ttl")
            if not api_key:
                raise HTTPException(status_code=400, detail="缺少 API Key")
            token = self.auth_manager.generate_token(api_key, ttl=ttl)
            return {"success": True, "token": token, "message": "Token 生成成功"}

        @self.app.post("/chat")
        async def chat(request: MessageRequest, x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            try:
                agent = self._get_agent(request.session_id)
                response = agent.run(request.message)
                return MessageResponse(success=True, response=response, session_id=agent.config.session_id or "")
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                return MessageResponse(success=False, response="", session_id=request.session_id or "", error=str(e))

        @self.app.get("/sessions")
        async def list_sessions_route(x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            return [] if not self._sessions else [
                {"session_id": session_id} for session_id in self._sessions.keys()
            ]

        @self.app.post("/sessions/{session_id}/reset")
        async def reset_session(session_id: str, x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            if session_id not in self._sessions:
                self._get_agent(session_id)
            self._sessions[session_id].reset()
            return {"success": True}

        @self.app.delete("/sessions/{session_id}")
        async def delete_session(session_id: str, x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            return {"success": self._delete_session(session_id)}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            heartbeat_task = None
            try:
                async def send_heartbeat():
                    while True:
                        try:
                            await asyncio.sleep(30)
                            await websocket.send_json({"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})
                        except Exception:
                            break

                heartbeat_task = asyncio.create_task(send_heartbeat())
                while True:
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    if message_data.get("type") == "pong":
                        continue
                    message = message_data.get("message", "")
                    session_id = message_data.get("session_id")
                    agent = self._get_agent(session_id)
                    response = agent.run(message)
                    await websocket.send_json({
                        "type": "response",
                        "success": True,
                        "response": response,
                        "session_id": agent.config.session_id or "",
                        "timestamp": asyncio.get_event_loop().time(),
                    })
            except WebSocketDisconnect:
                logger.info("WebSocket 连接已断开")
            except Exception as e:
                logger.error(f"WebSocket 错误: {e}")
                try:
                    await websocket.send_json({"type": "error", "success": False, "error": str(e)})
                except Exception:
                    pass
            finally:
                if heartbeat_task:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

        @self.app.get("/stats")
        async def get_stats(x_api_key: str | None = Header(None, alias="X-Api-Key")):
            self._require_api_key(x_api_key)
            stats = {"total_sessions": len(self._sessions), "coordinator_enabled": self.config.coordinator_enabled}
            if self._coordinator:
                stats["coordinator"] = self._coordinator.get_stats()
            return stats

    def run(self):
        import uvicorn
        logger.info(f"启动网关: {self.config.host}:{self.config.port}")
        uvicorn.run(self.app, host=self.config.host, port=self.config.port, log_level="info")


class MaxBotGateway(GatewayServer):
    pass


def create_gateway(
    host: str = "0.0.0.0",
    port: int = 8000,
    agent_config: AgentConfig | None = None,
    coordinator_enabled: bool = False,
    max_workers: int = 4,
) -> MaxBotGateway:
    config = GatewayConfig(
        host=host,
        port=port,
        agent_config=agent_config,
        coordinator_enabled=coordinator_enabled,
        max_workers=max_workers,
    )
    return MaxBotGateway(config)
