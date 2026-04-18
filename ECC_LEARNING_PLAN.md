# MaxBot 向 ECC 学习计划

> 学习目标：从 Everything Claude Code (ECC) 吸收先进理念，改进 MaxBot 代码
> 
> ECC 来源：https://github.com/affaan-m/everything-claude-code
> 
> 版本：v1.10.0 | 140K+ stars | 10+ 个月高强度实战打磨

---

## 学习总览

| 阶段 | 学习内容 | 预期成果 | 状态 |
|------|---------|---------|------|
| Phase 1 | Hook 自动化系统 | Pre/Post 工具调用钩子系统 | 🔲 未开始 |
| Phase 2 | 专用 Agent 体系 | planner/architect/reviewer 等专用 agent | 🔲 未开始 |
| Phase 3 | 技能模块化 | SKILL.md 标准化技能系统 | 🔲 未开始 |
| Phase 4 | 持续学习与记忆 | Instinct-based learning + 自动模式提取 | 🔲 未开始 |
| Phase 5 | 安全扫描集成 | AgentShield + security-reviewer | 🔲 未开始 |
| Phase 6 | 验证循环与质量门 | Grader types, pass@k metrics, quality gates | 🔲 未开始 |
| Phase 7 | 多语言审查器 | TypeScript/Python/Go/Rust/Java 专用审查 | 🔲 未开始 |
| Phase 8 | 运算符工作流 | operator-workflows 自动化任务 | 🔲 未开始 |

---

## Phase 1：Hook 自动化系统 🔲

### 学习目标
从 ECC 的 `hooks/hooks.json` 学习自动化钩子系统，实现：
- 工具调用前验证（PreToolUse）
- 工具调用后处理（PostToolUse）
- 会话开始/结束事件（SessionStart/SessionEnd）
- 上下文压缩触发（PreCompact）
- 运行时控制（ECC_HOOK_PROFILE, ECC_DISABLED_HOOKS）

### ECC 参考点
```
everything-claude-code/
├── hooks/
│   ├── hooks.json              # 钩子配置
│   └── README.md              # 钩子文档
├── scripts/hooks/
│   ├── pre-bash-dispatcher.js  # Bash 前置检查
│   ├── doc-file-warning.js     # 文档文件警告
│   ├── suggest-compact.js      # 建议压缩
│   ├── run-with-flags.js      # 运行时控制
│   └── continuous-learning-v2/hooks/
│       └── observe.sh          # 观察工具调用
```

### 实现（MaxBot 需要新增）

#### 1. Hook 核心架构
```
maxbot/
├── core/
│   └── hooks/                  # 新增
│       ├── __init__.py
│       ├── hook_manager.py      # 钩子管理器
│       ├── hook_events.py       # 事件定义
│       └── builtin_hooks.py     # 内置钩子
└── configs/
    └── hooks.yaml              # 钩子配置文件
```

**文件：`maxbot/core/hooks/hook_events.py`**
```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

class HookEvent(str, Enum):
    """Hook 事件类型（参考 ECC hooks.json）"""
    PRE_TOOL_USE = "pre_tool_use"          # 工具调用前
    POST_TOOL_USE = "post_tool_use"        # 工具调用后
    SESSION_START = "session_start"          # 会话开始
    SESSION_END = "session_end"            # 会话结束
    PRE_COMPACT = "pre_compact"             # 压缩前
    POST_COMPACT = "post_compact"           # 压缩后
    ERROR = "error"                         # 错误发生

@dataclass
class HookContext:
    """钩子执行上下文"""
    event: HookEvent
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

**文件：`maxbot/core/hooks/hook_manager.py`**
```python
from typing import Callable, Dict, List, Optional
from .hook_events import HookEvent, HookContext
import logging

logger = logging.getLogger(__name__)

