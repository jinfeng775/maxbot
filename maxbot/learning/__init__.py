"""
持续学习系统 - 模块初始化

学习系统的核心组件：
- Observer: 观察用户交互
- PatternExtractor: 提取模式
- PatternValidator: 验证模式
- InstinctStore: 存储本能
- InstinctApplier: 应用本能
- LearningLoop: 学习循环协调
"""

from maxbot.learning.observer import Observer, Observation, ToolCall, ToolResult
from maxbot.learning.config import LearningConfig, get_config
from maxbot.learning.pattern_extractor import PatternExtractor, Pattern
from maxbot.learning.pattern_validator import PatternValidator, ValidationScore, ValidationResult
from maxbot.learning.instinct_store import InstinctStore, Instinct
from maxbot.learning.instinct_applier import InstinctApplier, MatchResult, ApplicationResult
from maxbot.learning.learning_loop import LearningLoop, LearningStats

__all__ = [
    "Observer",
    "Observation",
    "ToolCall",
    "ToolResult",
    "LearningConfig",
    "get_config",
    "PatternExtractor",
    "Pattern",
    "PatternValidator",
    "ValidationScore",
    "ValidationResult",
    "InstinctStore",
    "Instinct",
    "InstinctApplier",
    "MatchResult",
    "ApplicationResult",
    "LearningLoop",
    "LearningStats",
]
