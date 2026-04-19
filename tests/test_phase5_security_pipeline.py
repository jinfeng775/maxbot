from maxbot.security.security_pipeline import run_security_pipeline, evaluate_quality_gate



def test_security_pipeline_collects_scan_results_and_summary():
    class FakeSystem:
        def run_security_scan(self, check_name=None):
            return {
                "checks_run": [check_name or "all"],
                "total_issues": 2,
                "by_severity": {"critical": 0, "high": 1, "medium": 1, "low": 0},
                "findings": [
                    {"severity": "high", "message": "hardcoded secret"},
                    {"severity": "medium", "message": "old dependency"},
                ],
                "passed": False,
            }

    report = run_security_pipeline(FakeSystem(), check_name="bandit")

    assert report["checks_run"] == ["bandit"]
    assert report["summary"]["total_issues"] == 2
    assert report["summary"]["highest_severity"] == "high"
    assert len(report["findings"]) == 2



def test_security_pipeline_handles_failed_scan_tool():
    class FakeSystem:
        def run_security_scan(self, check_name=None):
            return {
                "checks_run": [check_name or "all"],
                "total_issues": 0,
                "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "findings": [{"severity": "high", "error": "tool missing", "check": "bandit"}],
                "scan_failures": [{"check": "bandit", "error": "tool missing", "severity": "high"}],
                "passed": False,
            }

    report = run_security_pipeline(FakeSystem(), check_name="bandit")
    assert report["summary"]["total_issues"] == 0
    assert report["findings"][0]["error"] == "tool missing"
    assert report["scan_failures"] == [{"check": "bandit", "error": "tool missing", "severity": "high"}]



def test_quality_gate_blocks_high_and_critical_findings():
    report = {
        "summary": {"highest_severity": "high", "total_issues": 1},
        "by_severity": {"critical": 0, "high": 1, "medium": 0, "low": 0},
        "findings": [{"severity": "high", "message": "secret"}],
    }

    gate = evaluate_quality_gate(report)

    assert gate["passed"] is False
    assert gate["blocking_severity"] == "high"



def test_quality_gate_allows_medium_when_policy_only_blocks_high_and_above():
    report = {
        "summary": {"highest_severity": "medium", "total_issues": 1},
        "by_severity": {"critical": 0, "high": 0, "medium": 1, "low": 0},
        "findings": [{"severity": "medium", "message": "warning"}],
    }

    gate = evaluate_quality_gate(report)

    assert gate["passed"] is True
    assert gate["blocking_severity"] is None
