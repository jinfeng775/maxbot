# Phase 4 Memory Boundary

**阶段**: Phase 4 - Memory Persistence System  
**状态**: Draft / 作为实现边界基准  
**更新日期**: 2026-04-18

---

## 1. 目标

本文件用于固定 MaxBot 第四阶段中三个核心存储层的职责边界：

- `SessionStore`
- `Memory`
- `InstinctStore`

目标不是一次性实现完整 Phase 4，而是先回答一个关键问题：

> **什么信息该存到哪里，为什么？**

如果这个边界不先固定，后续实现容易继续出现：

- 把长期事实塞进会话层
- 把行为策略误写进普通记忆层
- 把 pattern learning 和 memory persistence 混在一起

---

## 2. Responsibilities

### 2.1 SessionStore

`SessionStore` 负责：

- 当前会话消息历史
- 会话标题、时间戳
- 会话级 metadata
- 与单次对话强绑定的短期上下文

`SessionStore` 不负责：

- 长期用户偏好知识库
- 项目长期事实库
- 可复用策略模式

### 2.2 Memory

`Memory` 负责：

- 稳定事实
- 用户偏好事实
- 项目上下文事实
- 全局长期知识片段
- 可搜索、可筛选、可注入 prompt 的长期上下文条目

`Memory` 不负责：

- 学习到的策略模式
- validator / pattern pipeline 的决策产物
- 单轮对话消息日志

### 2.3 InstinctStore

`InstinctStore` 负责：

- 可复用策略
- 行为模式
- 错误修复模式
- 自动应用经验
- 命中/成功/失败统计
- 质量状态、失效、清理治理

`InstinctStore` 不负责：

- 普通稳定事实
- 项目说明类知识
- 会话原始消息记录

---

## 3. Allowed Data Examples

### 应进入 Memory 的例子

- `user prefers Chinese`
- `project uses FastAPI + SQLite`
- `repo default branch is main`
- `deployment target is Railway`
- `team prefers pytest over unittest`

这些属于：
- 稳定事实
- 用户偏好
- 项目上下文
- 可以在未来会话中检索复用的信息

### 应进入 InstinctStore 的例子

- `when ImportError + missing package, run pip install ...`
- `for repeated read/search/patch workflow, prefer tool sequence A -> B -> C`
- `for this error signature, apply resolution steps X/Y/Z`
- `for medium-confidence pattern, suggest instead of auto-apply`

这些属于：
- 模式
- 策略
- 经验性动作
- 会被自动匹配/建议/应用的行为规则

### 应进入 SessionStore 的例子

- 当前会话消息列表
- 本轮 assistant/tool 的即时输出
- 当前会话标题
- 当前对话的临时 metadata（例如 project_id/user_id/session flags）

这些属于：
- 单会话上下文
- 不一定值得长期保留的交互历史

---

## 4. Disallowed Data Examples

### 不应写入 Memory 的内容

- `当出现某错误时执行哪些修复步骤`
- `某个 pattern 的 validation score`
- `某次 instinct 自动应用成功率`

原因：这些是策略或 learning pipeline 产物，应该进入 `InstinctStore`。

### 不应写入 InstinctStore 的内容

- `用户喜欢中文回复`
- `当前项目使用 FastAPI`
- `仓库默认分支是 main`

原因：这些是稳定事实，不是策略模式，应该进入 `Memory`。

### 不应只留在 SessionStore 的内容

- 长期稳定的用户偏好
- 多会话复用的项目事实
- 跨会话依然重要的环境说明

原因：这些信息如果只留在 `SessionStore`，会在换会话时丢失长期价值。

---

## 5. Write Path Rules

### SessionStore 写入规则

写入：
- 用户/assistant/tool 消息
- 会话 metadata
- conversation turns 等会话计数

不要写入：
- 需要跨会话检索的长期事实
- 需要自动匹配的行为模式

### Memory 写入规则

写入条件：
- 信息是稳定事实，而不是动作策略
- 信息在未来大概率可检索复用
- 信息不依赖当前单轮上下文才能成立

推荐 scope：
- `session` — 当前会话可复用但仍偏短期
- `project` — 项目级长期事实
- `user` — 用户偏好与稳定习惯
- `global` — 跨项目知识

### InstinctStore 写入规则

写入条件：
- 信息描述的是“在某种上下文下采取什么动作”
- 信息来自 observation -> extraction -> validation -> persist 学习链路
- 信息需要后续参与匹配、建议、自动应用、反馈治理

---

## 6. Retrieval Path Rules

### SessionStore 检索

用于：
- 恢复会话消息历史
- 恢复会话 metadata
- 续接当前对话

### Memory 检索

用于：
- 按 scope/project/user 过滤长期事实
- 注入 prompt 作为背景上下文
- 跨会话复用用户偏好、项目设定、全局说明

### InstinctStore 检索

用于：
- 匹配相似 pattern
- 生成 auto_apply / suggest / record 决策
- 回写 usage/success/failure

---

## 7. Collaboration Rules

三者是协作关系，不是替代关系：

- `SessionStore` 保存当前会话轨迹
- `Memory` 保存长期事实
- `InstinctStore` 保存长期策略

推荐协作模型：

```text
Session interaction
  -> SessionStore 保存会话轨迹
  -> LearningLoop 从会话/工具观察中提取 pattern
  -> InstinctStore 保存策略模式
  -> Agent/Memory 保存稳定事实
```

关键原则：

> **事实进 Memory，策略进 InstinctStore，会话过程进 SessionStore。**

---

## 8. Compatibility Notes

第四阶段第一步必须保持以下兼容性：

1. 旧 `Memory.set/get/delete/search/list_all/export_text` 调用不能直接失效
2. `SessionStore` 仍然是会话消息主存储
3. `InstinctStore` 的现有 Phase 3 生命周期逻辑不能被改坏
4. `Agent` 当前 memory tool 需要兼容旧参数格式
5. 历史 `tests/test_phase4.py` 仍视为 gateway compatibility 问题，不作为本边界文档的验收标准

---

## 9. Summary

本边界文档的最终结论是：

- `SessionStore` = 会话轨迹层
- `Memory` = 长期事实层
- `InstinctStore` = 长期策略层

后续 Phase 4 实现都应以这个边界为前提，避免继续出现语义漂移。
