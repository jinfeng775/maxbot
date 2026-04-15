"""Phase 2 测试 — 代码编辑引擎"""

import json
import tempfile
from pathlib import Path

import pytest

from maxbot.tools._registry import registry
from maxbot.tools.code_editor import (
    EditOperation,
    apply_edit,
    apply_edits,
    find_actual_string,
    generate_diff,
    generate_structured_patch,
    get_snippet,
    normalize_quotes,
)


# ── 引号标准化 ────────────────────────────────────────────

class TestQuoteNormalization:
    def test_normalize_curly_single(self):
        assert normalize_quotes("\u2018hello\u2019") == "'hello'"

    def test_normalize_curly_double(self):
        assert normalize_quotes("\u201chello\u201d") == '"hello"'

    def test_no_change(self):
        assert normalize_quotes("'hello'") == "'hello'"

    def test_find_exact(self):
        content = 'print("hello")'
        assert find_actual_string(content, 'print("hello")') == content

    def test_find_with_curly_quotes(self):
        content = 'print(\u201chello\u201d)'
        result = find_actual_string(content, 'print("hello")')
        assert result == content


# ── apply_edit 测试 ───────────────────────────────────────

class TestApplyEdit:
    def test_simple_replace(self):
        content = "hello world"
        new, count = apply_edit(content, "world", "maxbot")
        assert new == "hello maxbot"
        assert count == 1

    def test_replace_all(self):
        content = "aaa bbb aaa"
        new, count = apply_edit(content, "aaa", "xxx", replace_all=True)
        assert new == "xxx bbb xxx"
        assert count == 2

    def test_not_found(self):
        content = "hello world"
        new, count = apply_edit(content, "not_found", "xxx")
        assert new == content
        assert count == 0

    def test_multiline_replace(self):
        content = "line1\nline2\nline3"
        new, count = apply_edit(content, "line2", "REPLACED")
        assert new == "line1\nREPLACED\nline3"
        assert count == 1

    def test_delete_trailing_newline(self):
        content = "keep\ndelete_this\nkeep2"
        new, count = apply_edit(content, "delete_this", "")
        assert new == "keep\nkeep2"
        assert count == 1


# ── apply_edits 多编辑测试 ────────────────────────────────

class TestApplyEdits:
    def test_sequential_edits(self):
        content = "aaa bbb ccc"
        edits = [
            EditOperation("aaa", "AAA"),
            EditOperation("ccc", "CCC"),
        ]
        new, counts = apply_edits(content, edits)
        assert new == "AAA bbb CCC"
        assert counts == [1, 1]

    def test_conflict_detection(self):
        content = "hello world"
        edits = [
            EditOperation("hello", "world"),  # new_string = "world"
            EditOperation("world", "maxbot"),  # old_string 是前一个 new_string 的子串！
        ]
        with pytest.raises(ValueError, match="冲突"):
            apply_edits(content, edits)

    def test_not_found_error(self):
        content = "hello"
        edits = [EditOperation("not_found", "xxx")]
        with pytest.raises(ValueError, match="未找到"):
            apply_edits(content, edits)


# ── Diff 生成测试 ─────────────────────────────────────────

class TestDiff:
    def test_basic_diff(self):
        original = "line1\nline2\nline3"
        modified = "line1\nMODIFIED\nline3"
        diff = generate_diff(original, modified)
        assert "-line2" in diff
        assert "+MODIFIED" in diff

    def test_structured_patch(self):
        original = "a\nb\nc"
        modified = "a\nB\nc"
        patch = generate_structured_patch(original, modified)
        assert len(patch) > 0
        assert any(h["lines"] for h in patch)


# ── Snippet 测试 ──────────────────────────────────────────

class TestSnippet:
    def test_get_snippet(self):
        content = "\n".join(f"line{i}" for i in range(1, 21))
        snippet = get_snippet(content, change_line=10, context=2)
        # change_line=10 (1-indexed), context=2 → center=9, show indices 7-11 → lines 8-12
        assert "line8" in snippet
        assert "line12" in snippet


