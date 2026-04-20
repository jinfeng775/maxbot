def test_quality_gate_profiles_are_stable():
    from maxbot.evals.grader import get_quality_gate_policy

    strict = get_quality_gate_policy("strict")
    standard = get_quality_gate_policy("standard")
    relaxed = get_quality_gate_policy("relaxed")

    assert strict["min_pass_rate"] >= standard["min_pass_rate"] >= relaxed["min_pass_rate"]
    assert strict["min_avg_score"] >= standard["min_avg_score"] >= relaxed["min_avg_score"]
    assert strict["max_execution_failures"] <= standard["max_execution_failures"] <= relaxed["max_execution_failures"]



def test_quality_gate_accepts_profile_name_directly():
    from maxbot.evals.grader import evaluate_benchmark_quality_gate

    report = {
        "tasks_total": 2,
        "pass_rate": 0.75,
        "avg_score": 0.8,
        "execution_failures": [],
    }

    standard = evaluate_benchmark_quality_gate(report, policy="standard")
    strict = evaluate_benchmark_quality_gate(report, policy="strict")

    assert standard["passed"] is True
    assert strict["passed"] is False
    assert strict["blocking_reason"] in {"pass_rate", "avg_score"}



def test_report_store_can_compare_reports_and_summarize_trend(tmp_path):
    from maxbot.evals.report_store import ReportStore

    store = ReportStore(tmp_path / "benchmark-reports")
    old_id = store.write_report(
        {
            "suite_id": "suite-1",
            "suite_name": "phase8-regression",
            "pass_rate": 0.5,
            "avg_score": 0.7,
            "gate": {"passed": False},
            "results": [],
        }
    )
    new_id = store.write_report(
        {
            "suite_id": "suite-1",
            "suite_name": "phase8-regression",
            "pass_rate": 1.0,
            "avg_score": 0.95,
            "gate": {"passed": True},
            "results": [],
        }
    )

    comparison = store.compare_reports(old_id, new_id)
    assert comparison["pass_rate_delta"] == 0.5
    assert comparison["avg_score_delta"] == 0.25
    assert comparison["passed_changed"] is True

    trend = store.trend_summary(limit=2)
    assert trend["reports_considered"] == 2
    assert trend["latest_report_id"] == new_id
    assert trend["pass_rate_trend"] == "up"
    assert trend["avg_score_trend"] == "up"



def test_quality_gate_profile_is_recorded_in_report_and_trend_summary_tracks_latest_profile(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-profile",
        "suite_name": "phase8-profile-suite",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出状态",
                "expected_output": "phase8 ready",
                "metadata": {"normalize_whitespace": True},
            }
        ],
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    first_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": "phase8 ready"},
        policy="relaxed",
        persist=True,
    )
    second_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8   ready "},
        policy="standard",
        persist=True,
    )

    assert first_report["gate"]["policy"]["min_pass_rate"] == 0.5
    assert second_report["gate"]["policy"]["min_pass_rate"] == 0.7

    trend = store.trend_summary(limit=2)
    assert trend["latest_profile"] == "standard"
    assert trend["gate_pass_count"] == 2



def test_report_store_summarizes_multi_report_deltas_and_rule_summary(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-aggregate",
        "suite_name": "phase8-aggregate-suite",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出质量门状态",
                "expected_output": "phase8 quality gate ready",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.4},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["phase8", "quality", "ready"],
                            "min_keyword_coverage": 2 / 3,
                            "weight": 0.6,
                        },
                    ],
                    "min_composite_score": 0.5,
                },
            }
        ],
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    first_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": "phase8 quality only"},
        policy="relaxed",
        persist=True,
    )
    second_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8 quality ready "},
        policy="relaxed",
        persist=True,
    )

    comparison = store.compare_reports(first_report["report_id"], second_report["report_id"])
    assert comparison["pass_rate_delta"] == 1.0
    assert comparison["avg_score_delta"] == 0.2
    assert comparison["passed_changed"] is True
    assert comparison["latest_profile"] == "relaxed"
    assert comparison["rule_summary_delta"]["exact_match_normalized"]["pass_count_delta"] == 0
    assert comparison["rule_summary_delta"]["keyword_coverage"]["avg_weighted_score_delta"] == 0.2

    trend = store.trend_summary(limit=2)
    assert trend["reports_considered"] == 2
    assert trend["latest_profile"] == "relaxed"
    assert trend["avg_pass_rate_delta"] == 1.0
    assert trend["avg_score_delta"] == 0.2
    assert trend["gate_pass_count"] == 1
    assert trend["rule_summary"]["exact_match_normalized"]["avg_pass_rate"] == 0.0
    assert trend["rule_summary"]["keyword_coverage"]["avg_weighted_score"] == 0.5



