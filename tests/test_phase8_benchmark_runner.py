def test_benchmark_runner_builds_report_and_writes_to_store(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner
    from maxbot.evals.report_store import ReportStore

    suite = {
        "suite_id": "suite-1",
        "suite_name": "phase8-regression",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请总结",
                "expected_output": "总结完成",
                "metadata": {},
            },
            {
                "task_id": "task-2",
                "prompt": "请描述 phase8",
                "expected_output": "ignored",
                "metadata": {"required_keywords": ["phase8", "grader"]},
            },
        ],
    }
    outputs = {
        "task-1": "总结完成",
        "task-2": "phase8 grader groundwork ready",
    }

    store = ReportStore(tmp_path / "benchmark-reports")
    runner = BenchmarkRunner(report_store=store)

    report = runner.run_suite(
        suite=suite,
        outputs=outputs,
        policy={"min_pass_rate": 0.5, "min_avg_score": 0.9},
        persist=True,
    )

    assert report["suite_id"] == "suite-1"
    assert report["tasks_total"] == 2
    assert report["pass_rate"] == 1.0
    assert report["avg_score"] == 1.0
    assert report["gate"]["passed"] is True
    assert report["report_id"]

    latest = store.latest()
    assert latest["report_id"] == report["report_id"]
    assert latest["gate"]["passed"] is True



def test_report_store_latest_and_list_recent_are_stable(tmp_path):
    from maxbot.evals.report_store import ReportStore

    store = ReportStore(tmp_path / "benchmark-reports")
    first_id = store.write_report({"suite_id": "suite-a", "pass_rate": 1.0, "avg_score": 1.0, "gate": {"passed": True}, "results": []})
    second_id = store.write_report({"suite_id": "suite-b", "pass_rate": 0.5, "avg_score": 0.5, "gate": {"passed": False}, "results": []})

    latest = store.latest()
    recent = store.list_recent(limit=2)

    assert latest["report_id"] == second_id
    assert recent[0]["report_id"] == second_id
    assert recent[1]["report_id"] == first_id



def test_benchmark_runner_supports_executor_without_prebuilt_outputs():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-exec",
        "suite_name": "phase8-executor",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请总结",
                "expected_output": "总结完成",
                "metadata": {},
            },
            {
                "task_id": "task-2",
                "prompt": "请描述 phase8",
                "expected_output": "ignored",
                "metadata": {"required_keywords": ["phase8", "quality"]},
            },
        ],
    }

    def executor(task):
        if task["task_id"] == "task-1":
            return "总结完成"
        return "phase8 quality ready"

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        executor=executor,
        policy={"min_pass_rate": 1.0, "min_avg_score": 1.0},
        persist=False,
    )

    assert report["pass_rate"] == 1.0
    assert report["avg_score"] == 1.0
    assert report["execution_failures"] == []



def test_benchmark_runner_fail_closes_when_executor_raises():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-fail",
        "suite_name": "phase8-fail-closed",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请描述结果",
                "expected_output": "ignored",
                "metadata": {"required_keywords": ["phase8"]},
            }
        ],
    }

    def executor(task):
        raise RuntimeError(f"boom:{task['task_id']}")

    runner = BenchmarkRunner()
    report = runner.run_suite(suite=suite, executor=executor, persist=False)

    assert report["gate"]["passed"] is False
    assert report["gate"]["blocking_reason"] == "execution_failures"
    assert report["execution_failures"][0]["task_id"] == "task-1"
    assert "boom:task-1" in report["execution_failures"][0]["error"]
    assert report["results"][0]["score"] == 0.0



def test_benchmark_runner_preserves_fail_closed_gate_reason(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-2",
        "suite_name": "phase8-strict-gate",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请描述结果",
                "expected_output": "ignored",
                "metadata": {"required_keywords": ["phase8", "grader", "quality"]},
            }
        ],
    }
    outputs = {"task-1": "phase8 grader only"}

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs=outputs,
        policy={"min_pass_rate": 0.0, "min_avg_score": 0.9},
        persist=False,
    )

    assert report["gate"]["passed"] is False
    assert report["gate"]["blocking_reason"] == "avg_score"
    assert report["results"][0]["grading_mode"] == "keyword_coverage"



