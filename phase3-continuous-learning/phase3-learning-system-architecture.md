# MaxBot 第三阶段：持续学习系统架构与实现

**阶段**: Phase 3 - Continuous Learning System  
**状态**: ✅ MVP 完成（闭环、可测试、可交付）  
**更新日期**: 2026-04-18

---

## 1. 目标

第三阶段的目标是把 MaxBot 从“只记录交互”升级为“能从交互中提炼经验，并在相似场景中再次应用”的持续学习系统。

本阶段当前实现的核心闭环为：

```text
Observation -> Pattern Extraction -> Validation -> Persist -> Match/Apply -> Feedback -> Governance
```

---

## 2. 核心组件职责

### 2.1 LearningLoop

路径：`maxbot/learning/learning_loop.py`

职责：
- 协调观察、提取、验证、存储、应用五个阶段
- 提供同步/异步两条学习链路
- 提供错误学习专用入口
- 在应用 instinct 后回写成功/失败反馈统计
- 管理异步 worker、任务去重、失败重试

主要入口：
- `on_user_message(...)`
- `on_tool_call(...)`
- `on_tool_result(...)`
- `on_session_end(...)`
- `on_error(...)`
- `apply_instinct(...)`
- `cleanup_old_data()`

### 2.2 PatternExtractor

路径：`maxbot/learning/pattern_extractor.py`

职责：
- 聚合 observation 数据
- 从 observation 中提取 pattern candidates
- 提供统一 pattern 数据结构
- 提供错误专用提取入口 `extract_error_pattern(...)`

当前支持 3 类模式：
- `tool_sequence`
- `error_solution`
- `user_preference`

统一 pattern payload 字段：
- `signature`
- `match_context`
- `action`
- `evidence`

### 2.3 PatternValidator

路径：`maxbot/learning/pattern_validator.py`

职责：
- 对所有 pattern 进行统一验证
- 输出统一决策结构
- 拒绝低质量、低安全、低复现性的 pattern

统一验证输出字段：
- `score`
- `confidence`
- `reasons`
- `approved`
- `rejected`

验证维度：
- reproducibility
- value
- safety
- best_practice

### 2.4 InstinctStore

路径：`maxbot/learning/instinct_store.py`

职责：
- 持久化 instinct
- 合并重复 instinct
- 记录命中/成功/失败/最后使用时间
- 维护质量状态与失效状态
- 提供清理与统计接口

当前 lifecycle 字段：
- `usage_count`
- `success_count`
- `failure_count`
- `last_used_at`
- `invalidated_at`
- `quality_state`
- `enabled`

### 2.5 InstinctApplier

路径：`maxbot/learning/instinct_applier.py`

职责：
- 检索相似 instinct
- 计算匹配分数与综合置信度
- 输出触发策略
- 在高置信度场景执行自动应用，在中置信度场景给出建议

当前匹配维度：
- 事件类型
- 工具序列
- 错误签名
- 错误类型
- 用户偏好
- 语义描述相似度

当前置信度分层：
- `high` -> `auto_apply`
- `medium` -> `suggest`
- `low` -> `record`

---

## 3. 同步学习流程

### 3.1 正常 observation 学习

```text
on_user_message
  -> Observer.start_observation
on_tool_call / on_tool_result
  -> Observer.record_*
on_session_end
  -> PatternExtractor.extract_patterns
  -> PatternValidator.validate
  -> InstinctStore.save_instinct
```

特点：
- session 结束时统一提取
- 所有 pattern 入库前必须经过 validator
- pattern 不再允许绕过验证直接写库

### 3.2 错误学习

```text
on_error
  -> PatternExtractor.extract_error_pattern
  -> PatternValidator.validate
  -> InstinctStore.save_instinct
```

错误学习支持字段：
- `error`
- `error_signature`
- `error_type`
- `resolution`
- `resolution_summary`
- `solution_steps`
- `fix_success`
- `tool_name`
- `tool_args`
- `tool_result`
- `user_message`

当前错误分类：
- `tool_error`
- `runtime_error`
- `validation_error`
- `user_correction`（上下文可显式指定）

