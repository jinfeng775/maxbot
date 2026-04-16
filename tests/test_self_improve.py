"""
Phase 6 自我改进 — 测试

覆盖:
- self_analyzer: Issue/AnalysisReport 数据结构
- patch_generator: Patch 结构、diff 提取、文件提取、补丁验证
- self_improver: 改进流程（用 mock LLM）、回滚、历史记录
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch as mock_patch

import pytest


# ══════════════════════════════════════════════════════════════
# Self Analyzer Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.self_analyzer import Issue, AnalysisReport


class TestIssue:
    """Issue 数据结构"""

    def test_create(self):
        issue = Issue(
            category="bug",
            severity="high",
            file="core/agent_loop.py",
            line=42,
            title="空指针风险",
            description="未检查 None",
            suggestion="添加空值检查",
        )
        assert issue.category == "bug"
        assert issue.severity == "high"

    def test_defaults(self):
        issue = Issue(category="code_quality", severity="low", file="x.py")
        assert issue.line is None
        assert issue.title == ""


class TestAnalysisReport:
    """分析报告"""

    def test_empty_report(self):
        report = AnalysisReport(project_root="/test")
        assert report.total_count == 0
        assert report.critical_count == 0

    def test_counts(self):
        report = AnalysisReport(
            project_root="/test",
            issues=[
                Issue(category="bug", severity="critical", file="a.py"),
                Issue(category="bug", severity="high", file="b.py"),
                Issue(category="performance", severity="low", file="c.py"),
            ],
        )
        assert report.total_count == 3
        assert report.critical_count == 1

    def test_by_category(self):
        report = AnalysisReport(
            project_root="/test",
            issues=[
                Issue(category="bug", severity="high", file="a.py"),
                Issue(category="performance", severity="low", file="b.py"),
                Issue(category="bug", severity="medium", file="c.py"),
            ],
        )
        by_cat = report.by_category()
        assert len(by_cat["bug"]) == 2
        assert len(by_cat["performance"]) == 1

    def test_text_report(self):
        report = AnalysisReport(
            project_root="/test",
            issues=[Issue(
                category="bug", severity="high", file="x.py", line=10,
                title="Test bug", description="A bug", suggestion="Fix it",
            )],
        )
        text = report.text_report()
        assert "Test bug" in text
        assert "x.py:10" in text
        assert "Fix it" in text


# ══════════════════════════════════════════════════════════════
# Patch Generator Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.patch_generator import (
    Patch, _extract_diff, _extract_changed_files, validate_patch,
)


class TestPatch:
    """Patch 数据结构"""

    def test_valid_patch(self):
        p = Patch(
            issue_title="fix bug",
            diff="--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@\n-old\n+new\n",
            files_changed=["file.py"],
        )
        assert p.is_valid()

    def test_empty_patch(self):
        p = Patch(issue_title="nothing")
        assert not p.is_valid()

    def test_no_diff_markers(self):
        p = Patch(issue_title="bad", diff="just some text")
        assert not p.is_valid()


class TestDiffExtraction:
    """从 LLM 响应提取 diff"""

    def test_plain_diff(self):
        content = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old
+new"""
        diff = _extract_diff(content)
        assert "--- a/file.py" in diff
        assert "+new" in diff

    def test_markdown_wrapped(self):
        content = """```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old
+new
```"""
        diff = _extract_diff(content)
        assert "--- a/file.py" in diff
        assert "```" not in diff

    def test_no_diff(self):
        content = "I can't fix this issue."
        diff = _extract_diff(content)
        assert diff == ""

    def test_extract_files(self):
        diff = """--- a/core/agent.py
+++ b/core/agent.py
@@ -1,1 +1,1 @@
-old
+new
--- a/tools/shell.py
+++ b/tools/shell.py
@@ -1,1 +1,1 @@
-x
+y"""
        files = _extract_changed_files(diff)
        assert "core/agent.py" in files
        assert "tools/shell.py" in files


class TestPatchValidation:
    """补丁验证"""

    def test_invalid_patch(self):
        p = Patch(issue_title="bad")
        ok, reason = validate_patch(p, "/nonexistent")
        assert not ok

    def test_valid_diff_format_with_bad_project(self):
        p = Patch(
            issue_title="fix",
            diff="--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        )
        ok, reason = validate_patch(p, "/nonexistent")
        assert not ok  # git apply fails on nonexistent dir


# ══════════════════════════════════════════════════════════════
# Self Improver Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.self_improver import SelfImprover, ImprovementResult


class TestSelfImprover:
    """自我改进器"""

    def test_nonexistent_project(self):
        improver = SelfImprover("/nonexistent")
        # git clean check should fail gracefully
        assert improver._is_git_clean() is False

    def test_history_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            improver = SelfImprover(tmp)
            assert improver.get_history() == []

    def test_history_save_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            improver = SelfImprover(tmp)

            result = ImprovementResult(
                project_root=tmp,
                attempts=[],
            )
            result.attempts.append(type('obj', (object,), {
                'issue': type('obj', (object,), {
                    'title': 'fix bug',
                    'category': 'bug',
                })(),
                'applied': True,
                'test_passed': True,
                'rolled_back': False,
                'error': '',
                'elapsed': 1.5,
            })())

            improver._save_history(result)
            history = improver.get_history()
            assert len(history) == 1
            assert history[0]["issue"] == "fix bug"
            assert history[0]["applied"] is True

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Initialize git repo
            subprocess = __import__("subprocess")
            subprocess.run(["git", "init"], cwd=tmp, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, capture_output=True)

            # Create and commit a file
            p = Path(tmp) / "test.txt"
            p.write_text("original")
            subprocess.run(["git", "add", "."], cwd=tmp, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmp, capture_output=True)

            # Modify file
            p.write_text("modified")

            improver = SelfImprover(tmp)
            improver._rollback()

            assert p.read_text() == "original"


class TestImprovementResult:
    """改进结果"""

    def test_summary(self):
        result = ImprovementResult(project_root="/test")
        text = result.summary()
        assert "自我改进报告" in text
        assert "0" in text  # 0 issues, 0 attempts

    def test_counts(self):
        from maxbot.knowledge.self_improver import ImprovementAttempt
        result = ImprovementResult(
            project_root="/test",
            attempts=[
                ImprovementAttempt(
                    issue=Issue(category="bug", severity="high", file="a.py", title="fix a"),
                    applied=True, test_passed=True, rolled_back=False,
                ),
                ImprovementAttempt(
                    issue=Issue(category="bug", severity="medium", file="b.py", title="fix b"),
                    applied=True, test_passed=False, rolled_back=True,
                ),
            ],
        )
        assert result.applied_count == 1
        assert result.failed_count == 1
