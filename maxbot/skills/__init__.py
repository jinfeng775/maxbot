"""
技能系统性能优化

改进技能匹配和加载的性能
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from functools import lru_cache
import re


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

    # 性能优化：预编译正则表达式
    _trigger_patterns: list[re.Pattern] = field(default_factory=list, init=False)

    def __post_init__(self):
        """初始化后处理"""
        # 预编译触发词的正则表达式
        for trigger in self.triggers:
            try:
                pattern = re.compile(re.escape(trigger.lower()))
                self._trigger_patterns.append(pattern)
            except re.error:
                pass


class SkillManager:
    """
    技能管理器（性能优化版）

    改进：
    - 缓存技能匹配结果
    - 预编译正则表达式
    - 延迟加载技能内容
    - 支持增量更新
    - 默认同时加载用户技能目录与仓库内置核心技能目录
    """

    def __init__(self, skills_dir: str | Path | None = None):
        self.skills_dir = self._resolve_primary_skills_dir(skills_dir)
        self._load_dirs = self._resolve_load_dirs(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._skills_index: dict[str, list[str]] = {}  # 触发词索引
        self._last_load_time: float = 0
        self._load_skills()
        self._build_index()

    @staticmethod
    def _builtin_skills_dir() -> Path:
        return Path(__file__).resolve().parent / "core"

    @staticmethod
    def _default_user_skills_dir() -> Path:
        return (Path.home() / ".maxbot" / "skills").expanduser()

    @classmethod
    def _resolve_primary_skills_dir(cls, skills_dir: str | Path | None) -> Path:
        if skills_dir is None:
            return cls._default_user_skills_dir()
        return Path(skills_dir).expanduser()

    @classmethod
    def _resolve_load_dirs(cls, skills_dir: str | Path | None) -> list[Path]:
        builtin = cls._builtin_skills_dir()
        primary = cls._resolve_primary_skills_dir(skills_dir)
        default_user = cls._default_user_skills_dir()

        dirs: list[Path] = []
        if skills_dir is None or primary == default_user:
            dirs.extend([builtin, primary])
        else:
            dirs.append(primary)

        deduped: list[Path] = []
        seen: set[Path] = set()
        for directory in dirs:
            resolved = directory.expanduser()
            if resolved in seen:
                continue
            seen.add(resolved)
            deduped.append(resolved)
        return deduped

    def _load_skills(self):
        """从目录加载所有技能"""
        for base_dir in self._load_dirs:
            if not base_dir.exists():
                continue

            for skill_dir in base_dir.iterdir():
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
                    print(f"⚠️  加载技能失败: {skill_dir} — {e}")

    def _build_index(self):
        """构建触发词索引（用于快速匹配）"""
        self._skills_index = {}

        for skill_name, skill in self._skills.items():
            for trigger in skill.triggers:
                trigger_lower = trigger.lower()
                if trigger_lower not in self._skills_index:
                    self._skills_index[trigger_lower] = []
                self._skills_index[trigger_lower].append(skill_name)

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
                    description = meta.get("description", "")
                    triggers = meta.get("triggers") or meta.get("keywords") or []
                    tools_needed = meta.get("tools") or meta.get("tools_required") or []
                    category = meta.get("category", "general")
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

    @lru_cache(maxsize=128)
    def match_skills(self, user_message: str) -> list[Skill]:
        """
        根据用户消息匹配相关技能（带缓存）

        策略：
        1. 精确触发词匹配
        2. 关键词模糊匹配
        """
        matched = []
        msg_lower = user_message.lower()

        # 使用索引快速匹配
        for trigger_lower, skill_names in self._skills_index.items():
            if trigger_lower in msg_lower:
                for skill_name in skill_names:
                    if skill_name in self._skills:
                        skill = self._skills[skill_name]
                        if skill not in matched:
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
        separator = "\n\n---\n\n"
        for skill in matched:
            remaining = max_chars - total
            if remaining <= 0:
                break

            prefix = f"## 技能: {skill.name}\n\n"
            if len(prefix) >= remaining:
                break

            available_for_content = remaining - len(prefix)
            skill_body = skill.content
            if len(skill_body) > available_for_content:
                skill_body = skill_body[:available_for_content].rstrip()
                if not skill_body:
                    break

            segment = f"{prefix}{skill_body}"
            if parts and len(separator) <= max_chars - total:
                total += len(separator)
                parts.append(separator)
            elif parts:
                break

            parts.append(segment)
            total += len(segment)

        return "".join(parts)

    def install_skill(self, name: str, content: str) -> Skill:
        """安装新技能"""
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")

        skill = self._parse_skill(name, content, skill_dir)
        self._skills[name] = skill

        # 更新索引和缓存
        self._build_index()
        self.match_skills.cache_clear()

        return skill

    def reload_skills(self):
        """重新加载所有技能"""
        self._skills.clear()
        self._load_skills()
        self._build_index()
        self.match_skills.cache_clear()

    def get_stats(self) -> dict[str, Any]:
        """获取技能统计信息"""
        return {
            "total_skills": len(self._skills),
            "total_triggers": sum(len(s.triggers) for s in self._skills.values()),
            "categories": list(set(s.category for s in self._skills.values())),
            "cache_size": self.match_skills.cache_info().currsize,
        }
