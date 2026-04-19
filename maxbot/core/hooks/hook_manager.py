"""
Hook 管理器

参考 ECC hooks.json 的钩子系统实现
支持：
- 钩子注册
- 钩子触发（同步/异步）
- 钩子禁用
- 运行时配置（ECC_HOOK_PROFILE, ECC_DISABLED_HOOKS）
"""
import os
import asyncio
import logging
from typing import Callable, Dict, List
from .hook_events import HookEvent, HookContext

logger = logging.getLogger(__name__)


class HookAbortError(Exception):
    """表示 Hook 显式阻断主流程。"""


class HookManager:
    """钩子管理器（参考 ECC hooks 系统）
    
    功能：
    1. 注册钩子（register, register_many）
    2. 触发钩子（trigger, trigger_sync）
    3. 禁用/启用钩子（disable, enable）
    4. 运行时配置（set_profile）
    5. 钩子列表（list_hooks）
    """

    _PROFILE_DISABLED_HOOKS = {
        "minimal": {
            HookEvent.PRE_TOOL_USE: {"pre_documentation_warning", "pre_compact_suggest"},
            HookEvent.POST_TOOL_USE: {"post_tool_observation"},
            HookEvent.PRE_COMPACT: {"pre_compact_suggest"},
            HookEvent.POST_COMPACT: {"post_compact_summary"},
        },
        "standard": {},
        "strict": {},
    }

    def __init__(self):
        self._hooks: Dict[HookEvent, List[Callable]] = {}
        self._manual_disabled_hooks: set[HookEvent] = set()
        self._disabled_hooks: set[HookEvent] = set()
        self._env_disabled_hooks: set[HookEvent] = set()
        self._profile = "standard"  # minimal | standard | strict
        self._load_config_from_env()
    
    def _load_config_from_env(self):
        """从环境变量加载配置（参考 ECC）"""
        # ECC_HOOK_PROFILE: minimal | standard | strict
        profile = os.getenv("MAXBOT_HOOK_PROFILE", "standard")

        # ECC_DISABLED_HOOKS: comma-separated hook names
        disabled = os.getenv("MAXBOT_DISABLED_HOOKS", "")
        self._env_disabled_hooks.clear()
        if disabled:
            for hook_name in disabled.split(","):
                try:
                    event = HookEvent(hook_name.strip())
                    self._env_disabled_hooks.add(event)
                except ValueError:
                    logger.warning(f"Unknown hook event: {hook_name}")

        self.set_profile(profile)
    
    def register(self, event: HookEvent, hook: Callable):
        """注册钩子"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(hook)
        logger.debug(f"Registered hook for {event}: {hook.__name__}")
    
    def register_many(self, hooks: Dict[HookEvent, List[Callable]]):
        """批量注册钩子"""
        for event, hook_list in hooks.items():
            for hook in hook_list:
                self.register(event, hook)
    
    def unregister(self, event: HookEvent, hook: Callable):
        """注销钩子"""
        if event in self._hooks:
            if hook in self._hooks[event]:
                self._hooks[event].remove(hook)
                logger.debug(f"Unregistered hook for {event}: {hook.__name__}")

    def _prepare_context(self, context: HookContext) -> HookContext:
        context.profile = self._profile
        return context

    def _get_active_hooks(self, event: HookEvent) -> list[Callable]:
        disabled_names = self._PROFILE_DISABLED_HOOKS.get(self._profile, {}).get(event, set())
        return [
            hook
            for hook in self._hooks.get(event, [])
            if hook.__name__ not in disabled_names
        ]

    def _run_hook(self, hook: Callable, context: HookContext, *, allow_async: bool):
        if asyncio.iscoroutinefunction(hook):
            if allow_async:
                return hook(context)
            return None
        return hook(context)

    def _handle_hook_error(self, hook: Callable, error: Exception):
        if isinstance(error, HookAbortError):
            raise
        logger.error(f"Hook {hook.__name__} failed: {error}", exc_info=True)
    
    async def trigger(self, event: HookEvent, context: HookContext):
        """触发钩子（异步，参考 ECC 的 async execution）"""
        if event in self._disabled_hooks:
            logger.debug(f"Hook {event} is disabled, skipping")
            return
        
        prepared_context = self._prepare_context(context)
        hooks = self._get_active_hooks(event)
        for hook in hooks:
            try:
                result = self._run_hook(hook, prepared_context, allow_async=True)
                if result is not None and asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self._handle_hook_error(hook, e)
    
    def trigger_sync(self, event: HookEvent, context: HookContext):
        """触发钩子（同步，用于非异步上下文）"""
        if event in self._disabled_hooks:
            logger.debug(f"Hook {event} is disabled, skipping")
            return
        
        prepared_context = self._prepare_context(context)
        hooks = self._get_active_hooks(event)
        for hook in hooks:
            try:
                self._run_hook(hook, prepared_context, allow_async=False)
            except Exception as e:
                self._handle_hook_error(hook, e)
    
    def disable(self, event: HookEvent):
        """禁用钩子（参考 ECC_DISABLED_HOOKS）"""
        self._manual_disabled_hooks.add(event)
        self._apply_profile()
        logger.info(f"Disabled hook: {event}")
    
    def enable(self, event: HookEvent):
        """启用钩子"""
        if event in self._manual_disabled_hooks:
            self._manual_disabled_hooks.remove(event)
            self._apply_profile()
            logger.info(f"Enabled hook: {event}")

    def _apply_profile(self):
        self._disabled_hooks = set(self._env_disabled_hooks)
        self._disabled_hooks.update(self._manual_disabled_hooks)
    
    def set_profile(self, profile: str):
        """设置运行时配置（参考 ECC_HOOK_PROFILE）
        
        Args:
            profile: minimal | standard | strict
        """
        valid_profiles = ["minimal", "standard", "strict"]
        if profile not in valid_profiles:
            logger.warning(f"Invalid profile: {profile}, using 'standard'")
            profile = "standard"
        
        self._profile = profile
        self._apply_profile()
        logger.info(f"Set hook profile: {profile}")
    
    def get_profile(self) -> str:
        """获取当前 profile"""
        return self._profile
    
    def list_hooks(self) -> Dict[str, List[str]]:
        """列出所有已注册且当前启用的钩子"""
        result = {}
        for event, hooks in self._hooks.items():
            if event in self._disabled_hooks:
                continue
            result[event.value] = [h.__name__ for h in self._get_active_hooks(event)]
        return result
    
    def is_enabled(self, event: HookEvent) -> bool:
        """检查钩子是否启用"""
        return event not in self._disabled_hooks
