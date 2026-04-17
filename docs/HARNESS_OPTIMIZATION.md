# Meta-Harness 风格的 Harness 优化

## 概述

基于 [Meta-Harness 论文](https://yoonholee.com/meta-harness/) 的思想，为 MaxBot 实现了一个端到端的 Harness 优化器。

### 核心思想

传统的优化方法将历史压缩为简短摘要或标量评分，而 Meta-Harness 采用不同的方法：

- **完整的文件系统访问**：优化器可以访问所有历史候选者的源代码、执行轨迹和评分
- **执行轨迹保留**：不压缩历史，保留完整的执行日志（高达 10M tokens）
- **诊断驱动**：通过分析失败模式，提出针对性的 harness 修改

### 与 SelfEvolver 的区别

| 特性 | SelfEvolver | HarnessOptimizer |
|------|-------------|------------------|
| 目标 | 从外部吸收新能力 | 优化内部 harness 配置 |
| 上下文 | 能力缺口分析 | 完整执行轨迹 |
| 优化对象 | 工具/技能 | System Prompt、工具定义、上下文管理 |
| 信息来源 | 外部代码仓库 | 历史执行记录 |

## 架构

```
HarnessOptimizer
├── 工作目录 (.maxbot_harness_opt/)
│   ├── candidates/     # 所有候选者配置
│   ├── traces/         # 执行轨迹
│   ├── metrics/        # 评估指标
│   └── proposals/      # 提案记录
├── 优化循环
│   ├── 提案阶段：LLM 分析历史，提出新配置
│   ├── 评估阶段：在基准任务上测试候选者
│   ├── 选择阶段：选择最佳候选者
│   └── 收敛检查：判断是否停止
└── 输出
    ├── 最佳 harness 配置
    ├── 优化历史
    └── 详细报告
```

## 快速开始

### 1. 基本用法

```python
from pathlib import Path
from openai import OpenAI
from maxbot.knowledge.harness_optimizer import HarnessOptimizer

# 创建 LLM 客户端
client = OpenAI()

# 创建优化器
optimizer = HarnessOptimizer(
    project_root="/path/to/maxbot",
    work_dir="/path/to/work_dir",
)

# 定义评估函数
def evaluate_harness(harness_config, tasks):
    """
    在实际任务上评估 harness

    Returns:
        {
            "score": float,        # 综合评分 (0-1)
            "metrics": {...},       # 详细指标
            "traces": [...]        # 执行轨迹
        }
    """
    # 1. 使用 harness_config 创建 Agent
    # 2. 在所有任务上运行 Agent
    # 3. 收集执行轨迹和指标
    # 4. 返回评分和结果
    pass

# 执行优化
result = optimizer.optimize(
    llm_client=client,
    benchmark_tasks=[...],      # 基准测试任务
    max_iterations=10,          # 最大迭代次数
    candidates_per_iter=2,      # 每次迭代生成的候选者数
    initial_harness={...},      # 初始 harness 配置
    evaluation_fn=evaluate_harness,
    convergence_threshold=0.01,  # 收敛阈值
)

# 查看结果
print(result.summary())

# 获取最佳 harness
best = optimizer.get_best_harness()
print(f"最佳评分: {best.score:.2%}")
print(f"最佳配置: {best.config}")
```

### 2. 运行演示

```bash
# 设置 API Key
export OPENAI_API_KEY="your-api-key"

# 运行演示
python examples/harness_optimization_demo.py
```

## 优化对象

HarnessOptimizer 可以优化以下方面：

### 1. System 系统提示词
```python
{
    "system_prompt": "优化后的系统提示词...",
    "temperature": 0.7,
}
```

### 2. 工具定义
```python
{
    "tool_configs": {
        "code_editor": {
            "max_edit_length": 10000,
            "auto_backup": True,
        },
        "shell": {
            "timeout": 60,
            "allowed_commands": [...],
        }
    }
}
```

### 3. 上下文管理
```python
{
    "max_context_tokens": 128000,
.
```

### 4. 迭代控制
```python
{
    "max_iterations": 50,
    "early_stop_patience": 5,
}
```

## 评估函数设计

评估函数是优化的核心，需要：

### 必需返回字段

```python
{
    "score": float,        # 综合评分 (0-1)，越高越好
    "metrics": {           # 详细指标（可选）
        "total_tasks": int,
        "successful": int,
        "avg_tokens": float,
        "avg_time": float,
    },
    "traces": [            # 执行轨迹（重要！）
        {
            "task_id": str,
            "success": bool,
            "steps": int,
            "tokens_used": int,
            "error": str | None,
            "tool_calls": [...],
            "messages": [...],
        },
        ...
    ]
}
```

### 实际示例

```python
def evaluate_harness(harness_config, tasks):
    from maxbot.core.agent_loop import Agent, AgentConfig

    # 创建配置
    config = AgentConfig(**harness_config)

    # 创建 Agent
    agent = Agent(config=config)

    results = []
    traces = []

    for task in tasks:
        # 运行任务
        try:
            response = agent.chat(task["input"])

            # 检查是否成功
            success = check_success(response, task["expected"])

            # 记录轨迹
            trace = {
                "task_id": task["id"],
                "success": success,
                "steps": len(agent.get_history()),
                "tokens_used": agent.get_stats()["total_tokens_used"],
                "error": None if success else "未达到预期输出",
                "messages": agent.get_history(),
            }
            traces.append(trace)
            results.append(success)

        except Exception as e:
            traces.append({
                "task_id": task["id"],
                "success": False,
                "error": str(e),
            })
            results.append(False)

    # 计算评分
    score = sum(results) / len(results) if results else 0.0

    return {
        "score": score,
        "metrics": {
            "total_tasks": len(tasks),
            "successful": sum(results),
        },
        "traces": traces,
    }
```

## 文件系统结构

优化器在工作目录下创建以下结构：

```
.maxbot_harness_opt/
├── candidates/
│   ├── initial.json
│   ├── iter1_cand0.json
│   ├── iter1_cand1.json
│   └── ...
├── traces/
│   ├── initial.jsonl
│   ├── iter1_cand0.jsonl
│   └── ...
├── metrics/
│   └── ...
├── proposals/
│   ├── iter1_cand0.json
│   └── ...
└── optimization_result.json
```

提案者可以通过这些文件访问完整的历史信息。

## 高级用法

### 1. 自定义提案提示

继承 `HarnessOptimizer` 并重写 `_build_proposal_prompt`：

```python
class CustomOptimizer(HarnessOptimizer):
    def _build_proposal_prompt(self, iteration, candidate_idx):
        prompt = super()._build_proposal_prompt(iteration, candidate_idx)
        # 添加自定义指导
        prompt += "\n\n## 特殊约束\n..."
        return prompt
```

### 2. 多维度优化

```python
def multi_objective_evaluation(harness_config, tasks):
    # 评估多个维度
    accuracy = evaluate_accuracy(harness_config, tasks)
    efficiency = evaluate_efficiency(harness_config, tasks)
    safety = evaluate_safety(harness_config, tasks)

    # 加权综合评分
    score = 0.5 * accuracy + 0.3 * efficiency + 0.2 * safety

    return {
        "score": score,
        "metrics": {
            "accuracy": accuracy,
            "efficiency": efficiency,
            "safety": safety,
        },
        "traces": [...],
    }
```

### 3. 并行评估

```python
from concurrent.futures import ThreadPoolExecutor

def parallel_evaluate(harness_config, tasks, n_workers=4):
    def run_task(task):
        # 运行单个任务
        return evaluate_single_task(harness_config, task)

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(run_task, tasks))

    # 汇总结果
    return aggregate_results(results)
```

## 最佳实践

### 1. 设计好的基准测试集

- **多样性**：覆盖不同类型的任务
- **代表性**：反映实际使用场景
- **可重复**：任务输入和期望输出明确
- **可测量**：有清晰的评估标准

### 2. 记录丰富的执行轨迹

轨迹信息越多，优化器越能诊断问题：

```python
{
    "task_id": "task_001",
    "success": True,
    "steps": 5,
    "tokens_used": 1234,
    "time_elapsed": 2.5,
    "error": None,
    "tool_calls": [
        {"name": "read_file", "args": {"path": "file.py"}, "result": "..."},
        {"name": "code_edit", "args": {...}, "result": "..."},
    ],
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
    ],
    "intermediate_states": [...],  # 中间状态（可选）
}
```

### 3. 设置合理的收敛阈值

```python
# 根据任务难度调整
convergence_threshold = 0.01  # 简单任务
convergence_threshold = 0.05  # 困难任务
```

### 4. 保存和加载优化状态

```python
# 保存
optimizer.save_state("checkpoint.json")

# 加载
optimizer = HarnessOptimizer.load_state("checkpoint.json")
```

## 与 MaxBot 集成

### 在 CLI 中使用

```python
# maxbot/cli/harness_opt.py
from maxbot.knowledge.harness_optimizer import HarnessOptimizer

def optimize_harness_command():
    optimizer = HarnessOptimizer(project_root=".")
    result = optimizer.optimize(...)
    print(result.summary())
```

### 作为后台服务

```python
# 定期优化 harness
import schedule

def periodic_optimization():
    optimizer = HarnessOptimizer(...)
    result = optimizer.optimize(...)
    if result.best_score > current_best_score:
        deploy_harness(result.best_overall.config)

schedule.every().day.at("02:00").do(periodic_optimization)
```

## 性能考虑

### 1. 上下文管理

- 每个提案可访问高达 10M tokens
- 使用文件系统避免内存溢出
- LLM 只读取需要的部分

### 2. 评估效率

- 并行运行多个候选者
- 缓存任务结果
- 限制轨迹大小

### 3. 存储优化

```python
# 压缩旧轨迹
optimizer.compress_traces(older_than_days=7)

# 清理工作目录
optimizer.cleanup(keep_last_n=100)
```

## 故障排查

### 问题：评分不提升

**可能原因**：
- 基准测试任务太简单或太难
- 评估函数有问题
- 收敛阈值设置不当

**解决方案**：
- 检查基准测试集质量
- 验证评估函数返回值
- 调整收敛阈值

### 问题：提案质量差

**可能原因**：
- 历史信息不足
- 提示词不清晰
- LLM 模型能力不足

**解决方案**：
- 提供更多初始数据
- 改进提案提示
- 使用更强的 LLM

## 参考资料

- [Meta-Harness 论文](https://yoonholee.com/meta-harness/)
- [MaxBot 文档](../README.md)
- [SelfEvolver 文档](./SELF_EVOLUTION.md)

## 许可证

与 MaxBot 主项目相同
