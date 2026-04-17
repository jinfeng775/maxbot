"""
技能管理工具 — 管理生成的技能

功能:
- 列出所有技能
- 查看技能详情
- 删除技能
- 更新技能
- 重新生成技能
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maxbot.tools._registry import registry


@dataclass
class SkillInfo:
    """技能信息"""
    name: str
    path: str
    version: int
    description: str = ""
    tags: list[str] | None = None
    source: str = ""
    created_at: float = 0.0
    has_handler: bool = False
    has_meta: bool = False
    is_registered: bool = False


class SkillManager:
    """
    技能管理器

    用法:
        manager = SkillManager(skills_dir="~/.maxbot/skills")
        skills = manager.list_skills()
    """

    def __init__(self, skills_dir: str | Path | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else Path.home() / ".maxbot" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self, pattern: str = "") -> list[SkillInfo]:
        """
        列出所有技能

        Args:
            pattern: 名称过滤模式（支持部分匹配）
        """
        skills = []

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            if pattern and pattern.lower() not in skill_dir.name.lower():
                continue

            info = self._load_skill_info(skill_dir)
            if info:
                skills.append(info)

        return skills

    def get_skill(self, name: str) -> SkillInfo | None:
        """
        获取单个技能信息

        Args:
            name: 技能名称
        """
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return None

        return self._load_skill_info(skill_dir)

    def delete_skill(self, name: str) -> bool:
        """
        删除技能

        Args:
            name: 技能名称

        Returns:
            是否成功删除
        """
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return False

        # 从注册表中卸载
        tool = registry.get(name)
        if tool:
            registry.unregister(name)

        # 删除目录
        shutil.rmtree(skill_dir)
        return True

    def update_skill(
        self,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """
        更新技能元数据

        Args:
            name: 技能名称
            description: 新描述
            tags: 新标签列表

        Returns:
            是否成功更新
        """
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return False

        md_path = skill_dir / "SKILL.md"
        if not md_path.exists():
            return False

        # 读取 SKILL.md
        content = md_path.read_text()

        # 更新描述
        if description:
            import re
            # 更新 YAML frontmatter 中的 description
            def replace_desc(m):
                return f'description: "{description}"'
            content = re.sub(r'description: ".*?"', replace_desc, content, count=1)

        # 更新标签
        if tags is not None:
            import re
            tags_str = json.dumps(tags)
            def replace_tags(m):
                return f'tags: {tags_str}'
            content = re.sub(r'tags: \[.*?\]', replace_tags, content, count=1)

        # 写回
        md_path.write_text(content)
        return True

    def reload_skill(self, name: str) -> bool:
        """
        重新加载技能（热重载）

        Args:
            name: 技能名称

        Returns:
            是否成功重载
        """
        # 从注册表热重载
        return registry.hot_reload(name)

    def get_skill_content(self, name: str) -> dict[str, str]:
        """
        获取技能的所有内容

        Args:
            name: 技能名称

        Returns:
            包含 SKILL.md 和 handler.py 内容的字典
        """
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return {}

        result = {}

        md_path = skill_dir / "SKILL.md"
        if md_path.exists():
            result["SKILL.md"] = md_path.read_text()

        handler_path = skill_dir / "handler.py"
        if handler_path.exists():
            result["handler.py"] = handler_path.read_text()

        meta_path = skill_dir / "meta.json"
        if meta_path.exists():
            result["meta.json"] = meta_path.read_text()

        return result

    def _load_skill_info(self, skill_dir: Path) -> SkillInfo | None:
        """加载技能信息"""
        name = skill_dir.name

        md_path = skill_dir / "SKILL.md"
        handler_path = skill_dir / "handler.py"
        meta_path = skill_dir / "meta.json"

        if not md_path.exists():
            return None

        # 解析 SKILL.md
        description = ""
        tags = []
        source = ""
        version = 1
        created_at = 0.0

        md_content = md_path.read_text()

        # 解析 YAML frontmatter
        import re
        yaml_match = re.match(r'^---\n(.*?)\n---', md_content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
            # 简单解析（不使用 PyYAML 以减少依赖）
            for line in yaml_content.split('\n'):
                line = line.strip()
                if line.startswith('description:'):
                    description = line.split(':', 1)[1].strip().strip('"\'')
                elif line.startswith('tags:'):
                    tags_str = line.split(':', 1)[1].strip()
                    if tags_str.startswith('['):
                        try:
                            tags = json.loads(tags_str)
                        except:
                            pass
                elif line.startswith('source:'):
                    source = line.split(':', 1)[1].strip().strip('"\'')
                elif line.startswith('version:'):
                    try:
                        version = int(line.split(':', 1)[1].strip())
                    except:
                        pass

        # 解析 meta.json
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                if 'created_at' in meta:
                    created_at = meta['created_at']
            except:
                pass

        # 检查是否已注册
        is_registered = registry.get(name) is not None

        return SkillInfo(
            name=name,
            path=str(skill_dir),
            version=version,
            description=description,
            tags=tags,
            source=source,
            created_at=created_at,
            has_handler=handler_path.exists(),
            has_meta=meta_path.exists(),
            is_registered=is_registered,
        )


# 创建全局实例
skill_manager = SkillManager()


# 注册工具
@registry.tool(
    name="list_skills",
    description="列出所有已生成的技能",
    toolset="skill_management",
    tags=["skill", "list", "management"],
)
def list_skills(pattern: str = "") -> str:
    """
    列出所有技能

    Args:
        pattern: 名称过滤模式（可选）
    """
    skills = skill_manager.list_skills(pattern)
    if not skills:
        return "没有找到技能"

    result = []
    result.append(f"找到 {len(skills)} 个技能:\n")
    result.append("-" * 60)

    for skill in skills:
        status = "✅ 已注册" if skill.is_registered else "⚠️ 未注册"
        tags_str = ", ".join(skill.tags) if skill.tags else "-"
        result.append(
            f"\n📦 {skill.name}\n"
            f"   描述: {skill.description or '-'}\n"
            f"   版本: {skill.version} | {status}\n"
            f"   标签: {tags_str}\n"
            f"   来源: {skill.source or '-'}\n"
            f"   路径: {skill.path}"
        )

    return "\n".join(result)


@registry.tool(
    name="get_skill",
    description="查看技能的详细信息",
    toolset="skill_management",
    tags=["skill", "detail", "management"],
)
def get_skill(name: str) -> str:
    """
    查看技能详细信息

    Args:
        name: 技能名称
    """
    skill = skill_manager.get_skill(name)
    if not skill:
        return f"❌ 未找到技能: {name}"

    status = "✅ 已注册" if skill.is_registered else "⚠️ 未注册"
    tags_str = ", ".join(skill.tags) if skill.tags else "-"

    result = [
        f"📦 技能: {skill.name}",
        f"   描述: {skill.description or '-'}",
        f"   版本: {skill.version}",
        f"   状态: {status}",
        f"   标签: { {tags_str} }",
        f"   来源: {skill.source or '-'}",
        f"   路径: {skill.path}",
        f"   Handler: {'✅' if skill.has_handler else '❌'}",
        f"   Meta: {'✅' if skill.has_meta else '❌'}",
    ]

    return "\n".join(result)


@registry.tool(
    name="delete_skill",
    description="删除指定的技能",
    toolset="skill_management",
    tags=["skill", "delete", "management"],
)
def delete_skill(name: str) -> str:
    """
    删除技能

    Args:
        name: 技能名称
    """
    success = skill_manager.delete_skill(name)
    if success:
        return f"✅ 已删除技能: {name}"
    else:
        return f"❌ 删除失败: 未找到技能 {name}"


@registry.tool(
    name="update_skill",
    description="更新技能的描述或标签",
    toolset="skill_management",
    tags=["skill", "update", "management"],
)
def update_skill(name: str, description: str = "", tags: str = "") -> str:
    """
    更新技能

    Args:
        name: 技能名称
        description: 新描述（可选）
        tags: 新标签，逗号分隔（可选）
    """
    tags_list = None
    if tags:
        tags_list = [t.strip() for t in tags.split(',')]

    success = skill_manager.update_skill(name, description, tags_list)
    if success:
        return f"✅ 已更新技能: {name}"
    else:
        return f"❌ 更新失败: 未找到技能 {name}"


@registry.tool(
    name="reload_skill",
    description="重新加载技能（热重载）",
    toolset="skill_management",
    tags=["skill", "reload", "management"],
)
def reload_skill(name: str) -> str:
    """
    重新加载技能

    Args:
        name: 技能名称
    """
    success = skill_manager.reload_skill(name)
    if success:
        return f"✅ 已重新加载技能: {name}"
    else:
        return f"❌ 重载失败: 未找到技能 {name}"


@registry.tool(
    name="get_skill_content",
    description="获取技能的完整内容（SKILL.md 和 handler.py）",
    toolset="skill_management",
    tags=["skill", "content", "management"],
)
def get_skill_content(name: str) -> str:
    """
    获取技能内容

    Args:
        name: 技能名称
    """
    content = skill_manager.get_skill_content(name)
    if not content:
        return f"❌ 未找到技能: {name}"

    result = [f"📦 技能内容: {name}\n"]

    for filename, file_content in content.items():
        result.append(f"{'=' * 60}")
        result.append(f"📄 {filename}")
        result.append(f"{'=' * 60}")
        result.append(file_content)
        result.append("")

    return "\n".join(result)
