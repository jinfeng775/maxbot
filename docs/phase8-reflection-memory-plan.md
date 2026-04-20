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

### Task B3: 补齐 eval sample registry 与 benchmark seed 基础

**Objective:** 把 Phase 8 标题中的 `eval sample` 从概念补到代码，基于已落地的 trace 输出可复用评测样本，为 Phase 9 grader / quality gate 提供输入地基。

**Files:**
- Create: `maxbot/evals/sample_store.py`
- Create: `tests/test_phase8_eval_sample_store.py`
- Create: `tests/test_phase8_eval_sample_config.py`
- Modify: `maxbot/evals/__init__.py`
- Modify: `maxbot/core/agent_loop.py`
- Modify: `maxbot/config/default_config.yaml`
- Modify: `maxbot/config/config_loader.py`
- Modify: `tests/test_phase8_metrics_pipeline.py`

**Step 1: Write failing tests**
至少覆盖：
- `EvalSampleStore.promote_trace()` 可把 trace 升级为 eval sample
- `EvalSampleStore.latest()` / `list_recent()` 顺序稳定
- `build_benchmark_tasks()` 可输出后续 grader / harness 可消费的任务种子
- `Agent.run()` 在启用 eval sample 导出时会把成功任务写入样本库
- `AgentConfig` / `ConfigLoader` / YAML 默认值对齐

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_eval_sample_store.py \
  tests/test_phase8_eval_sample_config.py \
  tests/test_phase8_metrics_pipeline.py::TestPhase8MetricsPipeline::test_agent_exports_successful_trace_to_eval_sample_store -q
```
Expected: FAIL — `sample_store` / 新配置字段 / runtime 导出链路尚未实现

**Step 3: Implement minimal export path**
- 基于 `TraceStore.write_trace()` 的结果生成 eval sample
- 为 sample 保留 `prompt / response / trace_id / labels / metadata`
- 先使用文件目录存储，不引入数据库或复杂索引
- benchmark seed 先输出轻量 `prompt + expected_output + metadata`

**Step 4: Wire into runtime/config**
- 新增 `eval_samples_enabled` 与 `eval_sample_store_dir`
- 同步 `AgentConfig`、`SessionConfig`、默认 YAML 与环境变量映射
- 仅在成功任务结束时导出 eval sample，避免把异常中间态噪音写入样本库

**Step 5: Run tests to verify pass**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_eval_sample_store.py \
  tests/test_phase8_eval_sample_config.py \
  tests/test_phase8_metrics_pipeline.py::TestPhase8MetricsPipeline::test_agent_exports_successful_trace_to_eval_sample_store -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `maxbot/evals/sample_store.py` 已落地
- ✅ trace → eval sample 导出链路已接入 `agent_loop.py`
- ✅ `eval_samples_enabled` / `eval_sample_store_dir` 默认值、加载链路与环境变量映射已补齐
- ✅ 当前专项结果：新增 eval sample slice → `6 passed`

### Task B4: 落 benchmark registry / grader groundwork

**Objective:** 基于已落地的 eval sample，补齐 Phase 9 前置地基：可复用 benchmark suite 注册、最小 grader、以及可执行的 benchmark quality gate。

**Files:**
- Create: `maxbot/evals/benchmark_registry.py`
- Create: `maxbot/evals/grader.py`
- Create: `tests/test_phase8_benchmark_registry.py`
- Create: `tests/test_phase8_grader.py`
- Modify: `maxbot/evals/__init__.py`
- Modify: `docs/phase8-reflection-memory-plan.md`

**Step 1: Write failing tests**
至少覆盖：
- `BenchmarkRegistry.register_from_eval_samples()` 可把 eval sample 落成 suite
- `BenchmarkRegistry.latest()` / `list_suites()` 顺序稳定
- `build_task_set()` 可产出 `harness_optimizer` 可消费的 benchmark task 列表
- `BenchmarkGrader.grade_task()` 支持 exact match 与 keyword coverage 两类最小评分
- `BenchmarkGrader.grade_suite()` 可汇总平均分 / 通过率
- `evaluate_benchmark_quality_gate()` 可按 pass rate / avg score fail-closed

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_benchmark_registry.py \
  tests/test_phase8_grader.py -q
```
Expected: FAIL — `benchmark_registry` / `grader` 尚不存在

**Step 3: Implement minimal benchmark suite registry**
- 先用 JSON 文件存储 suite，不引入数据库
- suite 至少保留：`suite_id` / `suite_name` / `source` / `tasks` / `metadata`
- 与 `EvalSampleStore.build_benchmark_tasks()` 对接，直接复用样本输出

**Step 4: Implement minimal grader and gate**
- `grade_task()` 第一版支持：
  - exact match
  - required keyword coverage
