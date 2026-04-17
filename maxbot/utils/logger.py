"""
统一日志系统

提供:
- 标准化的日志格式
- 支持多种日志级别
- 支持文件和控制台输出
- 支持日志轮转
- 线程安全
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LoggerConfig:
    """日志配置"""
    name: str = "maxbot"
    level: str = "INFO"
    log_file: str | None = None
    console: bool = True
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    max_file_size: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5


class MaxBotLogger:
    """
    MaxBot 统一日志器

    用法:
        # 使用默认配置
        logger = MaxBotLogger.get_logger()
        logger.info("Agent 初始化")
        logger.error("工具调用失败", exc_info=True)

        # 自定义配置
        config = LoggerConfig(
            level="DEBUG",
            log_file="maxbot.log",
            console=True
        )
        logger = MaxBotLogger.get_logger(config=config)
    """

    _instances: dict[str, MaxBotLogger] = {}
    _loggers: dict[str, logging.Logger] = {}

    def __init__(self, config: LoggerConfig):
        """初始化日志器"""
        self.config = config
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志器"""
        logger = logging.getLogger(self.config.name)
        logger.setLevel(getattr(logging, self.config.level))

        # 清除现有的处理器
        logger.handlers.clear()

        # 创建格式化器
        formatter = logging.Formatter(
            fmt=self.config.format_string,
            datefmt=self.config.date_format,
        )

        # 添加控制台处理器
        if self.config.console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.config.level))
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # 添加文件处理器
        if self.config.log_file:
            log_path = Path(self.config.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用轮转文件处理器
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, self.config.level))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    @classmethod
    def get_logger(
        cls,
        name: str | None = None,
        config: LoggerConfig | None = None,
    ) -> logging.Logger:
        """
        获取日志器实例（单例模式）

        Args:
            name: 日志器名称（None = 使用默认名称）
            config: 日志配置（None = 使用默认配置）

        Returns:
            logging.Logger: 日志器实例
        """
        if config is None:
            config = LoggerConfig(name=name or "maxbot")
        elif name is not None:
            config.name = name

        # 检查是否已存在
        if config.name in cls._loggers:
            return cls._loggers[config.name]

        # 创建新实例
        instance = cls(config)
        cls._instances[config.name] = instance
        cls._loggers[config.name] = instance._logger

        return instance._logger

    @classmethod
    def reload_config(cls, name: str, config: LoggerConfig) -> None:
        """
        重新加载配置

        Args:
            name: 日志器名称
            config: 新的配置
        """
        if name in cls._instances:
            cls._instances[name].config = config
            cls._instances[name]._logger = cls._instances[name]._setup_logger()

    @classmethod
    def shutdown(cls) -> None:
        """关闭所有日志器"""
        for logger in cls._loggers.values():
            for handler in logger.handlers:
                handler.close()
        cls._loggers.clear()
        cls._instances.clear()

    # 便捷方法
    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """DEBUG 级别日志"""
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """INFO 级别日志"""
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """WARNING 级别日志"""
        self._logger.warning(msg, *args, **kwargs)

    def warn(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """WARNING 级别日志（别名）"""
        self.warning(msg, *args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """ERROR 级别日志"""
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """CRITICAL 级别日志"""
        self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """ERROR 级别日志（包含异常信息）"""
        kwargs["exc_info"] = True
        self._logger.error(msg, *args, **kwargs)


# 便捷函数
def get_logger(
    name: str = "maxbot",
    level: str | None = None,
    log_file: str | None = None,
    console: bool | None = None,
) -> logging.Logger:
    """
    获取日志器（便捷函数）

    Args:
        name: 日志器名称
        level: 日志级别（None = 使用配置）
        log_file: 日志文件路径（None = 使用配置）
        console: 是否输出到控制台（None = 使用配置）

    Returns:
        logging.Logger: 日志器实例

    Example:
        logger = get_logger("agent", level="DEBUG")
        logger.info("Agent 初始化")
    """
    config = LoggerConfig(
        name=name,
        level=level or "INFO",
        log_file=log_file,
        console=console if console is not None else True,
    )

    return MaxBotLogger.get_logger(config=config)


# 预定义的日志器
def get_agent_logger() -> logging.Logger:
    """获取 Agent 日志器"""
    return get_logger("maxbot.agent")


def get_tool_logger() -> logging.Logger:
    """获取工具日志器"""
    return get_logger("maxbot.tools")


def get_skill_logger() -> logging.Logger:
    """获取技能日志器"""
    return get_logger("maxbot.skills")


def get_config_logger() -> logging.Logger:
    """获取配置日志器"""
    return get_logger("maxbot.config")


def get_gateway_logger() -> logging.Logger:
    """获取网关日志器"""
    return get_logger("maxbot.gateway")
