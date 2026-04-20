def test_quality_gate_profiles_are_stable():
    from maxbot.evals.grader import get_quality_gate_policy

    strict = get_quality_gate_policy("strict")
    standard = get_quality_gate_policy("standard")
    relaxed = get_quality_gate_policy("relaxed")

    assert strict["thresholds"]["min_pass_rate"] >= standard["thresholds"]["min_pass_rate"] >= relaxed["thresholds"]["min_pass_rate"]
    assert strict["thresholds"]["min_avg_score"] >= standard["thresholds"]["min_avg_score"] >= relaxed["thresholds"]["min_avg_score"]
    assert strict["thresholds"]["max_execution_failures"] <= standard["thresholds"]["max_execution_failures"] <= relaxed["thresholds"]["max_execution_failures"]



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



def test_quality_gate_supports_named_policy_bundle_with_advisory_mode(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-gate-bundle",
        "suite_name": "phase8-gate-bundle",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 quality gate 状态",
                "expected_output": "phase8 quality ready",
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

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": "phase8 quality only"},
        policy={"min_tasks_total": 1, "min_pass_rate": 0.0, "min_avg_score": 0.75, "max_execution_failures": 1},
        persist=False,
    )

    gate = report["gate"]
    assert gate["operating_mode"] == "custom"
    assert gate["passed"] is False
    assert gate["blocking_summary"]["blocking"] is True
    assert gate["blocking_summary"]["primary_reason"] == "avg_score"
    assert gate["advisories"] == ["exact_match_normalized", "keyword_coverage"]



def test_quality_gate_lists_named_policy_bundles_and_emits_advisory_summary(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.grader import get_quality_gate_policy, list_quality_gate_policies

    policies = list_quality_gate_policies()
    assert "release_blocker" in policies
    assert "advisory" in policies

    release_blocker = get_quality_gate_policy("release_blocker")
    assert release_blocker["mode"] == "blocking"
    assert release_blocker["description"]
    assert release_blocker["thresholds"]["min_tasks_total"] == 2

    advisory = get_quality_gate_policy("advisory")
    assert advisory["mode"] == "advisory"
    assert advisory["thresholds"]["min_pass_rate"] == 0.0

    suite = {
        "suite_id": "suite-gate-policy-bundle",
        "suite_name": "phase9-gate-policy-bundle",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 release quality 状态",
                "expected_output": "phase9 ready",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["phase9", "ready"],
                            "weight": 0.5,
                        },
                    ],
                    "min_composite_score": 0.8,
                },
            }
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": "phase9 only"},
        policy="advisory",
        persist=False,
    )

    gate = report["gate"]
    assert gate["operating_mode"] == "advisory"
    assert gate["passed"] is True
    assert gate["blocking_summary"]["blocking"] is False
    assert gate["advisory_summary"]["has_advisories"] is True
    assert gate["policy_description"] == advisory["description"]
    assert gate["release_summary"]["is_release_blocker"] is False
    assert gate["release_summary"]["ready"] is False


def test_report_store_tracks_blocking_transitions_and_release_gate_summary(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-phase9-release-ops",
        "suite_name": "phase9-release-ops",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 phase9 质量状态",
                "expected_output": "phase9 quality ready",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["phase9", "quality", "ready"],
                            "weight": 0.5,
                        },
                    ],
                    "min_composite_score": 0.5,
                },
            },
            {
                "task_id": "task-2",
                "prompt": "请给出 trace 状态",
                "expected_output": "memory trace stable",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["memory", "trace", "stable"],
                            "weight": 0.5,
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
            "task-1": "phase9 quality ready extra",
            "task-2": "memory trace stable later",
        },
        policy="release_blocker",
        persist=True,
    )
    second_report = runner.run_suite(
        suite=suite,
        outputs={
            "task-1": "phase9 quality ready",
            "task-2": "memory trace stable",
        },
        policy="release_blocker",
        persist=True,
    )

    assert first_report["gate"]["blocking_reason"] == "avg_score"
    assert first_report["summary"]["gate"]["blocking_rule"]["rule_type"] == "exact_match_normalized"
    assert first_report["summary"]["gate"]["release_summary"]["is_release_blocker"] is True
    assert second_report["gate"]["blocking_reason"] is None

    comparison = store.compare_reports(first_report["report_id"], second_report["report_id"])
    assert comparison["blocking_reason_changed"] is True
    assert comparison["blocking_transition"] == {
        "from": "avg_score",
        "to": None,
        "resolved": True,
        "regressed": False,
        "policy_changed": False,
    }
    assert comparison["latest_weakest_rule"]["rule_type"] == "exact_match_normalized"

    trend = store.trend_summary(limit=2)
    assert trend["latest_blocking_reason"] is None
    assert trend["latest_advisories"] == ["exact_match_normalized", "keyword_coverage"]
    assert trend["summary"]["release_summary"]["is_release_blocker"] is True


