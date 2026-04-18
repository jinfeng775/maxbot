# MaxBot Phase 4 Step 5 / Phase 5 / Phase 6 / Phase 7 Consolidated Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan phase-by-phase, commit after each phase, and sync `MAXBOT_EVOLUTION_PLAN.md` after each phase lands.

**Goal:** 在第四阶段主线已打通的基础上，继续完成 Phase 4 的 MemPalace 外接记忆适配 PoC，同时推进 Phase 5（安全与验证系统）、Phase 6（多智能体协作）、Phase 7（Hook 系统补缺与正式验收），并为后续“所有阶段完成后的全仓复审”建立统一执行口径。

**Architecture:** 采用“先计划、再最小可交付实现、再测试回归、再文档同步、再单阶段提交”的方式推进。Phase 4 的 MemPalace 先以 CLI / adapter PoC 方式接入，不直接替换 MaxBot 内置 Memory；Phase 5 先把安全扫描系统做成可执行工作流和质量门；Phase 6 先收敛到真实可用的多智能体协调与验收基线；Phase 7 则把现有 Hook 体系中的 TODO 和未触发事件补齐并正式标记完成。

**Tech Stack:** Python 3.11, pytest, SQLite, existing MaxBot agent loop / memory system / security reviewer / hook system / multi-agent modules, MemPalace CLI + optional MCP integration.

---

## 0. 当前代码审查结论（本计划依据）

### Phase 4（MemPalace）当前状态
- 已完成：内置 `Memory` 分层模型、检索、注入、治理、边界测试、端到端测试。
- 已有文档：
  - `docs/phase4-memory-boundary.md`
  - `docs/phase4-step1-memory-boundary-implementation-plan.md`
  - `phase3-continuous-learning/phase4-preflight-report.md`
  - `phase3-continuous-learning/phase4-implementation-plan.md`
- 已确认 MemPalace 外部能力：
  - CLI：`mempalace init/mine/search/wake-up/mcp/hook`
  - MCP server：29 个工具
  - local-first / semantic search / wake-up context
- 当前仓库里还没有任何 `MemPalaceAdapter` 或本地集成实现。

### Phase 5 当前状态
- 已有：
  - `maxbot/security/security_review_system.py`
  - `maxbot/agents/security_reviewer_agent.py`
- 已有部分测试基础，但仍停留在“工具/类存在”的程度：
  - `tests/test_phase5_fixes.py`
- 当前缺口：
  - 没有统一安全扫描入口工具 / workflow
  - 没有质量门判定对象
  - 没有明确的依赖审计与结果汇总层
  - 没有端到端测试证明“可作为阶段交付物”

### Phase 6 当前状态
- 已有：
  - `maxbot/multi_agent/__init__.py` 中较完整的 orchestrator / delegate 草案
  - `maxbot/multi_agent/coordinator.py`
  - `maxbot/multi_agent/worker.py`
  - `maxbot/tools/multi_agent_tools.py`
  - `tests/test_multi_agent.py`
- 当前缺口：
  - 实现出现重复/分裂（`__init__.py` 与 `coordinator.py` / `worker.py` 两套形态）
  - Worker 分配策略极简
  - 缺少“能力匹配 / 依赖调度 / 汇总行为”的严格测试
  - 工具层 `spawn_agent` 能用，但还没形成“阶段完成”的统一口径

### Phase 7 当前状态
- 已有：
  - `maxbot/core/hooks/hook_events.py`
  - `maxbot/core/hooks/hook_manager.py`
  - `maxbot/core/hooks/builtin_hooks.py`
  - `tests/test_hooks.py`
  - `tests/test_phase3_learningloop_hook_integration.py`
  - `tests/test_phase3_agent_loop_hooks.py`
- Agent 主循环已触发：
  - `SESSION_START`
  - `PRE_TOOL_USE`
  - `POST_TOOL_USE`
  - `SESSION_END`
  - `ERROR`
- 当前缺口：
  - `PRE_COMPACT` / `POST_COMPACT` 还没有接到 `_compress_context()`
  - `HookManager.set_profile()` 里的 `minimal/strict` 逻辑仍是 TODO
  - 部分 builtin hooks 仍只有日志，没有更明确的执行语义

### 总体执行原则
1. 每个阶段单独形成“计划 → 实现 → 测试 → 文档 → commit”。
2. 每阶段完成后更新：
   - `MAXBOT_EVOLUTION_PLAN.md`
   - `EVOLUTION_PROGRESS.md`
   - 必要时同步 `ECC_LEARNING_PLAN.md`
3. 每阶段完成后立即 GitHub 提交。
4. 全部阶段完成后，再从 Phase 1 开始做全仓复审。

---

