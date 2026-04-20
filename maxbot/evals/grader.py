from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


_QUALITY_GATE_PROFILES: dict[str, dict[str, Any]] = {
    "strict": {
        "name": "strict",
        "description": "严格质量门：适合高置信度内部验收。",
        "mode": "blocking",
        "thresholds": {
            "min_tasks_total": 2,
            "min_pass_rate": 0.9,
            "min_avg_score": 0.9,
            "max_execution_failures": 0,
        },
    },
    "standard": {
        "name": "standard",
        "description": "标准质量门：适合常规回归与日常迭代。",
        "mode": "blocking",
        "thresholds": {
            "min_tasks_total": 1,
            "min_pass_rate": 0.7,
            "min_avg_score": 0.75,
            "max_execution_failures": 0,
        },
    },
    "relaxed": {
        "name": "relaxed",
        "description": "宽松质量门：适合基础探索与早期样本验证。",
        "mode": "blocking",
        "thresholds": {
            "min_tasks_total": 1,
            "min_pass_rate": 0.5,
            "min_avg_score": 0.6,
            "max_execution_failures": 1,
        },
    },
    "advisory": {
        "name": "advisory",
        "description": "建议模式：保留建议与告警，但不阻断结果。",
        "mode": "advisory",
        "thresholds": {
            "min_tasks_total": 1,
            "min_pass_rate": 0.0,
            "min_avg_score": 0.0,
            "max_execution_failures": 1,
        },
    },
    "release_blocker": {
        "name": "release_blocker",
        "description": "发布阻断模式：针对发布前收口，任务数和分数门槛更高。",
        "mode": "blocking",
        "thresholds": {
            "min_tasks_total": 2,
            "min_pass_rate": 0.95,
            "min_avg_score": 0.95,
            "max_execution_failures": 0,
        },
    },
}


