"""测试新增功能：安全沙箱、spawn_agent 工具、技能系统、知识吸收"""

import json
import tempfile
from pathlib import Path

import pytest

# ── 安全沙箱测试 ─────────────────────────────────────────

from maxbot.tools.sandbox import validate_command, validate_workdir, set_allowed_workdir


class TestSandbox:
    """命令安全检查"""

    def test_safe_commands(self):
        safe, _ = validate_command("ls -la")
        assert safe is True

    def test_dangerous_rm_rf(self):
        safe, reason = validate_command("rm -rf /")
        assert safe is False
        assert "黑名单" in reason

    def test_dangerous_rm_rf_star(self):
        safe, _ = validate_command("rm -rf *")
        assert safe is False

    def test_dangerous_shutdown(self):
        safe, _ = validate_command("shutdown -h now")
        assert safe is False

    def test_dangerous_dd(self):
        safe, _ = validate_command("dd if=/dev/zero of=/dev/sda")
        assert safe is False

    def test_dangerous_chmod_777(self):
        safe, _ = validate_command("chmod 777 /etc/passwd")
        assert safe is False

    def test_safe_git_commands(self):
        safe, _ = validate_command("git status")
        assert safe is True
        safe, _ = validate_command("git log --oneline")
        assert safe is True

    def test_safe_python_commands(self):
        safe, _ = validate_command("python3 -c 'print(1)'")
        assert safe is True

    def test_empty_command(self):
        safe, reason = validate_command("")
        assert safe is False

    def test_workdir_allowed(self):
        set_allowed_workdir(["/tmp", "/root"])
        safe, _ = validate_workdir("/tmp/test")
        assert safe is True
        safe, _ = validate_workdir("/root/project")
        assert safe is True
        set_allowed_workdir(None)

    def test_workdir_blocked(self):
        set_allowed_workdir(["/tmp"])
        safe, reason = validate_workdir("/etc")
        assert safe is False
        set_allowed_workdir(None)

    def test_workdir_none_allowed(self):
        safe, _ = validate_workdir("/anywhere")
        assert safe is True


# ── Shell 工具集成测试 ──────────────────────────────────

from maxbot.tools._registry import registry as tool_registry


class TestShellSecurity:
    """Shell 工具安全集成"""

    def test_safe_shell(self):
        result = tool_registry.call("shell", {"command": "echo hello"})
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "hello" in data["output"]

    def test_blocked_shell(self):
        result = tool_registry.call("shell", {"command": "rm -rf /"})
        data = json.loads(result)
        assert "error" in data
        assert "拒绝" in data["error"]

    def test_exec_python_safe(self):
        result = tool_registry.call("exec_python", {"code": "print('hello')"})
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "hello" in data["output"]


# ── spawn_agent 工具注册测试 ─────────────────────────────

class TestMultiAgentTools:
    """多 Agent 工具应该注册到 registry"""

    def test_spawn_agent_registered(self):
        tool = tool_registry.get("spawn_agent")
        assert tool is not None
        assert "子 Agent" in tool.description

    def test_spawn_agents_parallel_registered(self):
        tool = tool_registry.get("spawn_agents_parallel")
        assert tool is not None

    def test_spawn_agent_schema(self):
        schema = tool_registry.get("spawn_agent").to_schema()
        func = schema["function"]
        assert func["name"] == "spawn_agent"
        params = func["parameters"]
        assert "task" in params["properties"]
        assert "task" in params["required"]
        assert "description" not in params.get("required", [])  # 有默认值，非必须
        assert "max_iterations" not in params.get("required", [])


# ── 技能系统测试 ─────────────────────────────────────────

from maxbot.skills import SkillManager


