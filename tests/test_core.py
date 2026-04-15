"""核心模块测试"""

import json
import tempfile
from pathlib import Path

import pytest

from maxbot.core.tool_registry import ToolRegistry, ToolDef
from maxbot.core.memory import Memory
from maxbot.core.context import ContextManager, Message


# ── ToolRegistry 测试 ─────────────────────────────────────

class TestToolRegistry:
    def test_register_and_call(self):
        reg = ToolRegistry()
        reg.register(
            name="echo",
            description="回显",
            parameters={"text": {"type": "string"}},
            handler=lambda text: json.dumps({"echo": text}),
        )
        assert len(reg) == 1
        result = reg.call("echo", {"text": "hello"})
        assert json.loads(result)["echo"] == "hello"

    def test_unknown_tool(self):
        reg = ToolRegistry()
        result = reg.call("nonexistent", {})
        assert "error" in json.loads(result)

    def test_decorator(self):
        reg = ToolRegistry()

        @reg.tool(name="add", description="加法")
        def add(a: int, b: int) -> str:
            return json.dumps({"result": a + b})

        result = reg.call("add", {"a": 1, "b": 2})
        assert json.loads(result)["result"] == 3

    def test_schemas(self):
        reg = ToolRegistry()
        reg.register(
            name="test",
            description="测试",
            parameters={"x": {"type": "integer"}},
            handler=lambda x: str(x),
        )
        schemas = reg.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "test"

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(name="temp", description="", parameters={}, handler=lambda: "")
        assert len(reg) == 1
        reg.unregister("temp")
        assert len(reg) == 0

    def test_error_handler(self):
        reg = ToolRegistry()
        reg.register(
            name="fail",
            description="会失败",
            parameters={},
            handler=lambda: 1 / 0,  # type: ignore
        )
        result = json.loads(reg.call("fail", {}))
        assert "error" in result


# ── Memory 测试 ────────────────────────────────────────────

class TestMemory:
    def test_set_get(self, tmp_path):
        mem = Memory(tmp_path / "test.db")
        mem.set("name", "张三", category="user")
        assert mem.get("name") == "张三"

    def test_update(self, tmp_path):
        mem = Memory(tmp_path / "test.db")
        mem.set("key", "v1")
        mem.set("key", "v2")
        assert mem.get("key") == "v2"

    def test_delete(self, tmp_path):
        mem = Memory(tmp_path / "test.db")
        mem.set("key", "value")
        assert mem.delete("key") is True
        assert mem.get("key") is None

    def test_search(self, tmp_path):
        mem = Memory(tmp_path / "test.db")
        mem.set("user_name", "张三是个程序员", category="user")
        mem.set("other", "完全不相关")
        results = mem.search("张三")
        assert len(results) >= 1
        assert results[0].key == "user_name"

    def test_list_all(self, tmp_path):
        mem = Memory(tmp_path / "test.db")
        mem.set("a", "1", category="x")
        mem.set("b", "2", category="y")
        mem.set("c", "3", category="x")
        x_entries = mem.list_all(category="x")
        assert len(x_entries) == 2

    def test_export_text(self, tmp_path):
        mem = Memory(tmp_path / "test.db")
        mem.set("name", "张三", category="user")
        text = mem.export_text()
        assert "张三" in text
        assert "user" in text


# ── ContextManager 测试 ───────────────────────────────────

class TestContextManager:
    def test_estimate_tokens(self):
        ctx = ContextManager()
        assert ctx.estimate_tokens("hello") > 0
        assert ctx.estimate_tokens("你好世界") > 0

    def test_get_stats(self):
        ctx = ContextManager()
        messages = [
            Message(role="system", content="系统"),
            Message(role="user", content="你好"),
            Message(role="assistant", content="你好！"),
            Message(role="tool", content="result", name="test"),
        ]
        stats = ctx.get_stats(messages)
        assert stats.total_messages == 4
        assert stats.system_messages == 1
        assert stats.user_messages == 1

    def test_compress_noop(self):
        ctx = ContextManager()
        messages = [Message(role="user", content=f"msg {i}") for i in range(5)]
        compressed = ctx.compress(messages, keep_recent=20)
        assert len(compressed) == 5  # 不需要压缩

    def test_compress(self):
        ctx = ContextManager()
        messages = [Message(role="user", content=f"消息 {i}") for i in range(30)]
        compressed = ctx.compress(messages, keep_recent=10)
        assert len(compressed) < len(messages)
        # 第一条应该是摘要
        assert "历史摘要" in compressed[0].content
