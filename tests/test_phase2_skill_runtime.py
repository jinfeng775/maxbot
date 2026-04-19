from pathlib import Path
from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.skills import SkillManager


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
