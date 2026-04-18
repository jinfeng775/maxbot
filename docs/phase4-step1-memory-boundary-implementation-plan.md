# Phase 4 Step 1 — Memory / Session / Instinct Boundary Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 在不破坏现有 Phase 2 / Phase 3 能力的前提下，先完成第四阶段第一步：定义并落地 `memory` / `session` / `instinct` 三者边界，为后续分层记忆实现建立稳定数据模型与接口约束。

**Architecture:** 保持 `InstinctStore` 继续负责“可复用策略与行为模式”，保持 `SessionStore` 继续负责“会话消息持久化”，把 `Memory` 从当前简单 KV 存储升级为“可表达 scope/source/tags/importance 的长期事实存储”。第一步只解决边界、数据模型、兼容接口与测试，不直接做完整 prompt injection / retrieval ranking / governance 全量实现。

**Tech Stack:** Python 3.11, SQLite, FTS5, pytest, existing MaxBot session store / learning loop / agent loop.

---

## 0. 背景结论（实现前必须统一）

### 当前真实代码状态

- `maxbot/core/memory.py`
  - 当前只有 `key/value/category/created_at/updated_at`
  - 适合最小 KV 持久化
  - 还不具备分层记忆领域模型
- `maxbot/sessions/__init__.py`
  - 当前负责 `Session` / `SessionStore`
  - 持久化消息与 `metadata`
  - 并在同目录挂载 `memory.db`
- `maxbot/learning/instinct_store.py`
  - 当前已经是完整的模式/策略存储层
  - 持有 lifecycle 字段、质量状态、重复合并逻辑
- `maxbot/core/agent_loop.py`
  - 当前已接通 Hook + LearningLoop
  - 当前有内置 `memory` tool，但只暴露简单 `category`
  - 当前系统提示增强只注入 skills，还没正式接入 memory retrieval

### 本步骤要明确的职责边界

#### SessionStore 负责
- 会话消息历史
- 会话级 metadata
- 与单次对话流程强绑定的短期上下文

#### Memory 负责
- 稳定事实
- 用户偏好事实
- 项目上下文事实
- 全局长期知识片段
- 可搜索、可筛选、可注入的长期上下文条目

#### InstinctStore 负责
- 可复用策略
- 行为模式
- 错误修复模式
- 自动应用经验
- 命中/成功/失败统计与失效治理

### 明确禁止
- 不要把稳定事实写进 `InstinctStore`
- 不要把 pattern / validator 结果当普通 `Memory` 条目存储
- 不要把 `SessionStore` 当长期 user/project/global memory 使用

---

## 1. 目标产物

本步骤完成后，应新增/修改出以下产物：

- `maxbot/core/memory.py`
- `maxbot/sessions/__init__.py`
- `maxbot/core/agent_loop.py`
- `docs/phase4-memory-boundary.md`
- `tests/test_phase4_memory_boundary_model.py`
- `tests/test_phase4_memory_boundary_integration.py`

如果拆分更清晰，也可以新增：
- `maxbot/core/memory_types.py`

但**不要**在第一步里引入过多新模块；优先保持最小改动。

---

## 2. 实施原则

1. **先建边界，再扩功能**
   - 本步骤重点是 domain model 和接口边界
   - 不要在同一步把注入排序、清理压缩、全量 retrieval 全部做完

2. **向后兼容当前 Memory API**
   - 现有 `set/get/delete/search/list_all/export_text` 不能直接废弃
   - 旧调用至少还能工作

3. **不要破坏 Phase 3 回归基线**
   - LearningLoop / InstinctStore 行为必须不变
   - 若新增边界文档引用，也不要影响现有测试

4. **先测试后实现**
   - 每个任务都先写失败测试
   - 再做最小实现

---

## 3. 任务拆解

### Task 1: 编写边界设计文档

**Objective:** 先把 memory / session / instinct 的职责边界写成明确文档，避免后续实现继续漂移。

**Files:**
- Create: `docs/phase4-memory-boundary.md`
- Modify: `phase3-continuous-learning/phase4-preflight-report.md`

