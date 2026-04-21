# MaxBot Hermes 风格会话重置/新建实现计划

**Goal:** 让 MaxBot 的 `/new` 与 `/reset` 按 Hermes 风格工作：结束旧 session、保留旧会话历史、切换到新 session；并在 session 边界上把旧会话归档到 MemPalace。

**Architecture:** 将当前单一的 `Agent.reset()` 拆成两个显式语义：`reset()` 只清空当前上下文、保留当前 session_id；`new_session()` 结束旧 session、创建新 session_id、清空上下文但不删除旧 session。CLI `/new` 走 `new_session()`，`/reset` 走 `reset()`。在 `new_session()` 边界上优先保存旧会话到 `SessionStore`，再同步归档到 MemPalace。

**Tech Stack:** Python 3.11, SQLite SessionStore, existing Agent loop, MemPalaceAdapter CLI/Python fallback, pytest.

---

## 先确认的现状

### 当前错误行为
- `maxbot/cli/__init__.py`
  - `/new` 调用 `agent.reset()`
  - `/reset` 也调用 `agent.reset()`
- `maxbot/core/agent_loop.py`
  - `reset()` 会执行 `self.config.session_store.delete(self.config.session_id)`
  - 所以 `/new` / `/reset` 都会直接删除当前会话历史

### 目标行为（对齐 Hermes）
- `/new`
  - 结束旧 session
  - 保存旧 session 到 SessionStore
  - 把旧 session 同步到 MemPalace
  - 生成新的 `session_id`
  - 清空上下文
  - 老 session 保留可回看
- `/reset`
  - 清空当前上下文
  - 保留当前 `session_id`
  - 不删除 SessionStore 里的旧消息
  - 不新建 session

---

## Task 1: 先写 CLI 行为失败测试

**Objective:** 锁定 `/new` 与 `/reset` 的新语义，防止继续误删 session。

**Files:**
- Modify: `tests/test_agent_integration.py`

**Step 1: 写失败测试**
新增测试：
- `test_new_session_rotates_session_id_without_deleting_old_session`
- `test_reset_clears_runtime_messages_but_keeps_session_history`

覆盖点：
1. `new_session()` 前先保存一个旧 session
2. 调 `new_session()` 后：
   - `session_id` 变化
   - 旧 session 仍可 `store.get(old_session_id)`
   - 新 session 可继续使用
3. 调 `reset()` 后：
   - 当前内存消息清空
   - `conversation_turns` 清零
   - `session_id` 不变
   - store 里当前 session 仍存在，消息未被删除

**Step 2: 跑测试确认失败**
```bash
python3 -m pytest tests/test_agent_integration.py -q
```
预期：至少新增测试失败，因为当前 `reset()` 会删除会话且没有 `new_session()`。

---

## Task 2: 写 MemPalace 会话边界归档失败测试

**Objective:** 锁定“new/reset 时旧会话会归档到 MemPalace”的行为。

**Files:**
- Modify: `tests/test_phase4_mempalace_adapter.py`

**Step 1: 写失败测试**
新增测试：
- `test_new_session_archives_previous_session_to_mempalace`
- `test_reset_does_not_delete_session_store_history`

重点断言：
- `new_session()` 前已有消息
- monkeypatch `MemPalaceAdapter.store_session`
- 调用 `new_session()` 后：
  - `store_session` 被调用一次
  - 传入的是旧 `session_id`
  - 传入消息包含旧会话消息
- `reset()` 不触发 delete 行为

**Step 2: 跑测试确认失败**
```bash
python3 -m pytest tests/test_phase4_mempalace_adapter.py -q
```
预期：失败，因为当前没有 `new_session()` 边界归档逻辑。

---

## Task 3: 在 Agent 中实现 Hermes 风格 session lifecycle

**Objective:** 引入 `new_session()`，并修正 `reset()` 语义。

**Files:**
- Modify: `maxbot/core/agent_loop.py`

**Step 1: 增加 session id 生成 helper**
增加一个最小 helper，例如：
- `_generate_session_id()`