class BenchmarkGrader:
    def grade_task(self, *, task: dict[str, Any], candidate_output: str) -> dict[str, Any]:
        metadata = task.get("metadata") or {}
        grading_rules = metadata.get("grading_rules") or []
        if grading_rules:
            return self._grade_composite_task(task=task, candidate_output=candidate_output, grading_rules=grading_rules)
        return self._grade_legacy_task(task=task, candidate_output=candidate_output)

    def grade_suite(self, *, suite: dict[str, Any], outputs: dict[str, str]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for task in suite.get("tasks", []):
            task_id = task.get("task_id")
            result = self.grade_task(task=task, candidate_output=outputs.get(task_id, ""))
            results.append(result)

        tasks_total = len(results)
        passed_count = sum(1 for result in results if result.get("passed"))
        pass_rate = passed_count / tasks_total if tasks_total else 0.0
        avg_score = sum(float(result.get("score", 0.0)) for result in results) / tasks_total if tasks_total else 0.0
        return {
            "suite_id": suite.get("suite_id"),
            "suite_name": suite.get("suite_name"),
            "tasks_total": tasks_total,
            "passed_count": passed_count,
            "pass_rate": self._round(pass_rate),
            "avg_score": self._round(avg_score),
            "results": results,
            "rule_summary": self._build_rule_summary(results),
        }

    def _grade_legacy_task(self, *, task: dict[str, Any], candidate_output: str) -> dict[str, Any]:
        metadata = task.get("metadata") or {}
        required_keywords = metadata.get("required_keywords") or []
        if required_keywords:
            rule_result = self._grade_rule(
                task=task,
                candidate_output=candidate_output,
                rule={
                    "type": "keyword_coverage",
                    "required_keywords": required_keywords,
                    "min_keyword_coverage": metadata.get("min_keyword_coverage", 1.0),
                    "weight": 1.0,
                },
            )
        else:
            rule_result = self._grade_rule(
                task=task,
                candidate_output=candidate_output,
                rule={
                    "type": "exact_match",
                    "normalize_whitespace": metadata.get("normalize_whitespace", False),
                    "weight": 1.0,
                },
            )

        rule_result["weighted_score"] = float(rule_result.get("score", 0.0))
        return {
            "task_id": task.get("task_id"),
            "passed": bool(rule_result.get("passed")),
            "score": float(rule_result.get("score", 0.0)),
            "grading_mode": rule_result.get("rule_type"),
            "matched_keywords": list(rule_result.get("matched_keywords") or []),
            "rule_results": [rule_result],
        }

    def _grade_composite_task(
        self,
        *,
        task: dict[str, Any],
        candidate_output: str,
        grading_rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        metadata = task.get("metadata") or {}
        safe_weights = [max(float(rule.get("weight", 1.0)), 0.0) for rule in grading_rules]
        total_weight = sum(safe_weights) or float(len(grading_rules) or 1)
        rule_results: list[dict[str, Any]] = []

        for rule, weight in zip(grading_rules, safe_weights, strict=False):
            rule_result = self._grade_rule(task=task, candidate_output=candidate_output, rule=rule)
            normalized_weight = weight / total_weight if total_weight else 0.0
            rule_result["weight"] = self._round(weight)
            rule_result["normalized_weight"] = self._round(normalized_weight)
            rule_result["weighted_score"] = self._round(float(rule_result.get("score", 0.0)) * normalized_weight)
            rule_results.append(rule_result)

        composite_score = self._round(sum(float(rule_result.get("weighted_score", 0.0)) for rule_result in rule_results))
        min_composite_score = float(metadata.get("min_composite_score", 1.0))
        return {
            "task_id": task.get("task_id"),
            "passed": composite_score >= min_composite_score,
            "score": composite_score,
            "grading_mode": "composite",
            "matched_keywords": [],
            "rule_results": rule_results,
            "composite_threshold": self._round(min_composite_score),
        }

    def _grade_rule(self, *, task: dict[str, Any], candidate_output: str, rule: dict[str, Any]) -> dict[str, Any]:
        rule_type = rule.get("type", "exact_match")

        if rule_type == "keyword_coverage":
            required_keywords = rule.get("required_keywords") or []
            min_keyword_coverage = float(rule.get("min_keyword_coverage", 1.0))
            matched = [keyword for keyword in required_keywords if keyword in candidate_output]
            score = len(matched) / len(required_keywords) if required_keywords else 0.0
            return {
                "task_id": task.get("task_id"),
                "passed": score >= min_keyword_coverage,
                "score": score,
                "rule_type": "keyword_coverage",
                "matched_keywords": matched,
                "min_keyword_coverage": min_keyword_coverage,
            }

        if rule_type != "exact_match":
            raise ValueError(f"Unsupported grading rule type: {rule_type}")

        expected_output = str(rule.get("expected_output", task.get("expected_output", "")))
        if rule.get("normalize_whitespace"):
            normalized_expected = self._normalize_whitespace(expected_output)
            normalized_output = self._normalize_whitespace(candidate_output)
            passed = normalized_output == normalized_expected
            return {
                "task_id": task.get("task_id"),
                "passed": passed,
                "score": 1.0 if passed else 0.0,
                "rule_type": "exact_match_normalized",
                "matched_keywords": [],
            }

        passed = candidate_output == expected_output
        return {
            "task_id": task.get("task_id"),
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "rule_type": "exact_match",
            "matched_keywords": [],
        }

    def _build_rule_summary(self, results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, float | int]] = {}
        for result in results:
            rule_results = result.get("rule_results") or [
                {
                    "rule_type": result.get("grading_mode", "unknown"),
                    "passed": result.get("passed", False),
                    "score": result.get("score", 0.0),
                    "weighted_score": result.get("score", 0.0),
                }
            ]
            for rule_result in rule_results:
                rule_type = str(rule_result.get("rule_type") or "unknown")
                current = summary.setdefault(
                    rule_type,
                    {
                        "rule_count": 0,
                        "pass_count": 0,
                        "score_sum": 0.0,
                        "weighted_score_sum": 0.0,
                    },
                )
                current["rule_count"] += 1
                current["pass_count"] += 1 if rule_result.get("passed") else 0
                current["score_sum"] += float(rule_result.get("score", 0.0))
                current["weighted_score_sum"] += float(rule_result.get("weighted_score", rule_result.get("score", 0.0)))

        finalized: dict[str, dict[str, Any]] = {}
        for rule_type, current in summary.items():
            rule_count = int(current["rule_count"])
            pass_count = int(current["pass_count"])
            avg_score = float(current["score_sum"]) / rule_count if rule_count else 0.0
            avg_weighted_score = float(current["weighted_score_sum"]) / rule_count if rule_count else 0.0
            finalized[rule_type] = {
                "rule_count": rule_count,
                "pass_count": pass_count,
                "avg_score": self._round(avg_score),
                "avg_weighted_score": self._round(avg_weighted_score),
                "avg_pass_rate": self._round(pass_count / rule_count if rule_count else 0.0),
            }
        return finalized

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _round(self, value: float) -> float:
        return round(value, 10)


def get_quality_gate_policy(name: str) -> dict[str, Any]:
    if name not in _QUALITY_GATE_PROFILES:
        raise ValueError(f"Unknown quality gate profile: {name}")
    return deepcopy(_QUALITY_GATE_PROFILES[name])


def list_quality_gate_policies() -> list[str]:
    return sorted(_QUALITY_GATE_PROFILES)


def _select_rule_highlight(rule_summary: dict[str, dict[str, Any]], *, mode: str) -> dict[str, Any] | None:
    if not rule_summary:
        return None
    selector = min if mode == "weakest" else max
    rule_type, summary = selector(
        rule_summary.items(),
        key=lambda item: (float(item[1].get("avg_weighted_score", 0.0)), item[0]),
    )
    return {"rule_type": rule_type, **dict(summary)}


def _derive_blocking_rule(*, blocking_reason: str | None, weakest_rule: dict[str, Any] | None) -> dict[str, Any] | None:
    if blocking_reason in {"pass_rate", "avg_score"}:
        return deepcopy(weakest_rule) if weakest_rule else None
    return None


def _recommended_action(*, blocking_reason: str | None, blocking_rule: dict[str, Any] | None) -> str | None:
    if blocking_rule and blocking_rule.get("rule_type"):
        return f"improve_{blocking_rule['rule_type']}"
    if blocking_reason == "execution_failures":
        return "fix_execution_failures"
    if blocking_reason == "insufficient_tasks":
        return "add_more_tasks"
    if blocking_reason == "pass_rate":
        return "improve_pass_rate"
    if blocking_reason == "avg_score":
        return "improve_avg_score"
    return None


def evaluate_benchmark_quality_gate(
    report: dict[str, Any],
    policy: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    if isinstance(policy, str):
        policy_def = get_quality_gate_policy(policy)
        policy_name = policy
        policy_mode = str(policy_def.get("mode", "blocking"))
        policy_description = policy_def.get("description")
        thresholds = dict(policy_def.get("thresholds") or {})
    else:
        policy_name = None
        policy_mode = "blocking"
        policy_description = None
        thresholds = dict(policy or {})

    if not thresholds:
        default_policy = get_quality_gate_policy("strict")
        policy_name = policy_name or default_policy["name"]
        policy_mode = str(default_policy.get("mode", "blocking"))
        policy_description = default_policy.get("description")
        thresholds = dict(default_policy.get("thresholds") or {})

    tasks_total = int(report.get("tasks_total", 0))
    pass_rate = float(report.get("pass_rate", 0.0))
    avg_score = float(report.get("avg_score", 0.0))
    execution_failures = list(report.get("execution_failures") or [])
    rule_summary = report.get("rule_summary") or {}

    blocking_reason = None
    if len(execution_failures) > int(thresholds.get("max_execution_failures", 0)):
        blocking_reason = "execution_failures"
    elif tasks_total < int(thresholds.get("min_tasks_total", 1)):
        blocking_reason = "insufficient_tasks"
    elif pass_rate < float(thresholds.get("min_pass_rate", 1.0)):
        blocking_reason = "pass_rate"
    elif avg_score < float(thresholds.get("min_avg_score", 1.0)):
        blocking_reason = "avg_score"

    advisories = list(rule_summary.keys())
    should_block = blocking_reason is not None and policy_mode == "blocking"
    weakest_rule = _select_rule_highlight(rule_summary, mode="weakest")
    blocking_rule = _derive_blocking_rule(blocking_reason=blocking_reason, weakest_rule=weakest_rule)
    return {
        "passed": should_block is False,
        "blocking_reason": blocking_reason,
        "tasks_total": tasks_total,
        "pass_rate": pass_rate,
        "avg_score": avg_score,
        "execution_failures": execution_failures,
        "policy": thresholds,
        "profile": policy_name,
        "policy_mode": policy_mode,
        "policy_description": policy_description,
        "operating_mode": policy_name or "custom",
        "blocking_summary": {
            "blocking": should_block,
            "primary_reason": blocking_reason,
            "severity": "release_blocker" if policy_name == "release_blocker" else (policy_name or policy_mode),
            "weakest_rule": weakest_rule,
            "blocking_rule": blocking_rule,
            "recommended_action": _recommended_action(blocking_reason=blocking_reason, blocking_rule=blocking_rule),
        },
        "advisories": advisories,
        "advisory_summary": {
            "has_advisories": bool(advisories),
            "count": len(advisories),
            "rules": advisories,
        },
        "release_summary": {
            "is_release_blocker": policy_name == "release_blocker",
            "ready": policy_name == "release_blocker" and blocking_reason is None,
        },
    }