**Step 1: 写文档初稿**

创建 `docs/phase4-memory-boundary.md`，至少包含以下章节：

```md
# Phase 4 Memory Boundary

## Responsibilities
- SessionStore
- Memory
- InstinctStore

## Allowed Data Examples
## Disallowed Data Examples
## Write Path Rules
## Retrieval Path Rules
## Compatibility Notes
```

**Step 2: 在文档中写出“允许/禁止”的例子**

至少给出这些例子：

- `user prefers Chinese` -> Memory
- `project uses FastAPI + SQLite` -> Memory
- `when ImportError + missing package, run pip install ...` -> InstinctStore
- `current conversation messages` -> SessionStore

**Step 3: 在 preflight 文档补链接**

在 `phase3-continuous-learning/phase4-preflight-report.md` 增加一行，指向新文档：

```md
- 边界细化文档：`docs/phase4-memory-boundary.md`
```

**Step 4: 自检**

检查文档是否明确回答：
- 什么该进 Memory
- 什么该进 InstinctStore
- 什么只该留在 SessionStore

**Step 5: Commit**

```bash
git add docs/phase4-memory-boundary.md phase3-continuous-learning/phase4-preflight-report.md
git commit -m "docs: define phase4 memory session instinct boundaries"
```

---

### Task 2: 为 Memory 引入最小分层领域模型

**Objective:** 扩展 `MemoryEntry`，让 Memory 能表达 scope / source / tags / importance，同时保持旧 API 可用。

**Files:**
- Modify: `maxbot/core/memory.py`
- Test: `tests/test_phase4_memory_boundary_model.py`

**Step 1: 写失败测试，验证新字段默认值**

在 `tests/test_phase4_memory_boundary_model.py` 先写：

```python
from maxbot.core.memory import Memory


def test_memory_entry_defaults_support_scope_and_metadata(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set("user_name", "张三", category="user")
    entries = mem.list_all()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.scope == "global"
    assert entry.source == "manual"
    assert entry.tags == []
    assert entry.importance == 0.5
```

**Step 2: 写失败测试，验证 set 支持新参数**

```python
def test_memory_set_accepts_scope_source_tags_importance(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set(
        "project_stack",
        "FastAPI + SQLite",
        category="memory",
        scope="project",
        source="agent",
        tags=["tech-stack", "backend"],
        importance=0.9,
    )

    entry = mem.list_all()[0]
    assert entry.scope == "project"
    assert entry.source == "agent"
    assert entry.tags == ["tech-stack", "backend"]
    assert entry.importance == 0.9
```

**Step 3: 在 `maxbot/core/memory.py` 增加字段**

为 `MemoryEntry` 增加：

```python
scope: str = "global"
source: str = "manual"
tags: list[str] = field(default_factory=list)
importance: float = 0.5
session_id: str | None = None
project_id: str | None = None
user_id: str | None = None
```

如果 dataclass 已经使用简单导入，记得补：

```python
from dataclasses import dataclass, field
```

**Step 4: 给 SQLite schema 增加列迁移**

在 `_init_db()` 中：
- 保留现有表结构创建
- 增加 `PRAGMA table_info(memory)` 检查
- 缺字段时 `ALTER TABLE`

最少新增列：
- `scope TEXT DEFAULT 'global'`
- `source TEXT DEFAULT 'manual'`
- `tags TEXT DEFAULT '[]'`
- `importance REAL DEFAULT 0.5`
- `session_id TEXT`
- `project_id TEXT`
- `user_id TEXT`

**Step 5: 扩展 `set()` 参数但保留兼容**

目标签名：

```python
def set(
    self,
    key: str,
    value: str,
    category: str = "memory",
    scope: str = "global",
    source: str = "manual",
    tags: list[str] | None = None,
    importance: float = 0.5,
    session_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
) -> None:
```

并保证旧调用：

```python
mem.set("k", "v")
```

仍可正常工作。

**Step 6: 更新 `_row_to_entry()` 与 `list_all()`**

