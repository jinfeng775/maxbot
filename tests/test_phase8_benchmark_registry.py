from maxbot.evals.sample_store import EvalSampleStore



def test_benchmark_registry_registers_suite_from_eval_samples(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry

    sample_store = EvalSampleStore(tmp_path / "eval-samples")
    sample_store.promote_trace(
        {
            "trace_id": "trace-1",
            "task_id": "task-1",
            "user_message": "请分析项目结构",
            "final_output": "项目结构分析完成",
            "success": True,
        },
        labels=["analysis"],
        metadata={"source": "runtime"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-2",
            "task_id": "task-2",
            "user_message": "请总结测试结果",
            "final_output": "测试结果总结完成",
            "success": True,
        },
        labels=["summary"],
        metadata={"source": "runtime"},
    )

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    suite_id = registry.register_from_eval_samples(
        sample_store=sample_store,
        suite_name="phase8-regression",
        limit=2,
        metadata={"phase": "phase8"},
    )

    suite = registry.read_suite(suite_id)
    assert suite["suite_name"] == "phase8-regression"
    assert suite["metadata"]["phase"] == "phase8"
    assert len(suite["tasks"]) == 2
    assert suite["tasks"][0]["prompt"] in {"请分析项目结构", "请总结测试结果"}



def test_benchmark_registry_latest_returns_most_recent_suite_and_task_set(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    first_id = registry.register_suite(
        suite_name="suite-a",
        tasks=[{"task_id": "task-a", "prompt": "A", "expected_output": "AA", "trace_id": "trace-a", "metadata": {}}],
    )
    second_id = registry.register_suite(
        suite_name="suite-b",
        tasks=[{"task_id": "task-b", "prompt": "B", "expected_output": "BB", "trace_id": "trace-b", "metadata": {}}],
    )

    latest = registry.latest()
    assert latest["suite_id"] == second_id
    assert registry.read_suite(first_id)["suite_name"] == "suite-a"

    task_set = registry.build_task_set(limit=1)
    assert task_set == [{"task_id": "task-b", "prompt": "B", "expected_output": "BB", "trace_id": "trace-b", "metadata": {}}]



def test_benchmark_registry_filters_eval_samples_and_enriches_suite_metadata(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry

    sample_store = EvalSampleStore(tmp_path / "eval-samples")
    sample_store.promote_trace(
        {
            "trace_id": "trace-analysis",
            "task_id": "task-analysis",
            "user_message": "请分析架构",
            "final_output": "架构分析完成",
            "success": True,
        },
        labels=["analysis", "phase8"],
        metadata={"source": "runtime", "project": "maxbot"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-summary",
            "task_id": "task-summary",
            "user_message": "请总结结果",
            "final_output": "结果总结完成",
            "success": True,
        },
        labels=["summary"],
        metadata={"source": "runtime", "project": "other"},
    )

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    suite_id = registry.register_from_eval_samples(
        sample_store=sample_store,
        suite_name="analysis-only",
        limit=10,
        labels=["analysis"],
        metadata_filter={"project": "maxbot"},
        metadata={"phase": "phase8"},
    )

    suite = registry.read_suite(suite_id)
    assert len(suite["tasks"]) == 1
    assert suite["tasks"][0]["task_id"] == "task-analysis"
    assert suite["tasks"][0]["metadata"]["labels"] == ["analysis", "phase8"]
    assert suite["metadata"]["phase"] == "phase8"
    assert suite["metadata"]["source_sample_count"] == 1



def test_benchmark_registry_records_selection_policy_and_coverage_summary(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry

    sample_store = EvalSampleStore(tmp_path / "eval-samples")
    sample_store.promote_trace(
        {
            "trace_id": "trace-analysis-1",
            "task_id": "task-analysis-1",
            "user_message": "请分析 phase8 架构",
            "final_output": "phase8 架构分析完成",
            "success": True,
        },
        labels=["analysis", "phase8"],
        metadata={"source": "runtime", "project": "maxbot"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-analysis-2",
            "task_id": "task-analysis-2",
            "user_message": "请分析 benchmark",
            "final_output": "benchmark 分析完成",
            "success": True,
        },
        labels=["analysis"],
        metadata={"source": "runtime", "project": "maxbot"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-summary-1",
            "task_id": "task-summary-1",
            "user_message": "请总结 quality gate",
            "final_output": "quality gate 总结完成",
            "success": True,
        },
        labels=["summary"],
        metadata={"source": "imported", "project": "other"},
    )

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    suite_id = registry.register_from_eval_samples(
        sample_store=sample_store,
        suite_name="analysis-coverage",
        limit=5,
        labels=["analysis"],
        metadata_filter={"project": "maxbot"},
        metadata={"phase": "phase8"},
    )

    suite = registry.read_suite(suite_id)
    selection_policy = suite["metadata"]["selection_policy"]
    coverage_summary = suite["metadata"]["coverage_summary"]

    assert selection_policy == {
        "labels": ["analysis"],
        "metadata_filter": {"project": "maxbot"},
        "limit": 5,
    }
    assert coverage_summary["tasks_total"] == 2
    assert coverage_summary["labels"] == {"analysis": 2, "phase8": 1}
    assert coverage_summary["metadata"]["project"] == {"maxbot": 2}
    assert coverage_summary["metadata"]["source"] == {"runtime": 2}



def test_benchmark_registry_build_task_set_supports_suite_metadata_filter(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    registry.register_suite(
        suite_name="suite-phase8",
        tasks=[{"task_id": "task-phase8", "prompt": "P8", "expected_output": "OK", "trace_id": "trace-p8", "metadata": {}}],
        metadata={"phase": "phase8", "project": "maxbot"},
    )
    registry.register_suite(
        suite_name="suite-phase9",
        tasks=[{"task_id": "task-phase9", "prompt": "P9", "expected_output": "OK", "trace_id": "trace-p9", "metadata": {}}],
        metadata={"phase": "phase9", "project": "maxbot"},
    )

    task_set = registry.build_task_set(limit=10, suite_metadata_filter={"phase": "phase8"})

    assert task_set == [{"task_id": "task-phase8", "prompt": "P8", "expected_output": "OK", "trace_id": "trace-p8", "metadata": {}}]



def test_benchmark_registry_auto_assembles_suite_from_multiple_sample_filters(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry

    sample_store = EvalSampleStore(tmp_path / "eval-samples")
    sample_store.promote_trace(
        {
            "trace_id": "trace-a1",
            "task_id": "task-a1",
            "user_message": "请分析 phase8 质量门",
            "final_output": "phase8 质量门分析完成",
            "success": True,
        },
        labels=["analysis", "phase8"],
        metadata={"project": "maxbot", "source": "runtime"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-a2",
            "task_id": "task-a2",
            "user_message": "请总结 trace pipeline",
            "final_output": "trace pipeline 总结完成",
            "success": True,
        },
        labels=["summary", "phase8"],
        metadata={"project": "maxbot", "source": "runtime"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-a3",
            "task_id": "task-a3",
            "user_message": "请分析 phase9 plan",
            "final_output": "phase9 规划分析完成",
            "success": True,
        },
        labels=["analysis", "phase9"],
        metadata={"project": "maxbot", "source": "imported"},
    )

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    suite_id = registry.auto_assemble_suite(
        suite_name="phase8-auto-suite",
        sample_store=sample_store,
        selection_policies=[
            {"labels": ["analysis"], "metadata_filter": {"project": "maxbot"}, "limit": 1},
            {"labels": ["summary"], "metadata_filter": {"project": "maxbot"}, "limit": 1},
        ],
        metadata={"phase": "phase8"},
    )

    suite = registry.read_suite(suite_id)
    assert [task["task_id"] for task in suite["tasks"]] == ["task-a3", "task-a2"]
    assert suite["metadata"]["assembly_policy"]["policies_count"] == 2
    assert suite["metadata"]["assembly_policy"]["deduplicated_tasks"] == 2
    assert suite["metadata"]["coverage_summary"]["tasks_total"] == 2



def test_benchmark_registry_supports_named_suite_policy_bundle(tmp_path):
    from maxbot.evals.benchmark_registry import BenchmarkRegistry, get_suite_policy_bundle

    sample_store = EvalSampleStore(tmp_path / "eval-samples")
    sample_store.promote_trace(
        {
            "trace_id": "trace-b1",
            "task_id": "task-b1",
            "user_message": "请分析 reflection runtime",
            "final_output": "reflection runtime 分析完成",
            "success": True,
        },
        labels=["analysis", "phase8"],
        metadata={"project": "maxbot", "source": "runtime"},
    )
    sample_store.promote_trace(
        {
            "trace_id": "trace-b2",
            "task_id": "task-b2",
            "user_message": "请总结 report trend",
            "final_output": "report trend 总结完成",
            "success": True,
        },
        labels=["summary", "phase8"],
        metadata={"project": "maxbot", "source": "runtime"},
    )

    registry = BenchmarkRegistry(tmp_path / "benchmark-suites")
    suite_id = registry.auto_assemble_suite_from_bundle(
        suite_name="phase8-core-suite",
        sample_store=sample_store,
        bundle_name="phase8_core",
        metadata={"phase": "phase8"},
    )

    suite = registry.read_suite(suite_id)
    bundle = get_suite_policy_bundle("phase8_core")
    assert suite["metadata"]["assembly_policy"]["bundle_name"] == "phase8_core"
    assert suite["metadata"]["assembly_policy"]["policies_count"] == len(bundle)
    assert len(suite["tasks"]) == 2
