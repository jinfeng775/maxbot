---
description: "设置或查询会话轮询次数限制。超过限制后，Agent 会终止任务并返回提示。"
triggers: ["set conversation limit", "AgentConfig"]
tools: []
source: "maxbot/core/agent_loop.py"
source_function: "AgentConfig"
version: 1
confidence: 1.0
generated: true
tags: ["session", "limit", "control"]
---

# set_conversation_limit

设置或查询会话轮询次数限制。超过限制后，Agent 会终止任务并返回提示。

## 来源

- 文件: `maxbot/core/agent_loop.py`
- 函数: `AgentConfig`
- 版本: 1
- 置信度: 100%

## 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `max_turns` | integer |  | 最大会话轮询次数（默认 40） |
| `reset` | boolean |  | 是否重置当前计数器 |

## 返回值

返回当前设置或操作结果

## 使用方式

当用户请求与 `set_conversation_limit` 相关的任务时，自动调用此技能的 handler。

Handler 位于: `handler.py`
