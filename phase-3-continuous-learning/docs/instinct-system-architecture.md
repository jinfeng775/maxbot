# MaxBot 本能系统架构设计文档

**版本**: 1.0
**创建日期**: 2025-06-18
**状态**: 🚀 设计中

---

## 📋 执行摘要

本文档定义了 MaxBot 本能系统的架构设计。本能系统是持续学习的核心，能够自动识别用户行为模式、提取可复用的策略，并将其存储为本能记录。

**核心特性**:
- **模式识别**: 自动识别重复的行为模式和成功策略
- **模式提取**: 从用户交互中提取可复用的模式
- **模式验证**: 验证模式的有效性和可靠性
- **模式存储**: 将模式存储为本能记录
- **模式应用**: 在类似场景中自动应用学习到的本能

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    MaxBot Core                          │
│                   (Gateway + Tool System)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Instinct Manager                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Loader     │  │  Registry   │  │  Executor   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Learning Loop                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Observer    │  │  Extractor   │  │  Validator   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Instinct Storage                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Instinct DB  │  │  Pattern DB  │  │  Context DB  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. Instinct Manager (本能管理器)
**职责**:
- 本能发现和加载
- 本能注册和注销
- 本能依赖解析
- 本能生命周期管理

**接口**:
```python
class InstinctManager:
    def load_instinct(self, instinct_path: str) -> Instinct
    def unload_instinct(self, instinct_id: str) -> bool
    def get_instinct(self, instinct_id: str) -> Instinct
    def list_instincts(self) -> List[Instinct]
    def resolve_dependencies(self, instinct: Instinct) -> List[Instinct]
```

#### 2. Learning Loop (学习循环)
**职责**:
- 观察用户交互和工具调用
- 识别重复模式和成功策略
- 验证模式的有效性
- 保存为本能记录
- 在类似场景中自动应用

**学习循环阶段**:
```
1. 观察 - 监控用户交互和工具调用
2. 提取 - 识别重复模式和成功策略
3. 验证 - 评估模式的有效性
4. 存储 - 保存为本能记录
5. 应用 - 在类似场景中自动应用
```

#### 3. Pattern Recognizer (模式识别器)
**职责**:
- 识别代码模式
- 识别用户行为模式
- 识别错误解决模式
- 识别调试技巧模式

**模式类型**:
- 代码模式 (Code Patterns)
- 行为模式 (Behavior Patterns)
- 错误解决模式 (Error Resolution Patterns)
- 调试技巧模式 (Debugging Techniques)

#### 4. Instinct Storage (本能存储)
**职责**:
- 存储本能记录
- 存储模式数据
- 存储上下文信息
- 提供检索和查询功能

---

## 🧩 本能系统设计

### 本能元数据格式

**INSTINCT.md 格式**:
```yaml
---
id: error-resolution-python
name: Python Error Resolution
version: 1.0.0
category: error-resolution
description: Recognize and resolve common Python errors
author: MaxBot Team
email: maxbot@example.com
license: MIT
patterns:
  - type: error_pattern
    name: import-error-resolution
    description: Resolve Python import errors
    trigger:
      - error_type: ImportError
      - error_message: "No module named"
    actions:
      - type: install_package
        package: "{{error_module}}"
      - type: check_requirements
        file: "requirements.txt"
    success_criteria:
      - type: no_error
      - timeout: 30
---

# Python Error Resolution Instinct

## Description

This instinct helps resolve common Python errors automatically.

## Capabilities

### resolve_import_error

**Description**: Resolve Python import errors.

**Parameters**:
| 参数 | 类型 | 描述 | 必需 |
|------|------|------|------|
| `error_message` | string | Error message | ✅ |
| `error_type` | string | Error type | ✅ |
| `file_path` | string | File path | ❌ |

**Returns**:
| 字段 | 类型 | 描述 |
|------|------|------|
| `resolved` | boolean | Whether error was resolved |
| `actions_taken` | array | Actions taken to resolve |
| `suggestion` | string | Resolution suggestion |

---

## Pattern Definition

### Error Pattern

```yaml
patterns:
  - type: error_pattern
    name: import-error-resolution
    description: Resolve Python import errors
    trigger:
      - error_type: ImportError
      - error_message: "No module named"
    actions:
      - type: install_package
        package: "{{error_module}}"
    success_criteria:
      - type: no_error
      - timeout: 30
