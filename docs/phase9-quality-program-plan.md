# MaxBot Phase 9 Quality Program Launch Plan

> **For Hermes:** Execute this as the Phase 8 收官到 Phase 9 启动过渡计划. Keep `MAXBOT_EVOLUTION_PLAN.md` and `EVOLUTION_PROGRESS.md` in sync while landing each slice. Use TDD, keep commits phase-bounded, and push after each verified checkpoint.

**Goal:** 正式结束“无限扩张的 Phase 8”观感，把当前已经成型的评测/质量门基础设施收口为 Phase 8 基础层，并启动 **Phase 9：测试和质量保证 / 质量计划运营层**，先落地可复用 suite policy bundle 与 gate policy bundle 的正式运行层。

**Architecture:** 采用“两段式切换”推进。第一段先做 **Phase 8 封板**：明确哪些内容属于基础设施层，哪些内容从现在开始记入 Phase 9。第二段启动 **Phase 9 质量计划运营层**：围绕 named suite bundles、named gate bundles、blocking/advisory 语义、report summary 联动构建第一批可运营策略集。避免继续把所有质量门相关工作都挂在 Phase 8 名下。

**Tech Stack:** Python 3.11, pytest, existing `maxbot/evals/*`, JSON-file-backed suite/report stores, YAML config/docs workflow, git + GitHub push flow.

---

## 0. 当前状态审计结论

### 0.1 为什么现在要切段
当前仓库真实状态已经表明：
- Phase 8 不再只是“监控和分析”
- 已落地内容已经覆盖：
  - reflection runtime
  - metrics / trace / eval sample
  - promotion policy
  - benchmark registry / grader / runner / report store
  - profile / comparison / trend
  - composable grading / breakdown / aggregation
  - suite selection / auto-assembly / operating summaries
  - suite policy bundle groundwork

这意味着 **Phase 8 已经演化成“部署态进化基础设施总装阶段”**。
如果继续把新的 quality program work 全挂在 Phase 8 下，会持续造成：
- 阶段名不变但内容越来越像 Phase 9
- 用户观感上像“总在第八阶段打转”
- 路线图阶段边界越来越模糊

### 0.2 切段原则
从本轮开始采用新的边界：

#### 仍属于 Phase 8 的内容
- 基础 runtime / metrics / samples / benchmark infra
- deterministic grader / runner / report base
- suite assembly / report operational summary 的基础实现

#### 从现在开始记入 Phase 9 的内容
- 可运营的 suite strategy set
- 可运营的 gate policy bundle
- blocking / advisory / weakest-rule / changed-rules 联动规则
- 更正式的 quality review / release gating 语义

### 0.3 本轮目标
本轮不再继续“名义上推进 Phase 8”。
本轮目标是：
1. **文档上正式把当前节点定义为 Phase 8 收官节点 / Phase 9 启动点**
2. **实现第一批 Phase 9 运营层 bundle**
3. **提交时使用 Phase 9 口径**

---

## 1. 切段后的阶段定义

### Phase 8：部署态进化基础设施（封板口径）
封板结论：
- Reflection / metrics / trace / eval sample / promotion / benchmark infra 已具备最小可用闭环
- suite assembly / operating summary / bundle groundwork 已具备
- 后续不再继续无限向 Phase 8 里堆运营规则

### Phase 9：测试和质量保证 / 质量计划运营层（启动口径）
从当前开始，Phase 9 首批内容包括：
1. named suite policy bundles
2. named gate policy bundles
3. report summary 与 gate blocking/advisory 联动
4. 面向发布/验收的质量门语义

---

## 2. Workstream A：Phase 8 封板与 Phase 9 启动文档同步

### Task A1: 更新路线图与进度文档的切段口径

**Objective:** 在文档层正式承认当前节点已经从 Phase 8 基础设施层进入 Phase 9 运营层，消除“为什么还在第八阶段”的管理歧义。

**Files:**
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`
- Modify: `docs/phase8-reflection-memory-plan.md`
- Create: `docs/phase9-quality-program-plan.md`

**Step 1: Update `MAXBOT_EVOLUTION_PLAN.md`**
至少补充：
- Phase 8 = 基础设施封板
- Phase 9 = 质量计划运营层启动
- 将 suite/gate bundles 的“groundwork”从 Phase 8 描述迁移为“Phase 9 first-wave input”

**Step 2: Update `EVOLUTION_PROGRESS.md`**
至少补充：
- 当前阶段改为：Phase 8 基础设施已封板，Phase 9 启动中
- P0 下一步改为：named gate bundles / report-linked blocking semantics

**Step 3: Create `docs/phase9-quality-program-plan.md`**
写明：
- Phase 9 的首批策略集
- 目标 bundle 名称
- 测试命令
- 每轮提交口径

---

## 3. Workstream B：Named Suite Policy Bundles（Phase 9 首批）

### Task B1: 为 suite strategy set 补失败测试

**Objective:** 让 suite bundle 不只是“能拿到一个 bundle 名”，而是具备明确的策略集语义与元数据。

**Files:**
- Modify: `tests/test_phase8_benchmark_registry.py`
- Modify: `maxbot/evals/benchmark_registry.py`

**Step 1: Write failing tests**
至少覆盖：
- `get_suite_policy_bundle("phase9_release_core")`
- `list_suite_policy_bundles()`
- bundle 元数据包含：
  - `description`
  - `selection_policies`
  - `target_phase`
- `auto_assemble_suite_from_bundle()` 回写这些元数据到 suite

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py -q
```
Expected: FAIL — 还未支持 richer suite bundle metadata/listing

