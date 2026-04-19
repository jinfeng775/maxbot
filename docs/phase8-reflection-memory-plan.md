# MaxBot Phase 8 Reflection / Metrics / Memory Promotion Implementation Plan

> **For Hermes:** Execute this plan phase-by-phase. Keep `MAXBOT_EVOLUTION_PLAN.md` and `EVOLUTION_PROGRESS.md` in sync while landing each workstream. Prefer TDD, commit in small checkpoints, and do not start Phase 9 until Phase 8 regression and docs are green.

**Goal:** 把 Phase 8 从“监控和分析”扩展为 MaxBot 部署态进化的基础设施入口：先落地 Reflection runtime、统一 metrics/trace、以及 memory / instinct / skill 升级治理三条主线，为 Phase 9 的 grader / quality gate 与 Phase 12 的 harness optimization / controlled self-evolver 打基础。

**Architecture:** 采用“三层基础设施”推进。第一层是运行时反思闭环（draft → critique → revise → accept）；第二层是结构化执行指标与 trace 采集，为后续评测与优化提供统一输入；第三层是长期知识治理，把 Memory、Instinct、Skill 三层升级规则显式化，避免长期信息继续混放。Phase 8 只建设基础设施与最小可交付能力，不直接引入高风险自我修改或 self-play。

**Tech Stack:** Python 3.11, pytest, existing `agent_loop` / `hooks` / `learning_loop` / `memory` / `multi_agent` modules, YAML config, SQLite-backed memory, existing test suite and docs workflow.

---

## 0. 当前状态审计结论

### 0.1 已完成的主线基础
- Phase 1~7 当前已可按完成追踪。
- 当前主线下一阶段是 **Phase 8：监控和分析**。
- 当前仓库已经有可复用基础：
  - `maxbot/learning/learning_loop.py`
  - `maxbot/core/memory.py`
  - `maxbot/knowledge/self_improver.py`
  - `maxbot/knowledge/review_board.py`
  - `maxbot/knowledge/harness_optimizer.py`
  - `maxbot/multi_agent/coordinator.py`

### 0.2 Phase 8 当前缺口
目前 `MAXBOT_EVOLUTION_PLAN.md` 对 Phase 8 的定义仍过于抽象，仅包含：
- 工具使用统计
- 智能体调用追踪
- 性能指标收集
- 用户行为分析

但从仓库现状与后续路线看，Phase 8 应补成：
1. **Reflection runtime**：为关键任务引入 critique / revise 闭环
2. **Metrics / Trace / Eval sample**：统一执行指标与回放样本
3. **Memory / Instinct / Skill promotion policy**：长期知识治理边界显式化

### 0.3 本阶段不做的事情
为了控制范围，Phase 8 明确不做：
- 不做模型权重训练
- 不做 self-play / adversarial loop 主线化
- 不做自动合并主分支的 self-modification
- 不做完整 Phase 9 grader / pass@k / quality gates
- 不做 Phase 12 harness optimization 正式闭环

---

## 1. 阶段目标与验收标准

## 1.1 阶段目标
Phase 8 完成后，MaxBot 应具备：
- 关键任务可配置地进入 reflection 流程
- 结构化记录 task / tool / reflection / memory 相关指标
- 能区分一条长期沉淀应进入 memory、instinct 还是 skill
- 为 Phase 9 的 benchmark / grader / quality gate 提供可复用输入

## 1.2 最小验收标准
- [ ] `reflection` 模块存在并可在主循环中受策略触发
- [ ] 至少一类任务可完成 draft → critique → revise → accept 闭环
- [ ] metrics / trace 采集管线有专项测试
- [ ] promotion policy 能对 memory / instinct / skill 做最小分类决策
- [ ] `MAXBOT_EVOLUTION_PLAN.md` 与 `EVOLUTION_PROGRESS.md` 已同步更新
- [ ] Phase 8 新增测试全部通过，且不破坏 Phase 3~7 关键回归

---

## 2. Workstream A：Reflection Runtime

