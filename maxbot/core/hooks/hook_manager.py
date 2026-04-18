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
from typing import Callable, Dict, List, Optional, Any
from .hook_events import HookEvent, HookContext

logger = logging.getLogger(__name__)


class HookManager:
    """钩子管理器（参考 ECC hooks 系统）
    
    功能：
    1. 注册钩子（register, register_many）
    2. 触发钩子（trigger, trigger_sync）
    3. 禁用/启用钩子（disable, enable）
    4. 运行时配置（set_profile）
    5. 钩子列表（list_hooks）
    """
    
    def __init__(self):
        self._hooks: Dict[HookEvent, List[Callable]] = {}
        self._disabled_hooks: set = set()
        self._profile = "standard"  # minimal | standard | strict
        self._load_config_from_env()
    
    def _load_config_from_env(self):
        """从环境变量加载配置（参考 ECC）"""
        # ECC_HOOK_PROFILE: minimal | standard | strict
        profile = os.getenv("MAXBOT_HOOK_PROFILE", "standard")
        self.set_profile(profile)
        
        # ECC_DISABLED_HOOKS: comma-separated hook names
        disabled = os.getenv("MAXBOT_DISABLED_HOOKS", "")
        if disabled:
            for hook_name in disabled.split(","):
                try:
                    event = HookEvent(hook_name.strip())
                    self.disable(event)
                except ValueError:
                    logger.warning(f"Unknown hook event: {hook_name}")
    
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
    
    async def trigger(self, event: HookEvent, context: HookContext):
        """触发钩子（异步，参考 ECC 的 async execution）"""
        if event in self._disabled_hooks:
            logger.debug(f"Hook {event} is disabled, skipping")
            return
        
        hooks = self._hooks.get(event, [])
        for hook in hooks:
            try:
                # 检测是否是 async 函数
                if asyncio.iscoroutinefunction(hook):
                    await hook(context)
                else:
                    hook(context)
            except Exception as e:
                logger.error(f"Hook {hook.__name__} failed: {e}", exc_info=True)
    
    def trigger_sync(self, event: HookEvent, context: HookContext):
        """触发钩子（同步，用于非异步上下文）"""
        if event in self._disabled_hooks:
            logger.debug(f"Hook {event} is disabled, skipping")
            return
        
        hooks = self._hooks.get(event, [])
        for hook in hooks:
            try:
                # 同步调用，如果是 async 函数则忽略
                if not asyncio.iscoroutinefunction(hook):
                    hook(context)
            except Exception as e:
                logger.error(f"Hook {hook.__name__} failed: {e}", exc_info=True)
    
    def disable(self, event: HookEvent):
        """禁用钩子（参考 ECC_DISABLED_HOOKS）"""
        self._disabled_hooks.add(event)
        logger.info(f"Disabled hook: {event}")
    
    def enable(self, event: HookEvent):
        """启用钩子"""
        if event in self._disabled_hooks:
            self._disabled_hooks.remove(event)
            logger.info(f"Enabled hook: {event}")
    
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
        logger.info(f"Set hook profile: {profile}")
        
        # 根据 profile 调整钩子行为
        if profile == "minimal":
            # minimal profile 只保留安全相关钩子
            pass  # TODO: 实现 minimal profile 逻辑
        elif profile == "strict":
            # strict profile 启用所有检查
            pass  # TODO: 实现 strict profile 逻辑
    
    def get_profile(self) -> str:
        """获取当前 profile"""
        return self._profile
    
    def list_hooks(self) -> Dict[str, List[str]]:
        """列出所有已注册的钩子"""
        result = {}
        for event, hooks in self._hooks.items():
            result[event.value] = [h.__name__ for h in hooks]
        return result
    
    def is_enabled(self, event: HookEvent) -> bool:
        """检查钩子是否启用"""
        return event not in self._disabled_hooks
