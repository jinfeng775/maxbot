import json

from maxbot.tools import registry as tool_registry
from maxbot.security.security_pipeline import evaluate_quality_gate



def test_security_scan_tool_returns_pipeline_report(monkeypatch):
    from maxbot.tools.security_tools import security_scan

    class FakeSystem:
        def __init__(self, project_root: str):
            self.project_root = project_root

        def run_security_scan(self, check_name=None):
            return {
                "checks_run": [check_name or "all"],
                "total_issues": 1,
                "by_severity": {"critical": 0, "high": 1, "medium": 0, "low": 0},
                "findings": [{"severity": "high", "message": "secret found"}],
                "passed": False,
            }

    monkeypatch.setattr("maxbot.tools.security_tools.SecurityReviewSystem", FakeSystem)

    payload = json.loads(security_scan(check_name="bandit", project_root="/root/maxbot"))
    assert payload["report"]["summary"]["highest_severity"] == "high"
    assert payload["gate"]["passed"] is False



def test_security_scan_tool_is_registered():
    tool = tool_registry.get("security_scan")
    assert tool is not None
    assert "安全" in tool.description or "security" in tool.description.lower()