class HookManager:
    """钩子管理器（参考 ECC hooks 系统）"""
    
    def __init__(self):
        self._hooks: Dict[HookEvent, List[Callable]] = {}
        self._disabled_hooks: set = set()
        self._profile = "standard"  # minimal | standard | strict
        
    def register(self, event: HookEvent, hook: Callable):
        """注册钩子"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(hook)
        logger.debug(f"Registered hook for {event}: {hook.__name__}")
    
    def register_many(self, hooks: Dict[HookEvent, List[Callable]]):
        """批量注册钩子"""
        for event, hook_list in hooks.items():
            for hook in hook_list:
                self.register(event, hook)
    
    async def trigger(self, event: HookEvent, context: HookContext):
        """触发钩子（参考 ECC 的 async execution）"""
        if event in self._disabled_hooks:
            logger.debug(f"Hook {event} is disabled, skipping")
            return
        
        hooks = self._hooks.get(event, [])
        for hook in hooks:
            try:
                if hasattr(hook, "__code__") and "await" in hook.__code__.co_names:
                    await hook(context)
                else:
                    hook(context)
            except Exception as e:
                logger.error(f"Hook {hook.__name__} failed: {e}")
    
    def disable(self, event: HookEvent):
        """禁用钩子（参考 ECC_DISABLED_HOOKS）"""
        self._disabled_hooks.add(event)
    
    def set_profile(self, profile: str):
        """设置运行时配置（参考 ECC_HOOK_PROFILE）"""
        self._profile = profile
```

#### 2. 内置钩子实现

**文件：`maxbot/core/hooks/builtin_hooks.py`**

```python
import os
import logging
from typing import Dict, Any
from .hook_events import HookEvent, HookContext

logger = logging.getLogger(__name__)

# ========== Pre-Tool Hooks ==========

def pre_command_safety_check(context: HookContext):
    """
    危险命令检查（参考 ECC pre:bash:dispatcher）
    
    检查 shell 命令是否包含危险操作：
    - rm -rf /
    - dd if=/dev/zero
    - :(){ :|:& };:
    """
    if context.tool_name != "shell":
        return
    
    command = context.tool_args.get("command", "")
    dangerous = ["rm -rf /", "dd if=/dev/zero", ":(){ :|:& };:"]
    
    for pat in dangerous:
        if pat in command:
            raise ValueError(f"危险命令被拦截: {pat}")
    
    logger.info(f"Command safety check passed: {command[:50]}...")

def pre_documentation_warning(context: HookContext):
    """
    文档文件警告（参考 ECC pre:write:doc-file-warning）
    
    警告正在编辑非标准文档文件
    """
    if context.tool_name not in ["write_file", "edit_file"]:
        return
    
    file_path = context.tool_args.get("path", "")
    doc_paths = ["README.md", "CHANGELOG.md", "docs/", "docs/zh-CN/"]
    
    if any(dp in file_path for dp in doc_paths):
        logger.warning(f"正在编辑文档文件: {file_path}")

# ========== Post-Tool Hooks ==========

def post_tool_observation(context: HookContext):
    """
    工具调用观察（参考 ECC continuous-learning-v2 observe.sh）
    
    记录工具调用模式，用于持续学习
    """
    # TODO: 实现观察记录到数据库
    logger.info(f"Observed tool use: {context.tool_name} -> {context.result_type}")

# ========== Session Hooks ==========

def session_start_capture(context: HookContext):
    """
    会话开始捕获（参考 ECC SessionStart）
    
    记录会话元数据：时间戳、会话ID、初始上下文
    """
    session_id = context.session_id
    logger.info(f"Session started: {session_id}")
    # TODO: 实现会话记录到数据库

def session_end_summary(context: HookContext):
    """
    会话结束摘要（参考 ECC SessionEnd）
    
    生成会话摘要并保存到知识库
    """
    session_id = context.session_id
    logger.info(f"Session ended: {session_id}")
    # TODO: 实现会话摘要生成

# ========== Export hooks for registration ==========

BUILTIN_HOOKS = {
    HookEvent.PRE_TOOL_USE: [
        pre_command_safety_check,
        pre_documentation_warning,
    ],
    HookEvent.POST_TOOL_USE: [
        post_tool_observation,
    ],
    HookEvent.SESSION_START: [
        session_start_capture,
    ],
    HookEvent.SESSION_END: [
        session_end_summary,
    ],
}
```

#### 3. 集成到 Agent Loop

**修改：`maxbot/core/agent_loop.py`**

在 `AgentLoop` 类中添加 HookManager：

```python
from .hooks.hook_manager import HookManager
from .hooks.builtin_hooks import BUILTIN_HOOKS
from .hooks.hook_events import HookContext, HookEvent

class AgentLoop:
    def __init__(self, ...):
        # ... 现有初始化
        self.hook_manager = HookManager()
        self.hook_manager.register_many(BUILTIN_HOOKS)
    
    async def _call_tool(self, tool_name: str, tool_args: dict):
        """工具调用（集成钩子系统）"""
        # Pre-tool hook
        await self.hook_manager.trigger(
            HookEvent.PRE_TOOL_USE,
            HookContext(
                event=HookEvent.PRE_TOOL_USE,
                tool_name=tool_name,
                tool_args=tool_args,
                session_id=self.session_id
            )
        )
        
        # 执行工具
        result = await self.tool_registry.call(tool_name, **tool_args)
        
        # Post-tool hook
        await self.hook_manager.trigger(
            HookEvent.POST_TOOL_USE,
            HookContext(
                event=HookEvent.POST_TOOL_USE,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=result,
                session_id=self.session_id
            )
        )
        
        return result
```

### 测试计划

**新增测试文件：`tests/test_hooks.py`**

```python
import pytest
from maxbot.core.hooks import HookManager, HookEvent, HookContext
from maxbot.core.hooks.builtin_hooks import BUILTIN_HOOKS

def test_hook_registration():
    manager = HookManager()
    manager.register(HookEvent.PRE_TOOL_USE, lambda ctx: None)
    assert len(manager._hooks[HookEvent.PRE_TOOL_USE]) == 1

def test_builtin_hooks():
    manager = HookManager()
    manager.register_many(BUILTIN_HOOKS)
    assert HookEvent.PRE_TOOL_USE in manager._hooks
    assert HookEvent.SESSION_START in manager._hooks

def test_hook_disable():
    manager = HookManager()
    manager.register(HookEvent.PRE_TOOL_USE, lambda ctx: None)
    manager.disable(HookEvent.PRE_TOOL_USE)
    # 验证触发被跳过
```

### 验收标准
- [ ] Hook 核心架构实现完成
- [ ] 5+ 内置钩子实现
- [ ] 集成到 Agent Loop
- [ ] 测试覆盖 >= 80%
- [ ] 钩子配置文件支持 hooks.yaml
- [ ] 运行时控制（ECC_HOOK_PROFILE, ECC_DISABLED_HOOKS）

---

## Phase 2：专用 Agent 体系 🔲

### 学习目标
从 ECC 的 48 个专用 agents 学习，实现 MaxBot 的专用 agent 框架：
- planner — 实现规划 agent
- architect — 架构设计 agent
- code-reviewer — 代码审查 agent
- security-reviewer — 安全审查 agent
- tdd-guide — TDD 指导 agent
- build-error-resolver — 构建错误解决 agent

### ECC 参考点
```
everything-claude-code/agents/
├── planner.md
├── architect.md
├── code-reviewer.md
├── security-reviewer.md
├── tdd-guide.md
└── build-error-resolver.md
```

### 实现（MaxBot 需要新增）

```
maxbot/
├── agents/                       # 新增
│   ├── __init__.py
│   ├── base.py                   # Agent 基类
│   ├── planner.py
│   ├── architect.py
│   ├── code_reviewer.py
│   ├── security_reviewer.py
│   └── registry.py                # Agent 注册表
```

---

## Phase 3：技能模块化 🔲

### 学习目标
从 ECC 的 183 个 skills 学习，实现 SKILL.md 标准化技能系统：
- SKILL.md 标准格式（YAML frontmatter + Markdown body）
- 技能发现与热加载
- 技能依赖管理
- 选择性安装

### ECC 参考点
```
everything-claude-code/skills/
├── tdd-workflow/SKILL.md
├── backend-patterns/SKILL.md
├── frontend-patterns/SKILL.md
└── security-review/SKILL.md
```

---

## Phase 4：持续学习与记忆 🔲

### 学习目标
从 ECC 的 continuous-learning-v2 学习：
- Instinct-based learning
- 自动模式提取
- 置信度评分
- 技能进化

### ECC 参考点
```
everything-claude-code/
├── skills/continuous-learning-v2/SKILL.md
├── skills/continuous-learning-v2/hooks/observe.sh
└── .instincts/
```

---

## Phase 5：安全扫描集成 🔲

### 学习目标
从 ECC 的 AgentShield 集成安全扫描：
- 1282+ 安全规则
- 扫描命令：/security-scan
- 漏洞检测
- 依赖审计

### ECC 参考点
```
everything-claude-code/
├── skills/security-review/SKILL.md
├── agents/security-reviewer.md
└── rules/                     # 安全规则
```

---

## Phase 6：验证循环与质量门 🔲

### 学习目标
从 ECC 的 verification-loop 学习：
- Grader types
- pass@k metrics
- quality gates
- checkpoint vs continuous evals

### ECC 参考点
```
everything-claude-code/
├── skills/verification-loop/SKILL.md
├── agents/gan-evaluator.md
└── agents/gan-planner.md
```

---

## Phase 7：多语言审查器 🔲

### 学习目标
从 ECC 的多语言 agents 学习：
- typescript-reviewer
- python-reviewer
- go-reviewer
- rust-reviewer
- java-reviewer

---

## Phase 8：运算符工作流 🔲

### 学习目标
从 ECC 的 operator-workflows 学习：
- 自动化任务编排
- workspace-surface-audit
- customer-billing-ops
- google-workspace-ops

---

## 学习方法论

### ECC 核心理念（必须遵循）

1. **Agent-First** — 委派给专用 agent 处理领域任务
2. **Test-Driven** — 先写测试，80%+ 覆盖率
3. **Security-First** — 安全第一，验证所有输入
4. **Immutability** — 不可变，创建新对象不修改现有对象
5. **Plan Before Execute** — 复杂特性先规划

### 实施原则

- **直接移植** — 小型、自包含的功能直接移植
- **适配移植** — 大型功能适配 MaxBot 架构
- **理念吸收** — 吸收核心思想，用 Python 重新实现
- **渐进式** — 分阶段实施，每阶段验证通过后进入下一阶段

---

## 参考资料

- ECC 完整文档：https://github.com/affaan-m/everything-claude-code
- ECC 短篇指南：https://x.com/affaanmustafa/status/2012378465664745795
- ECC 长篇指南：https://x.com/affaanmustafa/status/2014040193557471352
- ECC 安全指南：https://x.com/affaanmustafa/status/2033263813387223421
