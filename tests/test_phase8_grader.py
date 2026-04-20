def test_benchmark_grader_scores_exact_match_and_keyword_coverage():
    from maxbot.evals.grader import BenchmarkGrader

    grader = BenchmarkGrader()

    exact = grader.grade_task(
        task={
            "task_id": "task-1",
            "prompt": "请总结测试情况",
            "expected_output": "测试通过",
            "metadata": {},
        },
        candidate_output="测试通过",
    )
    assert exact["passed"] is True
    assert exact["score"] == 1.0
    assert exact["grading_mode"] == "exact_match"

    keyword = grader.grade_task(
        task={
            "task_id": "task-2",
            "prompt": "请描述结果",
            "expected_output": "ignored",
            "metadata": {"required_keywords": ["memory", "trace", "score"]},
        },
        candidate_output="memory trace available",
    )
    assert keyword["grading_mode"] == "keyword_coverage"
    assert keyword["score"] == 2 / 3
    assert keyword["passed"] is False
    assert keyword["matched_keywords"] == ["memory", "trace"]



def test_benchmark_grader_supports_whitespace_normalization_and_keyword_threshold():
    from maxbot.evals.grader import BenchmarkGrader

    grader = BenchmarkGrader()

    normalized = grader.grade_task(
        task={
            "task_id": "task-normalized",
            "prompt": "请给出结果",
            "expected_output": "phase8 ready",
            "metadata": {"normalize_whitespace": True},
        },
        candidate_output=" phase8   ready\n",
    )
    assert normalized["passed"] is True
    assert normalized["grading_mode"] == "exact_match_normalized"

    threshold = grader.grade_task(
        task={
            "task_id": "task-threshold",
            "prompt": "请描述结果",
            "expected_output": "ignored",
            "metadata": {
                "required_keywords": ["phase8", "grader", "quality"],
                "min_keyword_coverage": 0.6,
            },
        },
        candidate_output="phase8 quality available",
    )
    assert threshold["score"] == 2 / 3
    assert threshold["passed"] is True
    assert threshold["grading_mode"] == "keyword_coverage"



def test_benchmark_grader_grades_suite_and_evaluates_quality_gate():
    from maxbot.evals.grader import BenchmarkGrader, evaluate_benchmark_quality_gate

    grader = BenchmarkGrader()
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
        "task-2": "phase8 groundwork ready",
    }

    result = grader.grade_suite(suite=suite, outputs=outputs)

    assert result["tasks_total"] == 2
    assert result["passed_count"] == 1
    assert result["pass_rate"] == 0.5
    assert result["avg_score"] == 0.75

    gate = evaluate_benchmark_quality_gate(result, policy={"min_pass_rate": 0.5, "min_avg_score": 0.7})
    assert gate["passed"] is True
    assert gate["blocking_reason"] is None

    strict_gate = evaluate_benchmark_quality_gate(result, policy={"min_pass_rate": 0.8, "min_avg_score": 0.9})
    assert strict_gate["passed"] is False
    assert strict_gate["blocking_reason"] == "pass_rate"



def test_benchmark_quality_gate_supports_min_tasks_and_execution_failure_limits():
    from maxbot.evals.grader import evaluate_benchmark_quality_gate

    insufficient = evaluate_benchmark_quality_gate(
        {"tasks_total": 1, "pass_rate": 1.0, "avg_score": 1.0, "execution_failures": []},
        policy={"min_tasks_total": 2, "min_pass_rate": 0.5, "min_avg_score": 0.5, "max_execution_failures": 0},
    )
    assert insufficient["passed"] is False
    assert insufficient["blocking_reason"] == "insufficient_tasks"

    failed = evaluate_benchmark_quality_gate(
        {
            "tasks_total": 3,
            "pass_rate": 1.0,
            "avg_score": 1.0,
            "execution_failures": [{"task_id": "task-1", "error": "boom"}],
        },
        policy={"min_tasks_total": 1, "min_pass_rate": 0.5, "min_avg_score": 0.5, "max_execution_failures": 0},
    )
    assert failed["passed"] is False
    assert failed["blocking_reason"] == "execution_failures"



def test_benchmark_grader_supports_composable_rules_and_rule_breakdown():
    from maxbot.evals.grader import BenchmarkGrader

    grader = BenchmarkGrader()
    result = grader.grade_task(
        task={
            "task_id": "task-composite",
            "prompt": "请给出 Phase 8 质量门状态",
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
        },
        candidate_output=" phase8 quality ready ",
    )

    assert result["grading_mode"] == "composite"
    assert result["passed"] is True
    assert result["score"] == 0.6
    assert len(result["rule_results"]) == 2
    assert result["rule_results"][0]["rule_type"] == "exact_match_normalized"
    assert result["rule_results"][0]["passed"] is False
    assert result["rule_results"][0]["weighted_score"] == 0.0
    assert result["rule_results"][1]["rule_type"] == "keyword_coverage"
    assert result["rule_results"][1]["passed"] is True
    assert result["rule_results"][1]["weighted_score"] == 0.6



def test_benchmark_grader_emits_suite_rule_summary_for_composite_rules():
    from maxbot.evals.grader import BenchmarkGrader

    grader = BenchmarkGrader()
    suite = {
        "suite_id": "suite-composite",
        "suite_name": "phase8-composite-suite",
        "tasks": [
            {
                "task_id": "task-1",
                "prompt": "请给出 Phase 8 质量门状态",
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
            },
            {
                "task_id": "task-2",
                "prompt": "请给出 memory trace 状态",
                "expected_output": "memory trace stable",
                "metadata": {
                    "grading_rules": [
                        {"type": "exact_match", "normalize_whitespace": True, "weight": 0.5},
                        {
                            "type": "keyword_coverage",
                            "required_keywords": ["memory", "trace"],
                            "weight": 0.5,
                        },
                    ],
                    "min_composite_score": 1.0,
                },
            },
        ],
    }
    outputs = {
        "task-1": " phase8 quality ready ",
        "task-2": "memory trace stable",
    }

    result = grader.grade_suite(suite=suite, outputs=outputs)

    assert result["tasks_total"] == 2
    assert result["passed_count"] == 2
    assert result["rule_summary"]["exact_match_normalized"]["rule_count"] == 2
    assert result["rule_summary"]["exact_match_normalized"]["pass_count"] == 1
    assert result["rule_summary"]["exact_match_normalized"]["avg_score"] == 0.5
    assert result["rule_summary"]["keyword_coverage"]["rule_count"] == 2
    assert result["rule_summary"]["keyword_coverage"]["pass_count"] == 2
    assert result["rule_summary"]["keyword_coverage"]["avg_weighted_score"] == 0.55
