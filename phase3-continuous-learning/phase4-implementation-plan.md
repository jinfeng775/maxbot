# MaxBot 第四阶段实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 基于现有 `Memory` 与 `SessionStore`，实现可交付的分层记忆持久化系统，并与第三阶段 instinct 学习系统完成边界清晰的协作。

**Architecture:** 以 `Memory` 为底层持久化存储，向上抽象 SESSION / PROJECT / USER / GLOBAL 四层语义记忆；由 Agent 在运行时执行检索、注入、更新与清理。InstinctStore 继续负责策略模式，Memory 负责稳定事实和长期上下文。

**Tech Stack:** Python 3.11, SQLite, FTS5, pytest, existing MaxBot session/memory infrastructure.

---

## 一、前置约束

### 已完成前置条件
- Phase 3 持续学习系统已完成 MVP
- `maxbot/core/memory.py` 已有最小可用实现
- `maxbot/sessions/__init__.py` 已有 SessionStore

### 本阶段不直接包含
- 历史 `tests/test_phase4.py` 的 gateway 兼容修复
- 多平台 gateway API 统一
- 外部 API 依赖治理

这些应作为独立兼容清理任务处理。

---

## 二、实施目标分解

### Task 1: 明确记忆领域模型

**Objective:** 定义四层记忆模型及其统一数据结构。

**Files:**
- Modify: `maxbot/core/memory.py`
- Create: `docs/phase4-memory-model.md`
- Test: `tests/test_phase4_memory_model.py`

**要实现：**
- 明确记忆层级：`session`, `project`, `user`, `global`
- 为 memory entry 增加必要字段（如 scope/key/source/tags/importance）
- 保持向后兼容当前简单 key-value 接口

**验证：**
- 新旧接口都可读写
- 不破坏 Phase 3 相关行为

---

### Task 2: 扩展 Memory 检索能力

**Objective:** 让记忆检索支持按层级、按范围、按主题查询。

**Files:**
- Modify: `maxbot/core/memory.py`
- Test: `tests/test_phase4_memory_search.py`

**要实现：**
- 支持按 category/scope 查询
- 支持 project/user 过滤
- 保留 FTS5 与 LIKE fallback
- 支持限制返回数量与排序策略

**验证：**
- 同一 query 在不同 scope 下结果不同
- 中文检索仍可用

---

### Task 3: 接入 SessionStore 与 Agent 记忆上下文

**Objective:** 让 Agent 能基于当前会话/项目/用户加载相关记忆。

**Files:**
- Modify: `maxbot/sessions/__init__.py`
- Modify: `maxbot/core/agent_loop.py`
- Test: `tests/test_phase4_memory_integration.py`

**要实现：**
- Agent 启动时加载相关记忆
- session 结束时可回写新记忆
- project/user 维度通过 metadata 或 config 注入

**验证：**
- 同用户不同项目看到不同上下文
- 同项目不同会话能检索到共享 project memory

---

### Task 4: 设计 Prompt Injection 机制

**Objective:** 控制记忆如何被注入到系统提示中，避免上下文污染。

**Files:**
- Modify: `maxbot/core/agent_loop.py`
- Create: `docs/phase4-memory-injection.md`
- Test: `tests/test_phase4_memory_injection.py`

**要实现：**
- 注入格式统一
- 注入字数限制
- 按层级优先级排序（session > project > user > global 或按实际策略）
- 避免重复注入相同条目

**验证：**
- 注入内容稳定可控
- 不超过预算
- 同类项不会重复堆叠

---

### Task 5: 记忆清理与压缩策略

**Objective:** 让记忆系统具备治理能力，而不是无限膨胀。

**Files:**
- Modify: `maxbot/core/memory.py`
- Test: `tests/test_phase4_memory_governance.py`

**要实现：**
- 低价值记忆删除/归档
- 过期 session memory 清理
- 重复 memory 合并
- 长期 project/user/global memory 的保留策略

**验证：**
- 清理后高价值项保留
- 重复项合并
- 不破坏检索正确性

---

### Task 6: 与 InstinctStore 边界联调

**Objective:** 明确 memory 与 instinct 的协作机制，避免职责重叠。

**Files:**
- Modify: `phase3-continuous-learning/phase3-learning-system-architecture.md`
- Modify: `docs/phase4-memory-model.md`
- Test: `tests/test_phase4_memory_instinct_boundary.py`

**要实现：**
- 文档明确：
  - instinct = 策略模式
  - memory = 稳定事实/长期上下文
