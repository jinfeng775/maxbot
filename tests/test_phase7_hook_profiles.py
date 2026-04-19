"""Phase 7 compact-hook/profile 回归测试。"""

from unittest.mock import MagicMock

import pytest

from maxbot.core.agent_loop import Agent, AgentConfig
from maxbot.core.hooks import HookAbortError, HookContext, HookEvent


class TestPhase7HookProfiles:
    def test_minimal_profile_disables_non_critical_pre_tool_hooks(self):
        from maxbot.core.hooks import HookManager, BUILTIN_HOOKS

        manager = HookManager()
        manager.register_many(BUILTIN_HOOKS)
        manager.set_profile("minimal")

        names = manager.list_hooks().get(HookEvent.PRE_TOOL_USE.value, [])

        assert "pre_command_safety_check" in names
        assert "pre_documentation_warning" not in names
        assert "pre_compact_suggest" not in names

    def test_standard_profile_restores_default_pre_tool_hooks(self):
        from maxbot.core.hooks import HookManager, BUILTIN_HOOKS

        manager = HookManager()
        manager.register_many(BUILTIN_HOOKS)
        manager.set_profile("minimal")
        manager.set_profile("standard")

        names = manager.list_hooks().get(HookEvent.PRE_TOOL_USE.value, [])

        assert "pre_command_safety_check" in names
        assert "pre_documentation_warning" in names
        assert "pre_compact_suggest" in names

    def test_strict_profile_blocks_protected_config_edit(self):
        from maxbot.core.hooks import HookManager, BUILTIN_HOOKS

        manager = HookManager()
        manager.register_many(BUILTIN_HOOKS)
        manager.set_profile("strict")

        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="write_file",
            tool_args={"path": ".eslintrc"},
        )

        with pytest.raises(HookAbortError, match="禁止编辑配置文件"):
            manager.trigger_sync(HookEvent.PRE_TOOL_USE, context)


class TestPhase7CompactEvents:
    def _make_agent(self) -> Agent:
        config = AgentConfig(
            api_key=None,
            session_id="phase7-compact-session",
            auto_save=False,
            skills_enabled=False,
            memory_enabled=False,
        )
        return Agent(config=config)

    def test_compress_context_triggers_pre_and_post_compact_hooks(self):
        agent = self._make_agent()
        agent.messages = [
            {"role": "system", "content": "system"},
            *[{"role": "user", "content": f"message-{idx}"} for idx in range(12)],
        ]

        captured = []

        def record(context: HookContext):
            captured.append((context.event, dict(context.metadata)))

        agent._hook_manager.register(HookEvent.PRE_COMPACT, record)
        agent._hook_manager.register(HookEvent.POST_COMPACT, record)

        agent._compress_context()

        assert [event for event, _ in captured] == [HookEvent.PRE_COMPACT, HookEvent.POST_COMPACT]
        pre_meta = captured[0][1]
        post_meta = captured[1][1]

        assert pre_meta["before_message_count"] == 13
        assert pre_meta["keep_messages"] == 10
        assert post_meta["before_message_count"] == 13
        assert post_meta["after_message_count"] == len(agent.messages)
        assert post_meta["compressed_messages"] == 2
        assert post_meta["compressed_tokens"] >= 0

    def test_run_auto_compression_path_triggers_compact_hooks(self, monkeypatch):
        agent = self._make_agent()
        agent.config.max_context_tokens = 1
        agent._conversation_turns = 0
        agent._last_progress_report_time = 10**9
        agent._save_session = MagicMock(return_value=None)
        agent._check_and_report_progress = MagicMock(return_value=None)
        agent._check_conversation_limit = MagicMock(return_value=False)
        agent._get_enhanced_system_prompt = MagicMock(return_value="system")

        compressed_calls = []
        original_compress = agent._compress_context

        def wrapped_compress():
            compressed_calls.append(True)
            return original_compress()

        monkeypatch.setattr(agent, "_compress_context", wrapped_compress)
        monkeypatch.setattr(
            "maxbot.core.agent_loop._retry_api_call",
            lambda fn, **_: fn(),
        )

        response_message = MagicMock(content="done", tool_calls=None)
        response = MagicMock(choices=[MagicMock(message=response_message)])
        agent._client = MagicMock()
        agent._client.chat.completions.create.return_value = response

        captured = []

        def record(context: HookContext):
            captured.append(context.event)

        agent._hook_manager.register(HookEvent.PRE_COMPACT, record)
        agent._hook_manager.register(HookEvent.POST_COMPACT, record)

        agent.messages = [
            {"role": "system", "content": "system"},
            *[{"role": "user", "content": f"long-message-{idx}"} for idx in range(12)],
        ]

        result = agent.run("trigger auto compact")

        assert result == "done"
        assert compressed_calls == [True]
        assert HookEvent.PRE_COMPACT in captured
        assert HookEvent.POST_COMPACT in captured
