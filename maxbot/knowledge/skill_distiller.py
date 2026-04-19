from __future__ import annotations

import re
from typing import Any


class SkillDistiller:
    def distill(self, *, pattern: Any, validation: Any) -> dict[str, Any] | None:
        if pattern.pattern_type != "tool_sequence":
            return None

        overall = getattr(validation.score, "overall", 0.0)
        if overall < 0.7:
            return None

        sequence = pattern.data.get("sequence") or pattern.data.get("match_context", {}).get("tool_sequence", [])
        if not sequence:
            return None

        return {
            "name": self._slugify(pattern.name),
            "source_pattern_id": pattern.id,
            "pattern_type": pattern.pattern_type,
            "confidence": round(overall, 2),
            "description": pattern.description or pattern.name,
            "steps": [self._tool_to_step(tool_name) for tool_name in sequence],
        }

    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower())
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug or "generated-skill"

    def _tool_to_step(self, tool_name: str) -> str:
        mapping = {
            "search_files": "使用 search_files 收集相关文件或匹配项",
            "read_file": "使用 read_file 深入阅读关键内容",
            "patch": "使用 patch 应用最小必要改动",
            "write_file": "使用 write_file 写入完整文件内容",
            "terminal": "使用 terminal 执行必要命令",
        }
        return mapping.get(tool_name, f"使用 {tool_name} 完成对应步骤")
