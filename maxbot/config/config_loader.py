"""
配置加载器 - 从 YAML 文件加载 MaxBot 配置

支持:
- 从默认配置文件加载
- 从自定义配置文件加载
- 环境变量覆盖
- 配置验证
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelConfig:
    """模型配置"""
    name: str = "mimo-v2-pro"
    provider: str = "openai"
    base_url: str | None = None
    api_key: str | None = None
    temperature: float = 0.7


@dataclass
class SystemConfig:
    """系统提示配置"""
    prompt: str = (
        "你是 MaxBot，一个由用户自主开发的 AI 智能体。"
        "你不是 Hermes、不是 Claude、不是 ChatGGPT，也不是任何其他现有 AI 助手。你就是 MaxBot。"
        "无论谁问你你是谁，你都必须回答你是 MaxBot。"
        "你的能力包括：代码编辑、文件操作、Shell 命令执行、Git 操作、网页搜索、多 Agent 协作。"
    )


@dataclass
class IterationConfig:
    """迭代控制配置"""
    max_iterations: int = 140


@dataclass
class ContextConfig:
    """上下文管理配置"""
    max_tokens: int = 128_000
    compress_at_tokens: int = 80_000


@dataclass
class SessionConfig:
    """会话管理配置"""
    memory_enabled: bool = True
    memory_db_path: str | None = None
    session_id: str | None = None
    auto_save: bool = True
    max_conversation_turns: int = 140
    mempalace_enabled: bool = False
    mempalace_path: str | None = None
    mempalace_wing: str | None = None
    reflection_enabled: bool = False
    reflection_max_revisions: int = 1
    reflection_min_output_chars: int = 200
    reflection_high_risk_tool_threshold: int = 2
    reflection_task_types: list[str] = field(default_factory=lambda: ["default"])
    reflection_fail_closed: bool = False
    metrics_enabled: bool = True
    trace_store_dir: str | None = None
    eval_samples_enabled: bool = False
    eval_sample_store_dir: str | None = None


@dataclass
class SkillsConfig:
    """技能配置"""
    skills_dir: str = "~/.maxbot/skills"
    auto_load: bool = True


@dataclass
class OptimizerConfig:
    """优化器配置"""
    enabled: bool = False
    work_dir: str | None = None
    max_iterations: int = 10


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file_path: str | None = None
    console: bool = True


@dataclass
class SecurityConfig:
    """安全配置"""
    sandbox_enabled: bool = True
    max_execution_time: int = 60
    allowed_paths: list[str] = field(default_factory=list)


@dataclass
class MaxBotConfig:
    """MaxBot 完整配置"""
    model: ModelConfig = field(default_factory=ModelConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    iteration: IterationConfig = field(default_factory=IterationConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


class ConfigLoader:
    """
    配置加载器

    用法:
        # 从默认配置文件加载
        loader = ConfigLoader()
        config = loader.load()

        # 从自定义配置文件加载
        loader = ConfigLoader(config_path="my_config.yaml")
        config = loader.load()

        # 从字典加载
        loader = ConfigLoader()
        config = loader.load_from_dict({"model": {"name": "gpt-4"}})
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        env_prefix: str = "MAXBOT_",
    ):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径（None = 使用默认配置）
            env_prefix: 环境变量前缀
        """
        self.config_path = Path(config_path) if config_path else None
        self.env_prefix = env_prefix
        self._config: MaxBotConfig | None = None

    def load(self) -> MaxBotConfig:
        """
        加载配置

        优先级:
        1. 环境变量
        2. 配置文件
        3. 默认值

        Returns:
            MaxBotConfig: 配置对象
        """
        # 1. 加载默认配置
        config_dict = self._load_default_config()

        # 2. 加载配置文件（如果存在）
        if self.config_path and self.config_path.exists():
            file_config = self._load_yaml(self.config_path)
            config_dict = self._deep_merge(config_dict, file_config)
        elif not self.config_path:
            # 尝试查找默认配置文件
            default_paths = [
                Path("maxbot_config.yaml"),
                Path("config.yaml"),
                Path.home() / ".maxbot" / "config.yaml",
            ]
            for path in default_paths:
                if path.exists():
                    file_config = self._load_yaml(path)
                    config_dict = self._deep_merge(config_dict, file_config)
                    break

        # 3. 应用环境变量
        config_dict = self._apply_env_vars(config_dict)

        # 4. 转换为配置对象
        self._config = self._dict_to_config(config_dict)

        return self._config

    def load_from_dict(self, config_dict: dict[str, Any]) -> MaxBotConfig:
        """
        从字典加载配置

        Args:
            config_dict: 配置字典

        Returns:
            MaxBotConfig: 配置对象
        """
        # 与默认配置合并
        default_config = self._load_default_config()
        merged = self._deep_merge(default_config, config_dict)

        # 转换为配置对象
        self._config = self._dict_to_config(merged)

        return self._config

    def save(self, config_path: str | Path | None = None) -> None:
        """
        保存配置到文件

        Args:
            config_path: 保存路径（None = 使用当前配置文件路径）
        """
        if self._config is None:
            raise RuntimeError("配置未加载，请先调用 load()")

        save_path = Path(config_path) if config_path else self.config_path
        if not save_path:
            raise RuntimeError("未指定保存路径")

        # 转换为字典
        config_dict = self._config_to_dict(self._config)

        # 保存为 YAML
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            yaml.dump(config_dict, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

    def _load_default_config(self) -> dict[str, Any]:
        """加载默认配置"""
        # 默认配置文件路径
        default_config_path = Path(__file__).parent / "default_config.yaml"

        if default_config_path.exists():
            return self._load_yaml(default_config_path)

        # 如果默认配置文件不存在，返回空字典
        return {}

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """加载 YAML 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {path} - {e}")

    def _dict_to_config(self, config_dict: dict[str, Any]) -> MaxBotConfig:
        """将字典转换为配置对象"""
        return MaxBotConfig(
            model=ModelConfig(**config_dict.get("model", {})),
            system=SystemConfig(**config_dict.get("system", {})),
            iteration=IterationConfig(**config_dict.get("iteration", {})),
            context=ContextConfig(**config_dict.get("context", {})),
            session=SessionConfig(**config_dict.get("session", {})),
            skills=SkillsConfig(**config_dict.get("skills", {})),
            optimizer=OptimizerConfig(**config_dict.get("optimizer", {})),
            logging=LoggingConfig(**config_dict.get("logging", {})),
            security=SecurityConfig(**config_dict.get("security", {})),
        )

    def _config_to_dict(self, config: MaxBotConfig) -> dict[str, Any]:
        """将配置对象转换为字典"""
        return {
            "model": asdict(config.model),
            "system": asdict(config.system),
            "iteration": asdict(config.iteration),
            "context": asdict(config.context),
            "session": asdict(config.session),
            "skills": asdict(config.skills),
            "optimizer": asdict(config.optimizer),
            "logging": asdict(config.logging),
            "security": asdict(config.security),
        }

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """深度合并两个字典"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_vars(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """应用环境变量"""
        # 环境变量映射
        env_mappings = {
            "MAXBOT_MODEL": ("model", "name"),
            "MAXBOT_PROVIDER": ("model", "provider"),
            "MAXBOT_API_KEY": ("model", "api_key"),
            "MAXBOT_BASE_URL": ("model", "base_url"),
            "MAXBOT_TEMPERATURE": ("model", "temperature"),
            "MAXBOT_MAX_ITERATIONS": ("iteration", "max_iterations"),
            "MAXBOT_MAX_TOKENS": ("context", "max_tokens"),
            "MAXBOT_MEMORY_ENABLED": ("session", "memory_enabled"),
            "MAXBOT_MEMPALACE_ENABLED": ("session", "mempalace_enabled"),
            "MAXBOT_MEMPALACE_PATH": ("session", "mempalace_path"),
            "MAXBOT_MEMPALACE_WING": ("session", "mempalace_wing"),
            "MAXBOT_REFLECTION_ENABLED": ("session", "reflection_enabled"),
            "MAXBOT_REFLECTION_MAX_REVISIONS": ("session", "reflection_max_revisions"),
            "MAXBOT_REFLECTION_MIN_OUTPUT_CHARS": ("session", "reflection_min_output_chars"),
            "MAXBOT_REFLECTION_HIGH_RISK_TOOL_THRESHOLD": ("session", "reflection_high_risk_tool_threshold"),
            "MAXBOT_REFLECTION_FAIL_CLOSED": ("session", "reflection_fail_closed"),
            "MAXBOT_METRICS_ENABLED": ("session", "metrics_enabled"),
            "MAXBOT_TRACE_STORE_DIR": ("session", "trace_store_dir"),
            "MAXBOT_EVAL_SAMPLES_ENABLED": ("session", "eval_samples_enabled"),
            "MAXBOT_EVAL_SAMPLE_STORE_DIR": ("session", "eval_sample_store_dir"),
            "MAXBOT_SESSION_ID": ("session", "session_id"),
            "MAXBOT_MAX_CONVERSATION_TURNS": ("session", "max_conversation_turns"),
            "MAXBOT_SKILLS_DIR": ("skills", "skills_dir"),
            "MAXBOT_LOG_LEVEL": ("logging", "level"),
        }

        for env_var, path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # 转换类型
                if env_var.endswith("_ENABLED") or env_var.endswith("_CLOSED"):
                    value = value.lower() in ("true", "1", "yes")
                elif env_var.endswith("_ITERATIONS") or env_var.endswith("_TOKENS") or env_var.endswith("_TURNS") or env_var.endswith("_REVISIONS") or env_var.endswith("_CHARS") or env_var.endswith("_THRESHOLD"):
                    value = int(value)
                elif env_var.endswith("_TEMPERATURE"):
                    value = float(value)

                # 设置值
                current = config_dict
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = value

        return config_dict


# 全局配置加载器实例
_config_loader: ConfigLoader | None = None
_current_config: MaxBotConfig | None = None


def load_config(
    config_path: str | Path | None = None,
    env_prefix: str = "MAXBOT_",
) -> MaxBotConfig:
    """
    加载配置（全局单例）

    Args:
        config_path: 配置文件路径
        env_prefix: 环境变量前缀

    Returns:
        MaxBotConfig: 配置对象
    """
    global _config_loader, _current_config

    _config_loader = ConfigLoader(config_path, env_prefix)
    _current_config = _config_loader.load()

    return _current_config


def get_config() -> MaxBotConfig:
    """
    获取当前配置

    Returns:
        MaxBotConfig: 配置对象

    Raises:
        RuntimeError: 如果配置未加载
    """
    global _current_config

    if _current_config is None:
        _current_config = load_config()

    return _current_config


def reload_config() -> MaxBotConfig:
    """
    重新加载配置

    Returns:
        MaxBotConfig: 配置对象
    """
    global _config_loader, _current_config

    if _config_loader is None:
        return load_config()

    _current_config = _config_loader.load()
    return _current_config