### Task A1: 为 reflection 策略写失败测试

**Objective:** 先定义什么场景会进入 reflection，以及 revise 上限、跳过条件与 fail-closed 行为。

**Files:**
- Create: `tests/test_phase8_reflection_policy.py`
- Create: `tests/test_phase8_reflection_loop.py`
- Modify: `maxbot/core/agent_loop.py`

**Step 1: Write failing tests**
覆盖最小行为：
- `should_reflect(task_type, risk_level, tool_count, output_length)`
- critique 命中时进入 revise
- revise 次数达到上限后停止
- 低风险短回答可跳过 reflection
- strict 模式下 critique / revise 异常时 fail-closed
- `apply_to_task_types=["*"]` 时任意 task type 可进入策略

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_reflection_policy.py tests/test_phase8_reflection_loop.py -q
```
Expected: FAIL — reflection module / policy / loop 尚不存在

**当前收口状态（2026-04-19）**
- ✅ 已补 `tests/test_phase8_reflection_policy.py`
- ✅ 已补 wildcard task type 与 revision-limit 停止原因测试
- ✅ `ReflectionResult.stopped_reason` 已落地（`accepted` / `skipped` / `max_revisions_reached`）
- ✅ 当前专项结果：`tests/test_phase8_reflection_policy.py tests/test_phase8_reflection_loop.py -q` → `10 passed`

### Task A2: 实现 reflection 模块最小闭环

**Objective:** 新建反思模块，并让 `agent_loop` 能受策略控制触发一轮 critique / revise。

**Files:**
- Create: `maxbot/reflection/__init__.py`
- Create: `maxbot/reflection/policy.py`
- Create: `maxbot/reflection/critic.py`
- Create: `maxbot/reflection/loop.py`
- Modify: `maxbot/core/agent_loop.py`
- Modify: `maxbot/config/default_config.yaml`
- Modify: `maxbot/config/config_loader.py`

**Step 1: Add config defaults**
新增配置项：
- `reflection.enabled`
- `reflection.max_revisions`
- `reflection.min_output_chars`
- `reflection.high_risk_tool_threshold`
- `reflection.apply_to_task_types`

**Step 2: Implement policy**
- 根据任务类型、输出长度、工具数量、风险等级判定是否触发
- 提供 `ReflectionDecision` 结构

**Step 3: Implement critic + loop**
- `ReflectionCritic` 负责返回 critique 结果
- `ReflectionLoop` 执行 draft → critique → revise
- 第一版只要求支持单 critique agent，不要求多 reviewer 并行

**Step 4: Wire into agent loop**
- 在主输出形成后、最终返回前可配置插入 reflection
- 记录 revise 次数与最终状态

**Step 5: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_reflection_policy.py tests/test_phase8_reflection_loop.py -q
```
Expected: PASS

---

## 3. Workstream B：Metrics / Trace / Eval Sample

### Task B1: 为 metrics / trace 管线写失败测试

**Objective:** 定义 Phase 8 统一指标模型，避免后续 evaluator 与 optimizer 没有共同输入。

**Files:**
- Create: `tests/test_phase8_metrics_pipeline.py`
- Create: `tests/test_phase8_trace_store.py`

