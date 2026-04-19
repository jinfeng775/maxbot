from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from maxbot.core.agent_loop import Agent, AgentConfig


class TestPhase8MetricsPipeline:
    def _make_agent(self, client_mock: MagicMock, tmp_path: Path) -> Agent:
        config = AgentConfig(
            api_key="test-key",
            base_url="http://localhost:99999/v1",
            model="test-model",
            session_id="session-metrics-test",
            auto_save=False,
            skills_enabled=False,
            reflection_enabled=True,
            reflection_max_revisions=1,
            reflection_min_output_chars=10,
            reflection_high_risk_tool_threshold=1,
            reflection_task_types=["default"],
            metrics_enabled=True,
            trace_store_dir=str(tmp_path / "traces"),
        )

        with patch.object(Agent, "_init_client", return_value=client_mock):
            return Agent(config=config)

    def test_agent_records_task_metrics_with_reflection(self, tmp_path: Path):
        message = SimpleNamespace(content="这是一个需要反思的答案输出", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = MagicMock()
        client.chat.completions.create.return_value = response

        agent = self._make_agent(client, tmp_path)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_apply_reflection", return_value=SimpleNamespace(
                 final_output="修订后的最终答案",
                 revision_count=1,
                 reflection_applied=True,
                 critiques=[{"feedback": "请补充边界条件", "revise": True}],
             )):
            result = agent.run("请输出需要反思的答案")

        assert result == "修订后的最终答案"
        summary = agent.get_runtime_metrics()
        assert summary["tasks_total"] == 1
        assert summary["reflection_count"] == 1
        assert summary["revision_count"] == 1
        assert summary["tool_calls"] == 0
        assert summary["success_count"] == 1

    def test_agent_metrics_count_tool_calls_from_response(self, tmp_path: Path):
        tool_call = SimpleNamespace(
            id="call-1",
            type="function",
            function=SimpleNamespace(name="list_skills", arguments="{}"),
        )
        first_message = SimpleNamespace(content="", tool_calls=[tool_call])
        second_message = SimpleNamespace(content="最终答案", tool_calls=None)
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=first_message)]),
            SimpleNamespace(choices=[SimpleNamespace(message=second_message)]),
        ]

        client = MagicMock()
        client.chat.completions.create.side_effect = responses

        agent = self._make_agent(client, tmp_path)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_detect_repetitive_work", return_value=(False, "")), \
             patch.object(agent, "_registry") as registry_mock:
            registry_mock.call.return_value = '{"message": "ok"}'
            result = agent.run("请列出技能")

        assert result == "最终答案"
        summary = agent.get_runtime_metrics()
        assert summary["tasks_total"] == 1
        assert summary["tool_calls"] == 1
        assert summary["success_count"] == 1

    def test_agent_metrics_capture_memory_hits_and_instinct_matches(self, tmp_path: Path):
        message = SimpleNamespace(content="这是一个需要记忆增强的答案输出", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = MagicMock()
        client.chat.completions.create.return_value = response

        agent = self._make_agent(client, tmp_path)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_build_memory_context", return_value="# 持久记忆\n## user\npreferred_language: zh-CN"), \
             patch.object(agent._learning_loop, "on_user_message", return_value={"match": {"instinct_id": "instinct-1"}}), \
             patch.object(agent, "_apply_reflection", return_value=SimpleNamespace(
                 final_output="修订后的最终答案",
                 revision_count=1,
                 reflection_applied=True,
                 critiques=[{"feedback": "请补充边界条件", "revise": True}],
             )):
            result = agent.run("请输出需要反思且需要记忆增强的答案")

        assert result == "修订后的最终答案"
        summary = agent.get_runtime_metrics()
        assert summary["memory_hits"] == 1
        assert summary["memory_misses"] == 0
        assert summary["instinct_matches"] == 1

        latest_trace = agent._trace_store.latest()
        assert latest_trace["memory_hits"] == 1
        assert latest_trace["instinct_matches"] == 1

    def test_agent_metrics_capture_memory_miss_when_context_empty(self, tmp_path: Path):
        message = SimpleNamespace(content="这是一个普通答案输出", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = MagicMock()
        client.chat.completions.create.return_value = response

        agent = self._make_agent(client, tmp_path)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_build_memory_context", return_value=""), \
             patch.object(agent._learning_loop, "on_user_message", return_value=None), \
             patch.object(agent, "_apply_reflection", return_value=SimpleNamespace(
                 final_output="普通最终答案",
                 revision_count=0,
                 reflection_applied=False,
                 critiques=[],
             )):
            result = agent.run("请输出普通答案")

        assert result == "普通最终答案"
        summary = agent.get_runtime_metrics()
        assert summary["memory_hits"] == 0
        assert summary["memory_misses"] == 1
        assert summary["instinct_matches"] == 0

    def test_agent_metrics_capture_worker_count_from_parallel_agent_tool(self, tmp_path: Path):
        tool_call = SimpleNamespace(
            id="call-parallel-1",
            type="function",
            function=SimpleNamespace(name="spawn_agents_parallel", arguments='{"tasks": [{"task": "a"}, {"task": "b"}]}'),
        )
        first_message = SimpleNamespace(content="", tool_calls=[tool_call])
        second_message = SimpleNamespace(content="并行任务执行完毕", tool_calls=None)
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=first_message)]),
            SimpleNamespace(choices=[SimpleNamespace(message=second_message)]),
        ]

        client = MagicMock()
        client.chat.completions.create.side_effect = responses

        agent = self._make_agent(client, tmp_path)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_detect_repetitive_work", return_value=(False, "")), \
             patch.object(agent, "_build_memory_context", return_value=""), \
             patch.object(agent._learning_loop, "on_user_message", return_value=None), \
             patch.object(agent, "_registry") as registry_mock:
            registry_mock.call.return_value = '{"total": 2, "results": {}}'
            result = agent.run("请并行处理两个任务")

        assert result == "并行任务执行完毕"
        summary = agent.get_runtime_metrics()
        assert summary["tool_calls"] == 1
        assert summary["worker_count"] == 2


class TestPhase8TraceStore:
    def test_trace_store_persists_latest_task_trace(self, tmp_path: Path):
        from maxbot.evals.trace_store import TraceStore

        store = TraceStore(tmp_path / "traces")
        trace_id = store.write_trace(
            {
                "task_id": "task-1",
                "session_id": "session-1",
                "user_message": "请分析项目",
                "final_output": "分析完成",
                "tool_calls": 2,
                "revision_count": 1,
            }
        )

        loaded = store.read_trace(trace_id)
        assert loaded["task_id"] == "task-1"
        assert loaded["revision_count"] == 1
        assert store.list_recent(limit=1)[0]["task_id"] == "task-1"
