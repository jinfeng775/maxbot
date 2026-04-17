---
description: "测试技能生成通知功能"
triggers: ["test notification skill", "test_function"]
tools: []
source: "examples/test_notification.py"
source_function: "test_function"
version: 1
confidence: 1.0
generated: true
tags: ["test", "notification"]
---

# test_notification_skill

测试技能生成通知功能

## 来源

- 文件: `examples/test_notification.py`
- 函数: `test_function`
- 版本: 1
- 置信度: 100%

## 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `message` | string |  | 测试消息 |

## 使用方式

当用户请求与 `test_notification_skill` 相关的任务时，自动调用此技能的 handler。

Handler 位于: `handler.py`
