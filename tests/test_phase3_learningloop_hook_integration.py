"""Phase 3: Agent 主循环与 LearningLoop 集成回归测试"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from maxbot.core.agent_loop import Agent, AgentConfig


class TestAgentLoopLearningLoopIntegration:
    def _make_agent(self, learning_loop_mock: MagicMock, client_mock: MagicMock) -> Agent:
        config = AgentConfig(
            api_key="test-key",
            base_url="http://localhost:99999/v1",
            model="test-model",
            session_id="session-learning-test",
            auto_save=False,
            skills_enabled=False,
        )

        with patch("maxbot.core.agent_loop.LearningLoop", return_value=learning_loop_mock), \
             patch.object(Agent, "_init_client", return_value=client_mock):
            return Agent(config=config)

    def test_run_routes_session_start_and_tool_hooks_into_learning_loop(self):
        learning_loop = MagicMock()
        tool_call = SimpleNamespace(
            id="call-1",
            type="function",
            function=SimpleNamespace(
                name="search_files",
                arguments='{"pattern": "HookEvent"}',
            ),
        )
        first_message = SimpleNamespace(content="", tool_calls=[tool_call])
        second_message = SimpleNamespace(content="任务完成", tool_calls=None)
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=first_message)]),
            SimpleNamespace(choices=[SimpleNamespace(message=second_message)]),
        ]

        client = MagicMock()
        client.chat.completions.create.side_effect = responses

        agent = self._make_agent(learning_loop, client)

        with patch("maxbot.core.agent_loop._retry_api_call", side_effect=lambda fn, **_: fn()), \
             patch.object(agent, "_save_session", return_value=None), \
             patch.object(agent, "_detect_repetitive_work", return_value=(False, "")), \
             patch.object(agent, "_registry") as registry_mock:
            registry_mock.call.return_value = '{"matches": 3}'
            result = agent.run("请搜索 HookEvent 定义")

        assert result == "任务完成"
        learning_loop.on_user_message.assert_called_once_with(
            session_id="session-learning-test",
            user_message="请搜索 HookEvent 定义",
            context={"user_message": "请搜索 HookEvent 定义"},
        )
        learning_loop.on_tool_call.assert_called_once_with(
            tool_name="search_files",
            arguments={"pattern": "HookEvent"},
            call_id="call-1",
        )
        learning_loop.on_tool_result.assert_called_once_with(
            tool_name="search_files",
            success=True,
            result_data={"matches": 3},
            error=None,
            call_id="call-1",
        )