**Step 1: Write failing tests**
覆盖最小能力：
- 单次任务执行会生成结构化 metrics
- tool 使用次数、reflection 次数、memory hit/miss 可计数
- trace store 可写入 / 读取一次任务样本
- 多 agent 汇总时可记录 worker 相关字段

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_metrics_pipeline.py tests/test_phase8_trace_store.py -q
```
Expected: FAIL — metrics / trace store 尚不存在

### Task B2: 实现 metrics / trace 存储层

**Objective:** 提供 Phase 8 最小结构化指标与 trace 存储。

**Files:**
- Create: `maxbot/evals/__init__.py`
- Create: `maxbot/evals/metrics.py`
- Create: `maxbot/evals/trace_store.py`
- Modify: `maxbot/core/agent_loop.py`
- Modify: `maxbot/learning/learning_loop.py`
- Modify: `maxbot/multi_agent/coordinator.py`

**Step 1: Define metrics dataclasses**
至少包含：
- `task_id`
- `session_id`
- `tool_calls`
- `reflection_count`
- `revision_count`
- `memory_hits`
- `memory_misses`
- `instinct_matches`
- `worker_count`
- `success`
- `elapsed`

**Step 2: Define trace store**
- 支持保存单次执行 trace 为 JSON 文件或轻量目录结构
- 支持读取最近 N 条 trace
- 第一版不要求复杂索引

**Step 3: Wire into runtime**
- 主循环结束后写入任务 metrics / trace
- multi-agent 汇总结果追加 worker 维度指标
- learning loop 可记录 instinct 匹配情况

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_metrics_pipeline.py tests/test_phase8_trace_store.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ 已落地 `memory_hits / memory_misses / instinct_matches / worker_count` 四类结构化指标
- ✅ `TraceStore.latest()` 已补齐，最近一次 trace 读取路径已具备专项回归
- ✅ 当前专项结果：`tests/test_phase8_metrics_pipeline.py tests/test_phase8_trace_store.py -q` → `7 passed`

---

## 4. Workstream C：Memory / Instinct / Skill Promotion Policy

### Task C1: 为 promotion policy 写失败测试

**Objective:** 明确长期沉淀升级路径，避免 Memory / Instinct / Skill 继续混放。

**Files:**
- Create: `tests/test_phase8_memory_promotion_policy.py`
- Create: `tests/test_phase8_learning_memory_skill_boundary.py`
- Create: `tests/test_phase8_skill_distiller.py`

**Step 1: Write failing tests**
至少覆盖：
- 稳定用户偏好进入 memory
- 重复高成功率行为模式进入 instinct
- 结构化可复用流程升级为 skill draft
- 低质量或一次性样本不升级

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_memory_promotion_policy.py tests/test_phase8_learning_memory_skill_boundary.py tests/test_phase8_skill_distiller.py -q
```
Expected: FAIL — promotion policy / skill distiller 尚不存在

### Task C2: 实现 promotion policy 与 skill distiller

**Objective:** 把长期知识治理显式化，建立 Phase 8 的升级规则。

**Files:**
- Create: `maxbot/learning/promotion_policy.py`
- Create: `maxbot/knowledge/skill_distiller.py`
- Modify: `maxbot/core/memory.py`
- Modify: `maxbot/learning/learning_loop.py`
- Modify: `maxbot/skills/__init__.py`

**Step 1: Implement promotion heuristics**
第一版最小规则：
- 用户稳定偏好 / 项目事实 → memory
- 重复模式且高成功率 → instinct
- 有步骤、有边界、可复用 → skill draft

**Step 2: Implement skill distiller**
- 输入 observation / pattern / memory entry
- 输出结构化 skill draft（先不要求直接写入正式核心技能目录）

**Step 3: Wire into learning loop**
- learning loop 完成 pattern 验证后可选择触发 promotion decision
- 第一版以 decision + draft 输出为主，不要求自动 promote 到 runtime

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_memory_promotion_policy.py tests/test_phase8_learning_memory_skill_boundary.py tests/test_phase8_skill_distiller.py -q
```
Expected: PASS

---

## 5. Workstream D：Phase 8 文档、计划书与回归收口

### Task D1: 同步计划书与进度文档

**Objective:** 让主计划与进度文档显式反映“Phase 8 = 六机制基础设施入口”的真实执行口径。

**Files:**
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`
- Create: `docs/phase8-reflection-memory-plan.md`

**Step 1: Update MAXBOT_EVOLUTION_PLAN.md**
至少补充：
- Phase 8 当前状态：计划制定中 / 基础设施入口
- 细化为 reflection、metrics/trace、memory promotion 三条主线
- 明确下一份计划文档路径

**Step 2: Update EVOLUTION_PROGRESS.md**
至少补充：
- 当前阶段：Phase 8 计划制定中
- P0 下一步不再只有“监控 report”，而是三条主线
- 底部 duplicated summary 一并同步

