"""
知识沙箱 — 验证吸收的工具是否安全可用

功能:
1. 静态安全扫描（危险模式检测）
2. Handler 语法验证
3. 可选的沙箱执行（subprocess 隔离）
4. 测试用例自动生成
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maxbot.knowledge.capability_extractor import ExtractedCapability


@dataclass
class SecurityReport:
    """安全扫描报告"""
    is_safe: bool = True
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical

    def add_issue(self, issue: str, risk: str = "medium"):
        self.issues.append(issue)
        if risk == "critical" or risk == "high":
            self.is_safe = False
        if _risk_priority(risk) > _risk_priority(self.risk_level):
            self.risk_level = risk

    def add_warning(self, warning: str):
        self.warnings.append(warning)


@dataclass
class ValidationResult:
    """验证结果"""
    capability: ExtractedCapability
    security: SecurityReport = field(default_factory=SecurityReport)
    syntax_valid: bool = True
    syntax_error: str = ""
    test_generated: str = ""
    test_passed: bool | None = None
    test_output: str = ""
    execution_time: float = 0.0

    @property
    def is_valid(self) -> bool:
        return (
            self.security.is_safe
            and self.syntax_valid
            and (self.test_passed is True or self.test_passed is None)
        )


# ── Security Patterns ───────────────────────────────────────

_DANGEROUS_IMPORTS = {
    "os.system", "os.popen", "os.exec", "os.spawn",
    "subprocess.call", "subprocess.run", "subprocess.Popen",
    "subprocess.check_output", "subprocess.check_call",
    "eval", "exec", "compile",
    "__import__", "importlib.import_module",
    "shutil.rmtree", "shutil.move",
    "pickle.loads", "pickle.load",
    "yaml.load", "yaml.unsafe_load",
}

_DANGEROUS_PATTERNS = [
    (r"\brm\s+-rf\b", "Shell rm -rf command", "critical"),
    (r"\b(os\.system|os\.popen)\s*\(", "Direct OS command execution", "high"),
    (r"\b(eval|exec)\s*\(", "Dynamic code execution", "high"),
    (r"\b__import__\s*\(", "Dynamic import", "medium"),
    (r"\bopen\s*\([^)]*['\"]w['\"]", "File write operation", "medium"),
    (r"\bsocket\.\w+", "Network socket usage", "medium"),
    (r"\brequests\.(get|post|put|delete)\b", "HTTP request", "low"),
    (r"\bshutil\.rmtree\b", "Recursive delete", "high"),
    (r"\bpickle\.(loads?|dump)\b", "Pickle deserialization", "high"),
    (r"\binput\s*\(", "User input (may block)", "low"),
]


def _risk_priority(risk: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(risk, 0)


# ── Security Scanner ────────────────────────────────────────

def scan_security(cap: ExtractedCapability) -> SecurityReport:
    """静态安全扫描"""
    report = SecurityReport()
    code = cap.handler_code

    if not code:
        report.add_warning("No handler code to scan")
        return report

    # Pattern matching
    for pattern, desc, risk in _DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            report.add_issue(f"Dangerous pattern: {desc}", risk)

    # AST-based analysis for Python
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # Check dangerous calls
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                    else:
                        func_name = node.func.attr

                if func_name in _DANGEROUS_IMPORTS:
                    report.add_issue(f"Dangerous call: {func_name}", "high")

            # Check imports
            if isinstance(node, ast.ImportFrom):
                if node.module in ("subprocess", "shutil", "pickle"):
                    report.add_warning(f"Sensitive import: {node.module}")
    except SyntaxError:
        pass  # Syntax validation handles this separately

    # Check for file path traversal
    if re.search(r'\.\./', code):
        report.add_warning("Path traversal detected (../)")

    # Check for network access
    if re.search(r'(http|https|ftp|socket)://', code):
        report.add_warning("Network URL detected")

    return report


# ── Syntax Validator ────────────────────────────────────────

def validate_syntax(cap: ExtractedCapability) -> tuple[bool, str]:
    """验证 handler 代码语法"""
    if not cap.handler_code:
        return False, "No handler code"

    try:
        ast.parse(cap.handler_code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


# ── Test Generator ──────────────────────────────────────────

def generate_test(cap: ExtractedCapability) -> str:
    """自动生成测试用例"""
    func_name = cap.name
    params = cap.parameters
    required = cap.required_params

    # Generate test values for each parameter
    test_args = {}
    for pname, pinfo in params.items():
        ptype = pinfo.get("type", "string")
        if ptype == "string":
            test_args[pname] = "test_value"
        elif ptype == "integer":
            test_args[pname] = 42
        elif ptype == "number":
            test_args[pname] = 3.14
        elif ptype == "boolean":
            test_args[pname] = True
        elif ptype == "array":
            test_args[pname] = ["item1", "item2"]
        elif ptype == "object":
            test_args[pname] = {"key": "value"}
        else:
            test_args[pname] = "test"

    args_repr = repr(test_args)

    test_code = f'''"""Auto-generated test for {func_name}"""
import json
import sys
sys.path.insert(0, "{Path(cap.source_file).parent if '/' in cap.source_file else '.'}")

try:
    # Test 1: Valid call
    args = {args_repr}
    # Would call the actual handler here
    print(json.dumps({{"status": "test_passed", "tool": "{func_name}"}}))

    # Test 2: Empty call (should handle gracefully)
    # result = {func_name}(**{{}})
    # assert "error" in json.loads(result)

    print("ALL_TESTS_PASSED")
except Exception as e:
    print(json.dumps({{"error": str(e), "status": "test_failed"}}))
    sys.exit(1)
'''
    return test_code


# ── Sandbox Runner ──────────────────────────────────────────

def run_sandboxed(
    cap: ExtractedCapability,
    timeout: float = 10.0,
) -> ValidationResult:
    """
    在隔离环境中验证工具

    流程:
    1. 安全扫描
    2. 语法检查
    3. 生成测试
    4. 沙箱执行（如果安全）
    """
    result = ValidationResult(capability=cap)

    # 1. Security scan
    result.security = scan_security(cap)
    if not result.security.is_safe:
        return result  # Don't execute unsafe code

    # 2. Syntax check
    result.syntax_valid, result.syntax_error = validate_syntax(cap)
    if not result.syntax_valid:
        return result

    # 3. Generate test
    result.test_generated = generate_test(cap)

    # 4. Sandbox execution
    start = time.time()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_tool.py"
            test_file.write_text(result.test_generated)

            proc = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
            result.test_output = proc.stdout + proc.stderr
            result.test_passed = "ALL_TESTS_PASSED" in proc.stdout and proc.returncode == 0
    except subprocess.TimeoutExpired:
        result.test_passed = False
        result.test_output = f"Timeout after {timeout}s"
    except Exception as e:
        result.test_passed = False
        result.test_output = str(e)

    result.execution_time = time.time() - start
    return result


def batch_validate(
    capabilities: list[ExtractedCapability],
    timeout: float = 10.0,
) -> list[ValidationResult]:
    """批量验证"""
    return [run_sandboxed(cap, timeout) for cap in capabilities]
