# MaxBot 第二阶段：技能体系建设 - 架构设计

**阶段：**.md Phase 2 - Skills System Architecture Design  
**创建日期：** 2025-04-18  
**预计执行期：** Week 3-4 (2025-06-24 ~ 2025-07-07)  
**参考模型：** Everything Claude Code (ECC)

---

## 📋 阶段目标

基于第一阶段的架构分析，为 MaxBot 设计和实现一个可扩展的技能系统架构，并集成从 ECC 复制的核心专业技能。

### 核心目标

1. **建立技能系统架构** - 设计符合 MaxBot 技术栈的技能系统
2. **复制核心技能** - 从 ECC 复制 20+ 核心技能并适配到 MaxBot
3. **实现专业 Agent** - 实现 Planner 和 Security Reviewer 等 Agent
4. **集成安全审查** - 建立安全检查和验证机制

---

## 🏗️ MaxBot 技能系统架构设计

### 设计原则

基于对 ECC 和 MaxBot 的分析，制定以下设计原则：

| 原则 | 说明 | 优先级 |
|------|------|--------|
| **Hermes 兼容** | 充分利用 Hermes 现有的 skill_manage 机制 | P0 |
| **消息平台适配** | 技能输出适配 WeChat/Telegram 等消息平台 | P0 |
| **渐进式扩展** | 从核心技能开始，逐步扩展到完整生态 | P0 |
| **工具集集成** | 技能与 MaxBot 工具系统无缝集成 | P1 |
| **持久化存储** | 技能和知识持久化到数据库 | P1 |

---

## 📁 技能目录结构

```
maxbot/
├── maxbot/
│   ├── skills/              # MaxBot 技能目录 (使用 Hermes 机制)
│   │   ├── core/             # 核心技能
│   │   │   ├── tdd-workflow/
│   │   │   │   └── SKILL.md
│   │   │   ├── security-review/
│   │   │   │   └── SKILL.md
│   │   │   ├── python-testing/
│   │   │   │   └── SKILL.md
│   │   │   └── code-analysis/
│   │   │       └── SKILL.md
│   │   ├── development/      # 开发技能
│   │   ├── security/         # 安全技能
│   │   └── domain/           # 领域技能
│   └── agents/               # MaxBot Agent 系统
│       ├── planner.py
│       ├── security_reviewer.py
│       ├── tdd_guide.py
│       └── architect_agent.py
│
├── phase2-skills-system/     # 第二阶段工作目录
│   ├── phase2-architecture-design.md
│   ├── phase2-implementation-plan.md
│   ├── skills-adaptation-guide.md
│   └── skill-catalog.md
│
└── docs/
    └── maxbot-skills-guide.md
```

---

## 🔄 技能系统架构层次

### 1. 技能发现和加载层

```
Hermes Skill System (已有)
  ↓
MaxBot Skill Registry (新增)
  ↓
Skill Categorization (新增)
  ↓
Agent Integration (新增)
```

**组件职责：**

| 组件 | 职责 | 依赖 |
|------|------|------|
| Hermes Skill System | 基础技能管理 (CRUD、搜索) | - |
| MaxBot Skill Registry | 技能分类、优先级、依赖管理 | Hermes |
| Skill Categorization | 技能分类标签、元数据管理 | Registry |
| Agent Integration | Agent 与技能的绑定 | Registry |

---

## 🎯 核心技能实现计划

### 第一批：P0 核心技能 (4个)

| 技能 | 来源 | 优先级 | 预计工作量 | 状态 |
|------|------|--------|------------|------|
| tdd-workflow | ECC | P0 | 2h | ⏳ 待实现 |
| security-review | ECC | P0 | 2h | ⏳ 待实现 |
| python-testing | ECC | P0 | 2h | ⏳ 待实现 |
| code-analysis | MaxBot 实现 | P0 | 3h | ⏳ 待实现 |

### 第二批：P1 重要技能 (6个)

