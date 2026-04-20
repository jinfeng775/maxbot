from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from maxbot.evals.grader import BenchmarkGrader, evaluate_benchmark_quality_gate
from maxbot.evals.report_store import ReportStore


class BenchmarkRunner:
    def __init__(
        self,
        *,
        grader: BenchmarkGrader | None = None,
        report_store: ReportStore | None = None,
    ):
        self.grader = grader or BenchmarkGrader()
        self.report_store = report_store

    def run_suite(
        self,
        *,
        suite: dict[str, Any],
        outputs: dict[str, str] | None = None,
        executor: Callable[[dict[str, Any]], str] | None = None,
        policy: dict[str, float] | str | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        resolved_outputs = dict(outputs or {})
        execution_failures: list[dict[str, Any]] = []

        if not resolved_outputs and executor is not None:
            for task in suite.get("tasks", []):
                task_id = task.get("task_id")
                try:
                    resolved_outputs[task_id] = executor(task)
                except Exception as exc:  # pragma: no cover - behavior verified by tests
                    execution_failures.append(
                        {
                            "task_id": task_id,
                            "error": str(exc),
                        }
                    )
                    resolved_outputs[task_id] = ""

        graded = self.grader.grade_suite(suite=suite, outputs=resolved_outputs)
        graded["execution_failures"] = execution_failures
        gate = evaluate_benchmark_quality_gate(graded, policy=policy)

        report = {
            "suite_id": suite.get("suite_id"),
            "suite_name": suite.get("suite_name"),
            "tasks_total": graded.get("tasks_total", 0),
            "passed_count": graded.get("passed_count", 0),
            "pass_rate": graded.get("pass_rate", 0.0),
            "avg_score": graded.get("avg_score", 0.0),
            "results": graded.get("results", []),
            "rule_summary": graded.get("rule_summary", {}),
            "summary": self._build_report_summary(suite=suite, graded=graded),
            "gate": gate,
            "execution_failures": execution_failures,
        }
        if persist:
            store = self.report_store or ReportStore(Path.home() / ".maxbot" / "benchmark_reports")
            report_id = store.write_report(report)
            report["report_id"] = report_id
        return report

    def _build_report_summary(self, *, suite: dict[str, Any], graded: dict[str, Any]) -> dict[str, Any]:
        rule_summary = graded.get("rule_summary") or {}
        return {
            "suite_metadata": dict(suite.get("metadata") or {}),
            "coverage_summary": {
                "tasks_total": graded.get("tasks_total", 0),
                "passed_count": graded.get("passed_count", 0),
                "pass_rate": graded.get("pass_rate", 0.0),
                "avg_score": graded.get("avg_score", 0.0),
            },
            "weakest_rule": self._select_rule_highlight(rule_summary, mode="weakest"),
            "strongest_rule": self._select_rule_highlight(rule_summary, mode="strongest"),
        }

    def _select_rule_highlight(self, rule_summary: dict[str, dict[str, Any]], *, mode: str) -> dict[str, Any] | None:
        if not rule_summary:
            return None
        selector = min if mode == "weakest" else max
        rule_type, summary = selector(
            rule_summary.items(),
            key=lambda item: (float(item[1].get("avg_weighted_score", 0.0)), item[0]),
        )
        return {"rule_type": rule_type, **summary}