- `grade_suite()` 输出：
  - `tasks_total`
  - `passed_count`
  - `pass_rate`
  - `avg_score`
  - `results`
- `evaluate_benchmark_quality_gate()` 第一版按：
  - `min_pass_rate`
  - `min_avg_score`
  做 fail-closed

**Step 5: Run tests to verify pass**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_benchmark_registry.py \
  tests/test_phase8_grader.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `maxbot/evals/benchmark_registry.py` / `maxbot/evals/grader.py` 已落地
- ✅ benchmark suite 注册、task set 输出、最小 grader 与 benchmark quality gate 已补齐
- ✅ 当前专项结果：benchmark/grader slice → `4 passed`

### Task B5: 补 benchmark runner / report store / runtime quality gate integration

**Objective:** 把 Phase 8 的 benchmark registry + grader 从“静态工具”推进到“可执行闭环”，形成 suite 执行、结果持久化、quality gate 结果收口的最小主线。

**Files:**
- Create: `maxbot/evals/benchmark_runner.py`
- Create: `maxbot/evals/report_store.py`
- Create: `tests/test_phase8_benchmark_runner.py`
- Modify: `maxbot/evals/__init__.py`
- Modify: `docs/phase8-reflection-memory-plan.md`

**Step 1: Write failing tests**
至少覆盖：
- `BenchmarkRunner.run_suite()` 可接受 suite + outputs 并产出结构化 report
- report 中包含 `suite_id / pass_rate / avg_score / gate / results`
- `ReportStore.write_report()` / `latest()` / `list_recent()` 顺序稳定
- runner 可选自动把 report 写入 report store
- benchmark quality gate 失败时，report 中保留 fail-closed 原因

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_runner.py -q
```
Expected: FAIL — `benchmark_runner` / `report_store` 尚不存在

**Step 3: Implement minimal execution loop**
- `BenchmarkRunner` 只负责：
  - 调 grader
  - 调 quality gate
  - 组装 report
- 不引入真正模型调用；第一版直接消费外部传入 `outputs`
- 保持和 `BenchmarkGrader` / `BenchmarkRegistry` 解耦

**Step 4: Implement report store**
- 用 JSON 文件保存 report
- 至少保留：`report_id` / `suite_id` / `suite_name` / `pass_rate` / `avg_score` / `gate` / `results` / `created_at_ns`
- 提供 `read_report()` / `latest()` / `list_recent()`

**Step 5: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_runner.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `maxbot/evals/benchmark_runner.py` / `maxbot/evals/report_store.py` 已落地
- ✅ suite 执行、report 写入、latest/list_recent 与 benchmark quality gate report 收口已补齐
- ✅ 当前专项结果：benchmark runner slice → `3 passed`

### Task B6: 补 executor-backed benchmark runner 与 execution failure 收口

**Objective:** 把 benchmark runner 从“仅接受预先提供 outputs”推进到“可选执行器模式”，让 suite 能通过统一 executor 跑起来，并把 execution failure 明确纳入 fail-closed report。

**Files:**
- Modify: `maxbot/evals/benchmark_runner.py`
- Modify: `tests/test_phase8_benchmark_runner.py`
- Optionally Modify: `maxbot/evals/grader.py`

**Step 1: Write failing tests**
至少覆盖：
- `run_suite()` 可接收 `executor(task) -> output` 的执行器
- executor 模式下无需预先传 `outputs`
- 单任务执行异常时，report 进入 fail-closed
- report 中保留 `execution_failures` 与 gate 的阻断原因
- 成功任务仍可正常产出 grading result

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_runner.py -q
```
Expected: FAIL — runner 尚不支持 executor / execution_failures

**Step 3: Implement minimal executor path**
- 支持二选一输入：
  - `outputs`
  - `executor`
- 若同时给出，优先使用显式 `outputs`
- executor 异常时：
  - 收集到 `execution_failures`
  - 对该任务打 0 分
  - report gate fail-closed

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_runner.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `run_suite()` 已支持 `executor(task) -> output` 模式
- ✅ `execution_failures`、executor fail-closed 与报告字段已补齐
- ✅ 当前专项结果：benchmark runner slice → `5 passed`

### Task B7: 扩展 grader policy / suite enrichment / quality gate closure

**Objective:** 把 Phase 8 的评测基础设施从“最小可运行”继续推进到“更接近 Phase 9 可用”：支持更丰富的 grading policy、按样本特征构建 suite，以及更完整的 quality gate 阻断规则。

**Files:**
- Modify: `maxbot/evals/sample_store.py`
- Modify: `maxbot/evals/benchmark_registry.py`
- Modify: `maxbot/evals/grader.py`
- Modify: `maxbot/evals/benchmark_runner.py`
- Modify: `tests/test_phase8_benchmark_registry.py`
- Modify: `tests/test_phase8_grader.py`
- Modify: `tests/test_phase8_benchmark_runner.py`

