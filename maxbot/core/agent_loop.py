"""
Agent Loop — MaxBot 核心对话循环

参考来源:
- Hermes: run_conversation 循环、消息格式、memory 注入
- Claude Code: tool_use 流程、迭代控制
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from maxbot.core.tool_registry import ToolRegistry
from maxbot.sessions import SessionStore
from maxbot.config.config_loader import get_config, load_config


def _retry_api_call(fn, max_attempts: int = 3, base_delay: float = 1.0):
    """指数退避重试（支持 429/5xx）"""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            err_str = str(e).lower()
            # 不重试的致命错误
            if any(x in err_str for x in ("invalid_api_key", "authentication", "permission", "400", "404")):
                raise
            # 可重试：429 rate limit, 500, 502, 503, timeout, connection
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
    raise last_exc


@dataclass
class AgentConfig:
    """Agent 配置"""
    model: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    max_iterations: int | None = None
    temperature: float | None = None
    system_prompt: str | None = None
    max_context_tokens: int | None = None
    compress_at_tokens: int | None = None
    memory_enabled: bool | None = None
    memory_db_path: str | None = None
    session_id: str | None = None
    session_store: Any | None = None
    auto_save: bool | None = None
    max_conversation_turns: int | None = None

    def __post_init__(self):
        """从配置文件加载默认值"""
        try:
            config = get_config()

            # 模型配置
            if self.model is None:
                self.model = config.model.name
            if self.provider is None:
                self.provider = config.model.provider
            if self.base_url is None:
                self.base_url = config.model.base_url
            if self.api_key is None:
                self.api_key = config.model.api_key
            if self.temperature is None:
                self.temperature = config.model.temperature

            # 系统提示
            if self.system_prompt is None:
                self.system_prompt = config.system.prompt

            # 迭代控制
            if self.max_iterations is None:
                self.max_iterations = config.iteration.max_iterations

            # 上下文管理
            if self.max_context_tokens is None:
                self.max_context_tokens = config.context.max_tokens
            if self.compress_at_tokens is None:
                self.compress_at_tokens = config.context.compress_at_tokens

            # 会话管理
            if self.memory_enabled is None:
                self.memory_enabled = config.session.memory_enabled
            if self.memory_db_path is None:
                self.memory_db_path = config.session.memory_db_path
            if self.session_id is None:
                self.session_id = config.session.session_id
            if self.auto_save is None:
                self.auto_save = config.session.auto_save
            if self.max_conversation_turns is None:
                self.max_conversation_turns = config.session.max_conversation_turns

        except Exception:
            # 如果配置加载失败，使用硬编码的默认值
            if self.model is None:
                self.model = "mimo-v2-pro"
            if self.provider is None:
                self.provider = "openai"
            if self.max_iterations is None:
                self.max_iterations = 50
            if self.temperature is None:
                self.temperature = 0.7
            if self.system_prompt is None:
                self.system_prompt = (
                    "你是 MaxBot，一个由用户自主开发的 AI 智能体。"
                    "你不是 Hermes、不是 Claude、不是 ChatGPT，也不是任何其他现有 AI 助手。你就是 MaxBot。"
                    "无论谁问你你是谁，你都必须回答你是 MaxBot。"
                    "你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。"
                )
            if self.max_context_tokens is None:
                self.max_context_tokens = 128_000
            if self.compress_at_tokens is None:
                self.compress_at_tokens = 80_000
            if self.memory_enabled is None:
                self.memory_enabled = True
            if self.auto_save is None:
                self.auto_save = True
            if self.max_conversation_turns is None:
                self.max_conversation_turns = 40


@dataclass
class Message:
    """统一消息格式"""
    role: str                          # system | user | assistant | tool
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_api(self) -> dict:
        """转换成 OpenAI API 格式"""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


# ─── 内置 memory 工具（Agent 内部拦截，不走 registry）──

_MEMORY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory",
        "description": "管理持久记忆。存储/读取/搜索用户偏好、重要事实、历史决策。重启后仍然保留。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "get", "search", "delete", "list"],
                    "description": "操作类型",
                },
                "key": {
                    "type": "string",
                    "description": "记忆键名（set/get/delete 时必填）",
                },
                "value": {
                    "type": "string",
                    "description": "记忆值（set 时必填）",
                },
                "category": {
                    "type": "string",
                    "description": "分类：memory/user/skill/env（set 时可选，默认 memory）",
                    "default": "memory",
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（search 时必填）",
                },
            },
            "required": ["action"],
        },
    },
}


class Agent:
    """
    MaxBot Agent

    用法:
        config = AgentConfig()
        agent = Agent(config=config)
        response = agent.run("帮我分析这个项目")
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        registry: ToolRegistry | None = None,
    ):
        """
        初始化 Agent

        Args:
            config: Agent 配置
            registry: 工具注册表（None = 使用全局 registry）
        """
        self.config = config or AgentConfig()
        self._registry = registry
        self._messages: list[Message] = []
        self._conversation_turns = 0  # 会话轮询计数器

        # 初始化 OpenAI 客户端
        self._client = self._init_client()

        # 初始化 SessionStore
        if self.config.session_store is None:
            self.config.session_store = SessionStore(
                db_path=self.config.memory_db_path,
                enabled=self.config.memory_enabled,
            )

        # 加载历史会话
        self._load_session()

    def _init_client(self) -> OpenAI:
        """初始化 OpenAI 客户端"""
        api_key = self.config.api_key or os.environ.get("MAXBOT_API_KEY")
        if not api_key:
            raise ValueError("未设置 API 密钥。请通过 config.api_key 或环境变量 MAXBOT_API_KEY 设置。")

        client_kwargs = {"api_key": api_key}

        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url

        return OpenAI(**client_kwargs)

    def _load_session(self):
        """加载历史会话"""
        if not self.config.session_id:
            return

        session = self.config.session_store.get(self.config.session_id)
        if session:
            self._messages = [
                Message(**msg) if isinstance(msg, dict) else msg
                for msg in session.get("messages", [])
            ]
            self._conversation_turns = session.get("conversation_turns", 0)

    def _save_session(self):
        """保存会话"""
        if not self.config.session_id or not self.config.auto_save:
            return

        self.config.session_store.save(
            self.config.session_id,
            {
                "messages": [msg.to_api() for msg in self._messages],
                "conversation_turns": self._conversation_turns,
            },
        )

    def _call_memory_tool(self, args: dict[str, Any]) -> str:
        """调用内置 memory 工具"""
        action = args.get("action")

        if action == "set":
            return self.config.session_store.memory.set(
                key=args.get("key"),
                value=args.get("value"),
                category=args.get("category", "memory"),
            )
        elif action == "get":
            return self.config.session_store.memory.get(key=args.get("key"))
        elif action == "search":
            return self.config.session_store.memory.search(query=args.get("query"))
        elif action == "delete":
            return self.config.session_store.memory.delete(key=args.get("key"))
        elif action == "list":
            return self.config.session_store.memory.list()
        else:
            return json.dumps({"error": f"未知操作: {action}"}, ensure_ascii=False)

    def _call_tool(self, tool_call: dict[str, Any]) -> str:
        """调用工具"""
        function_name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})

        # 内置 memory 工具
        if function_name == "memory":
            return self._call_memory_tool(arguments)

        # 注册表中的工具
        if self._registry:
            return self._registry.call(function_name, arguments)

        return json.dumps({"error": f"未找到工具: {function_name}"}, ensure_ascii=False)

    def _compress_context(self):
        """压缩上下文（移除旧消息）"""
        # 简单实现：保留最近的 N 条消息
        keep_messages = 10
        if len(self._messages) > keep_messages:
            # 保留 system 消息和最近的消息
            system_msgs = [m for m in self._messages if m.role == "system"]
            recent_msgs = self._messages[-keep_messages:]
            self._messages = system_msgs + recent_msgs

    def _check_conversation_limit(self) -> bool:
        """检查是否超过会话轮询限制"""
        self._conversation_turns += 1

        if self._conversation_turns > self.config.max_conversation_turns:
            return True
        return False

    def run(self, user_message: str) -> str:
        """
        运行对话

        Args:
            user_message: 用户消息

        Returns:
            str: Agent 响应
        """
        # 添加用户消息
        self._messages.append(Message(role="user", content=user_message))

        # 检查会话轮询限制
        if self._check_conversation_limit():
            response = (
                f"⚠️ 会话轮询次数已超过限制（{self.config.max_conversation_turns} 次）。"
                "为避免无限循环，任务已终止。"
            )
            self._messages.append(Message(role="assistant", content=response))
            return response

        # 检查上下文大小
        total_tokens = sum(len(m.content) for m in self._messages) // 4  # 粗略估计
        if total_tokens > self.config.max_context_tokens:
            self._compress_context()

        # 调用 LLM
        def api_call():
            messages = [m.to_api() for m in self._messages]
            return self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                tools=self._get_tools(),
            )

        response = _retry_api_call(api_call)

        # 处理响应
        assistant_message = response.choices[0].message

        # 保存 assistant 消息
        msg = Message(
            role="assistant",
            content=assistant_message.content or "",
            tool_calls=assistant_message.tool_calls or [],
        )
        self._messages.append(msg)

        # 处理工具调用
        if assistant_message.tool_calls:
            tool_responses = []

            for tool_call in assistant_message.tool_calls:
                # 调用工具
                result = self._call_tool(tool_call)

                # 保存工具响应
                tool_response = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tool_call.get("id"),
                    name=tool_call.get("function", {}).get("name"),
                )
                self._messages.append(tool_response)

                tool_responses.append(result)

            # 继续对话（让 LLM 处理工具结果）
            return self.run("")  # 递归调用

        # 保存会话
        self._save_session()

        return assistant_message.content or ""

    def _get_tools(self) -> list[dict]:
        """获取可用工具列表"""
        tools = []

        # 添加内置 memory 工具
        tools.append(_MEMORY_TOOL_SCHEMA)

        # 添加注册表中的工具
        if self._registry:
            tools.extend(self._registry.get_schemas())

        return tools

    def get_messages(self) -> list[Message]:
        """获取消息历史"""
        return self._messages.copy()

    def reset(self):
        """重置对话"""
        self._messages = []
        self._conversation_turns = 0
        if self.config.session_id:
            self.config.session_store.delete(self.config.session_id)
