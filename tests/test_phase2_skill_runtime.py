from pathlib import Path
from unittest.mock import MagicMock

import yaml

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.tool_registry import ToolRegistry
from maxbot.skills import SkillManager
from maxbot.config.config_loader import SystemConfig


CORE_SKILLS = {
    "tdd-workflow",
    "security-review",
    "python-testing",
    "code-analysis",
}


def _patch_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("maxbot.skills.Path.home", lambda: tmp_path)
    monkeypatch.setattr("maxbot.config.config_loader.Path.home", lambda: tmp_path)


def test_skill_manager_expands_default_user_skills_path(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    skill_dir = tmp_path / ".maxbot" / "skills" / "custom-review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: custom-review
description: custom skill
triggers: [\"custom review\"]
---

# Custom Review
""",
        encoding="utf-8",
    )

    manager = SkillManager(skills_dir="~/.maxbot/skills")

    names = {skill.name for skill in manager.list_skills()}
    assert "custom-review" in names


def test_default_skill_manager_loads_repo_core_skills(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)

    manager = SkillManager()

    names = {skill.name for skill in manager.list_skills()}
    assert CORE_SKILLS.issubset(names)


def test_agent_default_skill_path_injects_builtin_skill_content(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=True,
            skills_dir="~/.maxbot/skills",
            memory_enabled=False,
        )
    )

    prompt = agent._get_enhanced_system_prompt("please fix bug and write tests first")

    assert "相关技能指南" in prompt
    assert "tdd-workflow" in prompt


def test_agent_dynamic_capability_summary_does_not_overclaim_sparse_enabled_tools(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=False,
            eval_samples_enabled=False,
            metrics_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "文件操作" in summary
    assert "代码编辑" not in summary
    assert "命令执行" not in summary
    assert "Git" not in summary
    assert "项目分析" not in summary


def test_agent_dynamic_capability_summary_describes_partial_web_capabilities_precisely(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="web_search",
        description="搜索网页",
        parameters={"query": {"type": "string"}},
        handler=lambda query: query,
        toolset="web",
        required_params=["query"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=False,
            eval_samples_enabled=False,
            metrics_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "外部检索：网页搜索" in summary
    assert "外部检索：内容抓取" not in summary


def test_agent_dynamic_capability_summary_describes_partial_multi_agent_capabilities_precisely(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="agent_status",
        description="查看子 Agent 状态",
        parameters={},
        handler=lambda: "ok",
        toolset="multi_agent",
        required_params=[],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=False,
            eval_samples_enabled=False,
            metrics_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "多 Agent 协作：状态汇总" in summary
    assert "多 Agent 协作：任务派发" not in summary
    assert "多 Agent 协作：并行执行" not in summary


def test_agent_dynamic_capability_summary_marks_phase_capabilities_as_system_level(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=False,
            eval_samples_enabled=False,
            metrics_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "按进化路线形成的系统级能力" in summary
    assert "不等于当前会话全部已启用" in summary


def test_agent_dynamic_capability_summary_lists_enabled_optional_features_when_turned_on(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=True,
            reflection_enabled=True,
            mempalace_enabled=True,
            eval_samples_enabled=True,
            metrics_enabled=True,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "Reflection：当前会话已启用" in summary
    assert "MemPalace：当前会话已启用" in summary
    assert "Eval Samples：当前会话已启用" in summary


def test_agent_dynamic_capability_summary_marks_disabled_features_as_current_session_disabled(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=False,
            eval_samples_enabled=False,
            metrics_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "MemPalace：外接长期记忆 PoC 已接入，但当前会话未启用" in summary


def test_agent_dynamic_capability_summary_requires_memory_injection_for_mempalace_enabled_label(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=False,
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=True,
            eval_samples_enabled=False,
            metrics_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "MemPalace：当前会话已启用" not in summary
    assert "MemPalace：已接入，但当前记忆注入链路关闭，本会话不会自动注入" in summary


def test_agent_dynamic_capability_summary_groups_enabled_disabled_and_phase_capabilities(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    for name, description, toolset, required_param in [
        ("read_file", "读取文件", "file", "path"),
        ("web_search", "搜索网页", "web", "query"),
        ("security_scan", "执行安全扫描", "security", "check_name"),
        ("spawn_agent", "派生单个子 Agent", "multi_agent", "task"),
        ("spawn_agents_parallel", "并行派生多个子 Agent", "multi_agent", "tasks"),
        ("agent_status", "查看子 Agent 状态", "multi_agent", "status"),
    ]:
        registry.register(
            name=name,
            description=description,
            parameters={required_param: {"type": "string"}},
            handler=lambda **kwargs: kwargs,
            toolset=toolset,
            required_params=[required_param],
        )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=True,
            skills_dir="~/.maxbot/skills",
            memory_enabled=False,
            reflection_enabled=False,
            mempalace_enabled=False,
            eval_samples_enabled=False,
            metrics_enabled=True,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "当前已启用能力" in summary
    assert "已实现但默认未启用的能力" in summary
    assert "按进化路线形成的系统级能力" in summary
    assert "多 Agent 协作" in summary
    assert "Reflection" in summary
    assert "MemPalace" in summary
    assert "Phase 3 持续学习闭环" in summary
    assert "Phase 6 多 Agent 协作" in summary
    assert "Phase 8 反思、指标与评测基础设施" in summary
    assert "Phase 9 质量计划运营层" in summary
    assert "自我进化" in summary


def test_agent_dynamic_capability_summary_lists_runtime_tools_and_skills(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )
    registry.register(
        name="web_search",
        description="搜索网页",
        parameters={"query": {"type": "string"}},
        handler=lambda query: query,
        toolset="web",
        required_params=["query"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot",
            skills_enabled=True,
            skills_dir="~/.maxbot/skills",
            memory_enabled=False,
        ),
        registry=registry,
    )

    summary = agent._build_capability_summary()

    assert "动态生成" in summary
    assert "memory" in summary
    assert "read_file" in summary
    assert "web_search" in summary
    assert "tdd-workflow" in summary
    assert "code-analysis" in summary
    assert "builtin" in summary
    assert "file" in summary
    assert "web" in summary


def test_enhanced_system_prompt_uses_dynamic_capability_summary(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        description="读取文件",
        parameters={"path": {"type": "string"}},
        handler=lambda path: path,
        toolset="file",
        required_params=["path"],
    )

    agent = Agent(
        config=AgentConfig(
            api_key="test-key",
            system_prompt="你是 MaxBot，一个由用户自主开发的 AI 智能体。你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。",
            skills_enabled=True,
            skills_dir="~/.maxbot/skills",
            memory_enabled=False,
        ),
        registry=registry,
    )

    prompt = agent._get_enhanced_system_prompt("你有什么能力？")

    assert "你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。" not in prompt
    assert "当前可用能力摘要" in prompt
    assert "read_file" in prompt
    assert "tdd-workflow" in prompt


def test_system_prompt_defaults_are_consistent_and_not_static_capability_list(monkeypatch):
    monkeypatch.setattr("maxbot.core.agent_loop.get_config", lambda: (_ for _ in ()).throw(RuntimeError("force fallback")))

    yaml_prompt = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "maxbot" / "config" / "default_config.yaml").read_text(encoding="utf-8")
    )["system"]["prompt"].strip()
    dataclass_prompt = SystemConfig().prompt.strip()
    fallback_agent = AgentConfig(system_prompt=None)
    fallback_prompt = fallback_agent.system_prompt.strip()

    static_copy = "你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。"
    assert static_copy not in yaml_prompt
    assert static_copy not in dataclass_prompt
    assert static_copy not in fallback_prompt
    assert "\n" not in dataclass_prompt
    assert "\n" not in fallback_prompt
    assert yaml_prompt.replace("\n", "") == dataclass_prompt == fallback_prompt
    assert "动态描述" in yaml_prompt
