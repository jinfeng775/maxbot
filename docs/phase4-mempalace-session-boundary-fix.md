# Phase 4 MemPalace / SessionStore 边界修复说明

## 问题背景

当前 MaxBot 的第四阶段同时接入了三层与记忆相关的能力：

- `SessionStore`：保存当前会话消息历史与 metadata
- 内置 `Memory`：保存 `session / project / user / global` 四层稳定事实
- `MemPalace`：外接长期记忆召回层

本次修复前存在三个实际问题：

1. `_build_memory_context()` 直接把内部 memory 与 MemPalace 结果拼在同一个“持久记忆”块里，导致模型容易把外部召回错当成“自身记忆”。
2. 用户问“上次聊到哪了 / 上一轮怎么决定的”时，没有优先从 `SessionStore` 取会话历史，而是把问题继续当成普通 memory / MemPalace 检索问题。
3. `MemPalaceAdapter.store_session()` / `store_message()` 只在 Python `mempalace` 包可导入时才会写入；如果环境只有 CLI 没有 Python 包，读取能用、写入失败，导致“记忆宫殿查不到会话信息”。

## 修复后的边界

### 1. SessionStore

`SessionStore` 是 **会话历史的权威来源**。

适用内容：

- 当前 session 的 user / assistant / tool 消息
- session 标题
- session metadata（例如 `project_id`、`user_id`、`conversation_turns`）

适用查询：

- “我们上次聊到哪了？”
- “上一轮怎么决定的？”
- “把刚才的会话历史总结一下”

规则：

- 如果是会话回溯类问题，优先注入 `SessionStore` 历史。
- 如果 `SessionStore` 与外部记忆宫殿结果冲突，**以 `SessionStore` 为准**。

### 2. 内置 Memory

内置 `Memory` 只负责 **稳定事实与可复用上下文**。

适用内容：

- 用户偏好
- 项目事实
- 跨轮仍然有效的结论
- global 规则

规则：

- `_build_memory_context()` 现在只生成内部 memory，不再夹带 MemPalace 内容。
- 在增强 system prompt 里，这部分继续作为“相关记忆”注入。

### 3. MemPalace

`MemPalace` 是 **外部长期记忆召回层**，不是当前会话原文。

适用内容：

- 更长时间跨度的档案召回
- 外部材料/归档对话的补充线索
- SessionStore 与内置 Memory 之外的 recall 辅助

规则：

- 在 prompt 中单独放入“外部记忆宫殿召回”分区。
- 明确声明：**不是当前会话逐字记录，不能替代 SessionStore 会话历史。**
- 如果当前请求属于会话回溯类，还会额外声明：**若与 SessionStore 冲突，以 SessionStore 为准。**

## 本次实现要点

### `/new` / `/reset` 会话边界修复（对齐 Hermes）

现在 MaxBot 的 CLI 会话边界语义改成：

- `/new`
  - 先保存当前 session 到 `SessionStore`
  - 再把当前 session 归档到 `MemPalace`
  - 然后生成新的 `session_id`
  - 清空当前上下文
  - **旧会话不删除**
- `/reset`
  - 只清空当前运行时上下文
  - 保留当前 `session_id`
  - 保留 `SessionStore` 中的会话历史
- `/sessions`
  - 列出最近历史会话
  - 展示 `session_id / title / updated_at`
- `/resume <session_id>`
  - 切换到指定历史会话
  - 切换前先保存当前会话
  - 若开启 `MemPalace`，切换前也会归档当前会话

这与 Hermes 的“fresh session ID + preserve history”语义对齐，而不是过去那种 `/new` 直接删除当前 session 的行为。

### Prompt 路由修复

`maxbot/core/agent_loop.py`

新增/调整：

- `_is_session_recall_query(user_message)`
- `_build_session_recall_context(user_message)`
- `_build_external_memory_context(user_message)`
- `_build_memory_context()` 仅保留内部 memory
- `_get_enhanced_system_prompt()` 改为三路注入：
  1. `相关会话历史`
  2. `相关记忆`
  3. `外部记忆宫殿召回`

### MemPalace 写入回退修复

`maxbot/memory/mempalace_adapter.py`

新增：

- `_store_session_via_cli_mine(...)`

行为：

- 如果 Python `mempalace` 包可用，继续走原来的 Python API 写入。
- 如果 Python 包不可用但 `mempalace` CLI 可用，则自动导出临时 convo 文件并执行：

```bash
mempalace mine <temp_dir> --mode convos --wing <wing>
```

这样“只有 CLI 没有 Python 包”的环境也能写入会话。

### 默认配置修复

`maxbot/config/default_config.yaml`

- `mempalace_enabled` 默认值改为 `false`

目的：

- 与 `SessionConfig.mempalace_enabled = False` 保持一致
- 避免默认就开启外部召回，进一步加重边界混淆

## 回归测试

本次新增/修复的测试覆盖了：

- 默认配置下 MemPalace 关闭
- prompt 中内部记忆与 MemPalace 分区隔离
- `_build_memory_context()` 不再夹带 MemPalace
- 会话回溯问题优先使用 `SessionStore`
- 仅有 CLI 时，`MemPalaceAdapter.store_session()` 可以回退写入
- `Agent.save_session()` 仍能把 session 同步到 MemPalace

验证命令：

```bash
python3 -m pytest tests/test_phase4_mempalace_integration.py tests/test_phase4_mempalace_adapter.py -q
```

通过结果：

- `15 passed`

## 结论

修复后，MaxBot 的 Phase 4 记忆边界变为：

- **会话历史 → SessionStore**
- **稳定事实 → 内置 Memory**
- **外部长程召回 → MemPalace**

这三层现在在：

- 检索路由
- prompt 注入
- 写入回退
- 默认配置

上都已经更明确，不再把“记忆宫殿”混成“自己记忆”或“当前会话历史”。