def test_report_store_separates_policy_shift_from_quality_regression(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-phase9-policy-shift",
        "suite_name": "phase9-policy-shift",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 phase9 质量状态",
                "expected_output": "phase9 quality ready",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["phase9", "quality", "ready"],
                            "weight": 0.5,
                        },
                    ],
                    "min_composite_score": 0.5,
                },
            },
            {
                "task_id": "task-2",
                "prompt": "请给出 trace 状态",
                "expected_output": "memory trace stable",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["memory", "trace", "stable"],
                            "weight": 0.5,
                        },
                    ],
                    "min_composite_score": 0.5,
                },
            },
        ],
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    advisory_report = runner.run_suite(
        suite=suite,
        outputs={
            "task-1": "phase9 quality ready extra",
            "task-2": "memory trace stable later",
        },
        policy="advisory",
        persist=True,
    )
    release_report = runner.run_suite(
        suite=suite,
        outputs={
            "task-1": "phase9 quality ready extra",
            "task-2": "memory trace stable later",
        },
        policy="release_blocker",
        persist=True,
    )

    comparison = store.compare_reports(advisory_report["report_id"], release_report["report_id"])
    assert comparison["latest_profile"] == "release_blocker"
    assert comparison["policy_changed"] is True
    assert comparison["profile_transition"] == {"from": "advisory", "to": "release_blocker"}
    assert comparison["blocking_reason_changed"] is True
    assert comparison["blocking_transition"]["from"] is None
    assert comparison["blocking_transition"]["to"] == "avg_score"
    assert comparison["blocking_transition"]["regressed"] is False
    assert comparison["blocking_transition"]["policy_changed"] is True

    reverse = store.compare_reports(release_report["report_id"], advisory_report["report_id"])
    assert reverse["policy_changed"] is True
    assert reverse["blocking_transition"]["from"] == "avg_score"
    assert reverse["blocking_transition"]["to"] is None
    assert reverse["blocking_transition"]["resolved"] is False
    assert reverse["blocking_transition"]["policy_changed"] is True


def test_report_store_tracks_quality_program_transition_and_latest_summary(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-phase9-quality-program-summary",
        "suite_name": "phase9-quality-program-summary",
        "metadata": {
            "phase": "phase9",
            "assembly_policy": {
                "bundle_name": "phase9_release_core",
                "bundle_description": "Phase 9 发布前核心质量样本集",
                "target_phase": "phase9",
                "recommended_gate_policy": "release_blocker",
                "compatible_gate_policies": ["standard", "release_blocker"],
            },
        },
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 release ready",
                "expected_output": "release ready",
                "metadata": {"normalize_whitespace": True},
            },
            {
                "task_id": "task-2",
                "prompt": "请输出 quality locked",
                "expected_output": "quality locked",
                "metadata": {"normalize_whitespace": True},
            },
        ],
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    standard_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " release ready ", "task-2": " quality locked "},
        policy="standard",
        persist=True,
    )
    release_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " release ready ", "task-2": " quality locked "},
        policy="release_blocker",
        persist=True,
    )

    comparison = store.compare_reports(standard_report["report_id"], release_report["report_id"])
    assert comparison["quality_program_changed"] is True
    assert comparison["latest_quality_program"]["status"] == "release_ready"
    assert comparison["quality_program_transition"] == {
        "from_status": "upgrade_recommended",
        "to_status": "release_ready",
        "from_gate_policy": "standard",
        "to_gate_policy": "release_blocker",
    }

    trend = store.trend_summary(limit=2)
    assert trend["summary"]["quality_program"]["status"] == "release_ready"
    assert trend["summary"]["quality_program"]["recommended_gate_active"] is True
    assert trend["summary"]["quality_program"]["release_ready"] is True


def test_report_store_skips_quality_program_transition_for_no_bundle_alignment(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-no-bundle-quality-program",
        "suite_name": "suite-no-bundle-quality-program",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 no bundle ready",
                "expected_output": "no bundle ready",
                "metadata": {"normalize_whitespace": True},
            }
        ],
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    standard_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " no bundle ready "},
        policy="standard",
        persist=True,
    )
    strict_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " no bundle ready "},
        policy="strict",
        persist=True,
    )

    comparison = store.compare_reports(standard_report["report_id"], strict_report["report_id"])
    assert comparison["quality_program_changed"] is False
    assert comparison["quality_program_transition"] == {
        "from_status": "no_bundle_alignment",
        "to_status": "no_bundle_alignment",
        "from_gate_policy": None,
        "to_gate_policy": None,
    }


