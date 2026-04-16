"""
补丁生成器 — LLM 根据问题生成 unified diff 补丁

核心流程：
1. 给 LLM 问题描述 + 相关源码
2. LLM 输出 unified diff 格式的补丁
3. 验证补丁可应用
4. 返回 Patch 对象
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.self_analyzer import Issue


@dataclass
class Patch:
    """生成的补丁"""
    issue_title: str
    files_changed: list[str] = field(default_factory=list)
    diff: str = ""                # unified diff 格式
    description: str = ""
    confidence: float = 0.0
    raw_llm_response: str = ""

    def is_valid(self) -> bool:
        """基本格式检查"""
        return bool(self.diff) and "---" in self.diff and "+++" in self.diff


_SYSTEM_PROMPT = """你是一个代码修复专家。根据提供的问题描述和源码，生成 unified diff 格式的补丁。

规则：
1. 只输出 unified diff，不要有其他文字
2. 补丁必须可以被 `git apply` 或 `patch` 命令应用
3. 文件路径使用相对路径（相对于项目根目录）
4. 最小化改动 — 只改必要的部分
5. 不要改变函数签名（除非问题明确要求）
6. 保持原有代码风格

格式：
```
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line_start,line_count +line_start,line_count @@
 context line
-removed line
+added line
 context line
```

如果问题无法通过代码修改解决，返回空字符串。"""


def generate_patch(
    issue: Issue,
    project_root: str | Path,
    llm_client: Any,
    model: str = "gpt-4o-mini",
) -> Patch:
    """
    为单个问题生成补丁

    Args:
        issue: 要修复的问题
        project_root: 项目根目录
        llm_client: LLM 客户端
        model: 模型名
    """
    root = Path(project_root)
    patch = Patch(issue_title=issue.title)

    # 读取相关源码
    target_file = root / issue.file
    if not target_file.is_file():
        patch.description = f"文件不存在: {issue.file}"
        return patch

    try:
        source = target_file.read_text(encoding="utf-8")
    except Exception as e:
        patch.description = f"读取文件失败: {e}"
        return patch

    # 构建 prompt
    user_prompt = f"""# 问题

分类: {issue.category}
严重程度: {issue.severity}
文件: {issue.file}
标题: {issue.title}
描述: {issue.description}
建议: {issue.suggestion}

# 源码 ({issue.file})

```python
{source}
```

请生成 unified diff 补丁修复这个问题。只输出 diff 内容。"""

    try:
        response = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content.strip()
        patch.raw_llm_response = content

        # 提取 diff（可能被 ``` 包裹）
        diff = _extract_diff(content)
        patch.diff = diff
        patch.files_changed = _extract_changed_files(diff)
        patch.confidence = 0.8 if diff else 0.0

        if not diff:
            patch.description = "LLM 未生成有效 diff"

    except Exception as e:
        patch.description = f"LLM 调用失败: {e}"

    return patch


def generate_patches(
    issues: list[Issue],
    project_root: str | Path,
    llm_client: Any,
    model: str = "gpt-4o-mini",
    max_patches: int = 10,
) -> list[Patch]:
    """批量生成补丁"""
    patches = []
    for issue in issues[:max_patches]:
        if issue.category in ("missing_feature",):
            continue  # 缺失功能不适合用 patch 修复
        p = generate_patch(issue, project_root, llm_client, model)
        if p.is_valid():
            patches.append(p)
    return patches


def validate_patch(patch: Patch, project_root: str | Path) -> tuple[bool, str]:
    """
    验证补丁是否可以应用（dry-run）

    使用 `git apply --check` 或 `patch --dry-run`
    """
    if not patch.is_valid():
        return False, "补丁格式无效"

    root = Path(project_root)

    # 写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(patch.diff)
        patch_file = f.name

    try:
        # 先尝试 git apply
        result = subprocess.run(
            ["git", "apply", "--check", patch_file],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "git apply --check 通过"

        # 回退到 patch --dry-run
        result = subprocess.run(
            ["patch", "--dry-run", "-p1", f"<{patch_file}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            shell=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "patch --dry-run 通过"

        return False, f"补丁无法应用: {result.stderr[:200]}"

    except Exception as e:
        return False, f"验证失败: {e}"
    finally:
        Path(patch_file).unlink(missing_ok=True)


def _extract_diff(content: str) -> str:
    """从 LLM 响应中提取 diff 内容"""
    # 去掉 ``` 包裹
    content = re.sub(r'^```\w*\n?', '', content)
    content = re.sub(r'\n?```$', '', content)

    # 找到 --- 开头的 diff
    match = re.search(r'(^---\s+a/.*$)', content, re.MULTILINE)
    if match:
        return content[match.start():].strip()

    return content.strip() if "---" in content and "+++" in content else ""


def _extract_changed_files(diff: str) -> list[str]:
    """从 diff 中提取变更的文件列表"""
    return re.findall(r'^\+\+\+\s+b/(.+)$', diff, re.MULTILINE)
