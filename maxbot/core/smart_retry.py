"""
智能重试机制

功能：
- 基于错误类型的重试策略
- 指数退避重试
- 特定错误的特殊处理
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from enum import Enum

from maxbot.utils.logger import get_logger

logger = get_logger("smart_retry")


class ErrorType(Enum):
    """错误类型"""
    NETWORK = "network"  # 网络错误
    TIMEOUT = "timeout"  # 超时
    RATE_LIMIT = "rate_limit"  # 速率限制
    SERVER_ERROR = "server_error"  # 服务器错误 (5xx)
    CLIENT_ERROR = "client_error"  # 客户端错误 (4xx)
    PARSE_ERROR = "parse_error"  # 解析错误
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class RetryStrategy:
    """重试策略"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    retryable_errors: List[ErrorType] = field(default_factory=lambda: [
        ErrorType.NETWORK,
        ErrorType.TIMEOUT,
        ErrorType.RATE_LIMIT,
        ErrorType.SERVER_ERROR,
    ])
    custom_handlers: Dict[ErrorType, Callable] = field(default_factory=dict)


class SmartRetry:
    """
    智能重试器
    
    功能：
    - 自动识别错误类型
    - 应用重试策略
    - 指数退避
    - 自定义错误处理
    """

    def __init__(self, strategy: Optional[RetryStrategy] = None):
        """
        初始化智能重试器
        
        Args:
            strategy: 重试策略
        """
        self.strategy = strategy or RetryStrategy()
        self._error_patterns = self._init_error_patterns()

    def _init_error_patterns(self) -> Dict[ErrorType, List[str]]:
        """初始化错误模式"""
        return {
            ErrorType.NETWORK: [
                r"connection.*refused",
                r"connection.*reset",
                r"network.*unreachable",
                r"no.*route.*host",
            ],
            ErrorType.TIMEOUT: [
                r"timeout",
                r"timed out",
            ],
            ErrorType.RATE_LIMIT: [
                r"429",
                r"rate.*limit",
                r"too.*many.*requests",
                r"quota.*exceeded",
            ],
            ErrorType.SERVER_ERROR: [
                r"50[0-9]",
                r"internal.*server.*error",
                r"service.*unavailable",
            ],
            ErrorType.CLIENT_ERROR: [
                r"40[0-9]",
                r"bad.*request",
                r"unauthorized",
                r"forbidden",
                r"not.*found",
            ],
            ErrorType.PARSE_ERROR: [
                r"json.*decode",
                r"parse.*error",
                r"invalid.*format",
            ],
        }

    def classify_error(self, error: Exception | str) -> ErrorType:
        """
        分类错误类型
        
        Args:
            error: 错误对象或错误消息
            
        Returns:
            错误类型
        """
        error_msg = str(error).lower()
        
        # 检查每种错误类型
        for error_type, patterns in self._error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_msg):
                    return error_type
        
        return ErrorType.UNKNOWN

    def should_retry(self, error: Exception | str, attempt: int) -> bool:
        """
        判断是否应该重试
        
        Args:
            error: 错误
            attempt: 当前尝试次数
            
        Returns:
            是否应该重试
        """
        # 超过最大尝试次数
        if attempt >= self.strategy.max_attempts:
            return False
        
        # 分类错误
        error_type = self.classify_error(error)
        
        # 检查是否是可重试的错误类型
        return error_type in self.strategy.retryable_errors

    def calculate_delay(self, attempt: int, error: Exception | str) -> float:
        """
        计算重试延迟
        
        Args:
            attempt: 当前尝试次数
            error: 错误
            
        Returns:
            延迟时间（秒）
        """
        error_type = self.classify_error(error)
        
        # 速率限制使用更长的延迟
        if error_type == ErrorType.RATE_LIMIT:
            # 尝试从错误消息中提取重试时间
            error_msg = str(error)
            retry_match = re.search(r"retry.*after.*(\d+)", error_msg, re.IGNORECASE)
            if retry_match:
                return float(retry_match.group(1))
            
            # 默认使用较长的延迟
            base_delay = self.strategy.base_delay * 5
        else:
            base_delay = self.strategy.base_delay
        
        # 指数退避
        delay = base_delay * (self.strategy.backoff_multiplier ** attempt)
        
        # 限制最大延迟
        return min(delay, self.strategy.max_delay)

    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        执行函数并智能重试
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次执行的异常
        """
        last_error = None
        
        for attempt in range(self.strategy.max_attempts):
            try:
                return func(*args, **kwargs)
            
            except Exception as e:
                last_error = e
                error_type = self.classify_error(e)
                
                logger.warning(
                    f"执行失败 (尝试 {attempt + 1}/{self.strategy.max_attempts}): "
                    f"{error_type.value} - {str(e)[:200]}"
                )
                
                # 检查自定义处理器
                if error_type in self.strategy.custom_handlers:
                    try:
                        handler_result = self.strategy.custom_handlers[error_type](
                            e, attempt, *args, **kwargs
                        )
                        if handler_result is not None:
                            return handler_result
                    except Exception as handler_error:
                        logger.error(f"自定义错误处理器失败: {handler_error}")
                
                # 判断是否应该重试
                if not self.should_retry(e, attempt + 1):
                    break
                
                # 计算延迟
                delay = self.calculate_delay(attempt, e)
                
                logger.info(f"等待 {delay:.1f} 秒后重试...")
                time.sleep(delay)
        
        # 所有重试都失败
        logger.error(f"所有重试失败，放弃执行")
        raise last_error

    def add_custom_handler(
        self,
        error_type: ErrorType,
        handler: Callable[[Exception, int], Any],
    ):
        """
        添加自定义错误处理器
        
        Args:
            error_type: 错误类型
            handler: 处理器函数，接收 (error, attempt, *args, **kwargs)
        """
        self.strategy.custom_handlers[error_type] = handler
        logger.debug(f"添加自定义错误处理器: {error_type.value}")


# 导入 re
import re


# 默认重试器实例
default_retry = SmartRetry()