def test_report_store_treats_missing_legacy_quality_program_as_no_bundle_alignment(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    store = ReportStore(tmp_path / "benchmark-reports")
    legacy_id = store.write_report(
        {
            "suite_id": "suite-legacy-no-bundle",
            "suite_name": "suite-legacy-no-bundle",
            "pass_rate": 1.0,
            "avg_score": 1.0,
            "rule_summary": {},
            "gate": {"passed": True, "profile": "standard", "blocking_reason": None, "advisories": []},
            "summary": {},
            "results": [],
        }
    )

    runner = BenchmarkRunner(report_store=store)
    new_report = runner.run_suite(
        suite={
            "suite_id": "suite-legacy-no-bundle",
            "suite_name": "suite-legacy-no-bundle",
            "tasks": [
                {
                    "task_id": "task-1",
                    "prompt": "请输出 legacy ready",
                    "expected_output": "legacy ready",
                    "metadata": {"normalize_whitespace": True},
                }
            ],
        },
        outputs={"task-1": " legacy ready "},
        policy="strict",
        persist=True,
    )

    comparison = store.compare_reports(legacy_id, new_report["report_id"])
    assert comparison["quality_program_changed"] is False
    assert comparison["quality_program_transition"] == {
        "from_status": "no_bundle_alignment",
        "to_status": "no_bundle_alignment",
        "from_gate_policy": None,
        "to_gate_policy": None,
    }



def test_report_store_reconstructs_bundle_backed_legacy_quality_program(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    store = ReportStore(tmp_path / "benchmark-reports")
    legacy_id = store.write_report(
        {
            "suite_id": "suite-legacy-phase9-bundle",
            "suite_name": "suite-legacy-phase9-bundle",
            "pass_rate": 1.0,
            "avg_score": 1.0,
            "rule_summary": {},
            "gate": {
                "passed": True,
                "profile": "standard",
                "blocking_reason": None,
                "advisories": [],
                "release_summary": {"is_release_blocker": False, "ready": False},
            },
            "summary": {
                "suite_metadata": {
                    "phase": "phase9",
                    "assembly_policy": {
                        "bundle_name": "phase9_release_core",
                        "bundle_description": "Frozen Phase 9 发布前核心质量样本集",
                        "target_phase": "phase9",
                        "recommended_gate_policy": "standard",
                        "compatible_gate_policies": ["standard"],
                    }
                }
            },
            "results": [],
        }
    )

    runner = BenchmarkRunner(report_store=store)
    new_report = runner.run_suite(
        suite={
            "suite_id": "suite-legacy-phase9-bundle",
            "suite_name": "suite-legacy-phase9-bundle",
            "metadata": {
                "phase": "phase9",
                "assembly_policy": {
                    "bundle_name": "phase9_release_core",
                    "bundle_description": "Frozen Phase 9 发布前核心质量样本集",
                    "target_phase": "phase9",
                    "recommended_gate_policy": "standard",
                    "compatible_gate_policies": ["standard"],
                },
            },
            "tasks": [
                {
                    "task_id": "task-1",
                    "prompt": "请输出 legacy bundle ready",
                    "expected_output": "legacy bundle ready",
                    "metadata": {"normalize_whitespace": True},
                }
            ],
        },
        outputs={"task-1": " legacy bundle ready "},
        policy="standard",
        persist=True,
    )

    comparison = store.compare_reports(legacy_id, new_report["report_id"])
    assert comparison["quality_program_changed"] is False
    assert comparison["quality_program_transition"] == {
        "from_status": "quality_ready",
        "to_status": "quality_ready",
        "from_gate_policy": "standard",
        "to_gate_policy": "standard",
    }

    trend = store.trend_summary(limit=2)
    assert trend["summary"]["quality_program"]["status"] == "quality_ready"
    assert trend["summary"]["quality_program"]["recommended_gate_policy"] == "standard"


def test_report_store_does_not_backfill_live_gate_guidance_for_legacy_bundle_metadata(tmp_path):
    from maxbot.evals.quality_program import resolve_report_quality_program
    from maxbot.evals.report_store import ReportStore

    store = ReportStore(tmp_path / "benchmark-reports")
    legacy_id = store.write_report(
        {
            "suite_id": "suite-legacy-phase9-incomplete-guidance",
            "suite_name": "suite-legacy-phase9-incomplete-guidance",
            "pass_rate": 1.0,
            "avg_score": 1.0,
            "rule_summary": {},
            "gate": {
                "passed": True,
                "profile": "standard",
                "blocking_reason": None,
                "advisories": [],
                "release_summary": {"is_release_blocker": False, "ready": False},
            },
            "summary": {
                "suite_metadata": {
                    "phase": "phase9",
                    "assembly_policy": {
                        "bundle_name": "phase9_release_core",
                        "bundle_description": "Legacy Phase 9 发布前核心质量样本集",
                        "target_phase": "phase9",
                        "compatible_gate_policies": ["standard", "release_blocker"],
                    }
                }
            },
            "results": [],
        }
    )

    quality_program = resolve_report_quality_program(store.read_report(legacy_id))
    assert quality_program["bundle_name"] == "phase9_release_core"
    assert quality_program["recommended_gate_policy"] is None
    assert quality_program["compatible_gate_policies"] == ["standard", "release_blocker"]
    assert quality_program["status"] == "no_bundle_alignment"
