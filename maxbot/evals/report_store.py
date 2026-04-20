from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from maxbot.evals.quality_program import resolve_report_quality_program


class ReportStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write_report(self, report: dict[str, Any]) -> str:
        report_id = report.get("report_id") or str(uuid.uuid4())
        record = dict(report)
        created_at_ns = time.time_ns()
        record.setdefault("report_id", report_id)
        record.setdefault("created_at", created_at_ns / 1_000_000_000)
        record.setdefault("created_at_ns", created_at_ns)
        path = self.base_dir / f"{report_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return report_id

    def read_report(self, report_id: str) -> dict[str, Any]:
        path = self.base_dir / f"{report_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in self.base_dir.glob("*.json")]
        records.sort(
            key=lambda record: (record.get("created_at_ns", 0), record.get("report_id", "")),
            reverse=True,
        )
        return records[:limit]

    def latest(self) -> dict[str, Any] | None:
        recent = self.list_recent(limit=1)
        if not recent:
            return None
        return recent[0]

    def compare_reports(self, old_report_id: str, new_report_id: str) -> dict[str, Any]:
        old_report = self.read_report(old_report_id)
        new_report = self.read_report(new_report_id)
        old_profile = old_report.get("gate", {}).get("profile") or old_report.get("gate", {}).get("policy_name")
        new_profile = new_report.get("gate", {}).get("profile") or new_report.get("gate", {}).get("policy_name")
        old_quality_program = resolve_report_quality_program(old_report)
        new_quality_program = resolve_report_quality_program(new_report)
        rule_summary_delta = self._diff_rule_summary(
            old_report.get("rule_summary") or {},
            new_report.get("rule_summary") or {},
        )
        quality_program_changed = self._quality_program_changed(old_quality_program, new_quality_program)
        return {
            "old_report_id": old_report_id,
            "new_report_id": new_report_id,
            "pass_rate_delta": self._round(float(new_report.get("pass_rate", 0.0)) - float(old_report.get("pass_rate", 0.0))),
            "avg_score_delta": self._round(float(new_report.get("avg_score", 0.0)) - float(old_report.get("avg_score", 0.0))),
            "passed_changed": bool(new_report.get("gate", {}).get("passed")) != bool(old_report.get("gate", {}).get("passed")),
            "latest_profile": new_report.get("gate", {}).get("profile") or new_report.get("gate", {}).get("policy_name"),
            "policy_changed": old_profile != new_profile,
            "profile_transition": {
                "from": old_profile,
                "to": new_profile,
            },
            "blocking_reason_changed": (new_report.get("gate", {}).get("blocking_reason") != old_report.get("gate", {}).get("blocking_reason")),
            "blocking_transition": {
                "from": old_report.get("gate", {}).get("blocking_reason"),
                "to": new_report.get("gate", {}).get("blocking_reason"),
                "resolved": old_profile == new_profile and bool(old_report.get("gate", {}).get("blocking_reason")) and new_report.get("gate", {}).get("blocking_reason") is None,
                "regressed": old_profile == new_profile and old_report.get("gate", {}).get("blocking_reason") is None and bool(new_report.get("gate", {}).get("blocking_reason")),
                "policy_changed": old_profile != new_profile,
            },
            "quality_program_changed": quality_program_changed,
            "latest_quality_program": dict(new_quality_program),
            "quality_program_transition": self._quality_program_transition(old_quality_program, new_quality_program),
            "latest_weakest_rule": new_report.get("summary", {}).get("weakest_rule"),
            "rule_summary_delta": rule_summary_delta,
            "changed_rules": self._changed_rules(rule_summary_delta),
        }

    def trend_summary(self, limit: int = 5) -> dict[str, Any]:
        reports = list(reversed(self.list_recent(limit=limit)))
        if not reports:
            return {
                "reports_considered": 0,
                "latest_report_id": None,
                "latest_profile": None,
                "latest_blocking_reason": None,
                "latest_advisories": [],
                "gate_pass_count": 0,
                "pass_rate_trend": "flat",
                "avg_score_trend": "flat",
                "avg_pass_rate_delta": 0.0,
                "avg_score_delta": 0.0,
                "rule_summary": {},
                "summary": {
                    "weakest_rule": None,
                    "strongest_rule": None,
                    "changed_rules": [],
                    "release_summary": {},
                    "quality_program": {},
                },
            }

        latest = reports[-1]
        first = reports[0]
        latest_pass_rate = float(latest.get("pass_rate", 0.0))
        first_pass_rate = float(first.get("pass_rate", 0.0))
        latest_avg_score = float(latest.get("avg_score", 0.0))
        first_avg_score = float(first.get("avg_score", 0.0))
        latest_policy = latest.get("gate", {}).get("profile") or latest.get("gate", {}).get("policy_name")
        gate_pass_count = sum(1 for report in reports if report.get("gate", {}).get("passed"))
        aggregated_rule_summary = self._aggregate_rule_summary(reports)
        changed_rules = self._changed_rules_from_reports(reports)
        return {
            "reports_considered": len(reports),
            "latest_report_id": latest.get("report_id"),
            "latest_profile": latest_policy,
            "latest_blocking_reason": latest.get("gate", {}).get("blocking_reason"),
            "latest_advisories": list(latest.get("gate", {}).get("advisories") or []),
            "gate_pass_count": gate_pass_count,
            "pass_rate_trend": self._trend_label(first_pass_rate, latest_pass_rate),
            "avg_score_trend": self._trend_label(first_avg_score, latest_avg_score),
            "avg_pass_rate_delta": self._average_adjacent_delta(reports, field="pass_rate"),
            "avg_score_delta": self._average_adjacent_delta(reports, field="avg_score"),
            "rule_summary": aggregated_rule_summary,
            "summary": {
                "weakest_rule": self._select_rule_highlight(aggregated_rule_summary, mode="weakest"),
                "strongest_rule": self._select_rule_highlight(aggregated_rule_summary, mode="strongest"),
                "changed_rules": changed_rules,
                "release_summary": dict(latest.get("gate", {}).get("release_summary") or {}),
                "quality_program": resolve_report_quality_program(latest),
            },
        }

    def _trend_label(self, first: float, latest: float) -> str:
        if latest > first:
            return "up"
        if latest < first:
            return "down"
        return "flat"

    def _average_adjacent_delta(self, reports: list[dict[str, Any]], *, field: str) -> float:
        if len(reports) < 2:
            return 0.0
        deltas = [
            float(current.get(field, 0.0)) - float(previous.get(field, 0.0))
            for previous, current in zip(reports, reports[1:], strict=False)
        ]
        return self._round(sum(deltas) / len(deltas)) if deltas else 0.0

    def _aggregate_rule_summary(self, reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        aggregate: dict[str, dict[str, float | int]] = {}
        for report in reports:
            for rule_type, rule_summary in (report.get("rule_summary") or {}).items():
                current = aggregate.setdefault(
                    rule_type,
                    {
                        "report_count": 0,
                        "avg_pass_rate_sum": 0.0,
                        "avg_weighted_score_sum": 0.0,
                        "avg_score_sum": 0.0,
                    },
                )
                current["report_count"] += 1
                current["avg_pass_rate_sum"] += float(rule_summary.get("avg_pass_rate", 0.0))
                current["avg_weighted_score_sum"] += float(rule_summary.get("avg_weighted_score", 0.0))
                current["avg_score_sum"] += float(rule_summary.get("avg_score", 0.0))

        finalized: dict[str, dict[str, Any]] = {}
        for rule_type, current in aggregate.items():
            report_count = int(current["report_count"])
            finalized[rule_type] = {
                "report_count": report_count,
                "avg_pass_rate": self._round(float(current["avg_pass_rate_sum"]) / report_count if report_count else 0.0),
                "avg_weighted_score": self._round(float(current["avg_weighted_score_sum"]) / report_count if report_count else 0.0),
                "avg_score": self._round(float(current["avg_score_sum"]) / report_count if report_count else 0.0),
            }
        return finalized

    def _diff_rule_summary(
        self,
        old_summary: dict[str, dict[str, Any]],
        new_summary: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        keys = sorted(set(old_summary) | set(new_summary))
        diff: dict[str, dict[str, Any]] = {}
        for key in keys:
            old_rule = old_summary.get(key) or {}
            new_rule = new_summary.get(key) or {}
            diff[key] = {
                "rule_count_delta": int(new_rule.get("rule_count", 0)) - int(old_rule.get("rule_count", 0)),
                "pass_count_delta": int(new_rule.get("pass_count", 0)) - int(old_rule.get("pass_count", 0)),
                "avg_score_delta": self._round(float(new_rule.get("avg_score", 0.0)) - float(old_rule.get("avg_score", 0.0))),
                "avg_weighted_score_delta": self._round(
                    float(new_rule.get("avg_weighted_score", 0.0)) - float(old_rule.get("avg_weighted_score", 0.0))
                ),
                "avg_pass_rate_delta": self._round(
                    float(new_rule.get("avg_pass_rate", 0.0)) - float(old_rule.get("avg_pass_rate", 0.0))
                ),
            }
        return diff

    def _select_rule_highlight(
        self,
        aggregated_rule_summary: dict[str, dict[str, Any]],
        *,
        mode: str,
    ) -> dict[str, Any] | None:
        if not aggregated_rule_summary:
            return None
        comparator = min if mode == "weakest" else max
        rule_type, summary = comparator(
            aggregated_rule_summary.items(),
            key=lambda item: (float(item[1].get("avg_weighted_score", 0.0)), item[0]),
        )
        return {"rule_type": rule_type, **summary}

    def _changed_rules(self, rule_summary_delta: dict[str, dict[str, Any]]) -> list[str]:
        changed: list[str] = []
        for rule_type, delta in rule_summary_delta.items():
            if any(value != 0 and value != 0.0 for value in delta.values()):
                changed.append(rule_type)
        return changed

    def _changed_rules_from_reports(self, reports: list[dict[str, Any]]) -> list[str]:
        changed: set[str] = set()
        for previous, current in zip(reports, reports[1:], strict=False):
            delta = self._diff_rule_summary(previous.get("rule_summary") or {}, current.get("rule_summary") or {})
            changed.update(self._changed_rules(delta))
        return sorted(changed)

    def _quality_program_changed(self, old_quality_program: dict[str, Any], new_quality_program: dict[str, Any]) -> bool:
        old_status = old_quality_program.get("status") or "no_bundle_alignment"
        new_status = new_quality_program.get("status") or "no_bundle_alignment"
        if old_status == new_status == "no_bundle_alignment":
            return False
        return old_quality_program != new_quality_program

    def _quality_program_transition(self, old_quality_program: dict[str, Any], new_quality_program: dict[str, Any]) -> dict[str, Any]:
        old_status = old_quality_program.get("status") or "no_bundle_alignment"
        new_status = new_quality_program.get("status") or "no_bundle_alignment"
        if old_status == new_status == "no_bundle_alignment":
            return {
                "from_status": "no_bundle_alignment",
                "to_status": "no_bundle_alignment",
                "from_gate_policy": None,
                "to_gate_policy": None,
            }
        return {
            "from_status": old_quality_program.get("status"),
            "to_status": new_quality_program.get("status"),
            "from_gate_policy": old_quality_program.get("active_gate_policy"),
            "to_gate_policy": new_quality_program.get("active_gate_policy"),
        }

    def _round(self, value: float) -> float:
        return round(value, 10)