确保 JSON 字段 `tags` 被反序列化。

**Step 7: 跑测试**

Run:

```bash
python3 -m pytest tests/test_phase4_memory_boundary_model.py -q
```

Expected: PASS

**Step 8: Commit**

```bash
git add maxbot/core/memory.py tests/test_phase4_memory_boundary_model.py
git commit -m "feat: add scoped memory entry model"
```

---

### Task 3: 为 Memory 增加最小范围过滤接口

**Objective:** 让 Memory 至少可以按 scope / session_id / project_id / user_id 做过滤，为后续 retrieval 铺路。

**Files:**
- Modify: `maxbot/core/memory.py`
- Test: `tests/test_phase4_memory_boundary_model.py`

**Step 1: 写失败测试**

```python
def test_memory_list_all_can_filter_by_scope_and_project(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")

    mem.set("a", "global fact", scope="global")
    mem.set("b", "project fact", scope="project", project_id="p1")
    mem.set("c", "other project fact", scope="project", project_id="p2")

    entries = mem.list_all(scope="project", project_id="p1")
    assert [e.key for e in entries] == ["b"]
```

**Step 2: 扩展 `list_all()`**

将签名扩展为：

```python
def list_all(
    self,
    category: str | None = None,
    scope: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
) -> list[MemoryEntry]:
```

先用最小 SQL 动态拼接实现即可，不要过度抽象。

**Step 3: 扩展 `search()`**

也支持相同过滤参数：

```python
def search(self, query: str, limit: int = 10, scope: str | None = None, project_id: str | None = None, user_id: str | None = None, session_id: str | None = None) -> list[MemoryEntry]:
```

FTS 查出候选后，可先在 Python 侧做过滤，保持实现简单。

**Step 4: 跑测试**

Run:

```bash
python3 -m pytest tests/test_phase4_memory_boundary_model.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add maxbot/core/memory.py tests/test_phase4_memory_boundary_model.py
git commit -m "feat: add scoped memory filtering"
```

---

### Task 4: 给 SessionStore 增加最小上下文标识承载

**Objective:** 让 SessionStore 能稳定保存 project/user 维度元数据，但不把它自己演化成长期记忆系统。

**Files:**
- Modify: `maxbot/sessions/__init__.py`
- Test: `tests/test_phase4_memory_boundary_integration.py`

**Step 1: 写失败测试**

```python
from maxbot.sessions import SessionStore


def test_session_store_preserves_project_and_user_metadata(tmp_path):
    store = SessionStore(path=tmp_path / "sessions.db")
    session = store.create("s1", title="demo")

    session.metadata["project_id"] = "proj-1"
    session.metadata["user_id"] = "user-1"

    store.save_messages("s1", [{"role": "user", "content": "hi"}], metadata=session.metadata)
    loaded = store.get("s1")

    assert loaded.metadata["project_id"] == "proj-1"
    assert loaded.metadata["user_id"] == "user-1"
```

**Step 2: 扩展 `save_messages()`**

当前 `save_messages()` 只保存消息。改成：

```python
def save_messages(self, session_id: str, messages: list[dict], metadata: dict | None = None):
```

当 `metadata is not None` 时一起更新 `metadata` 列。

**Step 3: 补一个最小 helper（可选）**

如果实现更清晰，可加：

```python
def update_metadata(self, session_id: str, metadata: dict):
    ...
```

但不要强行加太多 helper。

**Step 4: 跑测试**

Run:

```bash
python3 -m pytest tests/test_phase4_memory_boundary_integration.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add maxbot/sessions/__init__.py tests/test_phase4_memory_boundary_integration.py
git commit -m "feat: persist session metadata for phase4 context"
```

---

### Task 5: 让 Agent 的 memory tool 支持边界字段透传

**Objective:** 不改 memory tool 名称，但让它可以安全写入新的 scope / source / tags / importance / project_id / user_id / session_id。

**Files:**
- Modify: `maxbot/core/agent_loop.py`
- Test: `tests/test_phase4_memory_boundary_integration.py`