def test_benchmark_runner_uses_quality_gate_closure_for_task_count_and_execution_failures():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-closure",
        "suite_name": "phase8-gate-closure",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 phase8 状态",
                "expected_output": "phase8 ready",
                "metadata": {"normalize_whitespace": True},
            }
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8   ready "},
        policy={"min_tasks_total": 2, "min_pass_rate": 0.5, "min_avg_score": 0.5, "max_execution_failures": 0},
        persist=False,
    )

    assert report["results"][0]["grading_mode"] == "exact_match_normalized"
    assert report["gate"]["passed"] is False
    assert report["gate"]["blocking_reason"] == "insufficient_tasks"


def test_benchmark_runner_emits_quality_program_summary_for_bundle_gate_alignment():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase9-quality-program",
        "suite_name": "phase9-quality-program",
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

    runner = BenchmarkRunner()
    standard_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " release ready ", "task-2": " quality locked "},
        policy="standard",
        persist=False,
    )

    standard_program = standard_report["summary"]["quality_program"]
    assert standard_program["active_gate_policy"] == "standard"
    assert standard_program["compatible_with_suite"] is True
    assert standard_program["recommended_gate_active"] is False
    assert standard_program["compatibility_level"] == "compatible"
    assert standard_program["status"] == "upgrade_recommended"
    assert standard_program["next_action"] == "rerun_with_release_blocker"
    assert standard_program["release_ready"] is False

    release_report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " release ready ", "task-2": " quality locked "},
        policy="release_blocker",
        persist=False,
    )

    release_program = release_report["summary"]["quality_program"]
    assert release_program["active_gate_policy"] == "release_blocker"
    assert release_program["compatible_with_suite"] is True
    assert release_program["recommended_gate_active"] is True
    assert release_program["compatibility_level"] == "recommended"
    assert release_program["status"] == "release_ready"
    assert release_program["next_action"] == "proceed_to_release"
    assert release_program["release_ready"] is True


def test_benchmark_runner_marks_non_release_recommended_bundle_as_quality_ready():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase8-quality-program",
        "suite_name": "phase8-quality-program",
        "metadata": {
            "phase": "phase8",
            "assembly_policy": {
                "bundle_name": "phase8_core",
                "bundle_description": "Phase 8 基础能力混合样本集",
                "target_phase": "phase8",
                "recommended_gate_policy": "standard",
                "compatible_gate_policies": ["standard", "strict"],
            },
        },
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 phase8 ready",
                "expected_output": "phase8 ready",
                "metadata": {"normalize_whitespace": True},
            }
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8   ready "},
        policy="standard",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert quality_program["recommended_gate_active"] is True
    assert quality_program["status"] == "quality_ready"
    assert quality_program["next_action"] == "continue_iteration"
    assert quality_program["release_ready"] is False


def test_benchmark_runner_keeps_blocking_state_for_non_recommended_gate_that_already_fails():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase9-nonrecommended-failing",
        "suite_name": "phase9-nonrecommended-failing",
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

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " release ready ", "task-2": " quality drifted "},
        policy="standard",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert report["gate"]["passed"] is False
    assert quality_program["recommended_gate_active"] is False
    assert quality_program["status"] == "blocking_issues_remaining"
    assert quality_program["next_action"] == "improve_exact_match_normalized"


def test_benchmark_runner_treats_stricter_compatible_gate_as_quality_ready(tmp_path):
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase8-strict-compatible",
        "suite_name": "phase8-strict-compatible",
        "metadata": {
            "phase": "phase8",
            "assembly_policy": {
                "bundle_name": "phase8_core",
                "bundle_description": "Phase 8 基础能力混合样本集",
                "target_phase": "phase8",
                "recommended_gate_policy": "standard",
                "compatible_gate_policies": ["relaxed", "standard", "strict"],
            },
        },
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 phase8 ready",
                "expected_output": "phase8 ready",
                "metadata": {"normalize_whitespace": True},
            },
            {
                "task_id": "task-2",
                "prompt": "请输出 phase8 locked",
                "expected_output": "phase8 locked",
                "metadata": {"normalize_whitespace": True},
            },
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8   ready ", "task-2": " phase8 locked "},
        policy="strict",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert report["gate"]["passed"] is True
    assert quality_program["recommended_gate_active"] is False
    assert quality_program["compatibility_level"] == "compatible"
    assert quality_program["status"] == "quality_ready"
    assert quality_program["next_action"] == "continue_iteration"


