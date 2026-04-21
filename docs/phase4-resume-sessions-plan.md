# MaxBot `/sessions + /resume` 实现计划

**Goal:** 为 MaxBot CLI 增加 Hermes 风格的 `/sessions` 与 `/resume`，让用户能列出历史会话并恢复旧 session，而不是只能新建/重置。

**Architecture:** 复用当前 `SessionStore` 作为会话历史源。`/sessions` 直接展示 `SessionStore.list_sessions()` 的结果；`/resume <session_id>` 通过 Agent 加载目标 session 的消息并切换 `session_id`。为避免切换时丢失当前会话，切换前先保存当前会话，并在 MemPalace 开启时归档当前会话边界。

**Tech Stack:** Python 3.11, existing `SessionStore`, `Agent`, CLI loop, pytest.

---

## 当前基础

已经具备：
- `SessionStore.list_sessions()`
- `Agent.list_sessions()`
- `Agent._load_session()`
- `Agent.save_session()`
- `Agent.new_session()`
- `MemPalace` session-boundary archive helper

当前缺的：
- CLI `/sessions`
- CLI `/resume <session_id>`
- Agent 级显式 `resume_session(session_id)`

---

## Task 1: 写失败测试

### 文件
- `tests/test_agent_integration.py`

### 新增测试
- `test_resume_session_loads_previous_messages`
- `test_resume_session_saves_current_session_before_switch`
- `test_list_sessions_returns_recent_sessions_for_cli`

### 断言点

#### `test_resume_session_loads_previous_messages`
- 预先创建两个 session：`s1`, `s2`
- `s1` 有消息 A，`s2` 有消息 B
- 当前 agent 在 `s2`
- 调 `agent.resume_session("s1")`
- 断言：
  - 当前 `session_id == "s1"`
  - `agent.messages` 被替换成 `s1` 的消息

#### `test_resume_session_saves_current_session_before_switch`
- 当前 agent 在 `active-session`
- 有未切换前的消息
- 目标 session 为 `target-session`
- 调 `resume_session("target-session")`
- 断言：
  - 当前 session 在切换前已被保存
  - 如果开启 MemPalace，则旧 session 已被归档

#### `test_list_sessions_returns_recent_sessions_for_cli`
- 创建多个 sessions
- 调 `agent.list_sessions()`
- 断言返回包含 `session_id/title/created_at/updated_at`

### 失败验证
```bash
python3 -m pytest tests/test_agent_integration.py -q
```

---

## Task 2: 在 Agent 中实现 `resume_session()`

### 文件
- `maxbot/core/agent_loop.py`

### 最小实现
新增：
- `resume_session(session_id: str) -> bool`

行为：
1. 如果当前有消息：
   - 先 `save_session()`
   - 如果开启 `MemPalace`，归档当前 session
2. 检查目标 session 是否存在，不存在返回 `False`
3. 设置 `self.config.session_id = target_session_id`
4. 清空当前 message manager
5. 调 `_load_session()`
6. 返回 `True`

注意：
- 不删除任何 session
- 不生成新 session
- 不污染目标 session 数据

---

## Task 3: 加 CLI `/sessions`

### 文件
- `maxbot/cli/__init__.py`

### 行为
增加命令：
- `/sessions`

输出格式建议：
- 最近 20 个 session
- 每项显示：
  - session_id
  - title
  - updated_at

示例：
```text
📚 历史会话：
1. persist-session-1 | 第一个会话 | 2026-04-21 04:10
2. 20260421_041532_ab12cd34 | 端口决策 | 2026-04-21 04:15
```

---

## Task 4: 加 CLI `/resume <session_id>`

### 文件
- `maxbot/cli/__init__.py`

### 行为
新增命令：
- `/resume <session_id>`

语义：
- 恢复指定历史 session
- 若成功：输出当前恢复成功提示
- 若失败：提示 session 不存在

建议文案：
```text
♻️ 已恢复会话 <session_id>
```

---

## Task 5: 更新 `/help`

### 文件
- `maxbot/cli/__init__.py`

补充命令列表：
- `/sessions       列出历史会话`
- `/resume <id>    恢复指定历史会话`

---

## Task 6: 跑测试

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

## Task 7: 提交

建议 commit message：
```bash
git commit -m "feat: 增加会话列表与历史会话恢复能力"
```
