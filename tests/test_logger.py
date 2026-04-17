"""
测试日志系统
"""

import logging
import sys
from pathlib import Path

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.utils.logger import (
    MaxBotLogger,
    LoggerConfig,
    get_logger,
    get_agent_logger,
    get_tool_logger,
)


def test_default_logger():
    """测试默认日志器"""
    print("=" * 70)
    print("测试 1: 默认日志器")
    print("=" * 70)

    logger = get_logger()
    logger.info("这是一条 INFO 日志")
    logger.warning("这是一条 WARNING 日志")
    logger.error("这是一条 ERROR 日志")

    print("✅ 默认日志器测试通过\n")


def test_custom_logger():
    """测试自定义日志器"""
    print("=" * 70)
    print("测试 2: 自定义日志器")
    print("=" * 70)

    config = LoggerConfig(
        name="custom_logger",
        level="DEBUG",
        console=True,
    )

    logger = MaxBotLogger.get_logger(config=config)
    logger.debug("这是一条 DEBUG 日志")
    logger.info("这是一条 INFO 日志")
    logger.warning("这是一条 WARNING 日志")
    logger.error("这是一条 ERROR 日志")

    print("✅ 自定义日志器测试通过\n")


def test_file_logger():
    """测试文件日志器"""
    print("=" * 70)
    print("测试 3: 文件日志器")
    print("=" * 70)

    log_file = "/tmp/test_maxbot.log"

    config = LoggerConfig(
        name="file_logger",
        level="DEBUG",
        log_file=log_file,
        console=True,
    )

    logger = MaxBotLogger.get_logger(config=config)
    logger.info("这条日志会写入文件")
    logger.warning("这条警告也会写入文件")
    logger.error("这条错误也会写入文件")

    # 读取日志文件
    log_path = Path(log_file)
    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        print(f"\n📄 日志文件内容:")
        print("-" * 70)
        print(content)
        print("-" * 70)
        print("✅ 文件日志器测试通过\n")
    else:
        print("❌ 日志文件未创建\n")


def test_singleton():
    """测试单例模式"""
    print("=" * 70)
    print("测试 4: 单例模式")
    print("=" * 70)

    logger1 = get_logger("test_singleton")
    logger2 = get_logger("test_singleton")

    if logger1 is logger2:
        print("✅ 单例模式正常工作\n")
    else:
        print("❌ 单例模式失败\n")


def test_predefined_loggers():
    """测试预定义的日志器"""
    print("=" * 70)
    print("测试 5: 预定义的日志器")
    print("=" * 70)

    agent_logger = get_agent_logger()
    tool_logger = get_tool_logger()

    agent_logger.info("Agent 日志器测试")
    tool_logger.info("工具日志器测试")

    print("✅ 预定义日志器测试通过\n")


def test_exception_logging():
    """测试异常日志"""
    print("=" * 70)
    print("测试 6: 异常日志")
    print("=" * 70)

    logger = get_logger("exception_test")

    try:
        1 / 0
    except Exception as e:
        logger.exception("发生异常")
        print("✅ 异常日志测试通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MaxBot 日志系统测试")
    print("=" * 70 + "\n")

    test_default_logger()
    test_custom_logger()
    test_file_logger()
    test_singleton()
    test_predefined_loggers()
    test_exception_logging()

    print("=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)
