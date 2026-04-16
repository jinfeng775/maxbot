"""
Phase 5 知识吸收系统 — 完整测试

覆盖模块:
- code_parser.py (多语言解析、项目扫描)
- capability_extractor.py (能力提取)
- skill_factory.py (技能生成)
- sandbox_validator.py (安全扫描、语法验证)
- auto_register.py (自动注册)
- KnowledgeAbsorber (端到端吸收)
"""

import json
import tempfile
from pathlib import Path

import pytest


# ══════════════════════════════════════════════════════════════
# Code Parser Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.code_parser import (
    parse_file, scan_project, summarize_structure,
    detect_language, ModuleInfo, FunctionInfo, ClassInfo,
    _parse_python, _parse_js_ts, _parse_go, _parse_rust,
)


class TestLanguageDetection:
    """语言检测"""

    def test_python(self):
        assert detect_language(Path("foo.py")) == "python"

    def test_javascript(self):
        assert detect_language(Path("app.js")) == "javascript"
        assert detect_language(Path("index.mjs")) == "javascript"
        assert detect_language(Path("comp.jsx")) == "javascript"

    def test_typescript(self):
        assert detect_language(Path("app.ts")) == "typescript"
        assert detect_language(Path("comp.tsx")) == "typescript"

    def test_go(self):
        assert detect_language(Path("main.go")) == "go"

    def test_rust(self):
        assert detect_language(Path("lib.rs")) == "rust"
        assert detect_language(Path("main.rs")) == "rust"

    def test_unknown(self):
        assert detect_language(Path("data.csv")) is None
        assert detect_language(Path("readme.md")) is None


class TestPythonParser:
    """Python AST 解析"""

    def test_simple_function(self):
        source = '''
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b
'''
        module = _parse_python(source, "math.py")
        assert module.language == "python"
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "add"
        assert func.docstring == "Add two numbers"
        assert func.return_type == "int"
        assert len(func.params) == 2
        assert func.params[0]["name"] == "a"
        assert func.params[0]["type"] == "int"

    def test_class_with_methods(self):
        source = '''
class Calculator:
    """A calculator"""
    def __init__(self):
        self.value = 0

    def add(self, n: int):
        """Add n to value"""
        self.value += n
'''
        module = _parse_python(source, "calc.py")
        assert len(module.classes) == 1
        cls = module.classes[0]
        assert cls.name == "Calculator"
        assert cls.docstring == "A calculator"
        assert len(cls.methods) == 2
        # __init__ should be extracted too (it's a method, not top-level private)
        method_names = [m.name for m in cls.methods]
        assert "add" in method_names

    def test_imports(self):
        source = '''
import os
import sys
from pathlib import Path
from typing import List, Dict
'''
        module = _parse_python(source, "imports.py")
        assert "os" in module.imports
        assert "sys" in module.imports
        assert "pathlib" in module.imports
        assert "typing" in module.imports

    def test_entry_point_main(self):
        source = '''
def main():
    print("hello")

if __name__ == "__main__":
    main()
'''
        module = _parse_python(source, "main.py")
        assert "__main__" in module.entry_points
        assert "main.py" in module.entry_points

    def test_async_function(self):
        source = '''
async def fetch(url: str) -> str:
    """Fetch a URL"""
    pass
'''
        module = _parse_python(source, "fetch.py")
        assert module.functions[0].is_async is True

    def test_decorators(self):
        source = '''
@app.route("/api")
def handler():
    """Handle request"""
    pass
'''
        module = _parse_python(source, "routes.py")
        assert "app.route" in module.functions[0].decorators[0]

    def test_default_params(self):
        source = '''
def greet(name: str, greeting: str = "Hello") -> str:
    """Greet someone"""
    return f"{greeting}, {name}"
'''
        module = _parse_python(source, "greet.py")
        func = module.functions[0]
        assert "'Hello'" in func.params[1].get("default", "")

    def test_syntax_error_graceful(self):
        source = "def broken(:\n  pass"
        module = _parse_python(source, "broken.py")
        assert module.language == "python"
        assert len(module.functions) == 0


