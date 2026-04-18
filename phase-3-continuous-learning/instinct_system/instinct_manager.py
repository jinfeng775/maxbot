"""
MaxBot 本能管理器

负责本能的发现、加载、注册和生命周期管理。
"""

import os
import re
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InstinctStatus(Enum):
    """本能状态"""
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    UNLOADED = "unloaded"


@dataclass
class InstinctMetadata:
    """本能元数据"""
    id: str
    name: str
    version: str
    category: str
    description: str
    author: str = "Unknown"
    email: Optional[str] = None
    license: str = "MIT"
    repository: Optional[str] = None
    homepage: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    patterns: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'category': self.category,
            'description': self.description,
            'author': self.author,
            'email': self.email,
            'license': self.license,
            'repository': self.repository,
            'homepage': self.homepage,
            'keywords': self.keywords,
            'tags': self.tags,
            'patterns': self.patterns
        }


@dataclass
class InstinctContext:
    """本能执行上下文"""
    user_id: str
    session_id: str
    workspace: str
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstinctResult:
    """本能执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


class BaseInstinct:
    """本能基类"""

    def __init__(self, metadata: InstinctMetadata, config: Dict[str, Any] = None):
        self.metadata = metadata
        self.config = config or {}
        self._status = InstinctStatus.LOADED
        self._patterns = metadata.patterns

    @property
    def status(self) -> InstinctStatus:
        """获取本能状态"""
        return self._status

    def recognize(self, context: InstinctContext) -> bool:
        """识别是否应该应用此本能"""
        raise NotImplementedError("Subclasses must implement recognize()")

    def apply(self, context: InstinctContext) -> InstinctResult:
        """应用本能"""
        raise NotImplementedError("Subclasses must implement apply()")

    def validate(self, result: InstinctResult) -> bool:
        """验证本能应用结果"""
        return result.success

    def get_confidence(self) -> float:
        """获取本能置信度"""
        return 0.5

    def activate(self):
        """激活本能"""
        self._status = InstinctStatus.ACTIVE
        logger.info(f"Instinct {self.metadata.id} activated")

    def deactivate(self):
        """停用本能"""
        self._status = InstinctStatus.LOADED
        logger.info(f"Instinct {self.metadata.id} deactivated")


class InstinctLoader:
    """本能加载器"""

    @staticmethod
    def parse_instinct_md(instinct_path: Path) -> Dict[str, Any]:
        """解析 INSTINCT.md 文件"""
        if not instinct_path.exists():
            raise FileNotFoundError(f"INSTINCT.md not found: {instinct_path}")

        with open(instinct_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取 YAML Frontmatter
        match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid INSTINCT.md format: {instinct_path}")

        # 解析元数据
        metadata = yaml.safe_load(match.group(1))
        body = match.group(2)

        return {
            'metadata': metadata,
            'body': body
        }

    @staticmethod
    def validate_metadata(metadata: Dict[str, Any]) -> bool:
        """验证本能元数据"""
        required_fields = ['id', 'name', 'version', 'category', 'description']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field: {field}")

        # 验证 ID 格式
        if not re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', metadata['id']):
            raise ValueError(f"Invalid instinct ID: {metadata['id']}")

        # 验证版本格式
        if not re.match(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', metadata['version']):
            raise ValueError(f"Invalid version: {metadata['version']}")

        # 验证分类格式
        if not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$', metadata['category']):
            raise ValueError(f"Invalid category: {metadata['category']}")

        return True

    @staticmethod
    def load_instinct_metadata(instinct_dir: Path) -> InstinctMetadata:
        """从本能目录加载元数据"""
        instinct_md_path = instinct_dir / "INSTINCT.md"

        # 解析 INSTINCT.md
        parsed = InstinctLoader.parse_instinct_md(instinct_md_path)
        metadata_dict = parsed['metadata']

        # 验证元数据
        InstinctLoader.validate_metadata(metadata_dict)

        # 创建 InstinctMetadata 对象
        return InstinctMetadata(**metadata_dict)

    @staticmethod
    def load_instinct_config(instinct_dir: Path) -> Dict[str, Any]:
        """加载本能配置"""
        config_path = instinct_dir / "config.yaml"

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

        return {}


class InstinctRegistry:
    """本能注册表"""

    def __init__(self):
        self.instincts: Dict[str, BaseInstinct] = {}
        self.metadata: Dict[str, InstinctMetadata] = {}
        self.categories: Dict[str, List[str]] = {}
        self.status: Dict[str, InstinctStatus] = {}

    def register(self, instinct: BaseInstinct):
        """注册本能"""
        instinct_id = instinct.metadata.id

        # 检查是否已注册
        if instinct_id in self.instincts:
            logger.warning(f"Instinct {instinct_id} already registered, replacing")

        # 注册本能
        self.instincts[instinct_id] = instinct
        self.metadata[instinct_id] = instinct.metadata
        self.status[instinct_id] = instinct.status

        # 添加到分类
        category = instinct.metadata.category
        if category not in self.categories:
            self.categories[category] = []
        if instinct_id not in self.categories[category]:
            self.categories[category].append(instinct_id)

        logger.info(f"Instinct {instinct_id} registered")

    def unregister(self, instinct_id: str) -> bool:
        """注销本能"""
        if instinct_id not in self.instincts:
            logger.warning(f"Instinct {instinct_id} not found")
            return False

        # 从分类中移除
        instinct = self.instincts[instinct_id]
        category = instinct.metadata.category
        if category in self.categories and instinct_id in self.categories[category]:
            self.categories[category].remove(instinct_id)

        # 移除本能
        del self.instincts[instinct_id]
        del self.metadata[instinct_id]
        del self.status[instinct_id]

        logger.info(f"Instinct {instinct_id} unregistered")
        return True

    def get(self, instinct_id: str) -> Optional[BaseInstinct]:
        """获取本能"""
        return self.instincts.get(instinct_id)

    def list_all(self) -> List[BaseInstinct]:
        """列出所有本能"""
        return list(self.instincts.values())

    def list_by_category(self, category: str) -> List[BaseInstinct]:
        """按分类列出本能"""
        instinct_ids = self.categories.get(category, [])
        return [self.instincts[instinct_id] for instinct_id in instinct_ids if instinct_id in self.instincts]

    def get_metadata(self, instinct_id: str) -> Optional[InstinctMetadata]:
        """获取本能元数据"""
        return self.metadata.get(instinct_id)

    def get_status(self, instinct_id: str) -> Optional[InstinctStatus]:
        """获取本能状态"""
        return self.status.get(instinct_id)


class InstinctManager:
    """本能管理器"""

    def __init__(self, instinct_paths: List[Path] = None):
        self.loader = InstinctLoader()
        self.registry = InstinctRegistry()
        self.instinct_paths = instinct_paths or []

    def add_instinct_path(self, path: Path):
        """添加本能搜索路径"""
        if path not in self.instinct_paths:
            self.instinct_paths.append(path)
            logger.info(f"Added instinct path: {path}")

    def discover_instincts(self) -> List[Path]:
        """发现所有本能目录"""
        discovered = []

        for instinct_path in self.instinct_paths:
            if not instinct_path.exists():
                logger.warning(f"Instinct path not found: {instinct_path}")
                continue

            # 搜索包含 INSTINCT.md 的目录
            for root, dirs, files in os.walk(instinct_path):
                if 'INSTINCT.md' in files:
                    discovered.append(Path(root))

        logger.info(f"Discovered {len(discovered)} instincts")
        return discovered

    def load_instinct(self, instinct_dir: Path) -> Optional[BaseInstinct]:
        """加载单个本能"""
        try:
            # 加载元数据
            metadata = self.loader.load_instinct_metadata(instinct_dir)

            # 加载配置
            config = self.loader.load_instinct_config(instinct_dir)

            # 创建本能实例
            # TODO: 这里应该根据本能类型动态加载具体的本能类
            # 目前使用 BaseInstinct 作为占位符
            instinct = BaseInstinct(metadata, config)

            # 注册本能
            self.registry.register(instinct)

            logger.info(f"Loaded instinct: {metadata.id} v{metadata.version}")
            return instinct

        except Exception as e:
            logger.error(f"Failed to load instinct from {instinct_dir}: {e}")
            return None

    def load_all_instincts(self) -> int:
        """加载所有发现的本能"""
        discovered = self.discover_instincts()
        loaded_count = 0

        for instinct_dir in discovered:
            if self.load_instinct(instinct_dir):
                loaded_count += 1

        logger.info(f"Loaded {loaded_count}/{len(discovered)} instincts")
        return loaded_count

    def get_instinct(self, instinct_id: str) -> Optional[BaseInstinct]:
        """获取本能"""
        return self.registry.get(instinct_id)

    def list_instincts(self) -> List[Dict[str, Any]]:
        """列出所有本能信息"""
        instincts_info = []

        for instinct in self.registry.list_all():
            instincts_info.append({
                'id': instinct.metadata.id,
                'name': instinct.metadata.name,
                'version': instinct.metadata.version,
                'category': instinct.metadata.category,
                'description': instinct.metadata.description,
                'status': instinct.status.value
            })

        return instincts_info

    def recognize_instincts(self, context: InstinctContext) -> List[BaseInstinct]:
        """识别适用的本能"""
        recognized = []

        for instinct in self.registry.list_all():
            if instinct.recognize(context):
                recognized.append(instinct)

        logger.info(f"Recognized {len(recognized)} instincts for context")
        return recognized

    def apply_instincts(self, context: InstinctContext) -> List[InstinctResult]:
        """应用识别到的本能"""
        recognized = self.recognize_instincts(context)
        results = []

        for instinct in recognized:
            try:
                # 激活本能
                instinct.activate()

                # 应用本能
                result = instinct.apply(context)

                # 验证结果
                if instinct.validate(result):
                    logger.info(f"Instinct {instinct.metadata.id} applied successfully")
                else:
                    logger.warning(f"Instinct {instinct.metadata.id} validation failed")

                # 停用本能
                instinct.deactivate()

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to apply instinct {instinct.metadata.id}: {e}")
                results.append(InstinctResult(
                    success=False,
                    error=str(e)
                ))

        return results

    def resolve_dependencies(self, instinct_id: str) -> List[str]:
        """解析本能依赖"""
        instinct = self.get_instinct(instinct_id)

        if not instinct:
            return []

        # TODO: 实现依赖解析
        return []


# 全局本能管理器实例
_global_instinct_manager: Optional[InstinctManager] = None


def get_global_instinct_manager() -> InstinctManager:
    """获取全局本能管理器实例"""
    global _global_instinct_manager

    if _global_instinct_manager is None:
        # 默认本能路径
        default_paths = [
            Path(__file__).parent.parent / "instinct_system" / "instincts",
            Path.home() / ".maxbot" / "instincts"
        ]

        _global_instinct_manager = InstinctManager(default_paths)

    return _global_instinct_manager


def initialize_instinct_manager(instinct_paths: List[Path] = None) -> InstinctManager:
    """初始化本能管理器"""
    global _global_instinct_manager

    _global_instinct_manager = InstinctManager(instinct_paths)

    # 自动加载所有本能
    _global_instinct_manager.load_all_instincts()

    return _global_instinct_manager