## 1. Phase 4 Step 5：MemPalace Adapter / PoC

### 验收目标
- 新增 MemPalace 适配层，能以本地 CLI 方式完成：
  - `mine`
  - `search`
  - `wake-up`
- Agent 可选择性读取 MemPalace 检索结果并注入 prompt
- 不替换内置 `Memory`
- 增加 PoC 测试和文档

### 任务 1.1：为 MemPalace adapter 写失败测试
**Files:**
- Create: `tests/test_phase4_mempalace_adapter.py`
- Create: `tests/test_phase4_mempalace_integration.py`

**Step 1: 写测试覆盖最小接口**
至少覆盖：
- `MemPalaceAdapter.is_available()`
- `MemPalaceAdapter.search(query, wing=None, limit=5)`
- `MemPalaceAdapter.wake_up(wing=None)`
- CLI 不存在时的 graceful fallback
- Agent 在启用 MemPalace 时会把外部结果拼进 memory context

**Step 2: 运行测试确认失败**
```bash
python3 -m pytest tests/test_phase4_mempalace_adapter.py tests/test_phase4_mempalace_integration.py -q
```

### 任务 1.2：实现 MemPalaceAdapter
**Files:**
- Create: `maxbot/memory/mempalace_adapter.py`
- Modify: `maxbot/core/agent_loop.py`
- Modify: `maxbot/config/config_loader.py`
- Modify: `maxbot/config/default_config.yaml`

**最小实现要求：**
- 配置项：
  - `session.mempalace_enabled: bool = False`
  - `session.mempalace_path: str | None = None`
  - `session.mempalace_wing: str | None = None`
- adapter 通过 `subprocess.run()` 调 CLI：
  - `mempalace search`
  - `mempalace wake-up`
- search 返回结构化结果；wake-up 返回文本
- `agent_loop._build_memory_context()` 在内置 Memory 之后追加 MemPalace 外部上下文（受预算限制）

### 任务 1.3：补文档与计划同步
**Files:**
- Modify: `phase3-continuous-learning/phase4-implementation-plan.md`
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`

**文档要求：**
- 明确 Phase 4 已完成内置主线
- MemPalace PoC 为第四阶段后半段交付
- 标明“内置 Memory + 外接 MemPalace”为双层结构

### 任务 1.4：验收与提交
**Run:**
```bash
python3 -m pytest tests/test_phase4_mempalace_adapter.py tests/test_phase4_mempalace_integration.py -q
python3 -m pytest tests/test_phase4_memory_boundary_model.py tests/test_phase4_memory_boundary_integration.py tests/test_phase4_memory_injection.py tests/test_phase4_memory_governance.py tests/test_phase4_memory_instinct_boundary.py tests/test_phase4_memory_end_to_end.py -q
```

**Commit:**
```bash
git add -A
git commit -m "feat: add mempalace adapter for phase4"
git push origin main
```

---

## 2. Phase 5：安全和验证系统

### 验收目标
- 提供可统一调用的安全扫描工作流
- 支持至少 bandit / safety / pip-audit 的统一结果收敛
- 引入质量门判定（critical/high 可阻断）
- 有端到端测试证明“可以作为阶段交付物”

### 任务 2.1：写失败测试
**Files:**
- Create: `tests/test_phase5_security_pipeline.py`
- Create: `tests/test_phase5_quality_gate.py`

**测试覆盖：**
- Security scan runner 可选择全部或单项扫描
- 缺工具时不会崩，而是给出结构化错误
- quality gate 会根据 severity 决定 pass/fail
- scan report 可按 severity 汇总

### 任务 2.2：重构/增强 SecurityReviewSystem
**Files:**
- Modify: `maxbot/security/security_review_system.py`
- Create: `maxbot/security/security_pipeline.py`
- Create: `maxbot/security/security_types.py`

**实现要求：**
- 抽出结果对象：finding / summary / gate_result
- 增加 `run_pipeline()`
- 增加 `evaluate_quality_gate()`
- 输出统一 JSON/dict 结构

### 任务 2.3：把安全工作流接成工具或明确入口
**Files:**
- Create: `maxbot/tools/security_tools.py`
- Modify: registry 接入位置（按项目现有注册方式）

**实现要求：**
- 暴露如 `security_scan` 工具
- 支持：`all` / `bandit` / `safety` / `pip-audit`
- 返回结构化输出

### 任务 2.4：文档与阶段同步
**Files:**
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`
- Modify: `ECC_LEARNING_PLAN.md`
- Create: `docs/phase5-security-validation-plan.md`

### 任务 2.5：验收与提交
**Run:**
```bash
python3 -m pytest tests/test_phase5_fixes.py tests/test_phase5_security_pipeline.py tests/test_phase5_quality_gate.py -q
```