class TestJavaScriptParser:
    """JavaScript 正则解析"""

    def test_function_declaration(self):
        source = '''
/**
 * Calculate sum
 */
function add(a, b) {
    return a + b;
}

export function multiply(a, b) {
    return a * b;
}
'''
        module = _parse_js_ts(source, "math.js", "javascript")
        assert module.language == "javascript"
        names = [f.name for f in module.functions]
        assert "add" in names
        assert "multiply" in names

    def test_arrow_function(self):
        source = '''
const double = (x) => x * 2;
export const triple = (x) => x * 3;
'''
        module = _parse_js_ts(source, "ops.js", "javascript")
        names = [f.name for f in module.functions]
        assert "double" in names

    def test_imports(self):
        source = '''
import React from 'react';
import { useState } from 'react';
const fs = require('fs');
'''
        module = _parse_js_ts(source, "app.js", "javascript")
        assert "react" in module.imports
        assert "fs" in module.imports

    def test_exports(self):
        source = '''
export function helper() {}
export const VALUE = 42;
'''
        module = _parse_js_ts(source, "lib.js", "javascript")
        assert "helper" in module.exports


class TestTypeScriptParser:
    """TypeScript 解析"""

    def test_typed_params(self):
        source = '''
function greet(name: string, age: number): string {
    return `Hello ${name}, age ${age}`;
}
'''
        module = _parse_js_ts(source, "greet.ts", "typescript")
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "greet"


class TestGoParser:
    """Go 正则解析"""

    def test_function(self):
        source = '''
package main

import "fmt"

// Add adds two integers
func Add(a int, b int) int {
    return a + b
}
'''
        module = _parse_go(source, "math.go")
        assert module.language == "go"
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "Add"
        assert func.docstring == "Add adds two integers"
        assert func.return_type == "int"

    def test_method(self):
        source = '''
func (s *Server) Start(addr string) error {
    return s.listenAndServe(addr)
}
'''
        module = _parse_go(source, "server.go")
        assert len(module.functions) == 1
        assert module.functions[0].is_method is True

    def test_main_entry(self):
        source = '''
func main() {
    fmt.Println("hello")
}
'''
        module = _parse_go(source, "main.go")
        assert "main()" in module.entry_points


class TestRustParser:
    """Rust 正则解析"""

    def test_function(self):
        source = '''
/// Add two numbers
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
'''
        module = _parse_rust(source, "lib.rs")
        assert module.language == "rust"
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "add"
        assert func.docstring == "Add two numbers"
        assert func.return_type == "i32"

    def test_struct(self):
        source = '''
pub struct Config {
    pub name: String,
}
'''
        module = _parse_rust(source, "config.rs")
        assert len(module.classes) == 1
        assert module.classes[0].name == "Config"

    def test_pub_exports(self):
        source = '''
pub fn public_api() {}
pub struct PublicStruct {}
pub enum PublicEnum {}
'''
        module = _parse_rust(source, "lib.rs")
        assert "public_api" in module.exports
        assert "PublicStruct" in module.exports


class TestProjectScanning:
    """项目扫描"""

    def test_scan_python_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create a mini project
            (Path(tmp) / "main.py").write_text('''
def main():
    """Entry point"""
    print("hello")
''')
            (Path(tmp) / "utils.py").write_text('''
def helper(x: int) -> int:
    """Helper function"""
    return x * 2
''')
            (Path(tmp) / "ignored.txt").write_text("not code")

            structure = scan_project(tmp)
            assert "python" in structure.languages
            assert structure.languages["python"] == 2
            assert len(structure.modules) == 2
            assert structure.total_functions == 2

    def test_skip_hidden_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            hidden = Path(tmp) / ".git"
            hidden.mkdir()
            (hidden / "config.py").write_text("SECRET = True")

            (Path(tmp) / "main.py").write_text("def main(): pass")

            structure = scan_project(tmp)
            assert len(structure.modules) == 1

    def test_summarize_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "api.py").write_text('''
def fetch_data(url: str) -> dict:
    """Fetch data from API"""
    pass
''')
            structure = scan_project(tmp)
            summary = summarize_structure(structure)
            assert "fetch_data" in summary
            assert "python" in summary


# ══════════════════════════════════════════════════════════════
# Capability Extractor Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.capability_extractor import (
    extract_capabilities_heuristic,
    extract_from_repo,
    ExtractedCapability,
)


