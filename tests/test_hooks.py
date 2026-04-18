"""
Hook 系统测试

测试 Hook 事件、管理器和内置钩子
"""
import pytest
from maxbot.core.hooks import HookManager, HookEvent, HookContext, BUILTIN_HOOKS
from maxbot.core.hooks.builtin_hooks import (
    pre_command_safety_check,
    pre_documentation_warning,
    pre_config_protection,
    pre_compact_suggest,
    post_tool_observation,
    session_start_capture,
    session_end_summary,
    error_capture,
)


class TestHookEvents:
    """测试 Hook 事件"""
    
    def test_hook_event_enum(self):
        """测试 Hook 事件枚举"""
        assert HookEvent.PRE_TOOL_USE == "pre_tool_use"
        assert HookEvent.POST_TOOL_USE == "post_tool_use"
        assert HookEvent.SESSION_START == "session_start"
        assert HookEvent.SESSION_END == "session_end"
        assert HookEvent.PRE_COMPACT == "pre_compact"
        assert HookEvent.POST_COMPACT == "post_compact"
        assert HookEvent.ERROR == "error"
    
    def test_hook_context_creation(self):
        """测试 Hook 上下文创建"""
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="shell",
            tool_args={"command": "ls -la"},
            session_id="session-123"
        )
        
        assert context.event == HookEvent.PRE_TOOL_USE
        assert context.tool_name == "shell"
        assert context.tool_args == {"command": "ls -la"}
        assert context.session_id == "session-123"


class TestHookManager:
    """测试 Hook 管理器"""
    
    def test_hook_registration(self):
        """测试钩子注册"""
        manager = HookManager()
        
        # 注册单个钩子
        def dummy_hook(context: HookContext):
            pass
        
        manager.register(HookEvent.PRE_TOOL_USE, dummy_hook)
        assert len(manager._hooks[HookEvent.PRE_TOOL_USE]) == 1
    
    def test_register_many(self):
        """测试批量注册"""
        manager = HookManager()
        
        hooks = {
            HookEvent.PRE_TOOL_USE: [lambda ctx: None],
            HookEvent.POST_TOOL_USE: [lambda ctx: None, lambda ctx: None],
        }
        
        manager.register_many(hooks)
        assert len(manager._hooks[HookEvent.PRE_TOOL_USE]) == 1
        assert len(manager._hooks[HookEvent.POST_TOOL_USE]) == 2
    
    def test_builtin_hooks(self):
        """测试内置钩子"""
        manager = HookManager()
        manager.register_many(BUILTIN_HOOKS)
        
        assert HookEvent.PRE_TOOL_USE in manager._hooks
        assert HookEvent.POST_TOOL_USE in manager._hooks
        assert HookEvent.SESSION_START in manager._hooks
        assert HookEvent.SESSION_END in manager._hooks
        assert HookEvent.ERROR in manager._hooks
    
    def test_hook_disable(self):
        """测试钩子禁用"""
        manager = HookManager()
        
        def dummy_hook(context: HookContext):
            pass
        
        manager.register(HookEvent.PRE_TOOL_USE, dummy_hook)
        manager.disable(HookEvent.PRE_TOOL_USE)
        
        assert not manager.is_enabled( HookEvent.PRE_TOOL_USE)
    
    def test_hook_enable(self):
        """测试钩子启用"""
        manager = HookManager()
        
        def dummy_hook(context: HookContext):
            pass
        
        manager.register(HookEvent.PRE_TOOL_USE, dummy_hook)
        manager.disable(HookEvent.PRE_TOOL_USE)
        manager.enable(HookEvent.PRE_TOOL_USE)
        
        assert manager.is_enabled(  HookEvent.PRE_TOOL_USE)
    
    def test_set_profile(self):
        """测试设置 profile"""
        manager = HookManager()
        
        manager.set_profile("minimal")
        assert manager.get_profile() == "minimal"
        
        manager.set_profile("standard")
        assert manager.get_profile() == "standard"
        
        manager.set_profile("strict")
        assert manager.get_profile() == "strict"
    
    def test_list_hooks(self):
        """测试列出钩子"""
        manager = HookManager()
        
        def hook1(ctx):
            pass
        def hook2(ctx):
            pass
        
        manager.register(HookEvent.PRE_TOOL_USE, hook1)
        manager.register(HookEvent.PRE_TOOL_USE, hook2)
        
        hooks = manager.list_hooks()
        assert "pre_tool_use" in hooks
        assert len(hooks["pre_tool_use"]) == 2
    
    def test_trigger_sync(self):
        """测试同步触发钩子"""
        manager = HookManager()
        
        call_count = []
        
        def counting_hook(context: HookContext):
            call_count.append(1)
        
        manager.register(HookEvent.PRE_TOOL_USE, counting_hook)
        
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="test",
        )
        
        manager.trigger_sync(HookEvent.PRE_TOOL_USE, context)
        assert len(call_count) == 1
    
    def test_trigger_disabled_hook(self):
        """测试触发已禁用的钩子"""
        manager = HookManager()
        
        call_count = []
        
        def counting_hook(context: HookContext):
            call_count.append(1)
        
        manager.register(HookEvent.PRE_TOOL_USE, counting_hook)
        manager.disable(HookEvent.PRE_TOOL_USE)
        
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="test",
        )
        
        manager.trigger_sync(HookEvent.PRE_TOOL_USE, context)
        assert len(call_count) == 0  # 钩子被禁用，不应该被调用


class TestBuiltinHooks:
    """测试内置钩子"""
    
    def test_pre_command_safety_check(self):
        """测试危险命令检查"""
        # 正常命令
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="shell",
            tool_args={"command": "ls -la"}
        )
        pre_command_safety_check(context)  # 不应该抛出异常
        
        # 危险命令
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero",
            ":(){ :|:& };:",
        ]
        
        for cmd in dangerous_commands:
            context = HookContext(
                event=HookEvent.PRE_TOOL_USE,
                tool_name="shell",
                tool_args={"command": cmd}
            )
            with pytest.raises(ValueError, match="危险命令被拦截"):
                pre_command_safety_check(context)
    
    def test_pre_documentation_warning(self):
        """测试文档文件警告"""
        # 文档文件
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="write_file",
            tool_args={"path": "docs/README.md"}
        )
        # 应该发出警告（这里只是调用，不检查日志输出）
        pre_documentation_warning(context)
        
        # 非文档文件
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="write_file",
            tool_args={"path": "src/main.py"}
        )
        pre_documentation_warning(context)
    
    def test_pre_config_protection(self):
        """测试配置文件保护"""
        # 受保护的配置文件
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="write_file",
            tool_args={"path": ".eslintrc"}
        )
        # 在 standard profile 下应该警告
        pre_config_protection(context)
    
    def test_post_tool_observation(self):
        """测试工具调用观察"""
        context = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="shell",
            tool_args={"command": "ls -la"},
            tool_result="file1\nfile2"
        )
        # 不应该抛出异常
        post_tool_observation(context)
    
    def test_session_hooks(self):
        """测试会话钩子"""
        # Session start
        context = HookContext(
            event=HookEvent.SESSION_START,
            session_id="session-123"
        )
        session_start_capture(context)
        
        # Session end
        context = HookContext(
            event=HookEvent.SESSION_END,
            session_id="session-123"
        )
        session_end_summary(context)
    
    def test_error_capture(self):
        """测试错误捕获"""
        context = HookContext(
            event=HookEvent.ERROR,
            metadata={"error": "Test error"}
        )
        # 不应该抛出异常
        error_capture(context)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