# ── 集成测试：工具注册 ────────────────────────────────────

class TestToolsRegistered:
    def test_code_edit_registered(self):
        assert registry.get("code_edit") is not None

    def test_code_edit_multi_registered(self):
        assert registry.get("code_edit_multi") is not None

    def test_undo_edit_registered(self):
        assert registry.get("undo_edit") is not None

    def test_code_create_registered(self):
        assert registry.get("code_create") is not None

    def test_notebook_tools_registered(self):
        assert registry.get("notebook_read") is not None
        assert registry.get("notebook_edit_cell") is not None
        assert registry.get("notebook_insert_cell") is not None
        assert registry.get("notebook_delete_cell") is not None

    def test_analysis_tools_registered(self):
        assert registry.get("analyze_python") is not None
        assert registry.get("analyze_code") is not None
        assert registry.get("analyze_project") is not None
        assert registry.get("get_function") is not None


# ── 端到端测试：code_edit 工具调用 ────────────────────────

class TestCodeEditE2E:
    def test_edit_file(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")

        result = registry.call("code_edit", {
            "file_path": str(test_file),
            "old_string": "print('world')",
            "new_string": "print('maxbot')",
        })

        data = json.loads(result)
        assert data["success"] is True
        assert data["replacements"] == 1
        assert test_file.read_text() == "def hello():\n    print('maxbot')\n"

    def test_edit_not_found(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("hello world")

        result = registry.call("code_edit", {
            "file_path": str(test_file),
            "old_string": "not_found",
            "new_string": "xxx",
        })

        data = json.loads(result)
        assert "error" in data

    def test_create_file(self, tmp_path):
        new_file = tmp_path / "new.py"
        result = registry.call("code_create", {
            "file_path": str(new_file),
            "content": "print('hello')",
        })
        data = json.loads(result)
        assert data["success"] is True
        assert new_file.read_text() == "print('hello')"

    def test_create_file_no_overwrite(self, tmp_path):
        existing = tmp_path / "existing.py"
        existing.write_text("old content")

        result = registry.call("code_create", {
            "file_path": str(existing),
            "content": "new content",
            "overwrite": False,
        })
        data = json.loads(result)
        assert "error" in data
        assert existing.read_text() == "old content"


# ── 代码分析测试 ──────────────────────────────────────────

class TestCodeAnalysis:
    def test_analyze_python(self, tmp_path):
        test_file = tmp_path / "sample.py"
        test_file.write_text('''
import os
from pathlib import Path

class MyClass:
    def method(self, x):
        return x * 2

def hello(name):
    print(f"Hello {name}")

async def fetch(url):
    pass
''')

        result = registry.call("analyze_python", {"file_path": str(test_file)})
        data = json.loads(result)

        assert len(data["imports"]) == 2
        assert len(data["classes"]) == 1
        assert data["classes"][0]["name"] == "MyClass"
        assert len(data["functions"]) == 2
        func_names = [f["name"] for f in data["functions"]]
        assert "hello" in func_names
        assert "fetch" in func_names

    def test_analyze_project(self, tmp_path):
        (tmp_path / "a.py").write_text("# empty")
        (tmp_path / "b.js").write_text("// empty")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").write_text("# empty")

        result = registry.call("analyze_project", {"project_path": str(tmp_path)})
        data = json.loads(result)
        assert data["total_files"] >= 3

    def test_get_function(self, tmp_path):
        test_file = tmp_path / "sample.py"
        test_file.write_text('''
def hello(name):
    """Say hello"""
    print(f"Hello {name}")
    return True

def goodbye():
    pass
''')

        result = registry.call("get_function", {
            "file_path": str(test_file),
            "function_name": "hello",
        })
        data = json.loads(result)
        assert data["name"] == "hello"
        assert "def hello" in data["source"]
        assert "name" in data["args"]