def test_benchmark_runner_and_report_store_emit_operational_rule_highlights(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-ops",
        "suite_name": "phase8-ops-suite",
        "metadata": {"phase": "phase8", "project": "maxbot"},
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 quality gate 状态",
                "expected_output": "phase8 quality gate ready",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["phase8", "quality", "ready"],
                            "min_keyword_coverage": 2 / 3,
                            "weight": 0.5,
                        },
                    ],
                    "min_composite_score": 0.4,
                },
            },
            {
                "task_id": "task-2",
                "prompt": "请给出 memory trace 状态",
                "expected_output": "memory trace stable",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.4},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["memory", "trace"],
                            "weight": 0.6,
                        },
                    ],
                    "min_composite_score": 0.5,
                },
            },
        ],
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    first_report = runner.run_suite(
        suite=suite,
        outputs={
            "task-1": "phase8 quality only",
            "task-2": "memory status only",
        },
        policy="relaxed",
        persist=True,
    )
    second_report = runner.run_suite(
        suite=suite,
        outputs={
            "task-1": " phase8 quality ready ",
            "task-2": "memory trace stable",
        },
        policy="relaxed",
        persist=True,
    )

    summary = second_report["summary"]
    assert summary["suite_metadata"]["phase"] == "phase8"
    assert summary["coverage_summary"]["tasks_total"] == 2
    assert summary["strongest_rule"]["rule_type"] == "keyword_coverage"
    assert summary["weakest_rule"]["rule_type"] == "exact_match_normalized"

    comparison = store.compare_reports(first_report["report_id"], second_report["report_id"])
    assert comparison["changed_rules"] == ["exact_match_normalized", "keyword_coverage"]

    trend = store.trend_summary(limit=2)
    assert trend["summary"]["weakest_rule"]["rule_type"] == "exact_match_normalized"
    assert trend["summary"]["strongest_rule"]["rule_type"] == "keyword_coverage"
    assert trend["summary"]["changed_rules"] == ["exact_match_normalized", "keyword_coverage"]



def test_quality_gate_supports_operating_modes_and_runner_emits_advisories(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-gate-ops",
        "suite_name": "phase8-gate-ops",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出质量状态",
                "expected_output": "phase8 quality ready",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.3},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["phase8", "quality", "ready"],
                            "min_keyword_coverage": 2 / 3,
                            "weight": 0.7,
                        },
                    ],
                    "min_composite_score": 0.6,
                },
            },
            {
                "task_id": "task-2",
                "prompt": "请给出 trace 状态",
                "expected_output": "memory trace stable",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.4},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["memory", "trace"],
                            "weight": 0.6,
                        },
                    ],
                    "min_composite_score": 0.7,
                },
            },
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={
            "task-1": "phase8 quality ready",
            "task-2": "memory status only",
        },
        policy={"min_tasks_total": 1, "min_pass_rate": 0.0, "min_avg_score": 0.75, "max_execution_failures": 0},
        persist=False,
    )

    gate = report["gate"]
    assert gate["operating_mode"] == "custom"
    assert gate["blocking_reason"] == "avg_score"
    assert gate["blocking_summary"]["primary_reason"] == "avg_score"
    assert gate["blocking_summary"]["blocking"] is True
    assert gate["advisories"] == ["exact_match_normalized", "keyword_coverage"]