---

## 4. 异步学习流程

### 4.1 设计

LearningLoop 支持异步 worker：
- `async_worker_count`
- `async_retry_limit`
- `async_retry_backoff`

异步 worker 能力：
- 消费 session/error 学习任务
- 根据 fingerprint 去重
- 遇到临时失败自动重试
- worker 结束前等待队列清空

### 4.2 一致性约束

无论同步还是异步路径，统一遵循：

```text
extract -> validate -> approve/reject -> persist
```

因此 worker 路径与同步路径的输出模型保持一致。

---

## 5. Instinct 生命周期治理

### 5.1 命中与反馈

每次 instinct 被应用或建议后，可回写：
- usage_count
- success_count
- failure_count
- last_used_at

### 5.2 质量状态

当前质量状态：
- `active`
- `degraded`
- `invalidated`

策略：
- 多次失败且成功率过低 -> `invalidated`
- 中度退化 -> `degraded`
- 高质量/恢复后 -> `active`

### 5.3 重复合并

以 pattern `signature` 为主键语义进行重复识别：
- 重复 pattern 不重复新增
- 合并 validation_score 与 pattern_data
- 保留既有 usage stats

### 5.4 清理策略

清理对象：
- 长期未使用 instinct
- 长期无效 instinct
- 已失效且过期 instinct
- 超过上限后的低优先级 instinct

---

## 6. Hook 集成

Agent 主循环已通过 hook 将持续学习系统接入：
- `SESSION_START`
- `PRE_TOOL_USE`
- `POST_TOOL_USE`
- `SESSION_END`
- `ERROR`

这保证学习系统不只是离线存在，而是已进入主循环事件流。

---

## 7. 调试指南

### 7.1 学习未发生

优先检查：
1. `LearningConfig` 是否启用对应开关
2. `min_session_length` / `min_occurrence_count` 是否过高
3. pattern 是否被 validator 拒绝
4. session 是否真的调用了 `on_session_end()`

### 7.2 错误学习未入库

优先检查：
1. `resolution` 是否存在
2. `occurrence_count` 是否达到阈值
3. validator 的 `approved` 是否为 `True`
4. instinct store 数据库是否完成 schema migration

### 7.3 误应用 / 误触发

优先检查：
1. instinct 的 `quality_state`
2. 匹配上下文 `match_context`
3. `auto_apply_threshold`
4. 最近失败次数是否已让 instinct 进入 `degraded` / `invalidated`

### 7.4 异步 worker 问题

优先检查：
1. queue fingerprint 是否误判重复
2. retry limit/backoff 是否太小
3. worker 是否在 shutdown 前完成 `join()`
4. 同步路径结果是否与异步路径一致

---

## 8. 当前测试覆盖

已覆盖：
- pattern extraction 主链
- validator 统一生效
- 错误学习提取/验证/入库
- instinct 匹配与自动应用分层
- 异步 worker 重试与去重
- instinct 统计、失效、清理、去重合并
- hook 与 LearningLoop 集成
- 主循环回归

当前相关验证结果：
- `python3 -m pytest tests/test_phase3.py tests/test_phase3_learningloop_error_learning.py tests/test_phase3_learningloop_hook_integration.py tests/test_phase3_agent_loop_hooks.py tests/test_phase3_main_loop_integration.py tests/test_phase3_pattern_pipeline.py tests/test_phase3_validator_pipeline.py tests/test_phase3_error_learning_and_instincts.py tests/test_phase3_async_and_governance.py test_phase3_learning_system.py test_phase3_observer_config.py -q`
- 结果：`39 passed`

---

## 9. 已知边界

当前为 Phase 3 MVP 完成态，仍有可继续增强的方向：
- 更复杂的 preference 识别维度
- 更细粒度的用户纠正学习
- 更强的语义匹配模型
- 更系统化的 dashboard / metrics 输出
- 与 Phase 4 记忆系统的更深耦合

但第三阶段最关键的“学习闭环 + 验证闭环 + 应用闭环 + 治理闭环”已经成立。
