# MaxBot `/resume (无参数) + /delete_session` 实现计划

**Goal:** 让 MaxBot CLI 的 `/resume` 在无参数时像 Hermes 一样展示最近会话，并新增显式的 `/delete_session <id>`，把“恢复历史会话”和“删除历史会话”完全分开。

**Architecture:** 保持 `SessionStore` 作为历史会话权威来源。CLI `/resume` 无参数时仅展示最近会话列表，不做副作用；CLI `/resume <id>` 继续调用 `Agent.resume_session(id)`；CLI `/delete_session <id>` 显式调用 `Agent.delete_session(id)`。不再把任何删除语义混入 `/new`、`/reset`、`/resume`。

**Tech Stack:** Python 3.11, existing `SessionStore`, `Agent`, CLI loop, pytest.

---

## 当前现状

已经具备：
- `Agent.list_sessions()`
- `Agent.delete_session()`
- `Agent.resume_session(session_id)`
- CLI `/sessions`
- CLI `/resume <id>`

当前还缺：
- `/resume` 无参数时列最近会话
- `/delete_session <id>` 显式删除历史会话
- `/help` 文案同步

---

## Task 1: 补 CLI 层失败测试（当前以行为验证为主）

### 文件
- `tests/test_agent_integration.py`

### 增加断言覆盖点
- `list_sessions()` 已返回完整会话结构（已存在）
- `delete_session()` 已支持显式删除（已存在）

CLI 层本轮先通过已有 Agent 行为 + 手工 CLI 逻辑实现，不额外加复杂交互测试。

---

## Task 2: 修改 CLI `/help`

### 文件
- `maxbot/cli/__init__.py`

### 更新内容
新增帮助项：
- `/resume [id]           恢复指定历史会话；无参数时列出最近会话`
- `/delete_session <id>   删除指定历史会话`

---

## Task 3: 修改 CLI `/resume`

### 文件
- `maxbot/cli/__init__.py`

### 行为
#### `/resume`
- 无参数时：
  - 列出最近 20 个会话
  - 展示 `session_id / title / updated_at`
  - 再提示：`用法: /resume <session_id>`

#### `/resume <id>`
- 有参数时：
  - 正常调用 `agent.resume_session(id)`
  - 成功则切换
  - 失败则提示未找到

---

## Task 4: 新增 CLI `/delete_session <id>`

### 文件
- `maxbot/cli/__init__.py`

### 行为
- 用户输入 `/delete_session <session_id>`
- 调用 `agent.delete_session(session_id)`
- 成功提示：
  - `已删除会话 <id>`
- 失败提示：
  - `未找到会话 <id>`

---

## Task 5: 跑测试

### 定向测试
```bash
python3 -m pytest tests/test_agent_integration.py -q
```

### 回归测试
```bash
python3 -m pytest \
  tests/test_phase4_mempalace_integration.py \
  tests/test_phase4_mempalace_adapter.py \
  tests/test_phase4_memory_injection.py \
  tests/test_phase4_memory_end_to_end.py \
  tests/test_agent_integration.py \
  tests/test_phase3_main_loop_integration.py -q
```

---

## Task 6: 提交

建议 commit message：
```bash
git commit -m "feat: 增强会话恢复与显式删除命令"
```