class TestCapabilityExtraction:
    """启发式能力提取"""

    def test_extract_with_docstring(self):
        source = '''
def translate(text: str, target_lang: str) -> str:
    """Translate text to target language using neural MT"""
    pass
'''
        module = _parse_python(source, "translate.py")
        caps = extract_capabilities_heuristic(module)
        assert len(caps) == 1
        cap = caps[0]
        assert cap.source_function == "translate"
        assert "Translate" in cap.description
        assert "target_lang" in cap.parameters

    def test_skip_short_docstring(self):
        source = '''
def foo():
    """Too short"""
    pass
'''
        module = _parse_python(source, "foo.py")
        caps = extract_capabilities_heuristic(module, min_docstring_len=20)
        assert len(caps) == 0

    def test_skip_private(self):
        source = '''
def _internal_helper():
    """This is a long enough docstring to pass the filter"""
    pass
'''
        module = _parse_python(source, "internal.py")
        caps = extract_capabilities_heuristic(module)
        assert len(caps) == 0

    def test_fingerprint_dedup(self):
        cap1 = ExtractedCapability(
            name="tool_a", description="d", source_file="a.py", source_function="fn",
        )
        cap2 = ExtractedCapability(
            name="tool_b", description="d", source_file="a.py", source_function="fn",
        )
        assert cap1.fingerprint() == cap2.fingerprint()  # Same source

    def test_to_tool_schema(self):
        cap = ExtractedCapability(
            name="my_tool",
            description="Does things",
            source_file="tools.py",
            source_function="do_thing",
            parameters={"x": {"type": "integer", "description": "input"}},
            required_params=["x"],
        )
        schema = cap.to_tool_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "my_tool"
        assert schema["function"]["parameters"]["required"] == ["x"]


class TestBatchExtraction:
    """批量提取"""

    def test_extract_from_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "api.py").write_text('''
def search(query: str, limit: int = 10) -> list:
    """Search for items matching the query string"""
    pass

def get_item(item_id: str) -> dict:
    """Retrieve a single item by its unique ID"""
    pass
''')
            caps = extract_from_repo(tmp)
            names = [c.source_function for c in caps]
            assert "search" in names
            assert "get_item" in names


# ══════════════════════════════════════════════════════════════
# Skill Factory Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.skill_factory import SkillFactory, GeneratedSkill


class TestSkillFactory:
    """技能工厂"""

    def test_generate_single_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            factory = SkillFactory(output_dir=tmp)
            cap = ExtractedCapability(
                name="translate_text",
                description="Translate text to target language",
                source_file="translate.py",
                source_function="translate",
                parameters={"text": {"type": "string"}, "lang": {"type": "string"}},
                required_params=["text", "lang"],
                confidence=0.85,
                tags=["nlp", "translation"],
            )

            skills = factory.generate([cap])
            assert len(skills) == 1

            skill = skills[0]
            assert skill.name == "translate_text"
            assert skill.version == 1

            # Check SKILL.md exists and has content
            skill_md = Path(tmp) / "translate_text" / "SKILL.md"
            assert skill_md.exists()
            content = skill_md.read_text()
            assert "translate_text" in content
            assert "Translate text" in content
            assert "translate.py" in content

            # Check handler exists
            handler = Path(tmp) / "translate_text" / "handler.py"
            assert handler.exists()

            # Check meta exists
            meta = Path(tmp) / "translate_text" / "meta.json"
            assert meta.exists()
            meta_data = json.loads(meta.read_text())
            assert meta_data["confidence"] == 0.85

    def test_conflict_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            factory = SkillFactory(output_dir=tmp)
            cap = ExtractedCapability(
                name="my_tool",
                description="A tool",
                source_file="old.py",
                source_function="fn",
            )

            # First generate
            skills1 = factory.generate([cap])
            assert len(skills1) == 1

            # Same source — should skip
            skills2 = factory.generate([cap])
            assert len(skills2) == 0

            # Different source — should version bump
            cap2 = ExtractedCapability(
                name="my_tool",
                description="Updated tool",
                source_file="new.py",
                source_function="fn",
            )
            skills3 = factory.generate([cap2])
            assert len(skills3) == 1
            assert skills3[0].version == 2

    def test_list_and_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            factory = SkillFactory(output_dir=tmp)
            cap = ExtractedCapability(
                name="test_skill",
                description="Test",
                source_file="test.py",
                source_function="fn",
            )
            factory.generate([cap])

            skills = factory.list_generated_skills()
            assert len(skills) == 1

            factory.remove_skill("test_skill")
            skills = factory.list_generated_skills()
            assert len(skills) == 0


# ══════════════════════════════════════════════════════════════
# Sandbox Validator Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.sandbox_validator import (
    scan_security, validate_syntax, generate_test,
    run_sandboxed, batch_validate,
)


