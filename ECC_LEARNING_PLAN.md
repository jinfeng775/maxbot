# MaxBot 向 ECC 学习计划

> 学习目标：从 Everything Claude Code (ECC) 吸收先进理念，系统性改进 MaxBot。
>
> ECC 来源：https://github.com/affaan-m/everything-claude-code
>
> 版本参考：v1.10.0 | 140K+ stars | 多月高强度实战打磨
>
> **本次更新：** 2026-04-18

---

## 说明

**本文件按“ECC 能力映射”组织，不等同于 `MAXBOT_EVOLUTION_PLAN.md` 的 12 阶段主线编号。**

也就是说：
- 这里的 Phase 1~8 是 **对 ECC 能力模块的学习路线图**；
- 主线项目进度请以 `EVOLUTION_PROGRESS.md` 为准；
- 某些能力（例如 Hook / 安全审查 / 专用 Agent）已经在主线中提前或交叉落地，因此不会严格按本文编号顺序出现。

---

## 当前结论

截至当前代码状态，MaxBot 对 ECC 的对齐进度可以概括为：

- **Phase 1 Hook 自动化系统：✅ 已完成**
- **Phase 2 专用 Agent 体系：🟡 部分完成**
- **Phase 3 技能模块化：✅ 已完成**
- **Phase 4 持续学习与记忆：🟡 部分完成**
- **Phase 5 安全扫描集成：🟡 已有基础，但未达到 ECC 同等规模**
- **Phase 6~8：⏳ 尚未正式展开**

**如果直接回答“MaxBot 目前进度到哪一层了”**：

> **按 ECC 对齐主线看，已经推进到 Phase 4。**
> 其中 **持续学习闭环（LearningLoop / Instinct）MVP 已完成**，
> **长期记忆持久化系统进入前置整理与实施规划阶段**。

---

## 学习总览

| 阶段 | ECC 能力映射 | 当前 MaxBot 状态 | 说明 |
|------|-------------|------------------|------|
| Phase 1 | Hook 自动化系统 | ✅ 已完成 | `HookManager`、`HookEvent`、`builtin_hooks`、`agent_loop` 已接通 |
| Phase 2 | 专用 Agent 体系 | 🟡 部分完成 | 已有 `PlannerAgent`、`SecurityReviewerAgent`，但未形成完整 agent family |
| Phase 3 | 技能模块化 | ✅ 已完成 | 已有 `SkillManager`、SKILL.md 体系、4 个核心技能 |
| Phase 4 | 持续学习与记忆 | 🟡 部分完成 | `LearningLoop` MVP 已完成；Memory 分层持久化仍待正式实施 |
| Phase 5 | 安全扫描集成 | 🟡 基础已具备 | 已有 `security-review` 技能与 `SecurityReviewSystem`，但未达到 AgentShield 级规则规模 |
| Phase 6 | 验证循环与质量门 | ⏳ 未开始 | 尚未形成 ECC 风格 grader / pass@k / quality gates |
| Phase 7 | 多语言审查器 | ⏳ 未开始 | 尚未实现 TypeScript/Python/Go/Rust/Java 专用 reviewer 体系 |
| Phase 8 | 运算符工作流 | ⏳ 未开始 | 尚未建设 operator-workflows 自动化编排 |

---

## Phase 1：Hook 自动化系统 ✅

### 已落地能力

当前仓库中已存在以下核心实现：

- `maxbot/core/hooks/hook_events.py`
- `maxbot/core/hooks/hook_manager.py`
- `maxbot/core/hooks/builtin_hooks.py`
- `maxbot/core/hooks/__init__.py`
- `maxbot/core/agent_loop.py`

并且主循环中已经可以看到真实触发点：

- `HookEvent.SESSION_START`
- `HookEvent.PRE_TOOL_USE`
- `HookEvent.POST_TOOL_USE`
- `HookEvent.SESSION_END`
- `HookEvent.ERROR`

