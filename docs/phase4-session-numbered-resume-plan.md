# Phase 4 会话编号恢复优化

## 目标

为 MaxBot CLI 的历史会话恢复增加编号快捷方式，降低复制完整 `session_id` 的成本。

## 本次改动

- `/resume 1` 这类纯数字参数，按最近会话列表顺序解释为编号。
- 编号顺序与 `/sessions`、`/resume` 无参数时展示顺序保持一致：按 `updated_at DESC`。
- 若输入同时匹配真实 `session_id`，优先按真实 `session_id` 恢复，避免破坏兼容性。
- 编号超出范围或小于等于 0 时，返回恢复失败，不切换当前会话。
- CLI 帮助与 `/resume` 无参数提示同步更新为 `session_id` / `编号` 双用法。

## 验证

- `tests/test_agent_integration.py`
  - `test_resume_session_accepts_recent_session_index`
  - `test_resume_session_rejects_out_of_range_index`
- 相关 Phase 4 / Phase 3 回归切片继续保持绿色。