**Step 1: 写失败测试**

```python
from unittest.mock import MagicMock

from maxbot.core.agent_loop import Agent, AgentConfig


def test_memory_tool_forwards_scope_metadata_fields(monkeypatch, tmp_path):
    store = MagicMock()
    store.memory = MagicMock()

    config = AgentConfig(api_key="test-key", auto_save=False, session_store=store)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    agent = Agent(config=config)

    agent._call_memory_tool({
        "action": "set",
        "key": "project_stack",
        "value": "FastAPI",
        "category": "memory",
        "scope": "project",
        "source": "agent",
        "tags": ["backend"],
        "importance": 0.8,
        "project_id": "p1",
        "user_id": "u1",
        "session_id": "s1",
    })

    store.memory.set.assert_called_once()
    kwargs = store.memory.set.call_args.kwargs
    assert kwargs["scope"] == "project"
    assert kwargs["project_id"] == "p1"
    assert kwargs["user_id"] == "u1"
```

**Step 2: 更新 `_MEMORY_TOOL_SCHEMA`**

在 `agent_loop.py` 里给 memory tool schema 增加：
- `scope`
- `source`
- `tags`
- `importance`
- `session_id`
- `project_id`
- `user_id`

**Step 3: 更新 `_call_memory_tool()`**

在 `set` 分支中透传这些参数：

```python
self.config.session_store.memory.set(
    key=...,
    value=...,
    category=...,
    scope=args.get("scope", "global"),
    source=args.get("source", "manual"),
    tags=args.get("tags") or [],
    importance=args.get("importance", 0.5),
    session_id=args.get("session_id"),
    project_id=args.get("project_id"),
    user_id=args.get("user_id"),
)
```

**Step 4: 保持旧行为兼容**

旧格式：

```python
{"action": "set", "key": "k", "value": "v"}
```

仍然必须可用。

**Step 5: 跑测试**

Run:

```bash
python3 -m pytest tests/test_phase4_memory_boundary_integration.py -q
```

Expected: PASS

**Step 6: Commit**

```bash
git add maxbot/core/agent_loop.py tests/test_phase4_memory_boundary_integration.py
git commit -m "feat: extend memory tool with scope metadata fields"
```

---

### Task 6: 给 Agent 会话保存流程补 metadata 回写

**Objective:** 让 project_id / user_id 等上下文标识能随 session 持久化，为后续 retrieval/injection 铺路。

**Files:**
- Modify: `maxbot/core/agent_loop.py`
- Modify: `maxbot/sessions/__init__.py`
- Test: `tests/test_phase4_memory_boundary_integration.py`

**Step 1: 写失败测试**

```python
def test_agent_save_session_persists_context_metadata(monkeypatch):
    store = MagicMock()
    store.get.return_value = None
    store.memory = MagicMock()

    config = AgentConfig(api_key="test-key", auto_save=True, session_id="s1", session_store=store)
    monkeypatch.setattr(Agent, "_init_client", lambda self: MagicMock())
    agent = Agent(config=config)

    agent._save_session()

    assert store.save_messages.called
    kwargs = store.save_messages.call_args.kwargs
    assert "metadata" in kwargs
```

**Step 2: 在 Agent 里构造 session metadata**

最低限度把这些信息写回：

```python
metadata = {
    "conversation_turns": self._conversation_turns,
}
```

如果当前配置 / session 上下文里已有 `project_id` / `user_id`，也一起带上。

**Step 3: 修改 `_save_session()`**

把：

```python
self.config.session_store.save_messages(...)
```

改成带 metadata 调用。

**Step 4: 跑测试**

Run:

```bash
python3 -m pytest tests/test_phase4_memory_boundary_integration.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add maxbot/core/agent_loop.py maxbot/sessions/__init__.py tests/test_phase4_memory_boundary_integration.py
git commit -m "feat: persist agent session context metadata"
```

---

### Task 7: 用测试固定三者边界，防止未来回归

**Objective:** 建立一组明确的边界测试，防止后续开发再次把事实、策略、会话状态混写。

