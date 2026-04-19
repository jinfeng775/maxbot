from __future__ import annotations

import json

from maxbot.security.security_pipeline import evaluate_quality_gate, run_security_pipeline
from maxbot.security.security_review_system import SecurityReviewSystem
from maxbot.tools._registry import registry


@registry.tool(name="security_scan", description="执行安全扫描并返回结构化报告与质量门结果")
def security_scan(check_name: str = "all", project_root: str = "/root/maxbot") -> str:
    system = SecurityReviewSystem(project_root)
    report = run_security_pipeline(system, check_name=None if check_name == "all" else check_name)
    gate = evaluate_quality_gate(report)
    return json.dumps({"report": report, "gate": gate}, ensure_ascii=False)
