"""
网关系统 - HTTP/WebSocket Gateway

提供 HTTP 和 WebSocket 接口，支持多平台接入
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.multi_agent.coordinator import Coordinator
from maxbot.gateway.auth import AuthManager
from maxbot.utils.logger import get_logger

# 获取网关日志器
logger = get_logger("gateway")

# 创建 FastAPI 应用
app = FastAPI(title="MaxBot Gateway", version="1.0.0")

# 全局认证管理器
auth_manager = AuthManager()


# ==================== 认证依赖 ====================

async def verify_api_key(x_api_key: str | None = Header(None)) -> bool:
    """
    验证 API Key 依赖

    Args:
        x_api_key: X-API-Key 请求头

    Raises:
        HTTPException: 认证失败
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key")

    if not auth_manager.verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="无效的 API Key")

    return True


async def verify_token(x_token: str | None = Header(None)) -> bool:
    """
    验证 Token 依赖

    Args:
        x_token: X-Token 请求头

    Raises:
        HTTPException: 认证失败
    """
    if not x_token:
        raise HTTPException(status_code=401, detail="缺少 Token")

    if not auth_manager.verify_token(x_token):
        raise HTTPException(status_code=401, detail="无效或过期的 Token")

    return True


# ==================== 错误处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    全局异常处理器

    Args:
        request: 请求
        exc: 异常

    Returns:
        错误响应
    """
    logger.error(f"未处理的异常: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
    )


# ==================== 数据模型 ====================

class MessageRequest(BaseModel):
    """消息请求"""
    message: str
    session_id: str | None = None
    skills_enabled: bool = True


class MessageResponse(BaseModel):
    """消息响应"""
    success: bool
    response: str
    session_id: str
    error: str | None = None


class TaskRequest(BaseModel):
    """任务请求"""
    description: str
    agent_type: str = "worker"
    priority: int = 0


class TaskResponse(BaseModel):
    """任务响应"""
    success: bool
    task_id: str
    error: str | None = None


# ==================== 网关配置 ====================

@dataclass
class GatewayConfig:
    """网关配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    agent_config: AgentConfig | None = None
    coordinator_enabled: bool = False
    max_workers: int = 4


# ==================== 网关类 ====================

