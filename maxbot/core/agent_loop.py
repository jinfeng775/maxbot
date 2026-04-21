"""
Agent Loop — MaxBot 核心对话循环

参考来源:
- Hermes: run_conversation 循环、消息格式、memory 注入
- Claude Code: tool_use 流程、迭代控制
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from maxbot.core.tool_registry import ToolRegistry
from maxbot.core.message_manager import Message, MessageManager
from maxbot.core.context_compressor import ContextCompressor
from maxbot.core.tool_cache import ToolCache, ToolPrioritizer
from maxbot.core.performance_monitor import PerformanceMonitor
from maxbot.core.tool_dependency_analyzer import ToolDependencyAnalyzer
from maxbot.core.tool_cache_enhanced import ToolCache as EnhancedToolCache
from maxbot.core.smart_retry import SmartRetry
from maxbot.sessions import SessionStore
from maxbot.config.config_loader import get_config, load_config
from maxbot.utils.logger import get_logger
from maxbot.skills import SkillManager
from maxbot.core.hooks import HookManager, BUILTIN_HOOKS, HookContext, HookEvent, HookAbortError
from maxbot.learning import LearningLoop
from maxbot.memory import MemPalaceAdapter
from maxbot.reflection import ReflectionCritic, ReflectionLoop, ReflectionPolicy
from maxbot.evals import RuntimeMetrics, RuntimeMetricsCollector, TraceStore, EvalSampleStore

# 获取 Agent 日志器
logger = get_logger("agent")


def _retry_api_call(fn, max_attempts: int = 3, base_delay: float = 1.0):
    """指数退避重试（支持 429/5xx）"""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            err_str = str(e).lower()
            # 不重试的致命错误
            if any(x in err_str for x in ("invalid_api_key", "authentication", "permission", "400", "404")):
                raise
            # 可重试：429 rate limit, 500, 502, 503, timeout, connection
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
    raise last_exc


@dataclass
class AgentConfig:
    """Agent 配置"""
    model: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    max_iterations: int | None = None
    temperature: float | None = None
    system_prompt: str | None = None
    max_context_tokens: int | None = None
    compress_at_tokens: int | None = None
    memory_enabled: bool | None = None
    memory_db_path: str | None = None
    mempalace_enabled: bool | None = None
    mempalace_path: str | None = None
    mempalace_wing: str | None = None
    reflection_enabled: bool | None = None
    reflection_max_revisions: int | None = None
    reflection_min_output_chars: int | None = None
    reflection_high_risk_tool_threshold: int | None = None
    reflection_task_types: list[str] | None = None
    reflection_fail_closed: bool | None = None
    metrics_enabled: bool | None = None
    trace_store_dir: str | None = None
    eval_samples_enabled: bool | None = None
    eval_sample_store_dir: str | None = None
    session_id: str | None = None
    session_store: Any | None = None
    auto_save: bool | None = None
    max_conversation_turns: int | None = None
    # 技能系统配置
    skills_enabled: bool | None = None
    skills_dir: str | None = None
    skill_injection_max_chars: int | None = None
    
    # 优化配置
    enable_tool_cache: bool | None = None
    enable_smart_retry: bool | None = None
    enable_parallel_execution: bool | None = None
    tool_cache_ttl: int | None = None
    max_result_cache_size: int | None = None

    def __post_init__(self):
        """从配置文件加载默认值"""
        try:
            config = get_config()
            self._load_from_config(config)
        except Exception:
            self._set_fallback_defaults()

    def _load_from_config(self, config: Any):
        """从配置对象加载"""
        # 配置映射表：(配置段, 配置键, 字段名)
        config_mappings = [
            ("model", "name", "model"),
            ("model", "provider", "provider"),
            ("model", "base_url", "base_url"),
            ("model", "api_key", "api_key"),
            ("model", "temperature", "temperature"),
            ("system", "prompt", "system_prompt"),
            ("iteration", "max_iterations", "max_iterations"),
            ("context", "max_tokens", "max_context_tokens"),
            ("context", "compress_at_tokens", "compress_at_tokens"),
            ("session", "memory_enabled", "memory_enabled"),
            ("session", "memory_db_path", "memory_db_path"),
            ("session", "mempalace_enabled", "mempalace_enabled"),
            ("session", "mempalace_path", "mempalace_path"),
            ("session", "mempalace_wing", "mempalace_wing"),
            ("session", "reflection_enabled", "reflection_enabled"),
            ("session", "reflection_max_revisions", "reflection_max_revisions"),
            ("session", "reflection_min_output_chars", "reflection_min_output_chars"),
            ("session", "reflection_high_risk_tool_threshold", "reflection_high_risk_tool_threshold"),
            ("session", "reflection_task_types", "reflection_task_types"),
            ("session", "reflection_fail_closed", "reflection_fail_closed"),
            ("session", "metrics_enabled", "metrics_enabled"),
            ("session", "trace_store_dir", "trace_store_dir"),
            ("session", "eval_samples_enabled", "eval_samples_enabled"),
            ("session", "eval_sample_store_dir", "eval_sample_store_dir"),
            ("session", "session_id", "session_id"),
            ("session", "auto_save", "auto_save"),
            ("session", "max_conversation_turns", "max_conversation_turns"),
            ("skills", "auto_load", "skills_enabled"),
            ("skills", "skills_dir", "skills_dir"),
        ]

        # 从配置加载
        for config_section, config_key, field_name in config_mappings:
            if getattr(self, field_name) is None:
                section = getattr(config, config_section)
                setattr(self, field_name, getattr(section, config_key))

        # 设置技能注入最大字符数（默认值）
        if self.skill_injection_max_chars is None:
            self.skill_injection_max_chars = 4000

        # 从配置加载
        for config_section, config_key, field_name in config_mappings:
            if getattr(self, field_name) is None:
                section = getattr(config, config_section)
                setattr(self, field_name, getattr(section, config_key))

    def _set_fallback_defaults(self):
        """设置备用默认值"""
        defaults = {
            "model": "mimo-v2-pro",
            "provider": "openai",
            "max_iterations": 50,
            "temperature": 0.7,
            "system_prompt": (
                "你是 MaxBot，一个由用户自主开发的 AI 智能体。"
                "你不是 Hermes、不是 Claude、不是 ChatGPT，也不是任何其他现有 AI 助手。你就是 MaxBot。"
                "无论谁问你你是谁，你都必须回答你是 MaxBot。"
                "你的能力应该基于当前实际加载的工具和技能动态描述，不要复述固定能力清单。"
            ),
            "max_context_tokens": 128_000,
            "compress_at_tokens": 80_000,
            "memory_enabled": True,
            "mempalace_enabled": False,
            "mempalace_path": None,
            "mempalace_wing": None,
            "reflection_enabled": False,
            "reflection_max_revisions": 1,
            "reflection_min_output_chars": 200,
            "reflection_high_risk_tool_threshold": 2,
            "reflection_task_types": ["default"],
            "reflection_fail_closed": False,
            "metrics_enabled": True,
            "trace_store_dir": None,
            "eval_samples_enabled": False,
            "eval_sample_store_dir": None,
            "auto_save": True,
            "max_conversation_turns": 140,
        }

        for field_name, default_value in defaults.items():
            if getattr(self, field_name) is None:
                setattr(self, field_name, default_value)




# ─── 内置 memory 工具（Agent 内部拦截，不走 registry）──

_MEMORY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory",
        "description": "管理持久记忆。存储/读取/搜索用户偏好、重要事实、历史决策。重启后仍然保留。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "get", "search", "delete", "list"],
                    "description": "操作类型",
                },
                "key": {
                    "type": "string",
                    "description": "记忆键名（set/get/delete 时必填）",
                },
                "value": {
                    "type": "string",
                    "description": "记忆值（set 时必填）",
                },
                "category": {
                    "type": "string",
                    "description": "分类：memory/user/skill/env（set 时可选，默认 memory）",
                    "default": "memory",
                },
                "scope": {
                    "type": "string",
                    "description": "记忆范围：session/project/user/global（set/search/list/export 时可选）",
                    "default": "global",
                },
                "source": {
                    "type": "string",
                    "description": "来源：manual/agent/imported/derived（set 时可选）",
                    "default": "manual",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表（set 时可选）",
                },
                "importance": {
                    "type": "number",
                    "description": "重要度 0.0-1.0（set 时可选）",
                    "default": 0.5,
                },
                "session_id": {
                    "type": "string",
                    "description": "会话 ID（set/search/list 时可选）",
                },
                "project_id": {
                    "type": "string",
                    "description": "项目 ID（set/search/list 时可选）",
                },
                "user_id": {
                    "type": "string",
                    "description": "用户 ID（set/search/list 时可选）",
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（search 时必填）",
                },
            },
            "required": ["action"],
        },
    },
}


class Agent:
    """
    MaxBot Agent

    用法:
        config = AgentConfig()
        agent = Agent(config=config)
        response = agent.run("帮我分析这个项目")
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        registry: ToolRegistry | None = None,
        session_id: str | None = None,
        memory: Any | None = None,
        session_store: Any | None = None,
    ):
        """
        初始化 Agent

        Args:
            config: Agent 配置
            registry: 工具注册表（None = 使用全局 registry）
            session_id: 会话 ID（可选）
            memory: 可选注入的 Memory 实例
            session_store: 可选注入的 SessionStore 实例
        """
        self.config = config or AgentConfig()
        if session_store is not None:
            self.config.session_store = session_store
        self._injected_memory = memory
        if self._injected_memory is not None:
            self.config.memory_enabled = True
        # 如果没有传入 registry，使用全局 registry
        if registry is None:
            from maxbot.tools import registry as global_registry
            self._registry = global_registry
        else:
            self._registry = registry
        
        # 优化：使用消息管理器
        self._message_manager = MessageManager()
        self._conversation_turns = 0  # 会话轮询计数器
        self._last_progress_report_time = 0  # 上次进度汇报时间
        self._progress_report_interval = 600  # 进度汇报间隔（秒）：10分钟 = 600秒
        
        # 效率优化：检测重复性工作
        self._recent_tool_calls = []  # 最近的工具调用记录
        self._max_recent_calls = 20  # 记录最近20次工具调用
        self._duplicate_threshold = 3  # 连续重复3次相同调用视为重复
        
        # 优化：上下文压缩器
        self._context_compressor = ContextCompressor(
            max_tokens=self.config.max_context_tokens,
            compress_at_tokens=self.config.compress_at_tokens,
            compress_ratio=0.5,
        )
        
        # 优化：工具缓存（使用增强版）
        self._tool_cache = EnhancedToolCache(
            cache_ttl=300,  # 工具列表缓存 TTL: 5 分钟
            result_cache_ttl=60,  # 结果缓存 TTL: 1 分钟
            max_result_cache_size=1000,  # 最大结果缓存条目数
        )
        
        # 优化：智能重试
        self._smart_retry = SmartRetry()
        
        # 优化：工具依赖分析器
        self._dep_analyzer = ToolDependencyAnalyzer()
        
        # 优化：性能监控器
        self._performance_monitor = PerformanceMonitor()
        
        # 兼容性：保留 _messages 属性（内部使用 message_manager）
        self._messages = []  # 不再使用，保留以兼容

        # Hook 系统初始化（参考 ECC hooks.json）
        self._hook_manager = HookManager()
        self._hook_manager.register_many(BUILTIN_HOOKS)
        logger.info(f"Hook 管理器初始化成功: {len(self._hook_manager.list_hooks())} 个钩子")

        # 持续学习系统初始化（通过 Hook 接入主循环）
        self._learning_loop: LearningLoop | None = None
        try:
            self._learning_loop = LearningLoop()
            self._register_learning_hooks()
            logger.info("持续学习系统初始化成功")
        except Exception as e:
            logger.warning(f"持续学习系统初始化失败: {e}")
            self._learning_loop = None

        # 设置会话 ID
        if session_id:
            self.config.session_id = session_id

        logger.info(f"Agent 初始化: 模型={self.config.model}, 会话ID={self.config.session_id}")

        # 初始化 OpenAI 客户端（延迟初始化，避免非运行路径也强制要求 API Key）
        self._client: OpenAI | None = None
        if self.config.api_key or os.environ.get("MAXBOT_API_KEY"):
            self._client = self._init_client()
            logger.debug("OpenAI 客户端初始化成功")
        else:
            logger.debug("未检测到 API Key，跳过客户端初始化，等待运行时再初始化")

        # 初始化 SessionStore
        if self.config.session_store is None:
            self.config.session_store = SessionStore(
                path=self.config.memory_db_path,
            )

        if self._injected_memory is not None:
            self.config.session_store.memory = self._injected_memory

        # 初始化技能管理器
        self._skill_manager: SkillManager | None = None
        if self.config.skills_enabled:
            try:
                self._skill_manager = SkillManager(skills_dir=self.config.skills_dir)
                logger.info(f"技能管理器初始化成功: {len(self._skill_manager.list_skills())} 个技能")
            except Exception as e:
                logger.warning(f"技能管理器初始化失败: {e}")
                self._skill_manager = None

        # Reflection 运行时初始化
        self._reflection_policy = ReflectionPolicy(
            enabled=bool(self.config.reflection_enabled),
            max_revisions=self.config.reflection_max_revisions or 1,
            min_output_chars=self.config.reflection_min_output_chars or 200,
            high_risk_tool_threshold=self.config.reflection_high_risk_tool_threshold or 2,
            apply_to_task_types=self.config.reflection_task_types or ["default"],
        )
        self._reflection_loop = ReflectionLoop(
            critic=ReflectionCritic(),
            max_revisions=self.config.reflection_max_revisions or 1,
        )

        # Runtime metrics / trace 初始化
        self._runtime_metrics = RuntimeMetricsCollector()
        trace_dir = self.config.trace_store_dir or (Path.home() / ".maxbot" / "traces")
        self._trace_store = TraceStore(trace_dir)
        sample_dir = self.config.eval_sample_store_dir or (Path.home() / ".maxbot" / "eval_samples")
        self._eval_sample_store = EvalSampleStore(sample_dir)
        self._active_run_depth = 0
        self._active_run_start: float | None = None
        self._active_root_user_message: str | None = None
        self._active_run_tool_calls = 0
        self._active_run_worker_count = 0
        self._last_memory_context_hit = False
        self._last_instinct_match_count = 0

        # 加载历史会话
        self._load_session()

    def _init_client(self) -> OpenAI:
        """初始化 OpenAI 客户端"""
        api_key = self.config.api_key or os.environ.get("MAXBOT_API_KEY")
        if not api_key:
            raise ValueError("未设置 API 密钥。请通过 config.api_key 或环境变量 MAXBOT_API_KEY 设置。")

        client_kwargs = {"api_key": api_key}

        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url

        return OpenAI(**client_kwargs)

    def _load_session(self):
        """加载历史会话"""
        if not self.config.session_id:
            logger.debug("未设置会话 ID，跳过历史会话加载")
            return

        logger.debug(f"加载历史会话: {self.config.session_id}")
        session = self.config.session_store.get(self.config.session_id)
        if session:
            # 优化：使用消息管理器加载消息
            messages = [
                Message(**msg) if isinstance(msg, dict) else msg
                for msg in session.messages
            ]
            self._message_manager.extend(messages)
            self._conversation_turns = session.metadata.get("conversation_turns", 0)
            logger.info(f"历史会话加载成功: {self._message_manager.get_message_count()} 条消息, {self._conversation_turns} 次轮询")
        else:
            logger.debug(f"未找到历史会话: {self.config.session_id}")

    def _save_session(self):
        """保存会话"""
        if not self.config.session_id or not self.config.auto_save:
            return False

        logger.debug(f"保存会话: {self.config.session_id}, {self._message_manager.get_message_count()} 条消息")
        # 确保 session 存在
        existing = self.config.session_store.get(self.config.session_id)
        if not existing:
            self.config.session_store.create(
                self.config.session_id,
                title=self._derive_session_title(),
            )
            existing = self.config.session_store.get(self.config.session_id)

        messages = [msg.to_api() for msg in self._message_manager.get_messages()]
        self.config.session_store.save_messages(
            self.config.session_id,
            messages,
            metadata=self._build_session_metadata(existing),
        )

        # 同步到 MemPalace
        if self.config.mempalace_enabled:
            try:
                from maxbot.memory import MemPalaceAdapter

                adapter = MemPalaceAdapter(self.config.mempalace_path)
                if adapter.is_available():
                    # 获取 wing 和 room
                    session_meta = self._build_session_metadata(existing)
                    wing = self.config.mempalace_wing or session_meta.get("project_id", "conversations")
                    room = session_meta.get("user_id", "general")

                    # 存储会话到 MemPalace
                    success = adapter.store_session(messages, self.config.session_id, wing=wing, room=room)
                    if success:
                        logger.info(f"会话已同步到 MemPalace: {self.config.session_id}")
            except Exception as e:
                logger.warning(f"同步到 MemPalace 失败: {e}")

        return True

    def _derive_session_title(self) -> str:
        for message in self._message_manager.get_messages():
            if message.role == "user" and message.content.strip():
                return message.content.strip()[:80]
        return ""

    def _build_session_metadata(self, existing_session=None) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if existing_session and getattr(existing_session, "metadata", None):
            metadata.update(existing_session.metadata)
        metadata["conversation_turns"] = self._conversation_turns
        for message in self._message_manager.get_messages():
            if not getattr(message, "metadata", None):
                continue
            for key in ("project_id", "user_id"):
                value = message.metadata.get(key)
                if value and key not in metadata:
                    metadata[key] = value
        return metadata

    def _call_memory_tool(self, args: dict[str, Any]) -> str:
        """调用内置 memory 工具"""
        action = args.get("action")
        logger.debug(f"调用 memory 工具: action={action}")

        if action == "set":
            self.config.session_store.memory.set(
                key=args.get("key"),
                value=args.get("value"),
                category=args.get("category", "memory"),
                scope=args.get("scope", "global"),
                source=args.get("source", "manual"),
                tags=args.get("tags") or [],
                importance=args.get("importance", 0.5),
                session_id=args.get("session_id"),
                project_id=args.get("project_id"),
                user_id=args.get("user_id"),
            )
            return json.dumps({"ok": True}, ensure_ascii=False)
        elif action == "get":
            value = self.config.session_store.memory.get(key=args.get("key"))
            return json.dumps({"key": args.get("key"), "value": value}, ensure_ascii=False)
        elif action == "search":
            entries = self.config.session_store.memory.search(
                query=args.get("query"),
                scope=args.get("scope"),
                session_id=args.get("session_id"),
                project_id=args.get("project_id"),
                user_id=args.get("user_id"),
            )
            return json.dumps(
                [{"key": e.key, "value": e.value, "category": e.category,
                  "scope": e.scope, "source": e.source, "tags": e.tags,
                  "importance": e.importance, "session_id": e.session_id,
                  "project_id": e.project_id, "user_id": e.user_id,
                  "created_at": e.created_at, "updated_at": e.updated_at}
                 for e in entries],
                ensure_ascii=False,
            )
        elif action == "delete":
            ok = self.config.session_store.memory.delete(key=args.get("key"))
            return json.dumps({"ok": ok}, ensure_ascii=False)
        elif action == "list":
            entries = self.config.session_store.memory.list_all(
                category=args.get("category"),
                scope=args.get("scope"),
                session_id=args.get("session_id"),
                project_id=args.get("project_id"),
                user_id=args.get("user_id"),
            )
            return json.dumps(
                [{"key": e.key, "value": e.value, "category": e.category,
                  "scope": e.scope, "source": e.source, "tags": e.tags,
                  "importance": e.importance, "session_id": e.session_id,
                  "project_id": e.project_id, "user_id": e.user_id,
                  "created_at": e.created_at, "updated_at": e.updated_at}
                 for e in entries],
                ensure_ascii=False,
            )
        else:
            logger.warning(f"未知的 memory 操作: {action}")
            return json.dumps({"error": f"未知操作: {action}"}, ensure_ascii=False)

    def _register_learning_hooks(self):
        """注册学习系统相关钩子"""
        if not self._learning_loop:
            return

        def _on_session_start(context: HookContext):
            user_message = context.metadata.get("user_message", "")
            suggestion = self._learning_loop.on_user_message(
                session_id=context.session_id or self.config.session_id or "unknown",
                user_message=user_message,
                context=context.metadata,
            )
            if suggestion:
                match = suggestion.get("match") if isinstance(suggestion, dict) else None
                if match:
                    self._last_instinct_match_count = 1

        def _on_pre_tool_use(context: HookContext):
            self._learning_loop.on_tool_call(
                tool_name=context.tool_name or "unknown",
                arguments=context.tool_args or {},
                call_id=context.metadata.get("call_id"),
            )

        def _on_post_tool_use(context: HookContext):
            tool_result = context.tool_result
            success = True
            error = None
            result_data = None

            if isinstance(tool_result, str):
                try:
                    parsed = json.loads(tool_result)
                    if isinstance(parsed, dict):
                        result_data = parsed
                        if parsed.get("error"):
                            success = False
                            error = parsed.get("error")
                except (json.JSONDecodeError, ValueError):
                    result_data = {"raw": tool_result}
            elif isinstance(tool_result, dict):
                result_data = tool_result
                if tool_result.get("error"):
                    success = False
                    error = tool_result.get("error")

            self._learning_loop.on_tool_result(
                tool_name=context.tool_name or "unknown",
                success=success,
                result_data=result_data,
                error=error,
                call_id=context.metadata.get("call_id"),
            )

        def _on_session_end(context: HookContext):
            self._learning_loop.on_session_end(
                session_id=context.session_id or self.config.session_id or "unknown"
            )

        def _on_error(context: HookContext):
            self._learning_loop.on_error(
                error=str(context.metadata.get("error", "unknown error")),
                context=context.metadata,
            )

        self._hook_manager.register(HookEvent.SESSION_START, _on_session_start)
        self._hook_manager.register(HookEvent.PRE_TOOL_USE, _on_pre_tool_use)
        self._hook_manager.register(HookEvent.POST_TOOL_USE, _on_post_tool_use)
        self._hook_manager.register(HookEvent.SESSION_END, _on_session_end)
        self._hook_manager.register(HookEvent.ERROR, _on_error)

    def _trigger_hook(self, event: HookEvent, **kwargs):
        """安全触发 Hook，避免钩子异常破坏主流程"""
        try:
            context = HookContext(event=event, session_id=self.config.session_id, **kwargs)
            self._hook_manager.trigger_sync(event, context)
        except HookAbortError:
            raise
        except Exception as e:
            logger.error(f"Hook 触发失败 [{event}]: {e}")

    def _call_tool(self, tool_call: dict[str, Any]) -> str:
        """调用工具（集成 Hook 系统）"""
        function_name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})
        call_id = tool_call.get("id")

        # arguments 可能是 JSON 字符串（来自 API），需要解析为 dict
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"工具参数 JSON 解析失败: {arguments[:200]}")
                arguments = {}

        # Pre-tool hook（参考 ECC PreToolUse）
        self._trigger_hook(
            HookEvent.PRE_TOOL_USE,
            tool_name=function_name,
            tool_args=arguments,
            metadata={"call_id": call_id},
        )

        # 内置 memory 工具
        if function_name == "memory":
            result = self._call_memory_tool(arguments)
        # 注册表中的工具
        elif self._registry:
            result = self._registry.call(function_name, arguments)
        else:
            logger.error(f"未找到工具: {function_name}")
            result = json.dumps({"error": f"未找到工具: {function_name}"}, ensure_ascii=False)

        # Post-tool hook（参考 ECC PostToolUse）
        self._trigger_hook(
            HookEvent.POST_TOOL_USE,
            tool_name=function_name,
            tool_args=arguments,
            tool_result=result,
            metadata={"call_id": call_id},
        )

        return result

    def _compress_context(self):
        """压缩上下文（移除旧消息）"""
        current_messages = self._message_manager.get_messages()
        keep_messages = 10
        if len(current_messages) > keep_messages:
            before_message_count = len(current_messages)
            before_tokens = sum(len((message.content or "")) for message in current_messages) // 4
            self._trigger_hook(
                HookEvent.PRE_COMPACT,
                metadata={
                    "before_message_count": before_message_count,
                    "before_tokens": before_tokens,
                    "keep_messages": keep_messages,
                },
            )

            system_msgs = [m for m in current_messages if m.role == "system"]
            recent_msgs = current_messages[-keep_messages:]
            self.messages = system_msgs + recent_msgs

            after_messages = self._message_manager.get_messages()
            after_message_count = len(after_messages)
            after_tokens = sum(len((message.content or "")) for message in after_messages) // 4
            self._trigger_hook(
                HookEvent.POST_COMPACT,
                metadata={
                    "before_message_count": before_message_count,
                    "after_message_count": after_message_count,
                    "compressed_messages": before_message_count - after_message_count,
                    "before_tokens": before_tokens,
                    "after_tokens": after_tokens,
                    "compressed_tokens": max(before_tokens - after_tokens, 0),
                    "keep_messages": keep_messages,
                },
            )

    def _check_conversation_limit(self) -> bool:
        """检查是否超过会话轮询限制"""
        self._conversation_turns += 1

        if self._conversation_turns > self.config.max_conversation_turns:
            return True
        return False

    def _check_and_report_progress(self) -> str | None:
        """
        检查并汇报进度

        Returns:
            进度汇报消息（如果需要汇报）
        """
        current_time = time.time()
        
        # 检查是否需要汇报进度
        if current_time - self._last_progress_report_time >= self._progress_report_interval:
            self._last_progress_report_time = current_time
            
            # 计算进度信息
            progress_report = (
                f"⏳ 正在工作中... 已执行 {self._conversation_turns} 次轮询，"
                f"上下文 {self._message_manager.get_total_tokens()} tokens，请继续等待。"
            )
            
            logger.info(f"进度汇报: 轮询={self._conversation_turns}, tokens={self._message_manager.get_total_tokens()}")
            return progress_report
        
        return None

    def _detect_repetitive_work(self, tool_name: str, tool_args: dict) -> tuple[bool, str]:
        """
        检测重复性工作

        Args:
            tool_name: 工具名称
            tool_args: 工具参数

        Returns:
            (是否重复, 警告消息)
        """
        import hashlib
        
        # 创建工具调用的唯一标识
        call_signature = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
        call_hash = hashlib.md5(call_signature.encode()).hexdigest()
        
        # 添加到最近调用记录
        self._recent_tool_calls.append({
            "name": tool_name,
            "args": tool_args,
            "hash": call_hash,
            "timestamp": time.time()
        })
        
        # 保持记录大小
        if len(self._recent_tool_calls) > self._max_recent_calls:
            self._recent_tool_calls.pop(0)
        
        # 检查是否有重复调用
        recent_hashes = [call["hash"] for call in self._recent_tool_calls]
        duplicate_count = recent_hashes[1:].count(call_hash)  # 不包括当前调用
        
        if duplicate_count >= self._duplicate_threshold:
            warning_msg = (
                f"⚠️ 检测到可能的重复性工作：\n"
                f"  • 工具: {tool_name}\n"
                f"  • 最近已调用 {duplicate_count} 次\n"
                f"  • 这可能导致效率低下\n"
                f"  • 建议：检查工具参数或调整任务策略"
            )
            logger.warning(f"重复性工作检测: {tool_name} 已调用 {duplicate_count} 次")
            return True, warning_msg
        
        return False, ""

    def _get_tool_usage_summary(self) -> str:
        """
        获取工具使用摘要（用于效率分析）

        Returns:
            工具使用摘要
        """
        if not self._recent_tool_calls:
            return ""
        
        # 统计工具使用频率
        tool_usage = {}
        for call in self._recent_tool_calls:
            name = call["name"]
            tool_usage[name] = tool_usage.get(name, 0) + 1
        
        # 生成摘要
        summary = "📈 工具使用统计（最近20次调用）：\n"
        for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
            summary += f"  • {tool}: {count} 次\n"
        
        return summary

    def _collect_runtime_inventory(self) -> tuple[list[str], list[str], list[str]]:
        """收集当前运行时真正暴露给模型的工具、工具集与技能。"""
        tool_names: list[str] = []
        toolsets: list[str] = []
        try:
            tool_schemas = self._get_tools()
            for schema in tool_schemas:
                function_def = schema.get("function", {}) if isinstance(schema, dict) else {}
                name = function_def.get("name")
                if not name:
                    continue
                tool_names.append(name)
                if name == "memory":
                    toolsets.append("builtin")
                elif self._registry:
                    tool_def = self._registry.get(name)
                    if tool_def and getattr(tool_def, "toolset", None):
                        toolsets.append(tool_def.toolset)
        except Exception as e:
            logger.warning(f"读取工具能力失败: {e}")

        skill_names: list[str] = []
        if self._skill_manager:
            try:
                skill_names = sorted(skill.name for skill in self._skill_manager.list_skills())
            except Exception as e:
                logger.warning(f"读取技能能力失败: {e}")

        return sorted(set(tool_names)), sorted(set(toolsets)), skill_names

    @staticmethod
    def _format_capability_section(title: str, items: list[str]) -> list[str]:
        lines = [f"{title}："]
        if not items:
            lines.append("- 暂无")
            return lines
        lines.extend(f"- {item}" for item in items)
        return lines

    def _build_capability_summary(self) -> str:
        """基于当前实际暴露给模型的工具、配置与阶段能力动态生成能力摘要。"""
        tool_names, toolsets, skill_names = self._collect_runtime_inventory()
        tool_name_set = set(tool_names)
        repo_root = Path(__file__).resolve().parents[1]

        enabled_capabilities: list[str] = []
        engineering_parts: list[str] = []
        if tool_name_set & {"read_file", "write_file", "search_files", "list_files", "patch_file"}:
            engineering_parts.append("文件操作")
        if tool_name_set & {"code_edit", "code_edit_multi", "code_create", "undo_edit"}:
            engineering_parts.append("代码编辑")
        if tool_name_set & {"execute_code", "exec_python", "shell"}:
            engineering_parts.append("命令执行")
        if tool_name_set & {"git_status", "git_diff", "git_log", "git_commit", "git_branch"}:
            engineering_parts.append("Git")
        if tool_name_set & {
            "analyze_code", "analyze_project", "analyze_python", "get_function",
            "notebook_read", "notebook_edit_cell", "notebook_insert_cell", "notebook_delete_cell",
        }:
            engineering_parts.append("项目分析")
        if engineering_parts:
            enabled_capabilities.append("工程执行：" + "、".join(engineering_parts))
        web_parts: list[str] = []
        if "web_search" in tool_name_set:
            web_parts.append("网页搜索")
        if "web_fetch" in tool_name_set:
            web_parts.append("内容抓取")
        if web_parts:
            enabled_capabilities.append("外部检索：" + "、".join(web_parts))

        multi_agent_parts: list[str] = []
        if "spawn_agent" in tool_name_set:
            multi_agent_parts.append("任务派发")
        if "spawn_agents_parallel" in tool_name_set:
            multi_agent_parts.append("并行执行")
        if "agent_status" in tool_name_set:
            multi_agent_parts.append("状态汇总")
        if multi_agent_parts:
            enabled_capabilities.append("多 Agent 协作：" + "、".join(multi_agent_parts))
        if "security_scan" in tool_name_set:
            enabled_capabilities.append("安全验证：安全扫描与质量门结果汇总")
        if "memory" in tool_name_set:
            if self.config.memory_enabled:
                enabled_capabilities.append("记忆系统：memory 工具、分层记忆检索与会话持久化")
            else:
                enabled_capabilities.append("记忆工具：可手动读写 memory，自动记忆注入当前关闭")
        if self.config.reflection_enabled:
            enabled_capabilities.append("Reflection：当前会话已启用 critique / revise 反思闭环")
        if self.config.mempalace_enabled:
            enabled_capabilities.append("MemPalace：当前会话已启用外接长期记忆检索与唤醒")
        if self.config.eval_samples_enabled:
            enabled_capabilities.append("Eval Samples：当前会话已启用成功任务评测样本导出")
        if self._learning_loop is not None:
            enabled_capabilities.append("持续学习：Hook 驱动的模式观察、验证与 instinct 沉淀")
        if self.config.metrics_enabled:
            enabled_capabilities.append("运行时评测基础设施：metrics、trace 与执行统计已开启")
        if skill_names:
            enabled_capabilities.append(f"技能系统：已加载 {len(skill_names)} 个技能，可按任务注入流程指南")

        disabled_capabilities: list[str] = []
        if not self.config.reflection_enabled:
            disabled_capabilities.append("Reflection：已实现 critique / revise 反思闭环，但当前默认未启用")
        if not self.config.mempalace_enabled:
            disabled_capabilities.append("MemPalace：外接长期记忆 PoC 已接入，但当前默认未启用")
        if not self.config.eval_samples_enabled:
            disabled_capabilities.append("Eval Samples：成功任务导出为评测样本的链路已实现，但当前默认未启用")
        if not self.config.memory_enabled:
            disabled_capabilities.append("自动记忆注入：分层 memory 检索/注入在当前会话关闭，可通过配置重新开启")
        if not self.config.metrics_enabled:
            disabled_capabilities.append("Runtime Metrics / Trace：运行时指标与轨迹记录当前关闭")

        evolution_capabilities: list[str] = []
        if self._learning_loop is not None:
            evolution_capabilities.append("Phase 3 持续学习闭环：观察 → 模式提取 → 验证 → 存储 → 应用")
        if self.config.session_store is not None and hasattr(self.config.session_store, "memory"):
            evolution_capabilities.append("Phase 4 分层记忆系统：session / project / user / global 记忆 + MemPalace PoC")
        if "security_scan" in tool_name_set or (repo_root / "security" / "security_pipeline.py").exists():
            evolution_capabilities.append("Phase 5 安全验证与质量门：security review pipeline / quality gate")
        if tool_name_set & {"spawn_agent", "spawn_agents_parallel", "agent_status"}:
            evolution_capabilities.append("Phase 6 多 Agent 协作：协调、派发、并行执行与状态汇总")
        if self._hook_manager and self._hook_manager.list_hooks():
            evolution_capabilities.append("Phase 7 Hook 自动化：会话、工具、压缩与错误生命周期 hooks")
        if self._reflection_loop is not None and self._runtime_metrics is not None and self._trace_store is not None:
            evolution_capabilities.append("Phase 8 反思、指标与评测基础设施：reflection、runtime metrics、trace / eval sample")
        if (repo_root / "evals" / "quality_program.py").exists():
            evolution_capabilities.append("Phase 9 质量计划运营层：benchmark runner、report store、quality_program")
        if (repo_root / "knowledge" / "self_improver.py").exists():
            evolution_capabilities.append("自我进化：能力缺口分析、外部知识吸收、技能蒸馏与自动注册")

        lines = ["当前可用能力摘要（动态生成，不是固定清单）："]
        lines.extend(self._format_capability_section("1) 当前已启用能力", enabled_capabilities))
        lines.extend(self._format_capability_section("2) 已实现但默认未启用的能力", disabled_capabilities))
        lines.extend(self._format_capability_section("3) 按进化路线形成的系统级能力（不等于当前会话全部已启用）", evolution_capabilities))
        lines.extend([
            "4) 底层运行时清单：",
            f"- 工具数量: {len(tool_names)}",
            f"- 工具集: {', '.join(toolsets) if toolsets else '无'}",
            f"- 工具名: {', '.join(tool_names) if tool_names else '无'}",
            f"- 技能数量: {len(skill_names)}",
            f"- 技能名: {', '.join(skill_names) if skill_names else '无'}",
            "- 当用户询问“你有什么能力/你能做什么”时，应先回答当前已启用能力，再说明哪些能力是系统已实现但默认未开启，最后补充进化路线上的系统级能力，避免把阶段成果误说成当前全部已启用。",
        ])
        return "\n".join(lines)

    def _build_system_prompt_with_capabilities(self) -> str:
        """在基础系统提示上附加动态能力摘要，并去掉静态能力枚举。"""
        base_prompt = self.config.system_prompt or ""
        static_capability_line = "你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。"
        if static_capability_line in base_prompt:
            base_prompt = base_prompt.replace(static_capability_line, "").strip()
        capability_summary = self._build_capability_summary()
        if not capability_summary:
            return base_prompt
        if not base_prompt:
            return capability_summary
        return f"{base_prompt}\n\n{capability_summary}"

    def _get_enhanced_system_prompt(self, user_message: str) -> str:
        """获取增强的系统提示（包含技能内容）"""
        base_prompt = self._build_system_prompt_with_capabilities()

        if not self._skill_manager and not self.config.memory_enabled:
            return base_prompt

        try:
            sections: list[str] = []
            self._last_memory_context_hit = False

            if self.config.memory_enabled and self.memory is not None:
                memory_context = self._build_memory_context()
                if memory_context:
                    logger.info(f"注入记忆内容: {len(memory_context)} 字符")
                    sections.append(f"相关记忆:\n\n{memory_context}")
                    self._last_memory_context_hit = True

            if self._skill_manager:
                # 获取匹配的技能内容
                skill_content = self._skill_manager.get_injectable_content(
                    user_message,
                    max_chars=self.config.skill_injection_max_chars
                )

                if skill_content:
                    logger.info(f"注入技能内容: {len(skill_content)} 字符")
                    sections.append(f"相关技能指南:\n\n{skill_content}")

            if sections:
                return f"{base_prompt}\n\n---\n\n" + "\n\n---\n\n".join(sections)

            return base_prompt
        except Exception as e:
            logger.warning(f"获取技能内容失败: {e}")
            return base_prompt

    def _build_memory_context(self) -> str:
        if self.memory is None and not self.config.mempalace_enabled:
            return ""
        session_meta = self._build_session_metadata(self.config.session_store.get(self.config.session_id) if self.config.session_id and self.config.session_store else None)
        session_id = self.config.session_id
        project_id = session_meta.get("project_id")
        user_id = session_meta.get("user_id")

        sections: list[str] = []
        seen_values: set[str] = set()
        if self.memory is not None:
            for scope_name, params in [
                ("session", {"scope": "session", "session_id": session_id}),
                ("project", {"scope": "project", "project_id": project_id}),
                ("user", {"scope": "user", "user_id": user_id}),
                ("global", {"scope": "global"}),
            ]:
                text = self.memory.export_text(
                    **params,
                    max_chars=self.config.skill_injection_max_chars,
                    dedupe_by_value=True,
                )
                if not text:
                    continue

                kept_lines: list[str] = []
                for line in text.splitlines()[1:]:
                    if not line.strip():
                        continue
                    value = line.split(": ", 1)[1] if ": " in line else line
                    if value in seen_values:
                        continue
                    seen_values.add(value)
                    kept_lines.append(line)

                if not kept_lines:
                    continue
                sections.append(f"## {scope_name}\n" + "\n".join(kept_lines))

        mempalace_text = self._build_mempalace_context(project_id=project_id)
        if mempalace_text:
            sections.append(f"## mempalace\n{mempalace_text}")

        if not sections:
            return ""

        combined = "# 持久记忆\n" + "\n".join(sections)
        max_chars = self.config.skill_injection_max_chars
        if max_chars and len(combined) > max_chars:
            combined = combined[:max_chars].rstrip()
        return combined

    def _build_mempalace_context(self, project_id: str | None = None) -> str:
        if not self.config.mempalace_enabled:
            return ""

        adapter = MemPalaceAdapter(self.config.mempalace_path)
        if not adapter.is_available():
            return ""

        wing = self.config.mempalace_wing or project_id
        parts: list[str] = []

        wakeup = adapter.wake_up(wing=wing)
        if wakeup:
            parts.append(wakeup)

        query = ""
        for message in reversed(self.messages):
            if message.role == "user" and message.content.strip():
                query = message.content.strip()
                break

        if query:
            for entry in adapter.search(query, wing=wing, limit=5):
                content = entry.get("content", "").strip()
                if content:
                    parts.append(content)

        unique_parts: list[str] = []
        seen = set()
        for part in parts:
            if part in seen:
                continue
            seen.add(part)
            unique_parts.append(part)

        return "\n".join(unique_parts)

    def _extract_memory_fact(self, text: str) -> tuple[str, str, str] | None:
        stripped = text.strip()
        if not stripped:
            return None
        if stripped.startswith("记住"):
            fact = stripped[2:].strip("：:，,。 ")
            if fact:
                return ("remembered_fact", fact, "user")
        if stripped.startswith("我叫") and len(stripped) > 2:
            name = stripped[2:].strip("：:，,。 ")
            if name:
                return ("user_name", name, "user")
        return None

    def _auto_extract_memory(self, user_message: str | None = None, response: str | None = None):
        if not self.config.memory_enabled or self.memory is None:
            return
        message_text = user_message
        if message_text is None:
            for message in reversed(self.messages):
                if message.role == "user" and message.content.strip():
                    message_text = message.content
                    break
        if not message_text:
            return
        extracted = self._extract_memory_fact(message_text)
        if not extracted:
            return
        key, value, category = extracted
        session_meta = self._build_session_metadata(self.config.session_store.get(self.config.session_id) if self.config.session_id and self.config.session_store else None)
        self.memory.set(
            key,
            value,
            category=category,
            scope="user",
            source="derived",
            user_id=session_meta.get("user_id"),
            project_id=session_meta.get("project_id"),
            session_id=self.config.session_id,
            tags=["auto-extracted"],
            importance=0.7,
        )

    def _handle_memory_call(self, args: dict[str, Any]) -> str:
        raw = self._call_memory_tool(args)
        try:
            parsed = json.loads(raw)
        except Exception:
            return raw

        action = args.get("action")
        if action == "set":
            return json.dumps({"success": parsed.get("ok", False)}, ensure_ascii=False)
        if action == "search":
            return json.dumps({"results": parsed}, ensure_ascii=False)
        if action == "list":
            return json.dumps({"entries": parsed}, ensure_ascii=False)
        if action == "delete":
            return json.dumps({"success": parsed.get("ok", False)}, ensure_ascii=False)
        return raw

    @property
    def memory(self):
        if not self.config.memory_enabled or not self.config.session_store:
            return None
        return self.config.session_store.memory

    @property
    def registry(self):
        return self._registry

    @property
    def messages(self):
        return self._message_manager.get_messages()

    @messages.setter
    def messages(self, value):
        self._message_manager.clear()
        converted = [Message(**msg) if isinstance(msg, dict) else msg for msg in value]
        self._message_manager.extend(converted)
        self._messages = converted.copy()

    def save_session(self) -> bool:
        original_auto_save = self.config.auto_save
        try:
            self.config.auto_save = True
            return bool(self._save_session())
        finally:
            self.config.auto_save = original_auto_save

    def list_sessions(self) -> list[dict[str, Any]]:
        if not self.config.session_store:
            return []
        return [
            {
                "session_id": session.session_id,
                "title": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in self.config.session_store.list_sessions()
        ]

    def delete_session(self, session_id: str) -> bool:
        if not self.config.session_store:
            return False
        return self.config.session_store.delete(session_id)

    def get_stats(self) -> dict[str, Any]:
        memory_entries = len(self.memory.list_all()) if self.memory is not None else 0
        return {
            "memory_enabled": bool(self.memory is not None),
            "memory_entries": memory_entries,
            "messages": self._message_manager.get_message_count(),
            "conversation_turns": self._conversation_turns,
            "registry_tools": len(self._registry) if self._registry is not None else 0,
        }

    def _apply_reflection(self, draft: str, user_message: str, *, tool_calls: int = 0):
        decision = self._reflection_policy.should_reflect(
            task_type="default",
            output_text=draft,
            tool_calls=tool_calls,
            metadata={"risk_level": "medium", "user_message": user_message},
        )

        return self._reflection_loop.run(
            draft=draft,
            decision=decision,
            revise_fn=lambda current, feedback: f"{current}\n\n[Reflection Revision]\n{feedback}",
            context={"task_type": "default", "user_message": user_message},
        )

    def _record_runtime_metrics(
        self,
        *,
        user_message: str,
        final_output: str,
        tool_calls: int,
        reflection_result: Any | None,
        elapsed: float,
        success: bool,
        memory_hits: int = 0,
        memory_misses: int = 0,
        instinct_matches: int = 0,
        worker_count: int = 0,
    ) -> dict[str, Any] | None:
        if not self.config.metrics_enabled:
            return None

        revision_count = 0
        reflection_count = 0
        if reflection_result is not None:
            revision_count = getattr(reflection_result, "revision_count", 0)
            reflection_count = 1 if getattr(reflection_result, "reflection_applied", False) else 0

        task_id = f"task-{int(time.time() * 1000)}"
        metrics = RuntimeMetrics(
            task_id=task_id,
            session_id=self.config.session_id,
            user_message=user_message,
            tool_calls=tool_calls,
            reflection_count=reflection_count,
            revision_count=revision_count,
            memory_hits=memory_hits,
            memory_misses=memory_misses,
            instinct_matches=instinct_matches,
            success=success,
            worker_count=worker_count,
            elapsed=elapsed,
        )
        self._runtime_metrics.add(metrics)
        trace_payload = {
            "task_id": task_id,
            "session_id": self.config.session_id,
            "user_message": user_message,
            "final_output": final_output,
            "tool_calls": tool_calls,
            "revision_count": revision_count,
            "reflection_count": reflection_count,
            "memory_hits": memory_hits,
            "memory_misses": memory_misses,
            "instinct_matches": instinct_matches,
            "worker_count": worker_count,
            "elapsed": elapsed,
            "success": success,
        }
        trace_id = self._trace_store.write_trace(trace_payload)
        trace_payload["trace_id"] = trace_id
        return trace_payload

    def get_runtime_metrics(self) -> dict[str, Any]:
        return self._runtime_metrics.summary()

    def run(self, user_message: str) -> str:
        """
        运行对话

        Args:
            user_message: 用户消息

        Returns:
            str: Agent 响应
        """
        # 添加用户消息
        self._message_manager.append(Message(role="user", content=user_message))
        logger.debug(f"添加用户消息: {len(user_message)} 字符")

        is_root_run = self._active_run_depth == 0
        if is_root_run:
            self._active_run_start = time.time()
            self._active_root_user_message = user_message
            self._active_run_tool_calls = 0
            self._active_run_worker_count = 0
            self._last_instinct_match_count = 0
        self._active_run_depth += 1

        # 会话开始 Hook
        if user_message:
            self._trigger_hook(
                HookEvent.SESSION_START,
                metadata={"user_message": user_message},
            )

        try:
            run_start = time.time()
            runtime_tool_calls = 0
            # 检查会话轮询限制
            if self._check_conversation_limit():
                response = (
                    f"⚠️ 会话轮询次数已超过限制（{self.config.max_conversation_turns} 次）。"
                    "为避免无限循环，任务已终止。"
                )
                self._message_manager.append(Message(role="assistant", content=response))
                logger.warning(f"会话轮询次数已超过限制: {self._conversation_turns}")
                self._trigger_hook(HookEvent.SESSION_END)
                return response

            # 检查并汇报进度（每10分钟）
            progress_report = self._check_and_report_progress()
            if progress_report:
                # 在工具调用后的递归调用中汇报进度
                # 添加进度汇报消息到消息列表
                self._message_manager.append(Message(role="assistant", content=progress_report))
                # 保存会话
                self._save_session()
                # 注意：不返回，继续正常流程，让用户在下次查询时看到进度

            # 检查上下文大小
            total_tokens = sum(len(m.content) for m in self._message_manager.get_messages()) // 4  # 粗略估计
            logger.debug(f"当前上下文大小: {total_tokens} tokens")
            if total_tokens > self.config.max_context_tokens:
                logger.info("上下文大小超过限制，触发压缩")
                self._compress_context()

            # 调用 LLM
            def api_call():
                if self._client is None:
                    self._client = self._init_client()
                # 获取增强的系统提示
                enhanced_system_prompt = self._get_enhanced_system_prompt(user_message)

                # 构建消息列表
                messages = [{"role": "system", "content": enhanced_system_prompt}]

                # 添加对话历史（跳过系统消息，避免重复）
                for m in self._message_manager.get_messages():
                    if m.role != "system":
                        messages.append(m.to_api())

                return self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    tools=self._get_tools(),
                )

            logger.debug("调用 LLM API")
            response = _retry_api_call(api_call)
            logger.debug("LLM API 调用成功")

            # 处理响应
            assistant_message = response.choices[0].message

            # 保存 assistant 消息（将 OpenAI SDK 对象转为 dict 以支持 JSON 序列化）
            tool_calls_dicts = []
            for tc in (assistant_message.tool_calls or []):
                tool_calls_dicts.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })
            msg = Message(
                role="assistant",
                content=assistant_message.content or "",
                tool_calls=tool_calls_dicts,
            )
            self._message_manager.append(msg)

            # 处理工具调用
            if assistant_message.tool_calls:
                tool_responses = []
                logger.info(f"收到 {len(assistant_message.tool_calls)} 个工具调用")

                for tool_call in assistant_message.tool_calls:
                    # 获取工具名称和参数（OpenAI SDK 返回的是对象，不是 dict）
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error(f"工具参数 JSON 解析失败: {tool_name}, 参数: {tool_call.function.arguments[:200]}, 错误: {e}")
                        tool_args = {}
                    
                    # 检测重复性工作
                    is_repetitive, warning_msg = self._detect_repetitive_work(tool_name, tool_args)
                    
                    if is_repetitive:
                        # 添加警告消息
                        self._message_manager.append(Message(role="assistant", content=warning_msg))
                        self._save_session()
                        logger.warning(f"检测到重复性工作: {tool_name}")
                    
                    # 调用工具（传入 dict 格式）
                    result = self._call_tool({
                        "id": tool_call.id,
                        "function": {
                            "name": tool_name,
                            "arguments": tool_call.function.arguments,
                        },
                    })
                    runtime_tool_calls += 1
                    self._active_run_tool_calls += 1
                    if tool_name == "spawn_agents_parallel":
                        try:
                            parallel_payload = json.loads(result)
                            self._active_run_worker_count += int(parallel_payload.get("total", 0))
                        except (json.JSONDecodeError, ValueError, TypeError):
                            pass

                    # 保存工具响应
                    tool_response = Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                        name=tool_name,
                    )
                    self._message_manager.append(tool_response)

                    tool_responses.append(result)

                # 继续对话（让 LLM 处理工具结果）
                logger.debug("继续对话处理工具结果")
                return self.run("")  # 递归调用

            # 保存会话
            self._save_session()
            self._trigger_hook(HookEvent.SESSION_END)

            final_output = assistant_message.content or ""
            reflection_result = None
            if self.config.reflection_enabled:
                try:
                    reflection_result = self._apply_reflection(
                        final_output,
                        user_message,
                        tool_calls=runtime_tool_calls,
                    )
                    final_output = reflection_result.final_output
                except Exception:
                    if self.config.reflection_fail_closed:
                        raise

            memory_hits = 1 if self._last_memory_context_hit else 0
            memory_misses = 0 if self._last_memory_context_hit else 1
            instinct_matches = self._last_instinct_match_count
            worker_count = self._active_run_worker_count

            trace_payload = self._record_runtime_metrics(
                user_message=self._active_root_user_message or user_message,
                final_output=final_output,
                tool_calls=self._active_run_tool_calls,
                reflection_result=reflection_result,
                elapsed=(time.time() - self._active_run_start) if self._active_run_start is not None else (time.time() - run_start),
                success=True,
                memory_hits=memory_hits,
                memory_misses=memory_misses,
                instinct_matches=instinct_matches,
                worker_count=worker_count,
            )
            if self.config.eval_samples_enabled and trace_payload is not None:
                self._eval_sample_store.promote_trace(
                    trace_payload,
                    labels=["phase8", "runtime"],
                    metadata={"source": "agent_run"},
                )

            logger.debug(f"对话完成，返回响应: {len(final_output)} 字符")
            return final_output
        except Exception as e:
            self._trigger_hook(
                HookEvent.ERROR,
                metadata={
                    "error": str(e),
                    "user_message": user_message,
                },
            )
            raise
        finally:
            self._active_run_depth -= 1
            if self._active_run_depth == 0:
                self._active_run_start = None
                self._active_root_user_message = None
                self._active_run_tool_calls = 0
                self._active_run_worker_count = 0
                self._last_instinct_match_count = 0

    def _get_tools(self) -> list[dict]:
        """获取可用工具列表"""
        tools = []

        # 添加内置 memory 工具
        tools.append(_MEMORY_TOOL_SCHEMA)

        # 添加注册表中的工具
        if self._registry:
            tools.extend(self._registry.get_schemas())

        return tools

    def get_messages(self) -> list[Message]:
        """获取消息历史"""
        return self._message_manager.get_messages()

    def reset(self):
        """重置对话"""
        logger.info(f"重置对话: {self.config.session_id}")
        self.messages = []
        self._conversation_turns = 0
        if self.config.session_id:
            self.config.session_store.delete(self.config.session_id)
        logger.debug("对话重置完成")
