# MaxBot 会话时间显示优化计划

**Goal:** 让 CLI `/sessions` 与 `/resume` 的时间显示从原始时间戳改成更友好的中文可读格式，例如“刚刚 / 5 分钟前 / 今天 04:10 / 昨天 23:15 / 2026-04-19 08:20”。

**Architecture:** 在 CLI 层增加一个轻量时间格式化 helper，例如 `_format_session_time(ts)`，由 `/sessions` 与 `/resume` 共用。优先做纯展示层改动，不改变 SessionStore 数据结构与 Agent 行为。

**Tech Stack:** Python 3.11, datetime/time, existing CLI loop, pytest.

---

## 当前现状

现在 `/sessions` 与 `/resume` 无参数时，直接打印：

```python
updated={session['updated_at']}
```

这会把浮点时间戳直接吐给用户，体验较差。

---

## Task 1: 写失败测试

### 文件
- `tests/test_agent_integration.py`

### 新增测试
- `test_list_sessions_exposes_timestamps_for_cli_formatting`

这个测试先保证 Agent 层继续稳定提供 `updated_at` / `created_at`，CLI 才能格式化。

CLI 层本轮仍走轻量实现，不额外加复杂交互测试；重点是把时间格式化 helper 写清楚并保证回归通过。

---

## Task 2: 增加 CLI 时间格式化 helper

### 文件
- `maxbot/cli/__init__.py`

### 新增 helper
建议新增：
- `_format_session_time(ts: float | None) -> str`

### 目标格式
- 小于 60 秒：`刚刚`
- 小于 1 小时：`N 分钟前`
- 同一天：`今天 HH:MM`
- 昨天：`昨天 HH:MM`
- 其他：`YYYY-MM-DD HH:MM`

---

## Task 3: 替换 `/sessions` 输出

### 文件
- `maxbot/cli/__init__.py`

把：
```python
updated={session['updated_at']}
```

改成：
```python
updated={_format_session_time(session['updated_at'])}
```

---

## Task 4: 替换 `/resume` 无参数输出

### 文件
- `maxbot/cli/__init__.py`

把最近会话列表展示也改成同样的时间格式。

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
git commit -m "feat: 优化会话列表时间显示"
```