class MaxBotGateway:
    """
    MaxBot 网关

    功能：
    - HTTP API
    - WebSocket 连接
    - 会话管理
    - 多 Agent 协作
    """

    def __init__(self, config: GatewayConfig):
        """
        初始化网关

        Args:
            config: 网关配置
        """
        self.config = config
        self._sessions: dict[str, Agent] = {}
        self._coordinator: Coordinator | None = None

        # 初始化协调器
        if config.coordinator_enabled:
            self._coordinator = Coordinator(max_workers=config.max_workers)
            logger.info("协调器已启用")

        # 注册路由
        self._register_routes()

        logger.info(f"网关初始化成功: {config.host}:{config.port}")

    def _get_agent(self, session_id: str | None) -> Agent:
        """
        获取或创建 Agent

        Args:
            session_id: 会话 ID

        Returns:
            Agent 实例
        """
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        # 创建新的 Agent
        agent_config = self.config.agent_config or AgentConfig()
        agent = Agent(config=agent_config, session_id=session_id)

        if session_id:
            self._sessions[session_id] = agent

        return agent

    def _register_routes(self):
        """注册路由"""

        @app.get("/")
        async def root():
            """根路径"""
            return {
                "name": "MaxBot Gateway",
                "version": "1.0.0",
                "status": "running",
            }

        @app.post("/auth/token")
        async def generate_token(request: dict):
            """
            生成 Token

            使用 API Key 生成访问 Token
            """
            try:
                api_key = request.get("api_key")
                ttl = request.get("ttl")

                if not api_key:
                    raise HTTPException(status_code=400, detail="缺少 API Key")

                token = auth_manager.generate_token(api_key, ttl=ttl)

                return {
                    "success": True,
                    "token": token,
                    "message": "Token 生成成功",
                }

            except ValueError as e:
                raise HTTPException(status_code=401, detail=str(e))
            except Exception as e:
                logger.error(f"生成 Token 失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/auth/verify", dependencies=[Depends(verify_api_key)])
        async def verify_api_key_endpoint():
            """验证 API Key"""
            return {"success": True, "message": "API Key 有效"}

        @app.get("/auth/stats", dependencies=[Depends(verify_api_key)])
        async def get_auth_stats():
            """获取认证统计信息"""
            return auth_manager.get_stats()

        @app.post("/chat", response_model=MessageResponse, dependencies=[Depends(verify_api_key)])
        async def chat(request: MessageRequest):
            """
            聊天接口

            处理用户消息，返回 Agent 响应
            """
            try:
                logger.info(f"收到消息: {request.message[:50]}...")

                # 获取 Agent
                agent = self._get_agent(request.session_id)

                # 执行消息
                response = agent.run(request.message)

                return MessageResponse(
                    success=True,
                    response=response,
                    session_id=agent.config.session_id or "",
                )

            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                return MessageResponse(
                    success=False,
                    response="",
                    session_id=request.session_id or "",
                    error=str(e),
                )

        @app.get("/sessions", dependencies=[Depends(verify_api_key)])
        async def list_sessions():
            """列出所有会话"""
            return {
                "total_sessions": len(self._sessions),
                "sessions": list(self._sessions.keys()),
            }

        @app.delete("/sessions/{session_id}", dependencies=[Depends(verify_api_key)])
        async def delete_session(session_id: str):
            """删除会话"""
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"会话已删除: {session_id}")
                return {"success": True}
            else:
                return {"success": False, "error": "会话不存在"}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            WebSocket 端点

            支持实时双向通信和心跳机制
            """
            await websocket.accept()
            session_id = None
            agent: Agent | None = None
            last_ping = asyncio.get_event_loop().time()
            heartbeat_task = None

            logger.info("WebSocket 连接已建立")

            async def send_heartbeat():
                """发送心跳"""
                while True:
                    try:
                        await asyncio.sleep(30)  # 每 30 秒发送一次心跳
                        await websocket.send_json({"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})
                    except:
                        break

            try:
                heartbeat_task = asyncio.create_task(send_heartbeat())

                while True:
                    # 接收消息
                    data = await websocket.receive_text()
                    message_data = json.loads(data)

                    # 处理心跳
                    if message_data.get("type") == "pong":
                        last_ping = asyncio.get_event_loop().time()
                        continue

                    # 处理聊天消息
                    message = message_data.get("message", "")
                    session_id = message_data.get("session_id")

                    # 获取 Agent
                    agent = self._get_agent(session_id)

                    # 执行消息
                    response = agent.run(message)

                    # 发送响应
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
                    await websocket.send_json({
                        "type": "error",
                        "success": False,
                        "error": str(e),
                        "timestamp": asyncio.get_event_loop().time(),
                    })
                except:
                    pass
            finally:
                if heartbeat_task:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

        @app.get("/stats", dependencies=[Depends(verify_api_key)])
        async def get_stats():
            """获取统计信息"""
            stats = {
                "total_sessions": len(self._sessions),
                "coordinator_enabled": self.config.coordinator_enabled,
            }

            if self._coordinator:
                stats["coordinator"] = self._coordinator.get_stats()

            return stats

    def run(self):
        """运行网关"""
        import uvicorn

        logger.info(f"启动网关: {self.config.host}:{self.config.port}")

        uvicorn.run(
            app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )


# ==================== 便捷函数 ====================

def create_gateway(
    host: str = "0.0.0.0",
    port: int = 8000,
    agent_config: AgentConfig | None = None,
    coordinator_enabled: bool = False,
    max_workers: int = 4,
) -> MaxBotGateway:
    """
    创建网关

    Args:
        host: 监听地址
        port: 监听端口
        agent_config: Agent 配置
        coordinator_enabled: 是否启用协调器
        max_workers: 最大 Worker 数

    Returns:
        网关实例
    """
    config = GatewayConfig(
        host=host,
        port=port,
        agent_config=agent_config,
        coordinator_enabled=coordinator_enabled,
        max_workers=max_workers,
    )

    return MaxBotGateway(config)
