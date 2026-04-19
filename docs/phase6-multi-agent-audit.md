# Phase 6 Multi-Agent Audit

## 结论

Phase 6 当前最大问题不是“完全没实现”，而是**存在两套并行实现且接口已经漂移**。在继续开发前，必须先收敛主实现。

## 当前发现的核心问题

### 1. Coordinator 有两套实现
- `maxbot/multi_agent/__init__.py`
  - `Coordinator(parent_agent, max_parallel=3)`
  - 面向 `SubTask`
  - 最终返回汇总字符串
- `maxbot/multi_agent/coordinator.py`
  - `Coordinator(max_workers=4)`
  - 面向 `Task`
  - 最终返回结构化 dict

这不是简单重复，而是**同名双主实现**。

### 2. 依赖模型漂移
- `__init__.py` 使用 `depends_on` + 子任务名
- `coordinator.py` 使用 `dependencies` + task_id
- `coordinator.py` 当前是单次扫描 pending 队列，依赖未满足的任务会被跳过，缺少完成后重扫逻辑

### 3. WorkerConfig 重复定义
- `coordinator.py`
- `worker.py`

两边字段几乎相同，但实际调度器并未统一使用 `WorkerAgent`。

### 4. worker.py 与 coordinator.py 脱节
- `worker.py` 有 `WorkerAgent.execute_task()` / `get_status()`
- `coordinator.py` 直接调用 `Agent.run()`
- `current_task/task_count/is_busy` 这套状态没有真正进入调度主链

### 5. `chat()` / `run()` 调用漂移
- `__init__.py` 和 `tools/multi_agent_tools.py` 使用 `child_agent.chat(...)`
- `coordinator.py` / `worker.py` 使用 `run(...)`
- 这是当前最危险的运行时兼容风险之一

### 6. 工具 schema 与运行时分叉
- `maxbot/multi_agent/tools.py` 的 schema 声明与 `maxbot/tools/multi_agent_tools.py` 的真实参数/行为不一致
- 包括：`allowed_tools`、`tasks` 参数形态、`agent_status` 等

## 最小测试补齐建议

至少先补 4 个测试：

1. **能力路由命中测试**
   - 有多个 worker 时，按 capability 选对 worker

2. **能力路由未命中测试**
   - 没有匹配 worker 时返回明确不可路由状态

3. **依赖调度测试**
   - A 完成后 B 才执行，不能永久 pending

4. **结果聚合测试**
   - 聚合结果统一包含：
     - `status`
     - `result`
     - `error`
     - `worker`

建议新增：
- `tests/test_phase6_multi_agent_orchestration.py`
- `tests/test_phase6_multi_agent_routing.py`

## 最安全的实现顺序

1. 先确定唯一主实现
   - 建议以 `coordinator.py` / `worker.py` 为主
   - `__init__.py` 收敛为兼容层 / 导出层

2. 先补测试，再改调度器
   - 先锁定 capability / dependency / aggregation 预期

3. 先统一共享类型
   - 收敛 `WorkerConfig`

4. 再实现 capability-aware `_assign_worker()`

5. 再修依赖调度
   - pending 队列需要重扫，直到稳定

6. 再统一结果 contract

7. 最后收 `multi_agent_tools.py` 和文档

## 风险点
- 直接删一套 Coordinator 会破兼容
- `chat()` / `run()` 不统一会导致隐藏运行时错误
- schema 与 runtime 不一致会让工具层继续漂移
- 当前 `tests/test_multi_agent.py` 更像 smoke test，不足以做阶段验收
