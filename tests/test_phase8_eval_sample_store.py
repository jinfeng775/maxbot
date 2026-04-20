from maxbot.evals.sample_store import EvalSampleStore


def test_eval_sample_store_promotes_trace_and_returns_benchmark_seed(tmp_path):
    store = EvalSampleStore(tmp_path / "eval-samples")

    trace = {
        "trace_id": "trace-1",
        "task_id": "task-1",
        "session_id": "session-1",
        "user_message": "请分析项目结构",
        "final_output": "项目结构分析完成",
        "tool_calls": 2,
        "reflection_count": 1,
        "revision_count": 1,
        "success": True,
    }

    sample_id = store.promote_trace(trace, labels=["phase8", "analysis"], metadata={"source": "runtime"})

    loaded = store.read_sample(sample_id)
    assert loaded["trace_id"] == "trace-1"
    assert loaded["prompt"] == "请分析项目结构"
    assert loaded["response"] == "项目结构分析完成"
    assert loaded["labels"] == ["phase8", "analysis"]
    assert loaded["metadata"]["source"] == "runtime"

    benchmark_tasks = store.build_benchmark_tasks(limit=1)
    assert benchmark_tasks == [
        {
            "task_id": "task-1",
            "prompt": "请分析项目结构",
            "expected_output": "项目结构分析完成",
            "trace_id": "trace-1",
            "metadata": {
                "session_id": "session-1",
                "tool_calls": 2,
                "reflection_count": 1,
                "revision_count": 1,
                "labels": ["phase8", "analysis"],
                "source": "runtime",
            },
        }
    ]



def test_eval_sample_store_latest_returns_most_recent_sample(tmp_path):
    store = EvalSampleStore(tmp_path / "eval-samples")

    first_id = store.promote_trace(
        {
            "trace_id": "trace-1",
            "task_id": "task-1",
            "user_message": "任务一",
            "final_output": "结果一",
            "success": True,
        }
    )
    second_id = store.promote_trace(
        {
            "trace_id": "trace-2",
            "task_id": "task-2",
            "user_message": "任务二",
            "final_output": "结果二",
            "success": True,
        }
    )

    latest = store.latest()

    assert latest["sample_id"] == second_id
    assert latest["trace_id"] == "trace-2"
    assert store.read_sample(first_id)["task_id"] == "task-1"