### Task B2: 实现 named suite strategy set

**Objective:** 为 Phase 9 提供第一批真正可复用的 suite 策略集，而不是只有硬编码列表。

**Files:**
- Modify: `maxbot/evals/benchmark_registry.py`
- Modify: `maxbot/evals/__init__.py`

**Step 1: Add suite bundle registry structure**
建议结构：
- `name`
- `description`
- `target_phase`
- `selection_policies`

**Step 2: Add helpers**
新增：
- `get_suite_policy_bundle(name)`
- `list_suite_policy_bundles()`

**Step 3: Enrich assembled suite metadata**
至少写入：
- `bundle_name`
- `bundle_description`
- `target_phase`

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py -q
```
Expected: PASS

**当前收口状态（2026-04-20）**
- ✅ `get_suite_policy_bundle()` 已支持 richer bundle metadata
- ✅ `list_suite_policy_bundles()` 已落地
- ✅ `auto_assemble_suite_from_bundle()` 已回写 `bundle_description` / `target_phase`
- ✅ suite bundle 已补齐 `recommended_gate_policy` / `compatible_gate_policies`
- ✅ `evaluate_suite_gate_compatibility()` 已落地，可返回 `recommended` / `compatible` / `incompatible`
- ✅ 当前专项结果：`tests/test_phase8_benchmark_registry.py -q` → `9 passed`

---

## 4. Workstream C：Named Gate Policy Bundles（Phase 9 首批）

### Task C1: 为 gate bundle 补失败测试

**Objective:** 让 gate profile 从简单阈值字典升级为更正式的 policy bundle 入口。

**Files:**
- Modify: `tests/test_phase8_report_profiles.py`
- Modify: `maxbot/evals/grader.py`

**Step 1: Write failing tests**
至少覆盖：
- `list_quality_gate_policies()`
- `get_quality_gate_policy("release_blocker")`
- gate result 返回：
  - `operating_mode`
  - `blocking_summary`
  - `advisory_summary`
- `release_blocker` / `advisory` / `standard` 的语义差异

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_report_profiles.py -q
```
Expected: FAIL — 还未支持 richer gate bundle listing / advisory summary

### Task C2: 实现更正式 gate bundle 入口

**Objective:** 为 Phase 9 提供第一批 named gate bundles。

**Files:**
- Modify: `maxbot/evals/grader.py`
- Modify: `maxbot/evals/__init__.py`

**Step 1: Extend gate bundle set**
新增或重构到至少：
- `advisory`
- `standard`
- `strict`
- `release_blocker`

**Step 2: Add helpers**
新增：
- `list_quality_gate_policies()`

**Step 3: Add summary fields**
在 gate result 中新增：
- `advisory_summary`
- optional `policy_description`

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_report_profiles.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `list_quality_gate_policies()` 已落地
- ✅ `get_quality_gate_policy()` 已升级为 richer policy profile（`description` / `mode` / `thresholds`）
- ✅ 已新增 `advisory` 与 `release_blocker` 两类 named gate bundles
- ✅ gate result 已输出 `advisory_summary` / `policy_description`
- ✅ 当前专项结果：`tests/test_phase8_report_profiles.py -q` → `10 passed`

### Task C3: 补齐 blocking/advisory/report 联动与 release_blocker 语义

**Objective:** 让 Phase 9 质量门不只会“给出一个 passed/failed”，而是能把阻断原因、最弱规则、建议动作、release 语义以及跨报告的阻断状态变化一起结构化输出。

**Files:**
- Modify: `tests/test_phase8_grader.py`
- Modify: `tests/test_phase8_report_profiles.py`
- Modify: `maxbot/evals/grader.py`
- Modify: `maxbot/evals/benchmark_runner.py`
- Modify: `maxbot/evals/report_store.py`

**Step 1: Write failing tests**
至少覆盖：
- `release_blocker` 返回：
  - `policy_mode`
  - `blocking_summary.severity`
  - `blocking_summary.weakest_rule`
  - `blocking_summary.blocking_rule`
  - `blocking_summary.recommended_action`
  - `release_summary`
