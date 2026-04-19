from maxbot.security.security_review_system import SecurityCheck, SecurityReviewSystem



def test_run_security_scan_fails_closed_when_security_tool_execution_fails(monkeypatch):
    system = SecurityReviewSystem("/root/maxbot")
    system.security_checks = {
        "bandit": SecurityCheck(
            name="bandit",
            command=["bandit", "-r", "maxbot/", "-f", "json"],
            severity="high",
            enabled=True,
        )
    }

    def fake_run_security_check(check):
        return {
            "success": False,
            "error": "Security tool 'bandit' not installed",
            "findings": [],
        }

    monkeypatch.setattr(system, "_run_security_check", fake_run_security_check)

    results = system.run_security_scan(check_name="bandit")

    assert results["checks_run"] == ["bandit"]
    assert results["passed"] is False
    assert results["findings"][0]["check"] == "bandit"
    assert results["findings"][0]["error"] == "Security tool 'bandit' not installed"
    assert results["scan_failures"] == [{"check": "bandit", "error": "Security tool 'bandit' not installed", "severity": "high"}]



def test_run_security_scan_marks_unknown_check_as_scan_failure():
    system = SecurityReviewSystem("/root/maxbot")

    results = system.run_security_scan(check_name="unknown-check")

    assert results["checks_run"] == []
    assert results["passed"] is False
    assert results["scan_failures"] == [{"check": "unknown-check", "error": "Unknown security check: unknown-check", "severity": "high"}]
    assert results["findings"][0]["check"] == "unknown-check"