### 当前判断

这部分已经不再是“计划中待实现”，而是**实际落地完成**的能力模块。

---

## Phase 2：专用 Agent 体系 🟡

### 已落地能力

当前已存在的专用 Agent：

- `maxbot/agents/planner_agent.py`
- `maxbot/agents/security_reviewer_agent.py`

当前安全能力还向上延伸到了：

- `maxbot/security/security_review_system.py`

### 已覆盖的 ECC 思路

- planner：任务分析、分解、阶段化计划输出
- security-reviewer：静态规则扫描、安全风险分级、修复建议

### 尚未补齐的差距

与 ECC 目标相比，仍缺：

- architect 类 Agent
- code-reviewer 类 Agent
- tdd-guide 类 Agent
- build-error-resolver 类 Agent
- 更统一的 agent registry / base abstraction
- 多 agent 协作协议与调度层

### 当前判断

**不是未开始，而是“部分完成”。**
目前已具备原型能力，但距离 ECC 那种成体系的专用 agent 生态还有明显差距。

---

## Phase 3：技能模块化 ✅

### 已落地能力

当前技能系统核心入口：

- `maxbot/skills/__init__.py`（`Skill` / `SkillManager`）
- `maxbot/knowledge/skill_factory.py`

当前已存在的核心技能：

- `maxbot/skills/core/tdd-workflow/SKILL.md`
- `maxbot/skills/core/security-review/SKILL.md`
- `maxbot/skills/core/python-testing/SKILL.md`
- `maxbot/skills/core/code-analysis/SKILL.md`

### 已覆盖的 ECC 思路

- `SKILL.md` 组织方式
- YAML frontmatter + Markdown 内容承载
- 技能发现与匹配
- 技能注入主循环（`agent_loop.py` 已引入 `SkillManager`）

### 当前判断

这部分已经具备**可工作的核心形态**，可以判定为 **✅ 已完成**。

> 备注：当前仓库仍缺“专门针对技能系统的独立回归测试基线”；
> `tests/test_phase2.py` 当前能通过，但主要覆盖 code editor / analysis tooling，
> 不能完全等同于技能体系专项验收。

---

## Phase 4：持续学习与记忆 🟡

### 已落地能力：持续学习闭环

当前学习系统核心文件：

- `maxbot/learning/config.py`
- `maxbot/learning/observer.py`
- `maxbot/learning/pattern_extractor.py`
- `maxbot/learning/pattern_validator.py`
- `maxbot/learning/instinct_store.py`
- `maxbot/learning/instinct_applier.py`
- `maxbot/learning/learning_loop.py`

当前已完成的关键能力：

- Observation → Extraction → Validation → Persist 主链闭环
- 3 类 pattern：`tool_sequence` / `error_solution` / `user_preference`
- 统一 `PatternValidator` 验证链路
- error learning 可分类、可验证、可复用
- instinct matching / auto-apply 的置信度分层
- async worker 去重、重试、一致性验证
- instinct 生命周期治理

### 已验证结果

本次核验执行：

```bash
python3 -m pytest \
  tests/test_phase3.py \
  tests/test_phase3_learningloop_error_learning.py \
  tests/test_phase3_learningloop_hook_integration.py \
  tests/test_phase3_agent_loop_hooks.py \
  tests/test_phase3_main_loop_integration.py \
  tests/test_phase3_pattern_pipeline.py \
  tests/test_phase3_validator_pipeline.py \
  tests/test_phase3_error_learning_and_instincts.py \
  tests/test_phase3_async_and_governance.py \
  test_phase3_learning_system.py \
  test_phase3_observer_config.py -q
```

结果：

```text
39 passed in 4.48s
```

### 记忆系统现状

与“持续学习”相比，“长期记忆持久化”仍处在下一步：

现有基础设施：

- `maxbot/core/memory.py`
- `maxbot/sessions/__init__.py`