- report summary 回写 gate 运营字段
- `compare_reports()` 输出 blocking transition
- `trend_summary()` 输出 latest blocking reason / advisories / release summary

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_grader.py::test_release_blocker_gate_emits_operational_blocking_and_release_summary \
  tests/test_phase8_report_profiles.py::test_report_store_tracks_blocking_transitions_and_release_gate_summary -q
```
Expected: FAIL — 尚未输出 release blocker 运营语义与跨报告阻断变更摘要

**Step 3: Implement runtime/report linkage**
至少新增：
- gate-level weakest/blocking rule selection
- recommended action derivation
- release blocker summary
- runner summary 回写 gate operational fields
- report diff/trend 输出 blocking/advisory 变更

**Step 4: Re-run focused validation**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_grader.py::test_release_blocker_gate_emits_operational_blocking_and_release_summary \
  tests/test_phase8_report_profiles.py::test_report_store_tracks_blocking_transitions_and_release_gate_summary -q
```
Expected: PASS

**当前收口状态（2026-04-20，第二刀）**
- ✅ `release_blocker` 已输出 `policy_mode` / `blocking_summary.severity` / `blocking_rule` / `recommended_action`
- ✅ gate 已输出 `release_summary`（仅在 `release_blocker` 且无阻断原因时标记 `ready=True`）
- ✅ `BenchmarkRunner` summary 已回写 gate 运营字段
- ✅ `ReportStore.compare_reports()` 已输出 `blocking_reason_changed` / `blocking_transition`，并区分 policy shift 与真实质量回归
- ✅ `ReportStore.trend_summary()` 已输出 `latest_blocking_reason` / `latest_advisories` / `summary.release_summary`
- ✅ 新增 suite/gate 对齐后的 `quality_program` 汇总：支持 `upgrade_recommended` / `quality_ready` / `release_ready` / `realignment_required` / `blocking_issues_remaining` 状态与 `next_action`
- ✅ `quality_program` 语义已修正为：非 release bundle 在推荐 gate 且通过时进入 `quality_ready`，不再错误落入 `blocking_issues_remaining`
- ✅ 非推荐但已失败的兼容 gate 会继续保留 `blocking_issues_remaining`，避免被误降级为 `upgrade_recommended`
- ✅ suite 已优先使用持久化 `assembly_policy` 中的 gate guidance，避免 live bundle 默认值回灌历史 suite
- ✅ `ReportStore.compare_reports()` / `trend_summary()` 已补齐 quality program transition 与 latest quality program 摘要，并避免 no-bundle 场景下产生伪 transition（含 legacy 报告兼容与 bundle-backed legacy quality program 重建）
- ✅ 已新增“legacy bundle 元数据不回灌 live gate guidance”回归，避免历史报告被当前 bundle 默认值重写
- ✅ 已新增“release_ready 不越权外溢到 no-bundle / incompatible suite”回归，避免质量计划状态与 release gate 结果自相矛盾
- ✅ 已新增“stricter compatible gate 通过时不误报 release_ready”回归，避免 `quality_ready` 与 `release_ready` 同时为真
- ✅ 定向 RED→GREEN 验证结果：新增 quality program 切片已全部收口（当前 `tests/test_phase8_report_profiles.py -q` → `16 passed`，`tests/test_phase8_benchmark_runner.py -q` → `14 passed`）

---

## 5. Workstream D：Phase 9 启动回归与提交

### Task D1: 运行专项与回归

**Run:**
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py tests/test_phase8_benchmark_runner.py -q
```

然后运行：
```bash
python3 -m pytest \
  tests/test_phase8_reflection_loop.py \
  tests/test_phase8_reflection_policy.py \
  tests/test_phase8_metrics_pipeline.py \
  tests/test_phase8_trace_store.py \
  tests/test_phase8_eval_sample_store.py \
  tests/test_phase8_eval_sample_config.py \
  tests/test_phase8_benchmark_registry.py \
  tests/test_phase8_grader.py \
  tests/test_phase8_benchmark_runner.py \
  tests/test_phase8_report_profiles.py \
  tests/test_phase8_memory_promotion_policy.py \
  tests/test_phase8_learning_memory_skill_boundary.py \
  tests/test_phase8_skill_distiller.py \
  tests/test_iteration_limit_defaults.py -q
```

### Task D2: Git 提交口径

本轮提交不再继续写成“第八阶段继续增强”。
在当前收口口径下，建议直接使用：

```bash
git commit -m "feat: 完成第九阶段质量计划运营层收口"
```

如果强调 quality program / suite-gate 联动，也可使用：

```bash
git commit -m "feat: 完成第九阶段质量计划与报告联动收口"
```

---

## 6. 结论

本轮已完成的收口结论是：

> **Phase 8 已封板，Phase 9 首批质量计划运营层（suite bundle / gate bundle / quality program / report linkage）已完成，并按当前用户要求停止在第 9 阶段。**
