# MaxBot 第四阶段前置整理报告

**阶段**: Phase 4 - 记忆持久化系统前置整理  
**日期**: 2026-04-18  
**状态**: ✅ 已完成前置审查，进入可规划状态

---

## 1. 目标

本次不是直接实现 Phase 4，而是完成 **第四阶段启动前整理**，明确：
- 现有代码基础是否可承接 Phase 4
- 当前测试阻塞点是什么
- Phase 4 需要先修哪些兼容层/命名层/接口层问题
- 第四阶段如何与 Phase 3 的 instinct learning system 正确衔接

---

## 2. 当前现状审查结论

### 2.1 已存在的 Phase 4 基础

#### Memory 基础模块
路径：`maxbot/core/memory.py`

当前已有：
- `MemoryEntry`
- `Memory`
- SQLite 存储
- FTS5 搜索
- `set/get/delete/search/list_all/export_text`

说明：
- 这说明 Phase 4 不是从零开始
- 已经有一个“可工作的最小持久记忆层”
- 但它当前更偏底层 KV + 搜索存储，还没有形成完整的“分层记忆系统”产品形态

#### Session 存储
路径：`maxbot/sessions/__init__.py`

当前已有：
- `Session`
- `SessionStore`
- session sqlite 持久化
- 与 memory.db 的基础连接

说明：
- 第四阶段可以基于 `SessionStore + Memory` 继续扩展
- 但当前 session / memory / instinct 的边界尚未文档化统一

---

### 2.2 当前阻塞点

#### 阻塞点 A：Phase 4 测试与实现命名不一致

测试：`tests/test_phase4.py`

它期望存在：
- `GatewayServer`
- `GatewayConfig`
- `ChatRequest`

但当前实现 `maxbot/gateway/server.py` 实际提供的是：
- `MaxBotGateway`
- `GatewayConfig`
- `MessageRequest`
- `MessageResponse`
- `TaskRequest`
- `TaskResponse`

结论：
- **测试与实现接口已漂移**
- 需要在正式进入 Phase 4 前先确定是：
  1. 修实现对齐旧测试接口
  2. 还是更新测试与当前网关设计对齐

#### 阻塞点 B：Gateway API 设计与测试期望不一致

`tests/test_phase4.py` 期望的网关能力包括：
- `server.app`
- `/health`
- `/tools`
- `/tools/{name}/call`
- `/sessions`
- `/sessions/{id}/reset`
- session manager 对象
- API key 认证白名单逻辑

当前 `maxbot/gateway/server.py`：
- 有 FastAPI app
- 但接口集合、返回格式、认证行为与测试不完全一致
- 缺 `GatewayServer` 兼容封装
- 缺 `ChatRequest` 兼容模型
- 缺测试所期待的 `session_manager` 接口层

#### 阻塞点 C：Phase 4 范围混杂了“gateway 多平台”和“memory persistent”

从命名上看：
- `tests/test_phase4.py` 实际更像 **Gateway 多平台阶段测试**
- 而进化总计划中的 Phase 4 是 **记忆持久化系统**

结论：
- 当前阶段编号在代码/测试/计划之间有语义漂移
- 进入 Phase 4 前必须先统一：
  - “计划里的 Phase 4”到底指 memory system
  - 还是历史代码里的 gateway phase4

否则后续会一直状态模糊

---

## 3. 与 Phase 3 的衔接关系

Phase 3 已完成的是：
- instinct 学习闭环
- pattern 提取/验证/应用/治理

Phase 4 应承接的是：
- 长期记忆分层
- memory retrieval
- project/user/global/session 语义化存储
- 与 instinct store 明确边界

### 推荐边界划分

#### InstinctStore 负责
- 可复用策略
- 行为模式
- 错误修复模式
- 自动应用经验

#### Memory 负责
- 稳定事实
- 用户偏好事实
- 项目上下文
- 可检索历史状态
- 长期上下文片段

### 不应混淆
- instinct 不是普通记忆
- memory 不是 pattern validator 的替代品
- session store 不是 user/global memory 的替代品

---

## 4. 第四阶段启动前需要先做的整理项

### P0：定义边界与命名
1. 明确 Phase 4 在计划中指 **Memory Persistence System**
2. 明确历史 `tests/test_phase4.py` 属于 gateway 兼容问题，不等同于当前计划中的 Phase 4
3. 在文档中标清：
   - memory system
   - session store
   - instinct store
   三者职责边界

### P1：建立 Memory System 设计文档
需要补充：
- 4 层记忆模型：SESSION / PROJECT / USER / GLOBAL
- 写入策略
- 检索策略
- 注入 prompt 策略
- 清理与压缩策略
- 与 instinct 的协作方式

### P2：建立 Phase 4 实施计划
要拆成小步：
1. 统一 memory domain model
2. 扩展 current `Memory` 到多层语义
3. 接入 Agent session / project / user contexts
4. 检索注入与限额控制
5. 回归测试

### P3：单独处理历史 gateway phase4 测试
建议不要把它混进“记忆持久化阶段”主线。
推荐：
- 单列为“gateway compatibility cleanup”
- 后续单独修正 `tests/test_phase4.py`

---

## 5. 当前建议的执行顺序

### 第一批：先文档与计划
1. 补 Phase 4 memory architecture 文档
2. 补 Phase 4 implementation plan
3. 更新总计划衔接说明

### 第二批：再进入实现
4. 扩展 Memory 为分层记忆系统
5. 接入 SessionStore / Agent
6. 做 retrieval / injection / pruning
7. 补回归测试

### 第三批：最后清历史兼容债
8. 单独处理 gateway `tests/test_phase4.py` 与当前实现漂移问题

---

## 6. 是否满足进入第四阶段条件

**结论：满足，但应先做文档与边界统一。**

原因：
- Phase 3 已经稳定完成
- Memory / SessionStore 已有基础设施
- 当前最大问题不是“没法做”，而是“阶段命名和范围漂移”

所以推荐状态：

**✅ 可启动 Phase 4 规划**  
**⚠ 先做边界统一与实施计划，再开始正式开发**