- 测试验证二者不会互相滥用

**验证：**
- 同一事实不会同时被错误写成 instinct + memory
- 检索与应用路径清晰分离

---

### Task 7: Phase 4 验收测试

**Objective:** 为第四阶段建立独立可回归的测试基线。

**Files:**
- Create: `tests/test_phase4_memory_end_to_end.py`

**要覆盖：**
- 写入记忆
- 检索记忆
- 注入上下文
- session/project/user/global 分层行为
- 清理/压缩
- 与 Phase 3 instinct 共存

**验证命令：**
```bash
python3 -m pytest tests/test_phase4_memory_model.py \
  tests/test_phase4_memory_search.py \
  tests/test_phase4_memory_integration.py \
  tests/test_phase4_memory_injection.py \
  tests/test_phase4_memory_governance.py \
  tests/test_phase4_memory_instinct_boundary.py \
  tests/test_phase4_memory_end_to_end.py -q
```

---

## 三、实施顺序建议

1. Task 1 - 领域模型
2. Task 2 - 检索扩展
3. Task 3 - Agent / SessionStore 接入
4. Task 4 - Injection 机制
5. Task 5 - 治理机制
6. Task 6 - 与 instinct 边界联调
7. Task 7 - 验收测试

---

## 四、风险与注意事项

### 风险 1：旧 Memory API 兼容性
必须保留当前 `set/get/search` 习惯用法，否则会影响已有功能。

### 风险 2：上下文膨胀
记忆注入一定要设置预算与去重，否则容易污染主循环上下文。

### 风险 3：职责混淆
不要把 pattern learning 写进 Memory，也不要把稳定事实写进 InstinctStore。

### 风险 4：历史 phase4 测试误导
`tests/test_phase4.py` 当前属于 gateway 兼容问题，不应作为本计划主要验收标准。

---

## 五、验收标准

完成后，第四阶段应满足：
- 能按 `session/project/user/global` 分层存储记忆
- Agent 能检索并注入相关记忆
- Memory 有清理、压缩、去重能力
- 与 Phase 3 instinct 系统边界清晰
- 有独立的 Phase 4 memory 测试基线
- 为外接本地记忆（如 MemPalace）预留清晰接入边界与集成计划

---

## 六、外接本地记忆规划：MemPalace

### 6.1 为什么考虑 MemPalace

MemPalace 的已知特征：
- local-first，本地优先
- verbatim storage，原文保存，不做摘要改写
- semantic search，支持语义检索
- pluggable backend，默认 ChromaDB
- knowledge graph / MCP server / CLI 工具链较完整

这些能力和 MaxBot 第四阶段目标有互补性，尤其适合作为：
- 外接长期记忆仓
- 大规模历史会话 / 项目资料归档层
- 独立于 MaxBot 主循环的本地记忆索引层

### 6.2 集成原则

MemPalace **不应直接替代** MaxBot 当前三层边界：
- `SessionStore` 仍负责当前会话轨迹
- `Memory` 仍负责 MaxBot 内部稳定事实层
- `InstinctStore` 仍负责策略/模式层

更合理的定位是：

**MemPalace = 外接本地长期记忆仓 / 可选增强检索层**

### 6.3 推荐接入方式

建议在 Phase 4 主线完成后，以“可选后端/外接记忆适配器”方式接入：

1. 新增 `MemPalaceAdapter`
2. 支持把项目资料、对话归档写入 MemPalace
3. 在 MaxBot 检索阶段增加一层外部召回：
   - 先查 MaxBot 内置 Memory
   - 再按需查 MemPalace
4. 对返回结果做统一注入预算控制
5. 保持完全本地运行，不引入云依赖

### 6.4 具体实施建议

可新增后续任务：
- `Task 8: MemPalace adapter 设计与 PoC`
- `Task 9: MemPalace 检索接入 Agent prompt injection`
- `Task 10: MemPalace 与内置 Memory 去重/优先级策略`

### 6.5 风险提醒

- 不要把 MemPalace 直接混成 `SessionStore` 的实现细节
- 不要让 MaxBot 内置 Memory 与 MemPalace 出现双写失控
- 不要把 instinct/pattern 数据直接塞进 MemPalace 长期仓
- 接入后必须增加独立集成测试，验证检索优先级、去重和上下文预算

---

## 七、补充说明

建议在正式开工前，把历史 `tests/test_phase4.py` 另行归类为：

**gateway compatibility cleanup**

避免继续与“第四阶段记忆持久化系统”主线混淆。