**Files:**
- Modify: `tests/test_phase4_memory_boundary_model.py`
- Modify: `tests/test_phase4_memory_boundary_integration.py`

**Step 1: 增加 boundary semantics 测试**

至少补这些断言：

```python
def test_memory_stores_facts_not_strategy_steps(tmp_path):
    mem = Memory(path=tmp_path / "memory.db")
    mem.set("user_language", "zh-CN", scope="user", user_id="u1")
    entry = mem.list_all()[0]
    assert entry.scope == "user"
    assert entry.value == "zh-CN"
```

```python
def test_instinct_store_remains_separate_from_memory_store(tmp_path):
    from maxbot.learning.instinct_store import InstinctStore
    mem = Memory(path=tmp_path / "memory.db")
    store = InstinctStore(db_path=str(tmp_path / "instincts.db"))

    mem.set("user_language", "zh-CN", scope="user")
    instincts = store.list_instincts()
    assert instincts == []
```

**Step 2: 跑本步骤全部测试**

Run:

```bash
python3 -m pytest \
  tests/test_phase4_memory_boundary_model.py \
  tests/test_phase4_memory_boundary_integration.py -q
```

Expected: PASS

**Step 3: 再回归 Phase 3 关键测试**

Run:

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

Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_phase4_memory_boundary_model.py tests/test_phase4_memory_boundary_integration.py
git commit -m "test: lock phase4 memory session instinct boundaries"
```

---

## 4. 代码实现提示

### `Memory` 第一阶段推荐最小实现方式

优先使用“**扩字段 + 兼容默认值**”方案，不要一开始重构成复杂 ORM：

```python
@dataclass
class MemoryEntry:
    key: str
    value: str
    category: str = "memory"
    scope: str = "global"
    source: str = "manual"
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
```

### `SessionStore` 的边界

`SessionStore` 不需要知道长期记忆怎么检索，只需要：
- 能保存消息
- 能保存会话元数据
- 能作为 Agent 当前上下文的桥梁

### `Agent` 第一阶段不要做的事

本步骤**不要**直接实现：
- 最终版 memory 注入排序
- 动态 token budget 裁剪
- 自动把 observation 变成 memory
- 复杂的 retrieval ranking

这些留给后续 Phase 4 正式实现步骤。

---

## 5. 验收标准

本步骤完成后，必须满足：

- `Memory` 能表达 scope / source / tags / importance / session_id / project_id / user_id
- 旧 `Memory.set/get/search/list_all` 调用保持兼容
- `SessionStore` 可稳定保存会话 metadata
- `Agent` 的 memory tool 能透传边界字段
- 文档明确写清 memory / session / instinct 边界
- 新增 Phase 4 边界测试通过
- Phase 3 回归测试不被破坏

---

## 6. 推荐执行顺序

1. Task 1 - 边界文档
2. Task 2 - Memory 领域模型
3. Task 3 - Memory 范围过滤
4. Task 4 - Session metadata 持久化
5. Task 5 - memory tool 透传字段
6. Task 6 - Agent session metadata 回写
7. Task 7 - 边界测试 + Phase 3 回归

---

## 7. 后续衔接

完成本步骤后，下一步再进入：

- Phase 4 Step 2：记忆检索与分层注入
- Phase 4 Step 3：记忆治理（清理 / 压缩 / 去重）
- Phase 4 Step 4：与 Instinct 的联动但不混层
- Phase 4 Step 5：外接本地记忆适配（MemPalace）

### MemPalace 预留说明

外接本地记忆建议采用 **可选增强层** 而不是替代内核：
- `SessionStore` 继续保存当前会话
- `Memory` 继续保存 MaxBot 内部稳定事实
- `InstinctStore` 继续保存策略/模式
- `MemPalace` 作为外接本地长期记忆仓 / 历史资料召回层

建议后续新增：
- `MemPalaceAdapter`
- 外部记忆检索优先级与去重策略
- 与 prompt injection 的统一预算控制

这会比一口气直接把 MemPalace 混进当前 Memory 内核更稳。