class TestSecurityScanning:
    """安全扫描"""

    def test_safe_handler(self):
        cap = ExtractedCapability(
            name="safe_tool",
            description="Safe tool",
            source_file="safe.py",
            source_function="fn",
            handler_code='def safe_tool(x: str) -> str:\n    return x.upper()',
        )
        report = scan_security(cap)
        assert report.is_safe is True
        assert report.risk_level == "low"

    def test_dangerous_eval(self):
        cap = ExtractedCapability(
            name="evil",
            description="Evil tool",
            source_file="evil.py",
            source_function="fn",
            handler_code='def evil(code: str) -> str:\n    return eval(code)',
        )
        report = scan_security(cap)
        assert report.is_safe is False
        assert any("eval" in issue for issue in report.issues)

    def test_dangerous_subprocess(self):
        cap = ExtractedCapability(
            name="runcmd",
            description="Run command",
            source_file="cmd.py",
            source_function="fn",
            handler_code='''
import subprocess
def runcmd(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True)
''',
        )
        report = scan_security(cap)
        assert report.is_safe is False

    def test_empty_handler(self):
        cap = ExtractedCapability(
            name="empty",
            description="Empty",
            source_file="e.py",
            source_function="fn",
            handler_code="",
        )
        report = scan_security(cap)
        assert report.is_safe is True
        assert len(report.warnings) > 0


class TestSyntaxValidation:
    """语法验证"""

    def test_valid_syntax(self):
        cap = ExtractedCapability(
            name="ok",
            description="OK",
            source_file="ok.py",
            source_function="fn",
            handler_code="def ok(): return 42",
        )
        valid, error = validate_syntax(cap)
        assert valid is True
        assert error == ""

    def test_invalid_syntax(self):
        cap = ExtractedCapability(
            name="bad",
            description="Bad",
            source_file="bad.py",
            source_function="fn",
            handler_code="def bad(:\n  pass",
        )
        valid, error = validate_syntax(cap)
        assert valid is False
        assert "Syntax error" in error


class TestSandboxExecution:
    """沙箱执行"""

    def test_safe_execution(self):
        cap = ExtractedCapability(
            name="add_tool",
            description="Add numbers",
            source_file="add.py",
            source_function="add",
            parameters={"a": {"type": "integer"}, "b": {"type": "integer"}},
            required_params=["a", "b"],
            handler_code="def add_tool(a: int, b: int) -> str:\n    return str(a + b)",
        )
        result = run_sandboxed(cap)
        assert result.security.is_safe is True
        assert result.syntax_valid is True

    def test_blocked_unsafe(self):
        cap = ExtractedCapability(
            name="dangerous",
            description="Dangerous",
            source_file="d.py",
            source_function="fn",
            handler_code='import os\ndef dangerous(): os.system("rm -rf /")',
        )
        result = run_sandboxed(cap)
        assert result.security.is_safe is False
        assert result.test_passed is None  # Shouldn't execute


class TestBatchValidation:
    """批量验证"""

    def test_batch(self):
        caps = [
            ExtractedCapability(
                name="good", description="Good", source_file="g.py",
                source_function="fn",
                handler_code="def good(): return 'ok'",
            ),
            ExtractedCapability(
                name="bad", description="Bad", source_file="b.py",
                source_function="fn",
                handler_code="def bad(: pass",
            ),
        ]
        results = batch_validate(caps)
        assert len(results) == 2
        assert results[0].syntax_valid is True
        assert results[1].syntax_valid is False


# ══════════════════════════════════════════════════════════════
# Auto Register Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge.auto_register import AutoRegister
from maxbot.core.tool_registry import ToolRegistry