**Commit:**
```bash
git add -A
git commit -m "feat: complete phase5 security and validation system"
git push origin main
```

---

## 3. Phase 6：多智能体协作

### 验收目标
- 明确保留一套主实现（避免双轨并存混乱）
- 支持：任务创建、依赖调度、结果汇总、并发执行
- 能根据 capability 做基础 worker 选择
- 有测试覆盖 orchestrate / dependency / capability routing

### 任务 3.1：写失败测试
**Files:**
- Create: `tests/test_phase6_multi_agent_orchestration.py`
- Create: `tests/test_phase6_multi_agent_routing.py`

**测试覆盖：**
- capability 匹配 worker
- 依赖未完成时任务不执行
- 并行任务可汇总
- 最终 coordinator 输出聚合结果

### 任务 3.2：收敛多 Agent 主实现
**Files:**
- Modify: `maxbot/multi_agent/coordinator.py`
- Modify: `maxbot/multi_agent/worker.py`
- Modify: `maxbot/multi_agent/__init__.py`
- Modify: `maxbot/tools/multi_agent_tools.py`

**实现要求：**
- 统一主入口，避免 `__init__.py` 中另一套编排逻辑继续漂移
- `_assign_worker()` 改成 capability-aware
- 任务汇总结果更明确（状态 / 结果 / 错误 / worker）
- `spawn_agent` / `spawn_agents_parallel` 与主编排层保持一致口径

### 任务 3.3：文档同步
**Files:**
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`
- Create: `docs/phase6-multi-agent-plan.md`

### 任务 3.4：验收与提交
**Run:**
```bash
python3 -m pytest tests/test_multi_agent.py tests/test_phase6_multi_agent_orchestration.py tests/test_phase6_multi_agent_routing.py -q
```

**Commit:**
```bash
git add -A
git commit -m "feat: complete phase6 multi-agent collaboration"
git push origin main
```

---

## 4. Phase 7：Hook 系统补缺与正式验收

### 验收目标
- `PRE_COMPACT` / `POST_COMPACT` 真正接到主循环
- `minimal/standard/strict` profile 行为不再只是空壳
- Hook 测试覆盖 profile 和 compact hooks
- 文档可正式标记 Phase 7 完成

### 任务 4.1：写失败测试
**Files:**
- Create: `tests/test_phase7_hook_profiles.py`
- Create: `tests/test_phase7_hook_compact_events.py`

**测试覆盖：**
- `minimal` profile 会禁用部分非关键 hook
- `strict` profile 对配置编辑更严格
- `_compress_context()` 触发 `PRE_COMPACT` / `POST_COMPACT`

### 任务 4.2：实现 Hook profile 与 compact 触发
**Files:**
- Modify: `maxbot/core/hooks/hook_manager.py`
- Modify: `maxbot/core/hooks/builtin_hooks.py`
- Modify: `maxbot/core/agent_loop.py`

**实现要求：**
- `HookManager.set_profile()` 落地最小逻辑
- `_compress_context()` 前后触发 compact hooks
- profile 行为能被测试观察到

### 任务 4.3：文档同步
**Files:**
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`
- Modify: `ECC_LEARNING_PLAN.md`
- Create: `docs/phase7-hooks-completion-plan.md`

### 任务 4.4：验收与提交
**Run:**
```bash
python3 -m pytest tests/test_hooks.py tests/test_phase3_learningloop_hook_integration.py tests/test_phase3_agent_loop_hooks.py tests/test_phase7_hook_profiles.py tests/test_phase7_hook_compact_events.py -q
```

**Commit:**
```bash
git add -A
git commit -m "feat: finalize phase7 hook system"
git push origin main
```

---

## 5. 全部阶段完成后的全仓复审

### 触发条件
仅当：
- Phase 4 MemPalace PoC 完成
- Phase 5 完成
- Phase 6 完成
- Phase 7 完成

### 复审目标
从 `MAXBOT_EVOLUTION_PLAN.md` Phase 1 开始，逐阶段核对：
- 是否有“文档写完成但代码没落地”的地方
- 是否有“代码存在但没有测试基线”的地方
- 是否有“阶段完成但总计划文档未同步”的地方
- 是否有“重复实现 / 漂移接口 / TODO 未收”的地方

### 复审产物
- `docs/full-evolution-audit-report.md`
- `docs/full-evolution-gap-list.md`
- 更新后的 `MAXBOT_EVOLUTION_PLAN.md`
- 更新后的 `EVOLUTION_PROGRESS.md`

### 复审提交
```bash
git add -A
git commit -m "docs: add full evolution audit after phase completion"
git push origin main
```
