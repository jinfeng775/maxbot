from __future__ import annotations

from typing import Any


SEVERITY_ORDER = ["low", "medium", "high", "critical"]



def _highest_severity(by_severity: dict[str, int]) -> str | None:
    highest = None
    for severity in SEVERITY_ORDER:
        if by_severity.get(severity, 0) > 0:
            highest = severity
    return highest



def run_security_pipeline(system: Any, check_name: str | None = None) -> dict[str, Any]:
    results = system.run_security_scan(check_name=check_name)
    by_severity = results.get("by_severity", {})
    report = {
        "checks_run": results.get("checks_run", []),
        "summary": {
            "total_issues": results.get("total_issues", 0),
            "highest_severity": _highest_severity(by_severity),
        },
        "by_severity": by_severity,
        "findings": results.get("findings", []),
        "scan_failures": results.get("scan_failures", []),
        "passed": results.get("passed", True),
    }
    return report



def evaluate_quality_gate(report: dict[str, Any], policy: dict[str, bool] | None = None) -> dict[str, Any]:
    policy = policy or {"fail_on_critical": True, "fail_on_high": True}
    by_severity = report.get("by_severity", {})

    blocking_severity = None
    if report.get("passed") is False:
        blocking_severity = "scan_failed"
    elif policy.get("fail_on_critical", True) and by_severity.get("critical", 0) > 0:
        blocking_severity = "critical"
    elif policy.get("fail_on_high", True) and by_severity.get("high", 0) > 0:
        blocking_severity = "high"

    return {
        "passed": blocking_severity is None,
        "blocking_severity": blocking_severity,
        "total_issues": report.get("summary", {}).get("total_issues", 0),
        "scan_failures": report.get("scan_failures", []),
    }