**Step 1: Write failing tests**
至少覆盖：
- `register_from_eval_samples()` 支持按 `labels` / `metadata_filter` 筛选样本生成 suite
- suite metadata 中保留 `source_sample_count` 等最小 enrichment 信息
- `BenchmarkGrader.grade_task()` 支持：
  - `normalize_whitespace`
  - `min_keyword_coverage`
- `evaluate_benchmark_quality_gate()` 支持：
  - `min_tasks_total`
  - `max_execution_failures`
- runner 把 execution failure 交给统一 quality gate 收口，而不是写死分支理由

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_benchmark_registry.py \
  tests/test_phase8_grader.py \
  tests/test_phase8_benchmark_runner.py -q
```
Expected: FAIL — registry/grader/gate 还不支持 richer policy 与 enrichment

**Step 3: Implement minimal richer policy layer**
- sample store / benchmark registry 增加标签与 metadata 过滤
- benchmark task metadata 透传样本标签
- grader 增加 whitespace-normalized exact match 与 keyword coverage threshold
- quality gate 增加 `insufficient_tasks` / `execution_failures` 两类阻断原因
- runner 统一走 `evaluate_benchmark_quality_gate()`

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest \
  tests/test_phase8_benchmark_registry.py \
  tests/test_phase8_grader.py \
  tests/test_phase8_benchmark_runner.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ sample 过滤、suite enrichment、normalized exact match、keyword coverage threshold 已落地
- ✅ quality gate 对 `tasks_total` / `execution_failures` 的统一收口已补齐
- ✅ 当前专项结果：registry/grader/runner richer policy slice → `13 passed`

### Task B8: 补 quality gate profile 与 report comparison / trend summary

**Objective:** 把 Phase 8 评测基础设施再推进一层：补可复用 quality gate profile，并能比较两次 benchmark report，为 Phase 9 的质量门趋势分析打底。

**Files:**
- Modify: `maxbot/evals/grader.py`
- Modify: `maxbot/evals/report_store.py`
- Modify: `maxbot/evals/__init__.py`
- Create: `tests/test_phase8_report_profiles.py`
- Modify: `docs/phase8-reflection-memory-plan.md`

**Step 1: Write failing tests**
至少覆盖：
- `get_quality_gate_policy("strict|standard|relaxed")` 返回稳定 profile
- `evaluate_benchmark_quality_gate()` 支持直接接收 profile name
- `ReportStore.compare_reports(old_id, new_id)` 输出：
  - `pass_rate_delta`
  - `avg_score_delta`
  - `passed_changed`
- `ReportStore.trend_summary(limit=N)` 输出最近 N 次 report 的趋势摘要

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_report_profiles.py -q
```
Expected: FAIL — 还不存在 profile / report comparison / trend summary 能力

**Step 3: Implement minimal profile + comparison layer**
- 先内置三套 gate profile：
  - `strict`
  - `standard`
  - `relaxed`
- report store 增加：
  - `compare_reports(old_id, new_id)`
  - `trend_summary(limit=...)`
- comparison 只做数值 delta 与 pass/fail 翻转，不做复杂 root cause 分析

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_report_profiles.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `strict / standard / relaxed` 三套 quality gate profile 已落地
- ✅ `ReportStore.compare_reports()` / `trend_summary()` 已补齐
- ✅ 当前专项结果：report profile slice → `4 passed`

### Task B9: 补 composable grading policy 与多报告趋势聚合

**Objective:** 在已有 profile 与 report comparison 基础上，继续向 Phase 9 入口推进：支持更细粒度 rule-level 评分拆解，以及跨多次 report 的聚合摘要。

**Files:**
- Modify: `maxbot/evals/grader.py`
- Modify: `maxbot/evals/report_store.py`
- Create/Modify: `tests/test_phase8_report_profiles.py`
- Modify: `docs/phase8-reflection-memory-plan.md`

