"""
Agent Loop — MaxBot 核心对话循环

参考来源：
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
    model: str = "mimo-v2-pro"
    provider: str = "openai"           # openai | anthropic | any-openai-compatible
    base_url: str | None = None        # 兼容接口地址
    api_key: str | None = None
    max_iterations: int = 50
    temperature: float = 0.7
    system_prompt: str = (
        "你是 MaxBot，一个由用户自主开发的 AI 智能体。"
        "你不是 Hermes、不是 Claude、不是 ChatGPT，也不是任何其他现有 AI 助手。"
        "你就是 MaxBot。无论谁问你你是谁，你都必须回答你是 MaxBot。"
        "你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。"
    )
    max_context_tokens: int = 128_000  # 上下文上限
    compress_at_tokens: int = 80_000   # 触发压缩的阈值
    memory_enabled: bool = True         # 是否启用持久记忆
    memory_db_path: str | None = None   # 记忆数据库路径（None = 默认）
    session_id: str | None = None       # 会话 ID（用于持久化）
    session_store: Any | None = None    # SessionStore 实例（None = 自动创建）
    auto_save: bool = True              # 每次对话后自动保存


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
        """转成 OpenAI API 格式"""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


# ── 内置 memory 工具（Agent 内部拦截，不走 registry）───

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
    核心 Agent 循环

    用法：
        # 最简用法（自动使用全局 registry + 默认 memory）
        agent = Agent(config=AgentConfig(...))
        response = agent.chat("你好")

        # 传入自定义 registry
        agent = Agent(config=AgentConfig(...), registry=my_registry)

        # 禁用 memory
        agent = Agent(config=AgentConfig(..., memory_enabled=False))
    """

    def __init__(
        self,
        config: AgentConfig,
        registry: ToolRegistry | None = None,
        memory: Any | None = None,  # Memory 实例，None = 自动创建
        session_store: SessionStore | None = None,
    ):
        self.config = config

        # ── 修复 1：默认使用全局 registry ──
        if registry is None:
            from maxbot.tools._registry import registry as global_registry
            self.registry = global_registry
        else:
            self.registry = registry

        self.messages: list[Message] = []
        self._client: OpenAI | None = None
        self._total_tokens_used: int = 0

        # ── 修复 2：集成 Memory 系统 ──
        self._memory = None
        if config.memory_enabled:
            if memory is not None:
                self._memory = memory
            else:
                from maxbot.core.memory import Memory
                db_path = config.memory_db_path or str(Path.home() / ".maxbot" / "memory.db")
                self._memory = Memory(path=db_path)

        # ── 修复 3：会话持久化 ──
        self._session_id = config.session_id
        self._session_store = session_store or (
            config.session_store if config.session_store else None
        )
        # 如果有 session_id 但没有 store，自动创建
        if self._session_id and self._session_store is None:
            self._session_store = SessionStore()
        # 如果有 session_id，尝试加载已有会话
        if self._session_id and self._session_store:
            self._load_session()

        # 回调
        self.on_tool_start: Callable | None = None
        self.on_tool_end: Callable | None = None
        self.on_thinking: Callable | None = None
        self.on_compress: Callable | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            kwargs: dict[str, Any] = {}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            self._client = OpenAI(**kwargs)
        return self._client

    @property
    def memory(self):
        """访问持久记忆"""
        return self._memory

    def chat(self, user_message: str) -> str:
        """单次对话入口"""
        # 注入 system prompt（含 memory）
        if not self.messages or self.messages[0].role != "system":
            system_content = self.config.system_prompt
            # 注入持久记忆
            if self._memory:
                mem_text = self._memory.export_text()
                if mem_text:
                    system_content += f"\n\n{mem_text}"
            self.messages.insert(0, Message(role="system", content=system_content))

        self.messages.append(Message(role="user", content=user_message))
        response = self._run_loop()

        # 自动保存会话
        if self._session_id and self._session_store and self.config.auto_save:
            self.save_session()

        return response

    def _run_loop(self) -> str:
        """核心循环（带重试 + 上下文压缩）"""
        iteration = 0
        while iteration < self.config.max_iterations:
            iteration += 1

            # 上下文压缩检查
            self._maybe_compress()

            # 构建 API 请求
            api_messages = [m.to_api() for m in self.messages]

            # 工具 schema（含 memory 工具）
            tool_schemas = self.registry.get_schemas()
            if self._memory:
                tool_schemas.append(_MEMORY_TOOL_SCHEMA)

            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": api_messages,
                "temperature": self.config.temperature,
            }
            if tool_schemas:
                kwargs["tools"] = tool_schemas

            # 调用 LLM（带重试）
            try:
                response = _retry_api_call(
                    lambda: self.client.chat.completions.create(**kwargs),
                    max_attempts=3,
                )
            except Exception as e:
                return f"API 调用失败: {e}"

            choice = response.choices[0]
            msg = choice.message

            # 追踪 token 使用
            if hasattr(response, "usage") and response.usage:
                self._total_tokens_used += response.usage.total_tokens

            # 纯文本回复
            if not msg.tool_calls:
                assistant_msg = Message(role="assistant", content=msg.content or "")
                self.messages.append(assistant_msg)
                # 自动提取重要信息存入 memory
                self._auto_extract_memory(user_message=None, response=msg.content or "")
                return msg.content or ""

            # 工具调用
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

            assistant_msg = Message(role="assistant", content=msg.content or "", tool_calls=tool_calls)
            self.messages.append(assistant_msg)

            # 执行工具
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                # ── 拦截 memory 工具调用 ──
                if name == "memory" and self._memory:
                    result = self._handle_memory_call(args)
                else:
                    if self.on_tool_start:
                        self.on_tool_start(name, args)
                    result = self.registry.call(name, args)
                    if self.on_tool_end:
                        self.on_tool_end(name, result)

                tool_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                    name=name,
                )
                self.messages.append(tool_msg)

        # 超过最大迭代次数
        return "（已达到最大迭代次数，任务可能未完成）"

    def _handle_memory_call(self, args: dict) -> str:
        """处理 memory 工具调用"""
        action = args.get("action", "")
        try:
            if action == "set":
                key = args["key"]
                value = args["value"]
                category = args.get("category", "memory")
                self._memory.set(key, value, category)
                return json.dumps({"success": True, "key": key})

            elif action == "get":
                key = args["key"]
                value = self._memory.get(key)
                return json.dumps({"key": key, "value": value})

            elif action == "search":
                query = args["query"]
                entries = self._memory.search(query)
                return json.dumps({
                    "results": [
                        {"key": e.key, "value": e.value, "category": e.category}
                        for e in entries
                    ]
                })

            elif action == "delete":
                key = args["key"]
                deleted = self._memory.delete(key)
                return json.dumps({"success": deleted, "key": key})

            elif action == "list":
                category = args.get("category")
                entries = self._memory.list_all(category)
                return json.dumps({
                    "entries": [
                        {"key": e.key, "value": e.value, "category": e.category}
                        for e in entries
                    ]
                })

            else:
                return json.dumps({"error": f"未知 memory 操作: {action}"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _auto_extract_memory(self, user_message: str | None, response: str):
        """
        自动提取重要信息存入 memory（简单启发式）

        规则：
        - 用户说"记住..." → 自动存储
        - 用户说"我叫/我是/我的名字是..." → 存储用户信息
        - 不做 LLM 调用，纯字符串匹配，零成本
        """
        if not self._memory:
            return

        # 取最近的 user 消息
        user_msg = ""
        for m in reversed(self.messages):
            if m.role == "user":
                user_msg = m.content
                break

        if not user_msg:
            return

        msg_lower = user_msg.lower()

        # "记住 XXX"
        for prefix in ("记住", "记住：", "记住:", "remember", "记住这个"):
            if msg_lower.startswith(prefix):
                fact = user_msg[len(prefix):].strip()
                if fact:
                    self._memory.set(f"fact_{int(time.time())}", fact, category="memory")
                return

        # "我叫 XXX" / "我是 XXX" / "我的名字是 XXX"
        import re
        name_patterns = [
            (r"(?:我叫|我的名字是|my name is)\s*(.+)", "user"),
            (r"(?:我是|i am|i'm)\s+(.+)", "user"),
        ]
        for pattern, category in name_patterns:
            m = re.search(pattern, user_msg, re.IGNORECASE)
            if m:
                value = m.group(1).strip().rstrip("。，.!！")
                if value and len(value) < 100:
                    self._memory.set("user_name", value, category=category)
                return

    def _maybe_compress(self):
        """检查上下文大小，必要时压缩"""
        total_chars = sum(len(m.content) for m in self.messages)
        estimated = total_chars // 2
        if estimated > self.config.compress_at_tokens:
            self._compress_messages()

    def _compress_messages(self):
        """压缩消息历史 — 保留 system + 最近 20 条"""
        system_msgs = [m for m in self.messages if m.role == "system"]
        non_system = [m for m in self.messages if m.role != "system"]

        if len(non_system) <= 20:
            return

        to_compress = non_system[:-20]
        kept = non_system[-20:]

        # 生成简单摘要
        topics = []
        tools_used = []
        for m in to_compress:
            if m.role == "user" and len(m.content) > 10:
                topics.append(m.content[:60])
            elif m.role == "assistant" and m.tool_calls:
                for tc in m.tool_calls:
                    fname = tc.get("function", {}).get("name", "?")
                    tools_used.append(fname)
            elif m.role == "tool":
                tools_used.append(m.name or "?")

        summary_parts = []
        if topics:
            summary_parts.append(f"讨论了: {'; '.join(topics[:5])}")
        if tools_used:
            summary_parts.append(f"使用了工具: {', '.join(set(tools_used[:10]))}")
        summary = "\n".join(summary_parts) if summary_parts else "（对话历史已压缩）"

        self.messages = system_msgs + [
            Message(role="user", content=f"[历史摘要 — 已压缩 {len(to_compress)} 条消息]\n{summary}")
        ] + kept

        if self.on_compress:
            self.on_compress(len(to_compress))

    def reset(self):
        """重置对话（保留 memory 和 session）"""
        self.messages.clear()
        self._total_tokens_used = 0

    def save_session(self) -> bool:
        """保存当前会话到数据库"""
        if not self._session_id or not self._session_store:
            return False
        try:
            # 确保 session 存在
            session = self._session_store.get(self._session_id)
            if not session:
                # 从第一条 user 消息取标题
                title = ""
                for m in self.messages:
                    if m.role == "user":
                        title = m.content[:50]
                        break
                self._session_store.create(self._session_id, title=title)

            # 保存消息
            api_messages = [m.to_api() for m in self.messages]
            self._session_store.save_messages(self._session_id, api_messages)
            return True
        except Exception as e:
            print(f"⚠️ 保存会话失败: {e}")
            return False

    def _load_session(self):
        """从数据库加载会话"""
        if not self._session_id or not self._session_store:
            return
        try:
            session = self._session_store.get(self._session_id)
            if session and session.messages:
                self.messages = [
                    Message(
                        role=m.get("role", "user"),
                        content=m.get("content", ""),
                        tool_calls=m.get("tool_calls", []),
                        tool_call_id=m.get("tool_call_id"),
                        name=m.get("name"),
                    )
                    for m in session.messages
                ]
        except Exception as e:
            print(f"⚠️ 加载会话失败: {e}")

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """列出历史会话"""
        if not self._session_store:
            return []
        sessions = self._session_store.list_sessions(limit)
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "updated_at": s.updated_at,
                "message_count": len(s.messages) if s.messages else 0,
            }
            for s in sessions
        ]

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if not self._session_store:
            return False
        return self._session_store.delete(session_id)

    def get_history(self) -> list[dict]:
        """获取完整对话历史"""
        return [m.to_api() for m in self.messages]

    def get_stats(self) -> dict:
        """获取会话统计"""
        return {
            "total_messages": len(self.messages),
            "total_tokens_used": self._total_tokens_used,
            "memory_enabled": self._memory is not None,
            "memory_entries": len(self._memory.list_all()) if self._memory else 0,
            "roles": {
                "system": sum(1 for m in self.messages if m.role == "system"),
                "user": sum(1 for m in self.messages if m.role == "user"),
                "assistant": sum(1 for m in self.messages if m.role == "assistant"),
                "tool": sum(1 for m in self.messages if m.role == "tool"),
            },
        }