| 技能 | 来源 | 优先级 | 预计工作量 | 状态 |
|------|------|--------|------------|------|
| code-generation | ECC | P1 | 3h | ⏳ 待实现 |
| debugging-techniques | ECC | P1 | 2h | ⏳ 待实现 |
| performance-analysis | ECC | P1 | 3h | ⏳ 待实现 |
| documentation-writing | ECC | P1 | 2h | ⏳ 待实现 |
| api-design | ECC | P1 | 2h | ⏳ 待实现 |
| test-driven-dev | ECC | P1 | 2h | ⏳ 待实现 |

---

## 🤖 Agent 系统设计

### Agent 定义格式

基于 MaxBot 的委托机制 (`delegate_task`)，Agent 定义为：

```python
# maxbot/agents/base_agent.py
class MaxBotAgent:
    """MaxBot Agent 基类"""
    
    def __init__(self, name: str, description: str, skills: list):
        self.name = name
        self.description = description
        self.skills = skills  # 技能名称列表
        self.model = None     # 可选的模型覆盖
        self.max_iterations = 50
    
    async def execute(self, context: str, **kwargs):
        """执行 Agent 任务"""
        # 使用 delegate_task 调用子智能体
        pass
```

### 预定义 Agent 清单

#### 1. Planner Agent

**职责：** 实现规划和任务分解
**使用技能：** planner, tdd-workflow, architecture-decision-records
**触发条件：** 复杂功能请求、重构任务

#### 2. Security Reviewer Agent

**职责：** 安全漏洞检测和代码审查
**使用技能：** security-review, python-security, static-analysis
**触发条件：** 提交前审查、敏感代码

#### 3. TDD Guide Agent

**职责：** 测试驱动开发指导
**使用技能：** tdd-workflow, python-testing, test-coverage
**触发条件：** 新功能开发、Bug 修复

#### 4. Code Reviewer Agent

**职责：** 代码质量和可维护性审查
**使用技能：** code-analysis, python-style, complexity-analysis
**触发条件：** 代码修改后

---

## 🔌 技能与工具集成

### 工具映射表

| ECC 技能 | MaxBot 工具 | 适配方式 |
|----------|-------------|----------|
| Bash 执行 | terminal | 直接使用 |
| 文件操作 | read_file/write_file/patch | 直接使用 |
| Web 搜索 | web_search (web_tools) | 直接使用 |
| 代码执行 | execute_code | 直接使用 |
| 浏览器自动化 | browser_tool | 直接使用 |
| MCP 调用 | mcp_tool | 直接使用 |
| Git 操作 | terminal (git commands) | 适配层 |

### 工具适配层

```python
# maxbot/tools/adapter_layer.py
class ToolAdapter:
    """ECC 工具到 MaxBot 工具的适配层"""
    
    @staticmethod
    def from_ecc_bash(command: str) -> dict:
        """将 ECC Bash 命令转换为 MaxBot terminal 调用"""
        return terminal
    
    @staticmethod
    def from_ecc_file_read(path: str) -> dict:
        """将 ECC 文件读取转换为 MaxBot read_file 调用"""
        return read_file
```

---

## 🧪 技能测试策略

### 测试金字塔

```
      /\
     /E2E\          - Agent 端到端测试 (5%)
    /------\
   /Integration\   - 技能与工具集成测试 (20%)
  /----------\
 /   Unit     \  - 技能单元测试 (75%)
/--------------\
```

### 测试覆盖目标

- **单元测试覆盖率：** 80%+ (每项技能)
- **集成测试覆盖率：** 60%+ (技能与工具交互)
- **E2E 测试覆盖率：** 30%+ (Agent 完整流程)

---

## 📊 技能元数据规范

### SKILL.md 格式扩展

基于 Hermes SKILL.md 格式，添加 MaxBot 特定字段：

```yaml
---
category: development          # 技能分类
priority: P0                  # 优先级
dependencies:                # 依赖技能
  - tdd-workflow
  - python-testing
tools_required:              # 需要的工具集
  - terminal
  - file_tools
  - web_tools
compatible_platforms:        # 兼容平台
  - cli
  - telegram
  - weixin
metrics:                    # 技能指标
  usage_count: 0
  success_rate: 0
---

# 技能内容...

## 工作流程

1. **步骤 1** - 描述
2. **步骤 2** - 描述

## 注意事项

- 技能使用时的注意事项
```