**Step 1: Write failing tests**
至少覆盖：
- `grade_task()` 输出 rule-level breakdown（如 exact / keyword）
- `grade_suite()` 输出 aggregated rule summary
- `trend_summary(limit=N)` 给出 average deltas / latest gate profile 概览

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_report_profiles.py -q
```
Expected: FAIL — 还未支持组合式评分拆解与趋势聚合

**Step 3: Implement minimal composition layer**
- 先做 deterministic rule breakdown，不引入 LLM judge
- trend 聚合先做 pass_rate / avg_score / gate pass 次数统计

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_report_profiles.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `BenchmarkGrader.grade_task()` 已支持 `grading_rules` 组合式评分与 rule-level breakdown
- ✅ `BenchmarkGrader.grade_suite()` 已输出 `rule_summary`（含 `avg_score` / `avg_weighted_score` / `avg_pass_rate`）
- ✅ `BenchmarkRunner.run_suite()` 已把 `rule_summary` 写入 report
- ✅ `ReportStore.compare_reports()` 已支持 `rule_summary_delta`
- ✅ `ReportStore.trend_summary()` 已支持 `avg_pass_rate_delta` / `avg_score_delta` / 聚合后的 `rule_summary`
- ✅ 当前专项结果：`tests/test_phase8_grader.py tests/test_phase8_report_profiles.py -q` → `11 passed`

### Task B10: 补 suite selection policy / coverage summary / report-level operational highlights

**Objective:** 在已有 composable grading 与 multi-report aggregation 基础上，继续向 Phase 9 运营层推进：让 suite 具备更明确的选择策略与覆盖摘要，并让 report / trend 能直接给出 weakest / strongest / changed rules 这种运营视角高亮。

**Files:**
- Modify: `maxbot/evals/benchmark_registry.py`
- Modify: `maxbot/evals/benchmark_runner.py`
- Modify: `maxbot/evals/report_store.py`
- Modify: `tests/test_phase8_benchmark_registry.py`
- Modify: `tests/test_phase8_report_profiles.py`
- Modify: `docs/phase8-reflection-memory-plan.md`

**Step 1: Write failing tests**
至少覆盖：
- `register_from_eval_samples()` 写入 `selection_policy` 与 `coverage_summary`
- `build_task_set()` 支持 `suite_metadata_filter`
- `run_suite()` 产出 report-level `summary`
- `compare_reports()` / `trend_summary()` 输出 `changed_rules`
- latest report/trend 能输出 `weakest_rule` / `strongest_rule`

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py -q
```
Expected: FAIL — 还未支持 suite selection / report operational highlights

**Step 3: Implement minimal operational layer**
- suite metadata 中记录 labels / metadata_filter / limit
- 基于样本 labels 与 metadata 做覆盖摘要
- report summary 先提供 deterministic weakest/strongest rule 高亮
- changed rules 先基于 rule summary delta 计算，不做复杂 RCA

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py tests/test_phase8_benchmark_runner.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `BenchmarkRegistry.register_from_eval_samples()` 已记录 `selection_policy` / `coverage_summary`
- ✅ `BenchmarkRegistry.build_task_set()` 已支持 `suite_metadata_filter`
- ✅ `BenchmarkRunner.run_suite()` 已输出 report-level `summary`
- ✅ `ReportStore.compare_reports()` / `trend_summary()` 已支持 `changed_rules`
- ✅ report/trend 已可输出 `weakest_rule` / `strongest_rule`
- ✅ 当前专项结果：`tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py tests/test_phase8_benchmark_runner.py -q` → `17 passed`

### Task B11: 补 suite auto-assembly 与 quality gate operating modes

**Objective:** 在已有 suite selection policy 与 report operational highlights 基础上，继续向 Phase 9 入口推进：支持多策略样本自动组装 suite，并让 quality gate 返回更明确的 operating mode / blocking summary / advisory 字段。

**Files:**
- Modify: `maxbot/evals/benchmark_registry.py`
- Modify: `maxbot/evals/grader.py`
- Modify: `tests/test_phase8_benchmark_registry.py`
- Modify: `tests/test_phase8_report_profiles.py`
- Modify: `docs/phase8-reflection-memory-plan.md`

**Step 1: Write failing tests**
至少覆盖：
- `auto_assemble_suite()` 基于多条 selection policy 组装 suite
- suite metadata 记录 assembly policy / dedup 结果
- quality gate 返回 `operating_mode`
- quality gate 返回 `blocking_summary`
- quality gate 返回 `advisories`

**Step 2: Run tests to verify failure**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py -q
```
Expected: FAIL — 还未支持 auto-assembly 与 gate operating fields

**Step 3: Implement minimal operating layer**
- auto assembly 先复用 sample filtering，不引入复杂调度器
- assembly metadata 先记录 policy 数量与去重结果
- gate operating fields 先基于现有 blocking reason / rule summary 生成
- advisory 输出保持 deterministic，不做 LLM 解释

**Step 4: Run tests to verify pass**
Run:
```bash
python3 -m pytest tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py tests/test_phase8_benchmark_runner.py -q
```
Expected: PASS

**当前收口状态（2026-04-19）**
- ✅ `BenchmarkRegistry.auto_assemble_suite()` 已支持多 selection policy 自动组装
- ✅ suite metadata 已记录 `assembly_policy`
- ✅ quality gate 已返回 `operating_mode` / `blocking_summary` / `advisories`
- ✅ 当前专项结果：`tests/test_phase8_benchmark_registry.py tests/test_phase8_report_profiles.py tests/test_phase8_benchmark_runner.py -q` → `19 passed`

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
