"""
学习系统配置

功能：
- 定义学习系统配置
- 提供配置验证
- 支持配置序列化和反序列化
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import json
from pathlib import Path


@dataclass
class LearningConfig:
    """学习系统配置"""

    # 观察配置
    min_session_length: int = 10  # 最小会话长度
    enable_tool_tracking: bool = True
    enable_error_tracking: bool = True
    store_path: str = "~/.maxbot/observations"

    # 提取配置
    pattern_threshold: str = "medium"  # low, medium, high
    min_occurrence_count: int = 3  # 最小出现次数
    enable_tool_sequence: bool = True
    enable_error_solution: bool = True
    enable_user_preference: bool = True

    # 验证配置
    validation_threshold: float = 0.7  # 70% 及格线
    auto_approve: bool = False  # 是否自动批准
    min_reproducibility: float = 0.5
    min_value_score: float = 0.5
    min_safety: float = 0.8  # 安全要求较高
    min_best_practice: float = 0.5

    # 存储配置
    instincts_db_path: str = "~/.maxbot/instincts.db"
    max_instincts: int = 1000  # 最大本能数量
    instinct_retention_days: int = 90  # 本能保留天数

    # 应用配置
    enable_auto_apply: bool = True  # 是否自动应用
    auto_apply_threshold: float = 0.9  # 高置信度自动应用
    require_user_confirmation: bool = True  # 中置信度时要求确认

    # 性能配置
    learning_loop_async: bool = True  # 异步执行学习循环
    async_worker_count: int = 1  # 异步 worker 数量
    async_retry_limit: int = 2  # 异步任务失败重试次数
    async_retry_backoff: float = 0.5  # 重试退避时间（秒）
    max_pattern_extract_time: float = 10.0  # 最大模式提取时间（秒）
    max_validation_time: float = 5.0  # 最大验证时间（秒）

    # 日志配置
    enable_logging: bool = True
    log_path: str = "~/.maxbot/learning.log"
    log_level: str = "INFO"

    def validate(self) -> List[str]:
        """验证配置

        Returns:
            错误消息列表（空表示有效）
        """
        errors = []

        # 验证观察配置
        if self.min_session_length < 1:
            errors.append("min_session_length must be >= 1")

        # 验证提取配置
        if self.pattern_threshold not in ["low", "medium", "high"]:
            errors.append("pattern_threshold must be one of: low, medium, high")

        if self.min_occurrence_count < 1:
            errors.append("min_occurrence_count must be >= 1")

        # 验证验证配置
        if not 0 <= self.validation_threshold <= 1:
            errors.append("validation_threshold must be between 0 and 1")

        if not 0 <= self.min_reproducibility <= 1:
            errors.append("min_reproducibility must be between 0 and 1")

        if not 0 <= self.min_value_score <= 1:
            errors.append("min_value_score must be between 0 and 1")

        if not 0 <= self.min_safety <= 1:
            errors.append("min_safety must be between 0 and 1")

        if not 0 <= self.min_best_practice <= 1:
            errors.append("min_best_practice must be between 0 and 1")

        # 验证存储配置
        if self.max_instincts < 10:
            errors.append("max_instincts must be >= 10")

        if self.instinct_retention_days < 1:
            errors.append("instinct_retention_days must be >= 1")

        # 验证应用配置
        if not 0 <= self.auto_apply_threshold <= 1:
            errors.append("auto_apply_threshold must be between 0 and 1")

        # 验证性能配置
        if self.async_worker_count < 1:
            errors.append("async_worker_count must be >= 1")

        if self.async_retry_limit < 0:
            errors.append("async_retry_limit must be >= 0")

        if self.async_retry_backoff < 0:
            errors.append("async_retry_backoff must be >= 0")

        if self.max_pattern_extract_time < 1:
            errors.append("max_pattern_extract_time must be >= 1")

        if self.max_validation_time < 1:
            errors.append("max_validation_time must be >= 1")

        # 验证日志配置
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            errors.append("log_level must be one of: DEBUG, INFO, WARNING, ERROR")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "min_session_length": self.min_session_length,
            "enable_tool_tracking": self.enable_tool_tracking,
            "enable_error_tracking": self.enable_error_tracking,
            "store_path": self.store_path,
            "pattern_threshold": self.pattern_threshold,
            "min_occurrence_count": self.min_occurrence_count,
            "enable_tool_sequence": self.enable_tool_sequence,
            "enable_error_solution": self.enable_error_solution,
            "enable_user_preference": self.enable_user_preference,
            "validation_threshold": self.validation_threshold,
            "auto_approve": self.auto_approve,
            "min_reproducibility": self.min_reproducibility,
            "min_value_score": self.min_value_score,
            "min_safety": self.min_safety,
            "min_best_practice": self.min_best_practice,
            "instincts_db_path": self.instincts_db_path,
            "max_instincts": self.max_instincts,
            "instinct_retention_days": self.instinct_retention_days,
            "enable_auto_apply": self.enable_auto_apply,
            "auto_apply_threshold": self.auto_apply_threshold,
            "require_user_confirmation": self.require_user_confirmation,
            "learning_loop_async": self.learning_loop_async,
            "async_worker_count": self.async_worker_count,
            "async_retry_limit": self.async_retry_limit,
            "async_retry_backoff": self.async_retry_backoff,
            "max_pattern_extract_time": self.max_pattern_extract_time,
            "max_validation_time": self.max_validation_time,
            "enable_logging": self.enable_logging,
            "log_path": self.log_path,
            "log_level": self.log_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningConfig":
        """从字典创建配置"""
        return cls(**data)

    def save_to_file(self, path: str = "~/.maxbot/learning_config.json"):
        """保存配置到文件"""
        filepath = Path(path).expanduser()
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_file(cls, path: str = "~/.maxbot/learning_config.json") -> "LearningConfig":
        """从文件加载配置"""
        filepath = Path(path).expanduser()

        if not filepath.exists():
            return cls()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def __str__(self) -> str:
        """返回配置的字符串表示"""
        return f"""LearningConfig(
    min_session_length={self.min_session_length}
    enable_tool_tracking={self.enable_tool_tracking}
    enable_error_tracking={self.enable_error_tracking}
    pattern_threshold={self.pattern_threshold}
    min_occurrence_count={self.min_occurrence_count}
    validation_threshold={self.validation_threshold}
    auto_approve={self.auto_approve}
    max_instincts={self.max_instincts}
    enable_auto_apply={self.enable_auto_apply}
    auto_apply_threshold={self.auto_apply_threshold}
    require_user_confirmation={self.require_user_confirmation}
    learning_loop_async={self.learning_loop_async}
    async_worker_count={self.async_worker_count}
    async_retry_limit={self.async_retry_limit}
    async_retry_backoff={self.async_retry_backoff}
    log_level={self.log_level}
)"""


DEFAULT_CONFIG = LearningConfig()

CONSERVATIVE_CONFIG = LearningConfig(
    validation_threshold=0.8,
    auto_approve=False,
    min_safety=0.9,
    enable_auto_apply=False,
    auto_apply_threshold=0.95,
    require_user_confirmation=True,
)

AGGRESSIVE_CONFIG = LearningConfig(
    validation_threshold=0.5,
    auto_approve=True,
    min_safety=0.6,
    enable_auto_apply=True,
    auto_apply_threshold=0.7,
    require_user_confirmation=False,
)


def get_config(profile: str = "default") -> LearningConfig:
    """获取配置"""
    if profile == "conservative":
        return CONSERVATIVE_CONFIG
    if profile == "aggressive":
        return AGGRESSIVE_CONFIG
    return DEFAULT_CONFIG
