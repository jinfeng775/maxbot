# Phase 7 Hook System Audit

## 结论

Phase 7 当前并不是“没有实现”，而是**主体已经存在，但还有两个关键收口点没完成**：

1. `PRE_COMPACT / POST_COMPACT` 没有真正接入 `_compress_context()`
2. `minimal / standard / strict` profile 还是半成品，缺少可观察行为

## 当前发现的核心问题

### 1. compact hooks 只定义了，没有接进主流程
- `hook_events.py` 定义了：
  - `PRE_COMPACT`
  - `POST_COMPACT`
- 但 `agent_loop.py::_compress_context()` 没有触发这两个 hook
- `builtin_hooks.py` 里也没有把 compact hooks 注册到 `BUILTIN_HOOKS`

### 2. `pre_compact_suggest()` 语义漂移
- 名字像 compact hook
- 实际挂在 `PRE_TOOL_USE`
- 函数体还是 `pass`

### 3. profile 逻辑只是存了字符串
- `HookManager.set_profile()` 现在主要只是设置 `_profile`
- `minimal / strict` 的实际启停逻辑还是 TODO
- 现有测试也只是验证 `get_profile()`，没有验收真实行为

### 4. 阻断型 hook 当前很可能不会真正阻断主流程
- `trigger_sync()` 会吞掉 hook 异常并记日志
- `_trigger_hook()` 也有兜底
- 这意味着 strict 下的阻断行为未必真的能阻断执行

### 5. profile 来源不统一
- `HookManager` 内部有 `_profile`
- `builtin_hooks.py` 的 `pre_config_protection()` 又直接读环境变量 `MAXBOT_HOOK_PROFILE`
- 如果只调 `manager.set_profile("strict")`，不一定会触发 strict 行为

## 最小测试补齐建议

建议新增：
- `tests/test_phase7_hook_profiles.py`
- `tests/test_phase7_hook_compact_events.py`

至少补 5 个测试：

1. `minimal` profile 会禁用一部分非关键 hooks
2. `standard` profile 能恢复默认行为
3. `strict` profile 下配置文件保护有更严格表现
4. `_compress_context()` 会触发 `PRE_COMPACT`
5. `_compress_context()` 会触发 `POST_COMPACT`

如果再多补一个，建议：
6. 主循环 `run()` 中上下文压缩路径也会触发 compact hooks

## 最安全的实现顺序

1. 先统一 profile 的“唯一真相”
   - 由 `HookManager` 控制，还是由环境变量控制，必须收敛

2. 先补 profile 测试，再落逻辑

3. 再把 compact hooks 接到 `_compress_context()`

4. 最后统一压缩阈值口径
   - 当前 `compress_at_tokens` / `ContextCompressor` / `_compress_context()` 逻辑并不完全一致

5. 最后跑 Hook + Phase 3 回归

## 风险点
- 如果不处理异常吞掉的问题，strict hook 可能“看起来存在，实际上不阻断”
- 如果 profile 来源继续分裂，测试会很脆弱
- 如果只补枚举和注册，不补主循环触发，还是假完成