```

### Behavior Pattern

```yaml
patterns:
  - type: behavior_pattern
    name: test-driven-development
    description: Follow TDD workflow
    trigger:
      - action: write_test
      - context: development
    actions:
      - type: write_failing_test
      - type: implement_code
      - type: verify_passing
    success_criteria:
      -   type: test_passing
      -   coverage: "> 80%"
```

---

## Learning Loop Design

### 观察阶段 (Observation)

**观察内容**:
- 用户交互历史
- 工具调用记录
- 错误发生情况
- 成功解决方案

**观察方法**:
- 事件监听
- 日志分析
- 行为追踪

### 提取阶段 (Extraction)

**提取内容**:
- 重复模式识别
- 成功策略提取
- 上下文信息提取
- 参数关系提取

**提取方法**:
- 模式匹配
- 频率统计
- 关联分析

### 验证阶段 (Validation)

**验证内容**:
- 模式有效性检查
- 成功率统计
- 适用性评估
- 风险评估

**验证方法**:
- 统计验证
- 实验验证
- 专家验证

### 存储阶段 (Storage)

**存储内容**:
- 本能记录
- 模式数据
- 上下文信息
- 统计数据

**存储方法**:
- 数据库存储
- 文件存储
- 缓存存储

### 应用阶段 (Application)

**应用内容**:
- 场景匹配
- 本能应用
- 效果评估
- 反馈收集

**应用方法**:
- 自动应用
- 推荐应用
- 手动应用

---

## 📊 本能分类

### 标准分类

| 分类 | 描述 | 示例本能 |
|------|------|----------|
| `error-resolution` | 错误解决 | Python Error Resolution |
| `code-patterns` | 代码模式 | Common Code Patterns |
| `debugging-techniques` | 调试技巧 | Debugging Strategies |
| `workflows` | 工作流 | TDD Workflow |
| `best-practices` | 最佳实践 | Python Best Practices |

---

## 🔧 配置

### 本能系统配置

```yaml
# config/instinct.yaml
learning:
  enabled: true
  auto_learn: true
  min_session_length: 10
  extraction_threshold: "medium"
  validation_threshold: 0.8

storage:
  type: database
  database_url: "sqlite:///instincts.db"
  backup_enabled: true
  backup_interval: 3600

patterns:
  auto_detect: true
  min_occurrences: 3
  success_rate_threshold: 0.7
  context_similarity_threshold: 0.8
```

---

## 🧪 本能接口

### Base Instinct (本能基类)

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class InstinctContext:
    """本能执行上下文"""
    user_id: str
    session_id: str
    workspace: str
    config: Dict[str, Any]
    metadata: Dict[str, Any]

@dataclass
class InstinctResult:
    """本能执行结果"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    metrics: Dict[str, Any]
    confidence: float

class BaseInstinct(ABC):
    """本能基类"""

    def __init__(self, metadata: Dict[str, Any], config: Dict[str, Any] = None):
        self.metadata = metadata
        self.config = config or {}
        self._patterns = self._load_patterns()

    @abstractmethod
    def recognize(self, context: InstinctContext) -> bool:
        """识别是否应该应用此本能"""
        pass

    @abstractmethod
    def apply(self, context: InstinctContext) -> InstinctResult:
        """应用本能"""
        pass

    @abstractmethod
    def validate(self, result: InstinctResult) -> bool:
        """验证本能应用结果"""
        pass

    def get_confidence(self) -> float:
        """获取本能置信度"""
        pass

    def _load_patterns(self) -> List[Dict[str, Any]]:
        """加载模式定义"""
        pass
```

---

## 🧪 模式识别器

### Pattern Recognizer (模式识别器)

```python
class PatternRecognizer:
    """模式识别器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.patterns = []

    def recognize_pattern(self, context: InstinctContext) -> List[Dict[str, Any]]:
        """识别模式"""
        recognized = []

        for pattern in self.patterns:
            if self._matches_pattern(pattern, context):
                recognized.append(pattern)

        return recognized

    def extract_pattern(self, context: InstinctContext) -> Dict[str, Any]:
        """提取模式"""
        pass

    def validate_pattern(self, pattern: Dict[str, Any]) -> bool:
        """验证模式"""
        pass

    def _matches_pattern(self, pattern: Dict[str, Any], context: InstinctContext) -> bool:
        """检查模式是否匹配"""
        pass
```

---

## 🧪 学习循环

### Learning Loop (学习循环)