class TestSkillManager:

    def test_empty_skills_dir(self):
        sm = SkillManager(skills_dir="/nonexistent/path")
        assert len(sm.list_skills()) == 0

    def test_install_and_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            sm = SkillManager(skills_dir=tmp)

            content = """---
description: 代码审查技能
triggers: ["review", "审查", "code review"]
tools: ["read_file", "analyze_code"]
category: development
---

# 代码审查流程
1. 读取文件
2. 分析结构
3. 给出建议
"""
            sm.install_skill("code-review", content)

            skills = sm.list_skills()
            assert len(skills) == 1
            assert skills[0].name == "code-review"

            # 触发词匹配
            matched = sm.match_skills("帮我 review 一下代码")
            assert len(matched) == 1
            assert matched[0].name == "code-review"

            # 中文触发
            matched = sm.match_skills("帮我审查这段代码")
            assert len(matched) == 1

            # 不匹配
            matched = sm.match_skills("今天天气怎么样")
            assert len(matched) == 0

    def test_get_injectable_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            sm = SkillManager(skills_dir=tmp)
            sm.install_skill("test-skill", "---\ntriggers: [\"test\"]\n---\n# Test\nDo something")

            content = sm.get_injectable_content("run test please")
            assert "test-skill" in content

            content = sm.get_injectable_content("nothing relevant")
            assert content == ""


# ── 知识吸收测试 ─────────────────────────────────────────

from maxbot.knowledge import KnowledgeAbsorber, ExtractedCapability


class TestKnowledgeAbsorber:

    def test_analyze_python_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 创建测试 Python 文件
            test_file = Path(tmp) / "example.py"
            test_file.write_text('''
"""Example module"""

def greet(name: str) -> str:
    """Say hello to someone"""
    return f"Hello, {name}"

def _private_helper():
    """Internal function - should be skipped"""
    pass

def test_something():
    """Test function - should be skipped"""
    pass

class MyClass:
    """A class"""
    def method(self):
        """A method"""
        pass
''')

            absorber = KnowledgeAbsorber()
            result = absorber.absorb(tmp, validate=False)

            # 只有 greet 应该被提取（非私有、有 docstring、非测试）
            func_names = [c.source_function for c in result.capabilities]
            assert "greet" in func_names
            assert "_private_helper" not in func_names
            assert "test_something" not in func_names

    def test_generate_tool_definition(self):
        cap = ExtractedCapability(
            name="example_greet",
            description="Say hello to someone",
            source_file="example.py",
            source_function="greet",
            parameters={"name": {"type": "string"}},
            required_params=["name"],
        )
        tool_def = cap.to_tool_schema()

        assert tool_def["function"]["name"] == "example_greet"
        assert tool_def["function"]["description"] == "Say hello to someone"
        assert "name" in tool_def["function"]["parameters"]["properties"]

    def test_generate_tool_code(self):
        cap = ExtractedCapability(
            name="example_greet",
            description="Say hello",
            source_file="example.py",
            source_function="greet",
            parameters={"name": {"type": "string"}},
            handler_code='def example_greet(name: str) -> str:\n    """Generated from example.py::greet"""\n    return "ok"',
        )
        assert "def example_greet" in cap.handler_code
        assert "example.py" in cap.handler_code

    def test_nonexistent_repo(self):
        absorber = KnowledgeAbsorber()
        result = absorber.absorb("/nonexistent/path")
        assert result.total_extracted == 0


# ── _extract_params required 测试 ───────────────────────

from maxbot.core.tool_registry import _extract_params


class TestExtractParams:

    def test_required_vs_optional(self):
        def my_func(required_arg: str, optional_arg: str = "default") -> str:
            pass

        params, required = _extract_params(my_func)
        assert "required_arg" in required
        assert "optional_arg" not in required
        assert params["optional_arg"]["default"] == "default"

    def test_all_required(self):
        def my_func(a: str, b: int) -> str:
            pass

        params, required = _extract_params(my_func)
        assert "a" in required
        assert "b" in required
        assert len(required) == 2

    def test_skip_self_and_task_id(self):
        class MyClass:
            def method(self, arg: str, task_id: str = None) -> str:
                pass

        params, required = _extract_params(MyClass.method)
        assert "self" not in params
        assert "task_id" not in params
        assert "arg" in params