class TestAutoRegister:
    """自动注册"""

    def test_register_with_registry(self):
        registry = ToolRegistry()
        register = AutoRegister(tool_registry=registry)

        cap = ExtractedCapability(
            name="absorbed_tool",
            description="An absorbed tool",
            source_file="external.py",
            source_function="tool_fn",
            parameters={"x": {"type": "string"}},
            required_params=["x"],
            handler_code="def absorbed_tool(x: str) -> str:\n    return x",
        )

        # Create a validation result that passes
        from maxbot.knowledge.sandbox_validator import ValidationResult, SecurityReport
        validation = ValidationResult(
            capability=cap,
            security=SecurityReport(is_safe=True),
            syntax_valid=True,
        )

        results = register.register_validated([validation])
        assert len(results) == 1
        assert results[0].success is True

        # Verify it's in the registry
        tool = registry.get("absorbed_tool")
        assert tool is not None
        assert tool.description == "An absorbed tool"
        assert tool.toolset == "absorbed"

    def test_reject_unsafe(self):
        registry = ToolRegistry()
        register = AutoRegister(tool_registry=registry)

        cap = ExtractedCapability(
            name="evil",
            description="Evil",
            source_file="e.py",
            source_function="fn",
            handler_code="import os",
        )
        from maxbot.knowledge.sandbox_validator import ValidationResult, SecurityReport
        validation = ValidationResult(
            capability=cap,
            security=SecurityReport(is_safe=False),
            syntax_valid=True,
        )

        results = register.register_validated([validation])
        assert results[0].success is False

    def test_unregister_all(self):
        registry = ToolRegistry()
        register = AutoRegister(tool_registry=registry)

        # Register directly
        registry.register(
            name="absorbed_a",
            description="A",
            parameters={},
            handler=lambda: "a",
            toolset="absorbed",
        )
        registry.register(
            name="absorbed_b",
            description="B",
            parameters={},
            handler=lambda: "b",
            toolset="absorbed",
        )

        count = register.unregister_absorbed()
        assert count == 2
        assert registry.get("absorbed_a") is None


# ══════════════════════════════════════════════════════════════
# End-to-End Integration Tests
# ══════════════════════════════════════════════════════════════

from maxbot.knowledge import KnowledgeAbsorber, AbsorptionResult


class TestEndToEnd:
    """端到端吸收流程"""

    def test_full_absorption_pipeline(self):
        with tempfile.TemporaryDirectory() as repo:
            # Create a mini "external" project
            (Path(repo) / "translator.py").write_text('''
"""Translation module"""

def translate(text: str, source: str = "auto", target: str = "en") -> str:
    """Translate text from source language to target language.

    Uses neural machine translation for high quality results.
    Supports 50+ languages.
    """
    return f"[{target}] {text}"

def detect_language(text: str) -> str:
    """Detect the language of input text using character analysis."""
    return "en"
''')

            (Path(repo) / "formatter.py").write_text('''
"""Formatting utilities"""

def format_json(data: dict, indent: int = 2) -> str:
    """Format a dictionary as pretty-printed JSON string"""
    import json
    return json.dumps(data, indent=indent)

def truncate(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length with ellipsis if needed"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
''')

            (Path(repo) / "_internal.py").write_text('''
def _helper():
    """Internal helper — should be skipped"""
    pass
''')

            # Run absorption with a fresh registry
            registry = ToolRegistry()
            with tempfile.TemporaryDirectory() as skills_dir:
                absorber = KnowledgeAbsorber(tool_registry=registry, skills_dir=skills_dir)
                result = absorber.absorb(repo, min_docstring_len=20)

            # Verify structure
            assert result.structure is not None
            assert result.structure.languages.get("python") == 3

            # Verify capabilities extracted
            assert result.total_extracted >= 3  # translate, detect_language, format_json, truncate
            func_names = [c.source_function for c in result.capabilities]
            assert "translate" in func_names
            assert "detect_language" in func_names
            assert "format_json" in func_names
            assert "truncate" in func_names
            assert "_helper" not in func_names  # Private skipped

            # Verify skills generated
            assert len(result.generated_skills) >= 3

            # Verify validations
            assert len(result.validations) >= 3

            # Verify registered (at least the safe ones)
            assert result.total_registered >= 1

            # Check summary
            summary = result.summary()
            assert "知识吸收报告" in summary
            assert "提取能力" in summary

    def test_scan_only(self):
        with tempfile.TemporaryDirectory() as repo:
            (Path(repo) / "main.py").write_text('def main(): """Entry""" pass')
            (Path(repo) / "utils.py").write_text('def util(): """Helper""" pass')

            absorber = KnowledgeAbsorber()
            structure = absorber.scan(repo)
            assert len(structure.modules) == 2

    def test_extract_from_structure(self):
        with tempfile.TemporaryDirectory() as repo:
            (Path(repo) / "api.py").write_text('''
def call_api(endpoint: str, method: str = "GET") -> dict:
    """Make an HTTP API call to the specified endpoint"""
    pass
''')
            absorber = KnowledgeAbsorber()
            structure = absorber.scan(repo)
            caps = absorber.extract(structure)
            assert len(caps) == 1
            assert caps[0].source_function == "call_api"

    def test_summary_report(self):
        result = AbsorptionResult(repo_path="/test/repo")
        summary = result.summary()
        assert "/test/repo" in summary
        assert "提取能力: 0" in summary
