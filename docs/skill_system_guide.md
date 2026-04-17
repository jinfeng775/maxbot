# MaxBot 技能系统完整指南

## 📋 目录

1. [系统架构](#系统架构)
2. [技能生成流程](#技能生成流程)
3. [技能管理工具](#技能管理工具)
4. [使用示例](#使用示例)
5. [最佳实践](#最佳实践)

---

## 系统架构

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                     MaxBot 技能系统                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ 代码分析器   │ →  │ 能力提取器   │ →  │ 技能工厂     │  │
│  │ CodeParser   │    │ Capability   │    │ SkillFactory │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         ↓                    ↓                    ↓          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ 项目结构     │    │ 能力定义     │    │ 技能生成     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                              ↓               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ 安全验证器   │ ←  │ 技能文件     │ →  │ 自动注册器   │  │
│  │ SandboxVal   │    │ SKILL.md    │    │ AutoRegister │  │
│  └──────────────┘    │ handler.py  │    └──────────────┘  │
│                       │ meta.json   │           ↓          │
│  ┌──────────────┐    └──────────────┘    ┌──────────────┐  │
│  │ 技能管理器   │                         │ 工具注册表   │  │
│  │ SkillManager │ ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │ ToolRegistry │  │
│  └──────────────┘                         └──────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 文件结构

```
maxbot/
├── knowledge/
│   ├── code_parser.py          # 代码解析器
│   ├── capability_extractor.py  # 能力提取器
│   ├── skill_factory.py         # 技能工厂
│   ├── sandbox_validator.py      # 安全验证器
│   ├── auto_register.py         # 自动注册器
│   └── harness_optimizer.py     # Meta-Harness 优化器
├── tools/
│   ├── _registry.py             # 工具注册表
│   └── skill_manager.py         # 技能管理工具
└── core/
    └── tool_registry.py         # 工具注册核心

~/.maxbot/
└── skills/                      # 技能存储目录
    ├── skill_name/
    │   ├── SKILL.md             # 技能文档
    │   ├── handler.py           # 执行逻辑
    │   └── meta.json            # 元数据
    └── ...
```

---

## 技能生成流程

### 完整流程

```python
# 步骤 1: 定义能力
from maxbot.knowledge.capability_extractor import ExtractedCapability

capability = ExtractedCapability(
    name="my_skill",
    description="我的技能描述",
    source_file="path/to/source.py",
    source_function="function_name",
    parameters={
        "param1": {"type": "string", "description": "参数1"},
    },
    required_params=["param1"],
    tags=["category", "tag"],
    handler_code="""
def handle_my_skill(args, agent):
    param1 = args.get("param1")
    return f"结果: {param1}"
    """,
    confidence=1.0,
)

# 步骤 2: 生成技能
from maxbot.knowledge.skill_factory import SkillFactory

factory = SkillFactory(output_dir="~/.maxbot/skills")
skills = factory.generate([capability], overwrite=True)

# 步骤 3: 验证安全性
from maxbot.knowledge.sandbox_validator import batch_validate

validations = batch_validate([capability])

# 步骤 4: 自动注册
from maxbot.knowledge.auto_register import AutoRegister
from maxbot.tools._registry import registry

auto_register = AutoRegister(tool_registry=registry)
registrations = auto_register.register_validated(validations, toolset="my_toolset")
```

### 生成的文件

#### 1. SKILL.md

```markdown
---
description: "我的技能描述"
triggers: ["my skill", "function_name"]
tools: []
source: "path/to/source.py"
source_function: "function_name"
version: 1
confidence: 1.0
generated: true
tags: ["category", "tag"]
---

# my_skill

我的技能描述

## 来源

- 文件: `path/to/source.py`
- 函数: `function_name`
- 版本: 1
- 置信度: 100%

## 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `param1` | string | ✓ | 参数1 |

## 返回值

返回执行结果

## 使用方式

当用户请求与 `my_skill` 相关的任务时，自动调用此技能的 handler。

Handler 位于: `handler.py`
```

#### 2. handler.py

```python
"""
Auto-generated handler for: my_skill
Source: path/to/source.py::function_name
"""

def handle_my_skill(args, agent):
    param1 = args.get("param1")
    return f"结果: {param1}"
```

#### 3. meta.json

```json
{
  "name": "my_skill",
  "version": 1,
  "created_at": 1744868168.123
}
```

---

## 技能管理工具

### 可用工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `list_skills` | 列出所有技能 | `pattern` (可选) |
| `get_skill` | 查看技能详情 | `name` |
| `delete_skill` | 删除技能 | `name` |
| `update_skill` | 更新技能元数据 | `name`, `description`, `tags` |
| `reload_skill` | 热重载技能 | `name` |
| `get_skill_content` | 获取技能完整内容 | `name` |

### 使用示例

```python
from maxbot.tools._registry import registry

# 加载技能管理工具
import maxbot.tools.skill_manager

# 列出所有技能
result = registry.call("list_skills", {"pattern": "translator"})
print(result)

# 查看技能详情
result = registry.call("get_skill", {"name": "my_skill"})
print(result)

# 更新技能
result = registry.call("update_skill", {
    "name": "my_skill",
    "description": "新的描述",
    "tags": "tag1,tag2,tag3"
})
print(result)

# 重新加载技能
result = registry.call("reload_skill", {"name": "my_skill"})
print(result)

# 获取技能内容
result = registry.call("get_skill_content", {"name": "my_skill"})
print(result)

# 删除技能
result = registry.call("delete_skill", {"name": "my_skill"})
print(result)
```

### SkillManager API

```python
from maxbot.tools.skill_manager import SkillManager

manager = SkillManager(skills_dir="~/.maxbot/skills")

# 列出技能
skills = manager.list_skills(pattern="")

# 获取技能
skill = manager.get_skill("my_skill")

# 删除技能
success = manager.delete_skill("my_skill")

# 更新技能
success = manager.update_skill(
    "my_skill",
    description="新描述",
    tags=["tag1", "tag2"]
)

# 重新加载
success = manager.reload_skill("my_skill")

# 获取内容
content = manager.get_skill_content("my_skill")
```

---

## 使用示例

### 示例 1: 从代码生成技能

```python
# examples/generate_conversation_limit_skill.py
# 完整演示技能生成流程

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.knowledge.capability_extractor import ExtractedCapability
from maxbot.knowledge.skill_factory import SkillFactory
from maxbot.knowledge.sandbox_validator import batch_validate
from maxbot.knowledge.auto_register import AutoRegister
from maxbot.tools._registry import registry

# 定义能力
capability = ExtractedCapability(
    name="set_conversation_limit",
    description="设置会话轮询次数限制",
    parameters={
        "max_turns": {"type": "integer", "minimum": 1},
    },
    handler_code="""
def handle_set_conversation_limit(args, agent):
    max_turns = args.get("max_turns")
    if max_turns:
        agent.config.max_conversation_turns = max_turns
        return f"✅ 已设置为 {max_turns} 次"
    return "❌ 无效参数"
    """,
    confidence=1.0,
)

# 生成技能
factory = SkillFactory()
skills = factory.generate([capability])

# 验证
validations = batch_validate([capability])

# 注册
auto_register = AutoRegister(tool_registry=registry)
registrations = auto_register.register_validated(validations)
```

### 示例 2: 管理现有技能

```python
# examples/test_existing_skills.py
# 演示技能管理工具的使用

from maxbot.tools._registry import registry
import maxbot.tools.skill_manager

# 列出所有技能
result = registry.call("list_skills", {})
print(result)

# 查看详情
result = registry.call("get_skill", {"name": "translator_detect_language"})
print(result)

# 更新技能
result = registry.call("update_skill", {
    "name": "translator_detect_language",
    "description": "检测文本语言",
    "tags": "language,detection"
})
print(result)
```

### 示例 3: 调用技能

```python
from maxbot.tools._registry import registry
from maxbot.core.agent_loop import Agent, AgentConfig

# 创建 Agent
agent = Agent(config=AgentConfig())

# 调用技能
result = registry.call("set_conversation_limit", {
    "max_turns": 50,
    "agent": agent
})
print(result)
```

---

## 最佳实践

### 1. 技能命名

- 使用清晰的、描述性的名称
- 使用下划线分隔单词（snake_case）
- 避免与内置工具冲突

```python
# ✅ 好的命名
name="translate_text"
name="analyze_file_structure"

# ❌ 不好的命名
name="tt"  # 太简短
name="TranslateText"  # 不符合约定
```

### 2. 参数设计

- 提供清晰的描述
- 设置合理的类型和约束
- 使用默认值减少必需参数

```python
parameters={
    "text": {
        "type": "string",
        "description": "要处理的文本",
    },
    "max_length": {
        "type": "integer",
        "description": "最大长度",
        "default": 1000,
        "minimum": 1,
        "maximum": 10000,
    },
}
```

### 3. Handler 编写

- 支持两种签名模式：
  - `def handle_xxx(args, agent):` - 参数字典模式
  - `def handle_xxx(**kwargs):` - 关键字参数模式

- 返回字符串或可 JSON 序列化的对象

```python
# 模式 1: 参数字典
def handle_my_skill(args, agent):
    param = args.get("param")
    return f"结果: {param}"

# 模式 2: 关键字参数
def handle_my_skill(param: str, agent):
    return f"结果: {param}"
```

### 4. 错误处理

```python
def handle_my_skill(args, agent):
    try:
        param = args.get("param")
        if not param:
            return {"error": "缺少必需参数: param"}

        # 执行操作
        result = do_something(param)

        return {"success": True, "result": result}

    except Exception as e:
        return {"error": str(e)}
```

### 5. 版本管理

- 更新技能时增加版本号
- 保留旧版本以便回滚

```python
# 更新技能
factory = SkillFactory()
skills = factory.generate([capability], overwrite=True)
```

### 6. 安全性

- 避免在 handler 中执行危险操作
- 使用沙箱执行外部代码
- 验证所有输入参数

```python
def handle_my_skill(args, agent):
    # 验证输入
    param = args.get("param")
    if not isinstance(param, str):
        return {"error": "参数必须是字符串"}

    # 避免危险操作
    # ❌ 不要这样做
    # exec(param)

    # ✅ 应该这样做
    result = safe_operation(param)
    return result
```

### 7. 文档化

- 在 SKILL.md 中提供详细说明
- 包含使用示例
- 说明参数和返回值

### 8. 测试

```python
# 测试技能
from maxbot.tools._registry import registry

result = registry.call("my_skill", {
    "param": "test"
})
assert "成功" in result
```

---

## 常见问题

### Q1: 如何批量生成技能？

```python
# 从多个能力批量生成
capabilities = [cap1, cap2, cap3]
factory = SkillFactory()
skills = factory.generate(capabilities)
```

### Q2: 如何从现有代码提取能力？

```python
from maxbot.knowledge.capability_extractor import CapabilityExtractor

extractor = CapabilityExtractor()
capabilities = extractor.extract_from_file("my_module.py")
```

### Q3: 技能调用失败怎么办？

```python
# 检查技能是否已注册
tool = registry.get("my_skill")
if not tool:
    print("技能未注册")
else:
    # 检查参数
    print(f"所需参数: {tool.required_params}")
```

### Q4: 如何卸载技能？

```python
# 从注册表卸载
registry.unregister("my_skill")

# 删除技能文件
from maxbot.tools.skill_manager import skill_manager
skill_manager.delete_skill("my_skill")
```

---

## 总结

MaxBot 技能系统提供了完整的技能生命周期管理：

1. **生成** - 从代码或手动定义生成技能
2. **验证** - 安全性和语法验证
3. **注册** - 自动注册到工具系统
4. **管理** - 列表、查看、更新、删除
5. **调用** - 通过注册表调用技能

通过这个系统，你可以：
- 将代码模块化为可复用的技能
- 自动提取和注册能力
- 安全地执行和管理技能
- 灵活地更新和维护技能

更多示例请查看 `examples/` 目录。
