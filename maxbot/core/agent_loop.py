"""
Agent Loop — MaxBot 核心对话循环

参考来源：
- Hermes: run_conversation 循环、消息格式
- Claude Code: tool_use 流程、迭代控制
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI

from maxbot.core.tool_registry import ToolRegistry


@dataclass
class AgentConfig:
    """Agent 配置"""
    model: str = "gpt-4o"
    provider: str = "openai"           # openai | anthropic | any-openai-compatible
    base_url: str | None = None        # 兼容接口地址
    api_key: str | None = None
    max_iterations: int = 50
    temperature: float = 0.7
    system_prompt: str = "你是一个强大的 AI 助手，名叫 MaxBot。"


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


class Agent:
    """
    核心 Agent 循环

    用法：
        registry = ToolRegistry()
        registry.load_builtins()

        agent = Agent(config=AgentConfig(...), registry=registry)
        response = agent.chat("你好")
    """

    def __init__(self, config: AgentConfig, registry: ToolRegistry | None = None):
        self.config = config
        self.registry = registry or ToolRegistry()
        self.messages: list[Message] = []
        self._client: OpenAI | None = None

        # 回调
        self.on_tool_start: Callable | None = None
        self.on_tool_end: Callable | None = None
        self.on_thinking: Callable | None = None

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

    def chat(self, user_message: str) -> str:
        """单次对话入口"""
        # 注入 system prompt
        if not self.messages or self.messages[0].role != "system":
            self.messages.insert(0, Message(role="system", content=self.config.system_prompt))

        self.messages.append(Message(role="user", content=user_message))
        return self._run_loop()

    def _run_loop(self) -> str:
        """核心循环"""
        iteration = 0
        while iteration < self.config.max_iterations:
            iteration += 1

            # 构建 API 请求
            api_messages = [m.to_api() for m in self.messages]
            tool_schemas = self.registry.get_schemas()

            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": api_messages,
                "temperature": self.config.temperature,
            }
            if tool_schemas:
                kwargs["tools"] = tool_schemas

            # 调用 LLM
            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            msg = choice.message

            # 纯文本回复
            if not msg.tool_calls:
                assistant_msg = Message(role="assistant", content=msg.content or "")
                self.messages.append(assistant_msg)
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

    def reset(self):
        """重置对话"""
        self.messages.clear()

    def get_history(self) -> list[dict]:
        """获取完整对话历史"""
        return [m.to_api() for m in self.messages]
