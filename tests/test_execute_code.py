"""execute_code 沙箱测试"""

import json
import pytest

from maxbot.tools._registry import registry


class TestExecuteCode:
    """execute_code 工具测试"""

    def test_basic_execution(self):
        """基础执行：不调用工具"""
        result = registry.call("execute_code", {
            "code": "print('hello maxbot')",
        })
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "hello maxbot" in data["output"]

    def test_tool_rpc_read_file(self, tmp_path):
        """沙箱内调用 read_file 工具"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\nline3\n")

        result = registry.call("execute_code", {
            "code": f'''
import maxbot_tools
data = maxbot_tools.read_file("{test_file}")
print(data["content"])
''',
            "timeout": 30,
        })
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "line1" in data["output"]
        assert "line2" in data["output"]
        assert data.get("tool_calls", 0) >= 1

    def test_tool_rpc_shell(self):
        """沙箱内调用 shell 工具"""
        result = registry.call("execute_code", {
            "code": '''
import maxbot_tools
data = maxbot_tools.shell("echo from_sandbox")
print(data["output"].strip())
''',
            "timeout": 30,
        })
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "from_sandbox" in data["output"]

    def test_multi_tool_chain(self, tmp_path):
        """多步工具链：写文件→读文件→处理→输出"""
        test_file = tmp_path / "chain_test.txt"

        result = registry.call("execute_code", {
            "code": f'''
import maxbot_tools, json

# Step 1: Write file
maxbot_tools.write_file("{test_file}", "hello world\\nfoo bar\\nbaz qux")

# Step 2: Read it back
data = maxbot_tools.read_file("{test_file}")

# Step 3: Process
lines = data["content"].split("\\n")
upper = [l.upper() for l in lines if l.strip()]

# Step 4: Output
print(json.dumps(upper))
''',
            "timeout": 30,
        })
        data = json.loads(result)
        assert data["exit_code"] == 0
        output = data["output"].strip()
        assert "HELLO WORLD" in output
        assert "FOO BAR" in output
        assert data.get("tool_calls", 0) >= 2

    def test_error_handling(self):
        """错误处理"""
        result = registry.call("execute_code", {
            "code": "import maxbot_tools; maxbot_tools.shell('nonexistent_command_xyz')",
            "timeout": 15,
        })
        data = json.loads(result)
        # Should not crash, error should be in the tool result
        assert data["exit_code"] == 0 or "error" in data.get("stderr", "") or "error" in data.get("output", "")

    def test_timeout(self):
        """超时控制"""
        result = registry.call("execute_code", {
            "code": "import time; time.sleep(100)",
            "timeout": 3,
        })
        data = json.loads(result)
        assert "error" in data or data.get("exit_code", 0) != 0

    def test_tool_call_limit(self):
        """工具调用数限制"""
        result = registry.call("execute_code", {
            "code": '''
import maxbot_tools
for i in range(60):
    try:
        maxbot_tools.shell("echo test")
    except RuntimeError as e:
        print(f"stopped at {i}: {e}")
        break
''',
            "timeout": 30,
            "max_tool_calls": 5,
        })
        data = json.loads(result)
        assert data["exit_code"] == 0
        # Should have hit the limit
        assert data.get("tool_calls", 0) <= 6  # slightly loose

    def test_helper_functions(self):
        """内置辅助函数：json_parse, shell_quote, retry"""
        result = registry.call("execute_code", {
            "code": '''
import maxbot_tools
# json_parse
data = maxbot_tools.json_parse('{"key": "value\\nwith\\nnewlines"}')
print(f"key={data['key']}")

# shell_quote
quoted = maxbot_tools.shell_quote("hello world")
print(f"quoted={quoted}")

# retry
count = [0]
def flaky():
    count[0] += 1
    if count[0] < 3:
        raise Exception("not yet")
    return "ok"
result = maxbot_tools.retry(flaky, max_attempts=5, delay=0.1)
print(f"retry={result}")
''',
            "timeout": 15,
        })
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "key=value" in data["output"]
        assert "quoted='hello world'" in data["output"]
        assert "retry=ok" in data["output"]
