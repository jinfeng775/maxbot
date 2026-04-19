# MaxBot Phase 5 / Phase 6 Completion Plan

> **For Hermes:** 按阶段分别完成、测试、同步文档、提交 GitHub；Phase 5 完成后先提交，再继续 Phase 6。

**Goal:** 把 MaxBot 第五阶段（安全和验证系统）与第六阶段（多智能体协作）收口到“可诚实标记为完成”的状态，并分别提交到 GitHub。

**Architecture:** Phase 5 采用“fail-closed 安全扫描 + 结构化 pipeline/gate + 工具入口 + 可追踪 scan failure”的最小完成口径；Phase 6 采用“运行时主链稳定 + legacy 兼容层保留 + run/chat 契约统一 + 完成态测试基线”的收口策略，避免激进删除旧实现。

**Tech Stack:** Python 3.11, pytest, MaxBot security pipeline/tooling, MaxBot multi-agent coordinator/worker/runtime tools, markdown docs, git.

---

## Phase 5 完成定义

### 完成口径
- `SecurityReviewSystem.run_security_scan()` 对扫描器失败和未知检查名一律 fail-closed
- `run_security_pipeline()` 保留 `scan_failures`
- `evaluate_quality_gate()` 输出结构化 gate，包含 `scan_failures`
- `security_scan` 工具返回 `report + gate`
- 有专门回归测试覆盖：扫描工具失败、未知检查名、pipeline 透传 scan_failures、工具入口结构化输出
- 文档和主线进度同步为“Phase 5 完成”

### 代码文件
- Modify: `maxbot/security/security_review_system.py`
- Modify: `maxbot/security/security_pipeline.py`
- Modify: `maxbot/tools/security_tools.py`（如需要）
- Create: `tests/test_phase5_security_review_system.py`
- Modify: `tests/test_phase5_security_pipeline.py`
- Modify: `docs/phase5-security-validation-plan.md`
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`

### 验证命令
```bash
python3 -m pytest \
  tests/test_phase5_security_review_system.py \
  tests/test_phase5_security_pipeline.py \
  tests/test_phase5_quality_gate.py \
  tests/test_phase5_security_tool.py -q
```

---

## Phase 6 完成定义

### 完成口径
- runtime 主链继续以 `coordinator.py` / `worker.py` 为准
- package-level legacy 多智能体层明确作为兼容层保留
- legacy / runtime / tool 层统一子 Agent 执行契约：优先 `run()`，必要时回退 `chat()`
- `multi_agent_tools.py` 运行时支持 `run/chat` 双兼容，不再隐式依赖不存在的 `chat()`
- 新增完成态回归测试覆盖：legacy delegate、legacy orchestrate、auto mode、worker pool、runtime tool result shape
- 文档和主线进度同步为“Phase 6 完成”

### 代码文件
- Modify: `maxbot/multi_agent/__init__.py`
- Modify: `maxbot/tools/multi_agent_tools.py`
- Create: `tests/test_phase6_multi_agent_completion.py`
- Modify: `docs/phase6-multi-agent-audit.md`
- Modify: `MAXBOT_EVOLUTION_PLAN.md`
- Modify: `EVOLUTION_PROGRESS.md`

### 验证命令
```bash
python3 -m pytest \
  tests/test_phase6_multi_agent_completion.py \
  tests/test_phase6_coordinator.py \
  tests/test_phase6_multi_agent_tools.py \
  tests/test_phase6_multi_agent_compat.py \
  tests/test_phase3.py \
  tests/test_multi_agent.py -q
```

---

## 分阶段交付顺序
1. 完成 Phase 5 代码与测试
2. 更新 Phase 5 文档与进度
3. Phase 5 单独 commit + push
4. 完成 Phase 6 代码与测试
5. 更新 Phase 6 文档与进度
6. Phase 6 单独 commit + push
7. 汇报测试结果、commit hash、主线状态
