from maxbot.security.security_pipeline import evaluate_quality_gate



def test_quality_gate_respects_fail_on_critical_only():
    report = {
        "summary": {"highest_severity": "high", "total_issues": 1},
        "by_severity": {"critical": 0, "high": 1, "medium": 0, "low": 0},
        "findings": [{"severity": "high", "message": "issue"}],
    }

    gate = evaluate_quality_gate(report, policy={"fail_on_critical": True, "fail_on_high": False})
    assert gate["passed"] is True



def test_quality_gate_blocks_critical_even_if_high_allowed():
    report = {
        "summary": {"highest_severity": "critical", "total_issues": 1},
        "by_severity": {"critical": 1, "high": 0, "medium": 0, "low": 0},
        "findings": [{"severity": "critical", "message": "issue"}],
    }

    gate = evaluate_quality_gate(report, policy={"fail_on_critical": True, "fail_on_high": False})
    assert gate["passed"] is False
    assert gate["blocking_severity"] == "critical"



def test_quality_gate_fails_closed_when_report_marks_scan_failed():
    report = {
        "summary": {"highest_severity": None, "total_issues": 0},
        "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "findings": [],
        "passed": False,
    }

    gate = evaluate_quality_gate(report)

    assert gate["passed"] is False
    assert gate["blocking_severity"] == "scan_failed"
