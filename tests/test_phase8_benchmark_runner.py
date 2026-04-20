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
