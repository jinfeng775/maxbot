"""
技能工厂 — 从提取的能力自动生成 SKILL.md + handler 脚本

流程:
1. 接收 ExtractedCapability 列表
2. 为每个能力生成 SKILL.md（含 YAML frontmatter）
3. 生成 handler 脚本（可执行的 Python 文件）
4. 版本管理（更新时保留旧版）
5. 冲突检测
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.capability_extractor import ExtractedCapability


@dataclass
class GeneratedSkill:
    """生成的技能"""
    name: str
    skill_md_path: str
    handler_path: str
    capability: ExtractedCapability
    version: int = 1
    created_at: float = field(default_factory=time.time)


class SkillFactory:
    """
    技能工厂 — 批量生成技能

    用法:
        factory = SkillFactory(output_dir="~/.maxbot/skills")
        skills = factory.generate(capabilities)
    """

    def __init__(self, output_dir: str | Path | None = None):
        self.output_dir = Path(output_dir) if output_dir else Path.home() / ".maxbot" / "skills"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        capabilities: list[ExtractedCapability],
        overwrite: bool = False,
    ) -> list[GeneratedSkill]:
        """
        从能力列表批量生成技能

        Args:
            capabilities: 提取出的能力列表
            overwrite: 是否覆盖已有技能

        Returns:
            生成的技能列表
        """
        skills = []
        for cap in capabilities:
            if not cap.name:
                continue
            skill = self._generate_single(cap, overwrite)
            if skill:
                skills.append(skill)
        return skills

    def _generate_single(
        self,
        cap: ExtractedCapability,
        overwrite: bool,
    ) -> GeneratedSkill | None:
        """生成单个技能"""
        skill_dir = self.output_dir / cap.name

        # Conflict detection
        if skill_dir.exists() and not overwrite:
            existing_md = skill_dir / "SKILL.md"
            if existing_md.exists():
                # Check if it's the same source
                existing_content = existing_md.read_text(encoding="utf-8")
                if cap.source_file in existing_content:
                    return None  # Already absorbed this file
                # Different source — version bump
                version = self._get_next_version(skill_dir)
            else:
                version = 1
        else:
            version = 1

        skill_dir.mkdir(parents=True, exist_ok=True)

        # Generate SKILL.md
        skill_md_content = self._build_skill_md(cap, version)
        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text(skill_md_content, encoding="utf-8")

        # Generate handler script
        handler_content = self._build_handler_script(cap)
        handler_path = skill_dir / "handler.py"
        handler_path.write_text(handler_content, encoding="utf-8")

        # Generate metadata
        meta = {
            "name": cap.name,
            "version": version,
            "source_file": cap.source_file,
            "source_function": cap.source_function,
            "created_at": time.time(),
            "confidence": cap.confidence,
            "tags": cap.tags,
        }
        meta_path = skill_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        return GeneratedSkill(
            name=cap.name,
            skill_md_path=str(skill_md_path),
            handler_path=str(handler_path),
            capability=cap,
            version=version,
        )

    def _build_skill_md(self, cap: ExtractedCapability, version: int) -> str:
        """构建 SKILL.md 内容"""
        # YAML frontmatter
        triggers = [cap.name.replace("_", " "), cap.source_function]
        tools_needed = []

        frontmatter = f"""---
description: "{cap.description}"
triggers: {json.dumps(triggers)}
tools: {json.dumps(tools_needed)}
source: "{cap.source_file}"
source_function: "{cap.source_function}"
version: {version}
confidence: {cap.confidence}
generated: true
tags: {json.dumps(cap.tags)}
---

"""

        # Body
        body = f"""# {cap.name}

{cap.description}

## 来源

- 文件: `{cap.source_file}`
- 函数: `{cap.source_function}`
- 版本: {version}
- 置信度: {cap.confidence:.0%}

## 参数

"""
        if cap.parameters:
            body += "| 参数 | 类型 | 必需 | 说明 |\n|------|------|------|------|\n"
            for pname, pinfo in cap.parameters.items():
                ptype = pinfo.get("type", "string")
                required = "✓" if pname in cap.required_params else ""
                desc = pinfo.get("description", "")
                body += f"| `{pname}` | {ptype} | {required} | {desc} |\n"
        else:
            body += "无参数\n"

        if cap.return_description:
            body += f"\n## 返回值\n\n{cap.return_description}\n"

        if cap.raw_docstring:
            body += f"\n## 原始文档\n\n```\n{cap.raw_docstring}\n```\n"

        body += f"""
## 使用方式

当用户请求与 `{cap.name}` 相关的任务时，自动调用此技能的 handler。

Handler 位于: `handler.py`
"""

        return frontmatter + body

    def _build_handler_script(self, cap: ExtractedCapability) -> str:
        """构建 handler 脚本"""
        if cap.handler_code:
            return f'''"""
Auto-generated handler for: {cap.name}
Source: {cap.source_file}::{cap.source_function}
"""

{cap.handler_code}
'''
        else:
            # Generate a fallback handler (shouldn't happen with proper extraction)
            params_sig = ", ".join(
                f'{pname}: str'
                for pname in cap.parameters
            )
            import_block = ""
            if cap.repo_path:
                import_block = f"""
    import sys
    if {cap.repo_path!r} not in sys.path:
        sys.path.insert(0, {cap.repo_path!r})"""

            mod_name = Path(cap.source_file).stem if cap.source_file else "unknown"
            return f'''"""
Auto-generated handler for: {cap.name}
Source: {cap.source_file}::{cap.source_function}
"""

import json


def {cap.name}({params_sig}) -> str:
    """{cap.description}"""
    try:{import_block}
        from {mod_name} import {cap.source_function} as _fn
        result = _fn({", ".join(f"{pname}={pname}" for pname in cap.parameters)})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({{"error": str(e)}}, ensure_ascii=False)
'''

    def _get_next_version(self, skill_dir: Path) -> int:
        """获取下一个版本号"""
        meta_path = skill_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                return meta.get("version", 0) + 1
            except Exception:
                pass
        return 1

    def list_generated_skills(self) -> list[dict[str, Any]]:
        """列出所有已生成的技能"""
        skills = []
        if not self.output_dir.exists():
            return skills

        for skill_dir in self.output_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            meta_path = skill_dir / "meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    skills.append(meta)
                except Exception:
                    pass
        return skills

    def remove_skill(self, name: str) -> bool:
        """删除已生成的技能"""
        skill_dir = self.output_dir / name
        if not skill_dir.exists():
            return False
        import shutil
        shutil.rmtree(skill_dir)
        return True