def test_benchmark_runner_prefers_persisted_suite_gate_guidance_over_live_bundle_defaults():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase9-frozen-guidance",
        "suite_name": "phase9-frozen-guidance",
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
                "prompt": "请输出 frozen ready",
                "expected_output": "frozen ready",
                "metadata": {"normalize_whitespace": True},
            }
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " frozen   ready "},
        policy="standard",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert quality_program["active_gate_policy"] == "standard"
    assert quality_program["recommended_gate_policy"] == "standard"
    assert quality_program["recommended_gate_active"] is True
    assert quality_program["compatibility_level"] == "recommended"
    assert quality_program["status"] == "quality_ready"


def test_benchmark_runner_keeps_no_bundle_runs_out_of_release_ready_state():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-no-bundle-release-blocker",
        "suite_name": "suite-no-bundle-release-blocker",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 no bundle ready",
                "expected_output": "no bundle ready",
                "metadata": {"normalize_whitespace": True},
            },
            {
                "task_id": "task-2",
                "prompt": "请输出 no bundle locked",
                "expected_output": "no bundle locked",
                "metadata": {"normalize_whitespace": True},
            },
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " no bundle ready ", "task-2": " no bundle locked "},
        policy="release_blocker",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert report["gate"]["release_summary"]["ready"] is True
    assert quality_program["compatible_with_suite"] is False
    assert quality_program["status"] == "no_bundle_alignment"
    assert quality_program["release_ready"] is False


def test_benchmark_runner_blocks_release_ready_when_gate_is_incompatible_with_suite():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase8-incompatible-release-blocker",
        "suite_name": "phase8-incompatible-release-blocker",
        "metadata": {
            "phase": "phase8",
            "assembly_policy": {
                "bundle_name": "phase8_core",
                "bundle_description": "Phase 8 基础能力混合样本集",
                "target_phase": "phase8",
                "recommended_gate_policy": "standard",
                "compatible_gate_policies": ["relaxed", "standard", "strict"],
            },
        },
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 phase8 ready",
                "expected_output": "phase8 ready",
                "metadata": {"normalize_whitespace": True},
            },
            {
                "task_id": "task-2",
                "prompt": "请输出 phase8 locked",
                "expected_output": "phase8 locked",
                "metadata": {"normalize_whitespace": True},
            },
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8 ready ", "task-2": " phase8 locked "},
        policy="release_blocker",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert report["gate"]["release_summary"]["ready"] is True
    assert quality_program["compatible_with_suite"] is False
    assert quality_program["status"] == "realignment_required"
    assert quality_program["release_ready"] is False


def test_benchmark_runner_keeps_release_ready_false_when_stricter_compatible_gate_passes():
    from maxbot.evals.benchmark_runner import BenchmarkRunner

    suite = {
        "suite_id": "suite-phase8-release-ready-not-yet",
        "suite_name": "phase8-release-ready-not-yet",
        "metadata": {
            "phase": "phase8",
            "assembly_policy": {
                "bundle_name": "phase8_core",
                "bundle_description": "Phase 8 基础能力混合样本集",
                "target_phase": "phase8",
                "recommended_gate_policy": "standard",
                "compatible_gate_policies": ["standard", "release_blocker"],
            },
        },
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请输出 phase8 ready",
                "expected_output": "phase8 ready",
                "metadata": {"normalize_whitespace": True},
            },
            {
                "task_id": "task-2",
                "prompt": "请输出 phase8 locked",
                "expected_output": "phase8 locked",
                "metadata": {"normalize_whitespace": True},
            },
        ],
    }

    runner = BenchmarkRunner()
    report = runner.run_suite(
        suite=suite,
        outputs={"task-1": " phase8 ready ", "task-2": " phase8 locked "},
        policy="release_blocker",
        persist=False,
    )

    quality_program = report["summary"]["quality_program"]
    assert report["gate"]["release_summary"]["ready"] is True
    assert quality_program["compatible_with_suite"] is True
    assert quality_program["gate_relation_to_recommended"] == "stricter"
    assert quality_program["status"] == "quality_ready"
    assert quality_program["release_ready"] is False
