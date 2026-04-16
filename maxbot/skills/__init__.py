"""
技能系统 — MaxBot 可执行知识

技能是自包含的指令文档（SKILL.md），告诉 Agent 如何执行特定任务。
参考 Hermes 的技能系统设计。

目录结构:
    ~/.maxbot/skills/
    ├── git-workflow/
    │   ├── SKILL.md          # 技能说明 + 执行步骤
    │   └── references/       # 参考资料（可选）
    └── code-review/
        └── SKILL.md
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    content: str                      # SKILL.md 的完整内容
    path: Path
    triggers: list[str] = field(default_factory=list)  # 触发关键词
    tools_needed: list[str] = field(default_factory=list)  # 依赖的工具
    category: str = "general"
    priority: int = 0


class SkillManager:
    """
    技能管理器

    用法:
        sm = SkillManager()
        skills = sm.list_skills()
        matched = sm.match_skills("帮我 review 代码")
    """

    def __init__(self, skills_dir: str | Path | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else Path.home() / ".maxbot" / "skills"
        self._skills: dict[str, Skill] = {}
        self._load_skills()

    def _load_skills(self):
        """从目录加载所有技能"""
        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                skill = self._parse_skill(skill_dir.name, content, skill_dir)
                self._skills[skill.name] = skill
            except Exception as e:
                print(f"⚠️ 加载技能失败: {skill_dir} — {e}")

    def _parse_skill(self, name: str, content: str, path: Path) -> Skill:
        """解析 SKILL.md（支持 YAML frontmatter）"""
        triggers = []
        tools_needed = []
        category = "general"
        description = ""

        # 尝试解析 YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    triggers = meta.get("triggers", [])
                    tools_needed = meta.get("tools", [])
                    category = meta.get("category", "general")
                    description = meta.get("description", "")
                except Exception:
                    pass

        if not description:
            # 从第一行非空文本提取描述
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---"):
                    description = line[:200]
                    break

        return Skill(
            name=name,
            description=description,
            content=content,
            path=path,
            triggers=triggers,
            tools_needed=tools_needed,
            category=category,
        )

    def list_skills(self) -> list[Skill]:
        """列出所有技能"""
        return list(self._skills.values())

    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能"""
        return self._skills.get(name)

    def match_skills(self, user_message: str) -> list[Skill]:
        """
        根据用户消息匹配相关技能

        策略：
        1. 精确触发词匹配
        2. 关键词模糊匹配
        """
        matched = []
        msg_lower = user_message.lower()

        for skill in self._skills.values():
            # 触发词匹配
            for trigger in skill.triggers:
                if trigger.lower() in msg_lower:
                    matched.append(skill)
                    break
            else:
                # 名称匹配
                if skill.name.replace("-", " ").replace("_", " ") in msg_lower:
                    matched.append(skill)

        # 按优先级排序
        matched.sort(key=lambda s: s.priority, reverse=True)
        return matched

    def get_injectable_content(self, user_message: str, max_chars: int = 4000) -> str:
        """
        获取应注入到 system prompt 的技能内容

        返回匹配技能的 SKILL.md 内容
        """
        matched = self.match_skills(user_message)
        if not matched:
            return ""

        parts = []
        total = 0
        for skill in matched:
            if total + len(skill.content) > max_chars:
                break
            parts.append(f"## 技能: {skill.name}\n\n{skill.content}")
            total += len(skill.content)

        return "\n\n---\n\n".join(parts)

    def install_skill(self, name: str, content: str) -> Skill:
        """安装新技能"""
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")

        skill = self._parse_skill(name, content, skill_dir)
        self._skills[name] = skill
        return skill