**Step 3: Keep ECC mapping distinct**
如需引用 ECC，对应表述应继续放在 `ECC_LEARNING_PLAN.md` 口径下，避免与主线阶段混淆。

### Task D2: 建立 Phase 8 回归命令

**Objective:** 为后续实现与每个 checkpoint 提供稳定回归切片。

**Files:**
- Modify: `docs/phase8-reflection-memory-plan.md`
- Optionally Modify: `docs/UPGRADE_SUMMARY.md`

**Run:**
```bash
python3 -m pytest \
  tests/test_phase8_reflection_policy.py \
  tests/test_phase8_reflection_loop.py \
  tests/test_phase8_metrics_pipeline.py \
  tests/test_phase8_trace_store.py \
  tests/test_phase8_memory_promotion_policy.py \
  tests/test_phase8_learning_memory_skill_boundary.py \
  tests/test_phase8_skill_distiller.py -q
```

---

## 6. 依赖关系与执行顺序

建议执行顺序：
1. Workstream A：Reflection Runtime
2. Workstream B：Metrics / Trace / Eval Sample
3. Workstream C：Promotion Policy
4. Workstream D：Docs / Plan Sync / Regression Slice

原因：
- Reflection 与 metrics 最早产生可观测收益
- metrics 是后续 evaluator / optimizer 的共同前置
- promotion policy 需要借助前两者提供的运行时证据
- 文档同步必须在当前阶段收口后立即完成

---

## 7. Phase 8 结束后的衔接

Phase 8 完成后，下一阶段衔接如下：

### Phase 9（测试和质量保证）
从 Phase 8 接棒：
- grader / benchmark registry
- reflection quality gate
- controlled self-evolver sandbox gate

### Phase 12（持续改进）
依赖 Phase 8 / 9 成熟后推进：
- harness optimization
- evolutionary search
- controlled self-evolver adoption / rollback loop

### Research Branch
不进入 Phase 8：
- self-play
- adversarial task generation
- Agent0 风格自我提问机制

---

## 8. 最终交付物清单

Phase 8 计划阶段完成后，仓库中应至少新增或更新：

### 新文档
- `docs/phase8-reflection-memory-plan.md`

### 新模块（计划中）
- `maxbot/reflection/*`
- `maxbot/evals/metrics.py`
- `maxbot/evals/trace_store.py`
- `maxbot/learning/promotion_policy.py`
- `maxbot/knowledge/skill_distiller.py`

### 新测试（计划中）
- `tests/test_phase8_reflection_policy.py`
- `tests/test_phase8_reflection_loop.py`
- `tests/test_phase8_metrics_pipeline.py`
- `tests/test_phase8_trace_store.py`
- `tests/test_phase8_memory_promotion_policy.py`
- `tests/test_phase8_learning_memory_skill_boundary.py`
- `tests/test_phase8_skill_distiller.py`

### 已同步文档
- `MAXBOT_EVOLUTION_PLAN.md`
- `EVOLUTION_PROGRESS.md`

---

## 9. 推荐提交节奏

本计划落地时建议至少按以下 checkpoint 提交：

1. `docs: add phase8 reflection and memory promotion plan`
2. `feat: add phase8 reflection runtime`
3. `feat: add phase8 metrics and trace pipeline`
4. `feat: add phase8 promotion policy for memory instinct skill`
5. `docs: sync phase8 progress and evolution plan`

---

## 10. 结论

Phase 8 不应再被理解为一个单纯的“监控报表阶段”，而应定义为：

> **MaxBot 部署态进化的基础设施阶段。**

本阶段最重要的不是一下子把所有“进化机制”都做完，而是先落地三件能为后续阶段持续复用的基础能力：
- Reflection runtime
- Metrics / trace / evaluation sample
- Memory / instinct / skill promotion policy

只有这三层打稳，Phase 9 的质量门、Phase 12 的 harness optimization 与 controlled self-evolver 才有可验证、可维护、可审计的落点。