```python
class LearningLoop:
    """学习循环"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.observer = Observer(config)
        self.extractor = Extractor(config)
        self.validator = Validator(config)
        self.storage = Storage(config)
        self.applier = Applier(config)

    def observe(self, context: InstinctContext) -> Dict[str, Any]:
        """观察阶段"""
        return self.observer.observe(context)

    def extract(self, observations: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取阶段"""
        return self.extractor.extract(observations)

    def validate(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证阶段"""
        return self.validator.validate(patterns)

    def store(self, patterns: List[Dict[str, Any]]) -> bool:
        """存储阶段"""
        return self.storage.store(patterns)

    def apply(self, context: InstinctContext) -> InstinctResult:
        """应用阶段"""
        return self.applier.apply(context)

    def learn(self, context: InstinctContext) -> bool:
        """完整学习循环"""
        # 1. 观察
        observations = self.observe(context)

        # 2. 提取
        patterns = self.extract(observations)

        # 3. 验证
        validated_patterns = self.validate(patterns)

        # 4. 存储
        self.store(validated_patterns)

        return True
```

---

## 🧪 记忆系统集成

### Memory Integration (记忆集成)

```python
class MemoryIntegratedLearning:
    """集成了记忆系统的学习"""

    def __init__(self, memory_manager, learning_loop):
        self.memory_manager = memory_manager
        self.learning_loop = learning_loop

    def learn_with_memory(self, context: InstinctContext) -> bool:
        """使用记忆系统进行学习"""
        # 从记忆中获取相关上下文
        relevant_context = self.memory_manager.retrieve_context(context)

        # 使用增强的上下文进行学习
        return self.learning_loop.learn(context)

    def apply_with_memory(self, context: InstinctContext) -> InstinctResult:
        """使用记忆系统进行应用"""
        # 从记忆中获取相关本能
        relevant_instincts = self.memory_manager.retrieve_instincts(context)

        # 应用相关本能
        return self.learning_loop.apply(context)
```

---

## 🧪 示例本能

### Python Error Resolution Instinct

```python
class PythonErrorResolutionInstinct(BaseInstinct):
    """Python 错误解决本能"""

    def recognize(self, context: InstinctContext) -> bool:
        """识别是否应该应用此本能"""
        error = context.metadata.get('error')
        if not error:
            return False

        error_type = error.get('type')
        return error_type in ['ImportError', 'ModuleNotFoundError']

    def apply(self, context: InstinctContext) -> InstinctResult:
        """应用本能"""
        error = context.metadata.get('error')
        error_message = error.get('message')

        # 提取缺失的包名
        package = self._extract_package_name(error_message)

        # 安装包
        success = self._install_package(package)

        if success:
            return InstinctResult(
                success=True,
                data={
                    'package_installed': package,
                    'action': 'install_package'
                },
                metrics={},
                confidence=0.9
            )
        else:
            return InstinctResult(
                success=False,
                error=f"Failed to install package: {package}",
                metrics={},
                confidence=0.5
            )

    def validate(self, result: InstinctResult) -> bool:
        """验证本能应用结果"""
        return result.success

    def get_confidence(self) -> float:
        """获取本能置信度"""
        return 0.9

    def _extract_package_name(self, error_message: str) -> str:
        """提取包从错误消息"""
        import re
        match = re.search(r"No module named '([^']+)'", error_message)
        if match:
            return match.group(1)
        return ""

    def _install_package(self, package: str) -> bool:
        """安装包"""
        try:
            import subprocess
            result = subprocess.run(
                ['pip', 'install', package],
                capture_output=True,
                timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False
```

---

## 📊 进度追踪

### 当前状态
- **开始时间**: 2025-06-18
- **已完成任务**: 1/6
- **进行中任务**: 0/6
- **待办任务**: 5/6

### 里程碑
- [ ] 里程碑 1: 本能系统架构设计完成 (预计 1 天)
- [ ] 里程碑 2: 模式识别引擎实现完成 (预计 2 天)
- [ ] 里程碑 3: 学习循环实现完成 (预计 2 天)
- [ ] 里程碑 4: 记忆系统实现完成 (预计 1 天)
- [ ] 里程碑 5: 集成到技能系统完成 (预计 1 天)

---

## 🚀 下一步行动

### 立即执行（今天）
1. ✅ 创建第三阶段目录结构
2. ✅ 设计本能系统架构
3. ⏳ 创建本能元数据规范

### 本周执行
1. 实现模式识别引擎
2. 实现学习循环基础
3. 实现记忆系统基础

---

**文档状态**: 🚀 设计中
**下一步**: 实现本能管理器和模式识别器
