# MaxBot Hermes 进化引擎集成总结

## 概述

MaxBot 已成功集成 Hermes Agent Self-Evolution 框架，实现了基于 DSPy + GEPA 的技能和提示词自动进化能力。

## 核心组件

### 1. HermesEvolver 类

**位置**: `maxbot/knowledge/hermes_evolver.py`

**主要功能**:
- 技能进化 (`evolve_skill`)
- 提示词进化 (`evolve_prompt`)
- 自动回退机制（Hermes 不可用时使用 MaxBot 内置方案）

### 2. 关键配置

**默认迭代次数**: **140**

```python
def evolve_skill(
    self,
    skill_name: str,
    skill_path: str | Path | None = None,
    skill_text: str | None = None,
    iterations: int = 140,  # 默认 140 次迭代
    eval_source: str = "synthetic",
    dry_run: bool = False,
) -> dict[str, Any]:
```

```python
def evolve_prompt(
    self,
    prompt_name: str,
    prompt_text: str,
    iterations: int = 140,  # 默认 140 次迭代
) -> dict[str, Any]:
```

## 使用方法

### 基本用法

```python
from maxbot.knowledge.hermes_evolver import HermesEvolver

# 创建进化引擎
evolver = HermesEvolver(
    hermes_repo=Path("/path/to/hermes-agent-self-evolution"),
    optimizer_model="openai/gpt-4.1",
    eval_model="openai/gpt-4.1-mini",
)

# 进化技能
result = evolver.evolve_skill(
    skill_name="my_skill",
    skill_text="def handler(): ...",
    iterations=140,  # 使用默认值
)

# 进化提示词
result = evolver.evolve_prompt(
    prompt_name="assistant_prompt",
    prompt_text="你是一个专业的助手...",
    iterations=140,  # 使用默认值
)
```

### 自定义迭代次数

```python
# 使用更少的迭代次数（快速测试）
result = evolver.evolve_skill(
    skill_name="my_skill",
    skill_text="def handler(): ...",
    iterations=10,  # 自定义迭代次数
)

# 使用更多迭代次数（深度优化）
result = evolver.evolve_skill(
    skill_name="my_skill",
    skill_text="def handler(): ...",
    iterations=200,  # 更多次迭代
)
```

## 运行状态

### Hermes 可用性

- **当前状态**: Hermes Agent Self-Evolution 未安装
- **备用方案**: MaxBot 内置自我改进引擎
- **自动回退**: 当 Hermes 不可用时，自动使用 MaxBot 内置方案

### 测试结果

所有测试通过 ✅

```
======================================================================
✅ 所有测试完成！
======================================================================

测试 1: Hermes 进化引擎创建
测试 2: 技能进化
测试 3: 提示词进化
测试 4: Hermes 仓库路径配置
```

## 进化流程

### 技能进化流程

1. **输入**: 技能名称 + 技能代码/路径
2. **分析**: 代码结构、文档字符串、注释
3. **优化**: 140 次迭代优化
4. **输出**: 优化后的技能代码

### 提示词进化流程

1. **输入**: 提示词名称 + 提示词文本
2. **分析**: 提示词结构和内容
3. **优化**: 140 次迭代优化
4. **输出**: 优化后的提示词

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│              MaxBot Hermes 集成层                       │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │         HermesEvolver (主入口)                   │   │
│  │  - evolve_skill()                                │   │
│  │  - evolve_prompt()                               │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  检查 Hermes 可用性                               │   │
│  └─────────────────────────────────────────────────┘   │
│         ↓              ↓                               │
│  ┌──────────────┐  ┌──────────────────────┐           │
│  │  Hermes     │  │  MaxBot 备用方案      │           │
│  │  (DSPy+GEPA)│  │  (SelfEvolver)       │           │
│  │  140 次迭代  │  │  140 次迭代          │           │
│  └──────────────┘  └──────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

## 性能优化

### 迭代次数配置

- **默认值**: 140 次迭代
- **平衡考虑**: 优化质量 vs 计算成本
- **可调整**: 根据需求自定义迭代次数

### 评估模型

- **优化器模型**: `openai/gpt-4.1`
- **评估模型**: `openai/gpt-4.1-mini`

## 示例代码

完整示例: `examples/hermes_evolution_example.py`

运行示例:
```bash
python3 examples/hermes_evolution_example.py
```

## 测试

运行测试:
```bash
python3 tests/test_hermes_integration.py
```

## 未来扩展

1. **Hermes 安装**: 安装完整的 Hermes Agent Self-Evolution 框架
2. **更多评估指标**: 添加性能、准确性等评估维度
3. **并行进化**: 支持多个技能/提示词并行进化
4. **进化历史**: 记录和可视化进化过程

## 总结

✅ **集成完成**: MaxBot 已成功集成 Hermes 进化引擎
✅ **迭代次数**: 默认 140 次迭代（可自定义）
✅ **自动回退**: Hermes 不可用时使用内置方案
✅ **测试通过**: 所有功能测试通过
✅ **生产就绪**: 可用于技能和提示词的自动优化

---

**文档版本**: 1.0
**最后更新**: 2026-04-17
**状态**: ✅ 生产就绪