---

## 🔄 持续集成和自动化

### CI/CD 流程

```yaml
# .github/workflows/skills-test.yml
name: Skills Test Suite

on:
  push:
    paths:
      - 'maxbot/skills/**'
      - 'maxbot/agents/**'

jobs:
  test-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run skill tests
        run: |
          pytest tests/skills/ --cov=maxbot/skills --cov-report=xml
      - name: Check coverage
        run: |
          pip install coverage
          coverage report --fail-under=80
```

---

## 📈 成功指标

### 量化指标

| 指标 | 目标值 | 当前值 | 状态 |
|------|--------|--------|------|
| 核心技能实现数 | 4+ | 0 | ⏳ |
| 预定义 Agent 数 | 2+ | 0 | ⏳ |
| 技能测试覆盖率 | 80%+ | 0% | ⏳ |
| 技能与工具集成 | 100% | 0% | ⏳ |
| 文档完整性 | 100% | 0% | ⏳ |

### 质量指标

- 所有核心技能都有完整的 SKILL.md 文档
- 所有技能都有对应的测试用例
- 技能使用示例清晰易懂
- Agent 能够正确加载和执行技能

---

## 🚀 实施路线图

### Week 3 (2025-06-24 ~ 2025-06-30)

**Day 1-2 (06-24 ~ 06-25)**
- [ ] 完成架构文档
- [ ] 设置开发环境
- [ ] 创建技能目录结构

**Day 3-4 (06-26 ~ 06-27)**
- [ ] 实现 tdd-workflow 技能
- [ ] 实现 security-review 技能

**Day 5-7 (06-28 ~ 06-30)**
- [ ] 实现 python-testing 技能
- [ ] 实现 code-analysis 技能
- [ ] 编写基础测试

### Week 4 (2025-07-01 ~ 2025-07-07)

**Day 1-2 (07-01 ~ 07-02)**
- [ ] 实现 Planner Agent
- [ ] 实现 Security Reviewer Agent

**Day 3-4 (07-03 ~ 07-04)**
- [ ] 集成安全审查系统
- [ ] 技能与工具集成测试

**Day 5-7 (07-05 ~ 07-07)**
- [ ] 完善文档
- [ ] 性能测试
- [ ] 编写完成报告

---

## ⚠️ 风险和缓解措施

### 已识别的风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| ECC 技能适配复杂 | 高 | 中 | 先实现核心技能，逐步扩展 |
| 工具集不兼容 | 中 | 低 | 使用适配层转换 |
| 测试覆盖率不足 | 中 | 中 | TDD 方法，测试驱动 |
| 文档不完整 | 低 | 高 | 强制文档要求 |

---

## 📚 参考文档

| 文档 | 位置 |
|------|------|
| ECC 架构分析 | `/root/maxbot/phase1-architecture-analysis/ecc-architecture-analysis.md` |
| MaxBot 现状评估 | `/root/maxbot/phase1-architecture-analysis/maxbot-current-state-assessment.md` |
| 对比分析 | `/root/maxbot/phase1-architecture-analysis/maxbot-vs-ecc-comparison.md` |
| 第一阶段完成报告 | `/root/maxbot/phase1-architecture-analysis/phase1-completion-report.md` |
| MaxBot 进化计划 | `/root/maxbot/MAXBOT_EVOLUTION_PLAN.md` |

---

## ✅ 验收标准

### 技能系统验收

- [ ] 4 个核心技能全部实现并测试通过
- [ ] 2 个预定义 Agent 能够正确执行
- [ ] 技能测试覆盖率达到 80%+
- [ ] 所有技能都有完整的 SKILL.md 文档
- [ ] 技能与工具系统无缝集成
- [ ] CI/CD 流程配置完成

### 文档验收

- [ ] 架构设计文档完整
- [ ] 技能使用指南清晰
- [ ] Agent 使用示例丰富
- [ ] 完成报告详细

---

**文档状态：** ✅ 完成  
**下一步：** 实现核心技能  
**预计完成：** 2025-07-07