当前结论：

- **Learning / Instinct MVP：已完成**
- **Memory Persistence：主线已打通，MemPalace PoC 开始落地**
- **MemPalace：已纳入第四阶段后续适配计划，且 adapter 测试基线已建立**

### 当前判断

因此本阶段应标记为：

> **🟡 部分完成（Learning MVP 已完成，Memory Persistence 主线已打通，进入收尾）**

---

## Phase 5：安全扫描集成 🟡

### 已落地能力

当前已存在安全相关基础：

- `maxbot/skills/core/security-review/SKILL.md`
- `maxbot/agents/security_reviewer_agent.py`
- `maxbot/security/security_review_system.py`

### 已覆盖的 ECC 思路

- 安全审查技能
- 安全 reviewer agent
- 外部工具集成入口（如 bandit / safety / pip-audit）
- pre-commit 风格安全检查能力

### 仍未达到的目标

与 ECC / AgentShield 风格目标相比，还缺：

- 大规模规则库
- 独立 `/security-scan` 工作流命令
- 更系统的依赖审计与门禁策略
- 与验证循环的深度联动

### 当前判断

**已有基础，但不能算完成。**
更准确的状态是：**🟡 基础已具备，后续可升级为正式阶段交付。**

---

## Phase 6：验证循环与质量门 ⏳

### 目标

从 ECC 的 verification-loop 学习：

- grader types
- pass@k metrics
- quality gates
- checkpoint vs continuous evals

### 当前判断

仓库中还没有形成完整的 verification-loop / grading framework，
因此仍然是 **⏳ 未开始**。

---

## Phase 7：多语言审查器 ⏳

### 目标

从 ECC 的多语言 reviewers 学习：

- typescript-reviewer
- python-reviewer
- go-reviewer
- rust-reviewer
- java-reviewer

### 当前判断

当前只有通用安全审查与通用技能，
尚未演化出“按语言分工”的 reviewer 体系，故为 **⏳ 未开始**。

---

## Phase 8：运算符工作流 ⏳

### 目标

从 ECC 的 operator-workflows 学习：

- 自动化任务编排
- workspace-surface-audit
- customer-billing-ops
- google-workspace-ops

### 当前判断

当前仓库未见 operator-workflow 类自动化工作流体系，故为 **⏳ 未开始**。

---

## 建议的下一步优先级

1. **先完成 Phase 4 的长期记忆持久化主线**
   - 统一 memory / session / instinct 三者边界
   - 完成分层记忆模型与检索注入
   - 建立独立 Phase 4 memory 回归测试基线

2. **补强 Phase 2 / Phase 5 的“体系化程度”**
   - 专用 Agent 从 2 个扩展到 agent family
   - 安全扫描从基础能力升级为规则化、门禁化、命令化

3. **再进入 Phase 6~8 的 ECC 深水区能力**
   - verification loop
   - multi-language reviewers
   - operator workflows

---

## ECC 核心方法论（继续沿用）

1. **Agent-First** — 复杂任务尽量委派给专用 agent
2. **Test-Driven** — 先写测试，建立独立回归基线
3. **Security-First** — 默认做输入校验与安全边界控制
4. **Plan Before Execute** — 复杂阶段先做 preflight / implementation plan
5. **Gradual Adoption** — 小步快跑，按模块逐步吸收 ECC 能力

---

## 参考资料

- ECC 完整文档：https://github.com/affaan-m/everything-claude-code
- 主线进度：`EVOLUTION_PROGRESS.md`
- 主线计划：`MAXBOT_EVOLUTION_PLAN.md`
- 第三阶段完成报告：`phase3-continuous-learning/phase3-completion-report.md`
- 第四阶段前置报告：`phase3-continuous-learning/phase4-preflight-report.md`
- 第四阶段实施计划：`phase3-continuous-learning/phase4-implementation-plan.md`