实现风格对齐 Hermes：
```python
now = time.strftime("%Y%m%d_%H%M%S")
short = uuid.uuid4().hex[:8]
return f"{now}_{short}"
```

**Step 2: 增加旧 session 归档 helper**
新增 helper，例如：
- `_archive_current_session_before_boundary()`

职责：
1. 如果当前有 `session_id` 且有消息：
   - 先 `save_session()`
   - 如果 `mempalace_enabled`：调用 `MemPalaceAdapter.store_session(...)`
2. 用当前 session metadata 决定 `wing` / `room`
3. 返回归档是否成功（可忽略失败，不应阻断 `/new`）

**Step 3: 实现 `new_session()`**
实现语义：
1. 记录 `old_session_id`
2. 调 `_archive_current_session_before_boundary()`
3. 生成新的 `session_id`
4. 清空 runtime messages
5. 清零 `conversation_turns`
6. 如果 `auto_save`：为新 session 创建空记录或在首次 `save_session()` 时自动创建
7. **绝不删除旧 session**

**Step 4: 修正 `reset()`**
改成：
- 清空 `self.messages`
- 清零 `self._conversation_turns`
- 保留当前 `session_id`
- 不调用 `session_store.delete(...)`

---

## Task 4: 修 CLI 路由

**Objective:** 让 `/new` 与 `/reset` 走不同语义。

**Files:**
- Modify: `maxbot/cli/__init__.py`

**Step 1: 修改 `/new`**
从：
```python
agent.reset()
```
改成：
```python
agent.new_session()
```

**Step 2: 保持 `/reset` 走清上下文**
```python
agent.reset()
```

**Step 3: 调整提示文案**
- `/new` → “新会话已开启，旧会话已保留”
- `/reset` → “当前上下文已清空，会话历史仍保留”

---

## Task 5: 若需要，补 SessionStore / Gateway 兼容层

**Objective:** 确保 gateway/session_manager 不因为 Agent 语义变化而出错。

**Files:**
- Inspect/Modify if needed: `maxbot/gateway/server.py`

重点检查：
- `session_manager.reset()` 当前仍调用 `agent.reset()`
- 如果将来 gateway 也要对齐 Hermes，可后续把 gateway `/new` 接到 `new_session()`

这一步先保持最小改动：
- 当前先修 CLI
- 若 gateway tests 因语义变更失败，再补兼容逻辑

---

## Task 6: 文档同步

**Objective:** 明确 `/new` / `/reset` / MemPalace 归档边界。

**Files:**
- Modify: `docs/phase4-mempalace-session-boundary-fix.md`
- Optional: `examples/config_example.yaml` 注释如有必要

需要写清楚：
- `/new` = 新 session，旧会话保留并归档到 MemPalace
- `/reset` = 清空当前上下文，不删历史
- SessionStore 是精确会话历史源
- MemPalace 是边界归档与长期召回层

---

## Task 7: 运行验证

**Objective:** 确认功能和相关回归稳定。

**Step 1: 先跑针对性测试**
```bash
python3 -m pytest \
  tests/test_agent_integration.py \
  tests/test_phase4_mempalace_adapter.py -q
```

**Step 2: 再跑相关 Phase 4 回归**
```bash
python3 -m pytest \
  tests/test_phase4_mempalace_integration.py \
  tests/test_phase4_mempalace_adapter.py \
  tests/test_phase4_memory_injection.py \
  tests/test_phase4_memory_end_to_end.py \
  tests/test_agent_integration.py -q
```

---

## Task 8: 提交

**Objective:** 用中文 commit message 提交本次修复。

**Commit message 建议：**
```bash
git commit -m "fix: 按 Hermes 语义修复会话重置并归档到记忆宫殿"
```

---

## 成功标准

完成后应满足：
- `/new` 不再删除旧 session
- `/new` 会生成新 `session_id`
- `/reset` 只清上下文，不删历史
- 旧 session 在边界切换时会写入 MemPalace
- 相关测试全部通过
