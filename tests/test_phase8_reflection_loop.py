from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from maxbot.core.agent_loop import Agent, AgentConfig


class TestReflectionPolicy:
    def test_should_reflect_for_high_risk_tool_usage(self):
        from maxbot.reflection.policy import ReflectionPolicy

        policy = ReflectionPolicy(
            enabled=True,
            max_revisions=1,
            min_output_chars=20,
            high_risk_tool_threshold=2,
            apply_to_task_types=["default"],
        )

        decision = policy.should_reflect(
            task_type="default",
            output_text="这是一个足够长的初稿输出，用来触发反思流程。",
            tool_calls=3,
            metadata={"risk_level": "medium"},
        )

        assert decision.enabled is True
        assert decision.reason == "high_risk_tool_usage"

    def test_should_skip_when_output_too_short(self):
        from maxbot.reflection.policy import ReflectionPolicy

        policy = ReflectionPolicy(
            enabled=True,
            max_revisions=1,
            min_output_chars=50,
            high_risk_tool_threshold=2,
            apply_to_task_types=["default"],
        )

        decision = policy.should_reflect(
            task_type="default",
            output_text="太短",
            tool_calls=0,
            metadata={},
        )

        assert decision.enabled is False
        assert decision.reason == "output_too_short"

    def test_should_skip_when_task_type_not_enabled(self):
        from maxbot.reflection.policy import ReflectionPolicy

        policy = ReflectionPolicy(
            enabled=True,
            max_revisions=1,
            min_output_chars=10,
            high_risk_tool_threshold=1,
            apply_to_task_types=["code"],
        )

        decision = policy.should_reflect(
            task_type="default",
            output_text="这是一个足够长的输出",
            tool_calls=4,
            metadata={},
        )

        assert decision.enabled is False
        assert decision.reason == "task_type_not_enabled"


class TestReflectionLoop:
    def test_loop_revises_once_when_critique_requests_revision(self):
        from maxbot.reflection.loop import ReflectionLoop
        from maxbot.reflection.policy import ReflectionDecision

        critic = MagicMock()
        critic.critique.side_effect = [
            {"revise": True, "feedback": "请补充边界条件"},
            {"revise": False, "feedback": "通过"},
        ]
        revise_fn = MagicMock(side_effect=["修订后的答案"])

        loop = ReflectionLoop(critic=critic, max_revisions=2)
        result = loop.run(
            draft="初稿答案",
            decision=ReflectionDecision(enabled=True, reason="high_risk_tool_usage", max_revisions=2),
            revise_fn=revise_fn,
            context={"task_type": "default"},
        )

        assert result.final_output == "修订后的答案"
        assert result.revision_count == 1
        assert result.reflection_applied is True
        revise_fn.assert_called_once_with("初稿答案", "请补充边界条件")

    def test_loop_returns_original_when_decision_disabled(self):
        from maxbot.reflection.loop import ReflectionLoop
        from maxbot.reflection.policy import ReflectionDecision

        critic = MagicMock()
        revise_fn = MagicMock()
        loop = ReflectionLoop(critic=critic, max_revisions=2)

        result = loop.run(
            draft="初稿答案",
            decision=ReflectionDecision(enabled=False, reason="output_too_short", max_revisions=2),
            revise_fn=revise_fn,
            context={},
        )

        assert result.final_output == "初稿答案"
        assert result.revision_count == 0
        assert result.reflection_applied is False
        critic.critique.assert_not_called()
        revise_fn.assert_not_called()

    def test_loop_stops_when_revision_limit_reached(self):
        from maxbot.reflection.loop import ReflectionLoop
        from maxbot.reflection.policy import ReflectionDecision

        critic = MagicMock()
        critic.critique.side_effect = [
            {"revise": True, "feedback": "第一轮修订"},
            {"revise": True, "feedback": "第二轮修订"},
        ]
        revise_fn = MagicMock(side_effect=["修订后的答案"])

        loop = ReflectionLoop(critic=critic, max_revisions=1)
        result = loop.run(
            draft="初稿答案",
            decision=ReflectionDecision(enabled=True, reason="high_risk_tool_usage", max_revisions=3),
            revise_fn=revise_fn,
            context={"task_type": "default"},
        )

        assert result.final_output == "修订后的答案"
        assert result.revision_count == 1
        assert len(result.critiques) == 2
        assert result.stopped_reason == "max_revisions_reached"
        revise_fn.assert_called_once_with("初稿答案", "第一轮修订")


class TestAgentLoopReflectionIntegration:
    def _make_agent(self, client_mock: MagicMock) -> Agent:
        config = AgentConfig(
            api_key="test-key",
            base_url="http://localhost:99999/v1",
            model="test-model",
            session_id="session-reflection-test",
            auto_save=False,
            skills_enabled=False,
            reflection_enabled=True,
            reflection_max_revisions=1,
            reflection_min_output_chars=10,
            reflection_high_risk_tool_threshold=1,
            reflection_task_types=["default"],
        )

        with patch.object(Agent, "_init_client", return_value=client_mock):
            return Agent(config=config)

    def test_run_applies_reflection_before_returning(self):
        first_message = SimpleNamespace(content="需要修订的初稿答案", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=first_message)])

        client = MagicMock()
        client.chat.completions.create.return_value = response

        agent = self._make_agent(client)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_apply_reflection", return_value=SimpleNamespace(
                 final_output="修订后的最终答案",
                 revision_count=1,
                 reflection_applied=True,
                 critiques=[{"feedback": "请补充边界条件", "revise": True}],
             )) as reflection_mock:
            result = agent.run("请给我一个高风险任务的结果")

        assert result == "修订后的最终答案"
        reflection_mock.assert_called_once()

    def test_run_fail_closes_when_reflection_errors_in_strict_mode(self):
        first_message = SimpleNamespace(content="需要修订的初稿答案", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=first_message)])

        client = MagicMock()
        client.chat.completions.create.return_value = response

        agent = self._make_agent(client)
        agent.config.reflection_fail_closed = True

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_apply_reflection", side_effect=RuntimeError("reflection failed")):
            with pytest.raises(RuntimeError, match="reflection failed"):
                agent.run("请给我一个高风险任务的结果")
