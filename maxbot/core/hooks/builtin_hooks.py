"""
内置钩子实现

参考 ECC hooks/hooks.json 的内置钩子
"""
import os
import re
import logging
from typing import Dict, Any
from .hook_events import HookEvent, HookContext
from .hook_manager import HookAbortError

logger = logging.getLogger(__name__)


def _resolve_profile(context: HookContext) -> str:
    return context.profile or os.getenv("MAXBOT_HOOK_PROFILE", "standard")


# ========== Pre-Tool Hooks ==========

def pre_command_safety_check(context: HookContext):
    """
    危险命令检查（参考 ECC pre:bash:dispatcher）
    
    检查 shell 命令是否包含危险操作：
    - rm -rf /
    - dd if=/dev/zero
    - :(){ :|:& };:
    - mkfs.ext4
    - 格式化命令
    """
    if context.tool_name != "shell":
        return
    
    command = context.tool_args.get("command", "")
    
    # 危险命令模式
    dangerous_patterns = [
        r"rm\s+-rf\s+/",          # rm -rf /
        r"dd\s+if=/dev/zero",    # dd if=/dev/zero
        r":\(\)\s*\{\s*:\|:&\s*\};:",  # fork bomb
        r"mkfs\.",                 # mkfs 格式化
        r"format\s+[a-z]:",        # Windows format
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            raise ValueError(f"危险命令被拦截: {command[:100]}")
    
    logger.debug(f"Command safety check passed: {command[:50]}...")


def pre_documentation_warning(context: HookContext):
    """
    文档文件警告（参考 ECC pre:write:doc-file-warning）
    
    警告正在编辑非标准文档文件
    """
    if context.tool_name not in ["write_file", "edit_file", "code_edit"]:
        return
    
    file_path = context.tool_args.get("path", "")
    
    # 栓准文档路径
    doc_paths = [
        "README.md",
        "CHANGELOG.md",
        "docs/",
        "docs/zh-CN/",
        "docs/en/",
        "AGENTS.md",
        "PLAN.md",
    ]
    
    if any(dp in file_path for dp in doc_paths):
        logger.warning(f"正在编辑文档文件: {file_path}")


def pre_config_protection(context: HookContext):
    """
    配置文件保护（参考 ECC pre:config-protection）
    
    阻止编辑 linter/formatter 配置文件
    """
    if context.tool_name not in ["write_file", "edit_file", "code_edit"]:
        return
    
    file_path = context.tool_args.get("path", "")
    
    # 受保护的配置文件
    protected_configs = [
        ".eslintrc",
        ".prettierrc",
        "pylint.rc",
        ".pylintrc",
        "ruff.toml",
        ".ruff.toml",
    ]
    
    for config in protected_configs:
        if file_path.endswith(config):
            # 在 strict profile 下拦截
            if _resolve_profile(context) == "strict":
                raise HookAbortError(f"禁止编辑配置文件: {file_path}（请修复代码而非放宽配置）")
            else:
                logger.warning(f"建议修复代码而非编辑配置文件: {file_path}")


def pre_compact_suggest(context: HookContext):
    """
    建议压缩（参考 ECC pre:edit-write:suggest-compact）
    
    在逻辑间隔建议手动压缩上下文
    """
    if context.event == HookEvent.PRE_COMPACT:
        before_messages = context.metadata.get("before_message_count", 0)
        before_tokens = context.metadata.get("before_tokens", 0)
        keep_messages = context.metadata.get("keep_messages")
        logger.info(
            "Preparing context compaction: messages=%s, tokens=%s, keep=%s",
            before_messages,
            before_tokens,
            keep_messages,
        )
        return

    if context.tool_name not in ["edit_file", "code_edit"]:
        return

    logger.debug("Compact suggestion hook checked for tool: %s", context.tool_name)


# ========== Post-Tool Hooks ==========

def post_compact_summary(context: HookContext):
    """记录上下文压缩后的摘要信息。"""
    after_messages = context.metadata.get("after_message_count", 0)
    after_tokens = context.metadata.get("after_tokens", 0)
    compressed_messages = context.metadata.get("compressed_messages", 0)
    compressed_tokens = context.metadata.get("compressed_tokens", 0)
    logger.info(
        "Context compacted: after_messages=%s, after_tokens=%s, compressed_messages=%s, compressed_tokens=%s",
        after_messages,
        after_tokens,
        compressed_messages,
        compressed_tokens,
    )


# ========== Post-Tool Hooks ==========

def post_tool_observation(context: HookContext):
    """
    工具调用观察（参考 ECC continuous-learning-v2 observe.sh）
    
    记录工具调用模式，用于持续学习
    """
    # 记录工具调用
    logger.info(f"Observed tool use: {context.tool_name}")
    
    # TODO: 实现观察记录到数据库
    # TODO: 实现模式提取


# ========== Session Hooks ==========

def session_start_capture(context: HookContext):
    """
    会话开始捕获（参考 ECC SessionStart）
    
    记录会话元数据：时间戳、会话ID、初始上下文
    """
    session_id = context.session_id or "unknown"
    logger.info(f"Session started: {session_id}")
    
    # TODO: 实现会话记录到数据库
    # TODO: 创建会话租约


def session_end_summary(context: HookContext):
    """
    会话结束摘要（参考 ECC SessionEnd）
    
    生成会话摘要并保存到知识库
    """
    session_id = context.session_id or "unknown"
    logger.info(f"Session ended: {session_id}")
    
    # TODO: 实现会话摘要生成
    # TODO: 移除会话租约


# ========== Error Hooks ==========

def error_capture(context: HookContext):
    """
    错误捕获
    
    记录错误信息，用于调试和分析
    """
    error = context.metadata.get("error")
    logger.error(f"Error captured: {error}")
    
    # TODO: 实现错误记录到数据库
    # TODO: 错误分类和分析


# ========== Export hooks for registration ==========

BUILTIN_HOOKS = {
    HookEvent.PRE_TOOL_USE: [
        pre_command_safety_check,
        pre_documentation_warning,
        pre_config_protection,
        pre_compact_suggest,
    ],
    HookEvent.POST_TOOL_USE: [
        post_tool_observation,
    ],
    HookEvent.PRE_COMPACT: [
        pre_compact_suggest,
    ],
    HookEvent.POST_COMPACT: [
        post_compact_summary,
    ],
    HookEvent.SESSION_START: [
        session_start_capture,
    ],
    HookEvent.SESSION_END: [
        session_end_summary,
    ],
    HookEvent.ERROR: [
        error_capture,
    ],
}
