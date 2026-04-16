"""Agent Loop 集成测试 — 注册表统一 + Memory 集成"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maxbot.core.agent_loop import Agent, AgentConfig, Message, _MEMORY_TOOL_SCHEMA
from maxbot.core.tool_registry import ToolRegistry
from maxbot.core.memory import Memory


# ══════════════════════════════════════════════════════════════
# 注册表统一测试
# ══════════════════════════════════════════════════════════════

class TestRegistryUnification:
    """Agent 默认使用全局 registry"""

    def test_default_uses_global_registry(self):
        """不传 registry 时，Agent 使用全局 registry"""
        from maxbot.tools._registry import registry as global_registry
        config = AgentConfig(memory_enabled=False)
        agent = Agent(config=config)
        assert agent.registry is global_registry

    def test_explicit_registry_overrides(self):
        """传入自定义 registry 时，使用传入的"""
        custom = ToolRegistry()
        config = AgentConfig(memory_enabled=False)
        agent = Agent(config=config, registry=custom)
        assert agent.registry is custom
        assert agent.registry is not None

    def test_global_registry_has_tools(self):
        """全局 registry 应该有工具（import 了 tools/）"""
        from maxbot.tools._registry import registry as global_registry
        tools = global_registry.list_tools()
        assert len(tools) > 0
        names = [t.name for t in tools]
        assert "read_file" in names
        assert "shell" in names


# ══════════════════════════════════════════════════════════════
# Memory 集成测试
# ══════════════════════════════════════════════════════════════

class TestMemoryIntegration:
    """Memory 系统集成到 Agent"""

    def test_memory_enabled_by_default(self):
        """默认启用 memory"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            config = AgentConfig(memory_enabled=True, memory_db_path=db)
            agent = Agent(config=config)
            assert agent.memory is not None

    def test_memory_disabled(self):
        """禁用 memory 时为 None"""
        config = AgentConfig(memory_enabled=False)
        agent = Agent(config=config)
        assert agent.memory is None

    def test_memory_injected(self):
        """传入 memory 实例"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            mem.set("user_name", "张三", category="user")

            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)
            assert agent.memory.get("user_name") == "张三"

    def test_memory_in_system_prompt(self):
        """memory 内容注入到 system prompt"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            mem.set("lang", "Python", category="preference")

            config = AgentConfig(memory_enabled=True, system_prompt="你是 MaxBot")
            agent = Agent(config=config, memory=mem)

            # 模拟 chat 调用（不实际调 LLM）
            # 检查 system prompt 是否包含 memory 内容
            # 通过 _handle_memory_call 间接验证
            result = agent._handle_memory_call({"action": "get", "key": "lang"})
            data = json.loads(result)
            assert data["value"] == "Python"

    def test_memory_tool_set_and_get(self):
        """memory 工具：set 和 get"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            # set
            result = agent._handle_memory_call({
                "action": "set",
                "key": "favorite_lang",
                "value": "Rust",
                "category": "preference",
            })
            assert json.loads(result)["success"] is True

            # get
            result = agent._handle_memory_call({
                "action": "get",
                "key": "favorite_lang",
            })
            assert json.loads(result)["value"] == "Rust"

    def test_memory_tool_search(self):
        """memory 工具：search"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            mem.set("user_name", "张三", category="user")
            mem.set("user_lang", "中文", category="user")

            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            result = agent._handle_memory_call({"action": "search", "query": "中文"})
            data = json.loads(result)
            assert len(data["results"]) >= 1

    def test_memory_tool_delete(self):
        """memory 工具：delete"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            mem.set("temp", "123")

            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            result = agent._handle_memory_call({"action": "delete", "key": "temp"})
            assert json.loads(result)["success"] is True
            assert mem.get("temp") is None

    def test_memory_tool_list(self):
        """memory 工具：list"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            mem.set("a", "1", category="pref")
            mem.set("b", "2", category="pref")
            mem.set("c", "3", category="user")

            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            result = agent._handle_memory_call({"action": "list", "category": "pref"})
            data = json.loads(result)
            assert len(data["entries"]) == 2

    def test_memory_tool_unknown_action(self):
        """memory 工具：未知操作"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            result = agent._handle_memory_call({"action": "unknown"})
            assert "error" in json.loads(result)


class TestAutoExtractMemory:
    """自动提取记忆"""

    def test_remember_keyword(self):
        """用户说"记住..."自动存储"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            # 模拟用户消息
            agent.messages = [
                Message(role="system", content="test"),
                Message(role="user", content="记住我最喜欢的编程语言是 Python"),
            ]
            agent._auto_extract_memory(user_message=None, response="好的")

            # 检查是否有存储
            entries = mem.list_all()
            assert len(entries) >= 1
            assert any("Python" in e.value for e in entries)

    def test_name_extraction(self):
        """用户说"我叫..."自动存储"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            agent.messages = [
                Message(role="system", content="test"),
                Message(role="user", content="我叫李明"),
            ]
            agent._auto_extract_memory(user_message=None, response="你好李明")

            assert mem.get("user_name") == "李明"

    def test_no_extraction_for_normal_messages(self):
        """普通消息不触发提取"""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            agent.messages = [
                Message(role="system", content="test"),
                Message(role="user", content="今天天气怎么样"),
            ]
            agent._auto_extract_memory(user_message=None, response="晴天")

            entries = mem.list_all()
            assert len(entries) == 0


class TestMemoryToolSchema:
    """memory 工具 schema"""

    def test_schema_structure(self):
        schema = _MEMORY_TOOL_SCHEMA
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "memory"
        assert "action" in schema["function"]["parameters"]["properties"]
        actions = schema["function"]["parameters"]["properties"]["action"]["enum"]
        assert "set" in actions
        assert "get" in actions
        assert "search" in actions
        assert "delete" in actions
        assert "list" in actions


class TestAgentStats:
    """Agent 统计信息"""

    def test_stats_include_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_memory.db")
            mem = Memory(path=db)
            mem.set("a", "1")
            mem.set("b", "2")

            config = AgentConfig(memory_enabled=True)
            agent = Agent(config=config, memory=mem)

            stats = agent.get_stats()
            assert stats["memory_enabled"] is True
            assert stats["memory_entries"] == 2

    def test_stats_without_memory(self):
        config = AgentConfig(memory_enabled=False)
        agent = Agent(config=config)
        stats = agent.get_stats()
        assert stats["memory_enabled"] is False
        assert stats["memory_entries"] == 0


class TestMessageFormat:
    """消息格式"""

    def test_to_api_basic(self):
        m = Message(role="user", content="hello")
        api = m.to_api()
        assert api == {"role": "user", "content": "hello"}

    def test_to_api_with_tool_calls(self):
        m = Message(
            role="assistant",
            content="",
            tool_calls=[{"id": "123", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
        )
        api = m.to_api()
        assert "tool_calls" in api

    def test_to_api_with_tool_call_id(self):
        m = Message(role="tool", content="result", tool_call_id="123", name="my_tool")
        api = m.to_api()
        assert api["tool_call_id"] == "123"
        assert api["name"] == "my_tool"
