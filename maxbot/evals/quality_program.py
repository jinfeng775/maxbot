from __future__ import annotations

from typing import Any

from maxbot.evals.grader import get_quality_gate_policy


def _mode_rank(mode: str) -> int:
    return {"advisory": 0, "blocking": 1}.get(mode, 1)


def _policy_relation_to_recommended(*, active_gate_policy: str | None, recommended_gate_policy: str | None) -> str | None:
    if not recommended_gate_policy:
        return None
    if not active_gate_policy:
        return "unknown"
    if active_gate_policy == recommended_gate_policy:
        return "same"

    try:
        active_policy = get_quality_gate_policy(active_gate_policy)
        recommended_policy = get_quality_gate_policy(recommended_gate_policy)
    except ValueError:
        return "unknown"

    active_thresholds = dict(active_policy.get("thresholds") or {})
    recommended_thresholds = dict(recommended_policy.get("thresholds") or {})

    active_stricter_or_equal = (
        _mode_rank(str(active_policy.get("mode", "blocking"))) >= _mode_rank(str(recommended_policy.get("mode", "blocking")))
        and int(active_thresholds.get("min_tasks_total", 0)) >= int(recommended_thresholds.get("min_tasks_total", 0))
        and float(active_thresholds.get("min_pass_rate", 0.0)) >= float(recommended_thresholds.get("min_pass_rate", 0.0))
        and float(active_thresholds.get("min_avg_score", 0.0)) >= float(recommended_thresholds.get("min_avg_score", 0.0))
        and int(active_thresholds.get("max_execution_failures", 0)) <= int(recommended_thresholds.get("max_execution_failures", 0))
    )
    active_weaker_or_equal = (
        _mode_rank(str(active_policy.get("mode", "blocking"))) <= _mode_rank(str(recommended_policy.get("mode", "blocking")))
        and int(active_thresholds.get("min_tasks_total", 0)) <= int(recommended_thresholds.get("min_tasks_total", 0))
        and float(active_thresholds.get("min_pass_rate", 0.0)) <= float(recommended_thresholds.get("min_pass_rate", 0.0))
        and float(active_thresholds.get("min_avg_score", 0.0)) <= float(recommended_thresholds.get("min_avg_score", 0.0))
        and int(active_thresholds.get("max_execution_failures", 0)) >= int(recommended_thresholds.get("max_execution_failures", 0))
    )

    if active_stricter_or_equal and active_weaker_or_equal:
        return "same"
    if active_stricter_or_equal:
        return "stricter"
    if active_weaker_or_equal:
        return "weaker"
    return "unknown"


def build_quality_program_summary(*, suite_metadata: dict[str, Any] | None, gate: dict[str, Any]) -> dict[str, Any]:
    suite_metadata = suite_metadata or {}
    assembly_policy = suite_metadata.get("assembly_policy") or {}
    bundle_name = assembly_policy.get("bundle_name")
    active_gate_policy = gate.get("profile") or gate.get("policy_name")
    release_summary = dict(gate.get("release_summary") or {})
    gate_passed = bool(gate.get("passed"))

    if not bundle_name:
        return {
            "bundle_name": None,
            "active_gate_policy": active_gate_policy,
            "compatible_with_suite": False,
            "recommended_gate_policy": None,
            "recommended_gate_active": False,
            "compatible_gate_policies": [],
            "compatibility_level": "not_applicable",
            "gate_relation_to_recommended": None,
            "status": "no_bundle_alignment",
            "next_action": None,
            "release_ready": False,
        }

    target_phase = assembly_policy.get("target_phase")
    recommended_gate_policy = assembly_policy.get("recommended_gate_policy")
    compatible_gate_policies = list(assembly_policy.get("compatible_gate_policies") or [])

    if recommended_gate_policy is None or not compatible_gate_policies:
        return {
            "bundle_name": bundle_name,
            "target_phase": target_phase,
            "active_gate_policy": active_gate_policy,
            "compatible_with_suite": False,
            "recommended_gate_policy": None,
            "recommended_gate_active": False,
            "compatible_gate_policies": compatible_gate_policies,
            "compatibility_level": "not_applicable",
            "gate_relation_to_recommended": None,
            "status": "no_bundle_alignment",
            "next_action": None,
            "release_ready": False,
        }

    compatible = bool(active_gate_policy) and active_gate_policy in compatible_gate_policies
    recommended_gate_active = bool(active_gate_policy) and active_gate_policy == recommended_gate_policy
    compatibility_level = "incompatible"
    if compatible:
        compatibility_level = "recommended" if recommended_gate_active else "compatible"
    gate_relation_to_recommended = _policy_relation_to_recommended(
        active_gate_policy=active_gate_policy,
        recommended_gate_policy=recommended_gate_policy,
    )
    release_ready = bool(release_summary.get("ready"))

    if not compatible:
        status = "realignment_required"
        next_action = f"rerun_with_{recommended_gate_policy}" if recommended_gate_policy else "review_gate_policy"
        release_ready = False
    elif gate_passed and recommended_gate_active and release_ready:
        status = "release_ready"
        next_action = "proceed_to_release"
    elif gate_passed and (recommended_gate_active or gate_relation_to_recommended == "stricter"):
        status = "quality_ready"
        next_action = "continue_iteration"
        release_ready = False
    elif gate_passed:
        status = "upgrade_recommended"
        next_action = f"rerun_with_{recommended_gate_policy}" if recommended_gate_policy else "review_gate_policy"
        release_ready = False
    else:
        status = "blocking_issues_remaining"
        next_action = gate.get("blocking_summary", {}).get("recommended_action") or "resolve_blockers"
        release_ready = False

    return {
        "bundle_name": bundle_name,
        "target_phase": target_phase,
        "active_gate_policy": active_gate_policy,
        "compatible_with_suite": compatible,
        "recommended_gate_policy": recommended_gate_policy,
        "recommended_gate_active": recommended_gate_active,
        "compatible_gate_policies": compatible_gate_policies,
        "compatibility_level": compatibility_level,
        "gate_relation_to_recommended": gate_relation_to_recommended,
        "status": status,
        "next_action": next_action,
        "release_ready": release_ready,
    }


def resolve_report_quality_program(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    quality_program = summary.get("quality_program")
    if quality_program:
        return dict(quality_program)
    return build_quality_program_summary(
        suite_metadata=summary.get("suite_metadata") or {},
        gate=report.get("gate") or {},
    )
