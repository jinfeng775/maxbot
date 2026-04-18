"""Phase 3: Agent 主循环 Hook 集成回归测试"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from maxbot.core.agent_loop import Agent, AgentConfig


class TestAgentLoopHookIntegration:
    def _make_agent(self, learning_loop_mock: MagicMock, client_mock: MagicMock) -> Agent:
        config = AgentConfig(
            api_key="test-key",
            base_url="http://localhost:99999/v1",
            model="test-model",
            session_id="session-hook-test",
            auto_save=False,
            skills_enabled=False,
        )

        with patch("maxbot.core.agent_loop.LearningLoop", return_value=learning_loop_mock), \
             patch.object(Agent, "_init_client", return_value=client_mock):
            return Agent(config=config)

    def test_run_triggers_session_end_on_success(self):
        learning_loop = MagicMock()
        message = SimpleNamespace(content="任务完成", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = MagicMock()
        client.chat.completions.create.return_value = response

        agent = self._make_agent(learning_loop, client)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()):
            result = agent.run("请完成任务")

        assert result == "任务完成"
        learning_loop.on_user_message.assert_called_once()
        learning_loop.on_session_end.assert_called_once_with(session_id="session-hook-test")
        learning_loop.on_error.assert_not_called()

    def test_run_triggers_error_hook_on_api_exception(self):
        learning_loop = MagicMock()
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("boom")

        agent = self._make_agent(learning_loop, client)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()):
            with pytest.raises(RuntimeError, match="boom"):
                agent.run("请执行失败任务")

        learning_loop.on_user_message.assert_called_once()
        learning_loop.on_error.assert_called_once()
        error_call = learning_loop.on_error.call_args
        assert "boom" in error_call.kwargs["error"]
        assert error_call.kwargs["context"]["user_message"] == "请执行失败任务"
