# Meta-Harness 优化器实践指南

## 🎯 日常使用场景

### 场景 1：发现 MaxBot 在某类任务上表现不佳

**问题**：你发现 MaxBot 在处理"数据分析任务"时经常失败或效率低。

**解决流程**：

```python
# 步骤 1: 收集失败案例
failed_tasks = [
    {
        "id": "task_001",
        "type": "data_analysis",
        "input": "分析这个 CSV 文件...",
        "expected": "应该返回统计结果...",
        "description": "简单的数据统计任务"
    },
    {
        "id": "task_002",
        "type": "data_analysis",
        "input": "找出异常值...",
        "expected": "应该标记出异常...",
        "description": "异常检测任务"
    },
    # ... 更多失败案例
]

# 步骤 2: 运行优化器
from maxbot.knowledge import HarnessOptimizer
from openai import OpenAI

optimizer = HarnessOptimizer(project_root="/path/to/maxbot")

# 定义针对数据分析的评估函数
def evaluate_data_analysis_harness(harness_config, tasks):
    from maxbot.core.agent_loop import Agent, AgentConfig
    
    # 创建 Agent
    config = AgentConfig(**harness_config)
    agent = Agent(config=config)
    
    results = []
    traces = []
    
    for task in tasks:
        try:
            # 运行任务
            response = agent.chat(task["input"])
            
            # 评估结果（简单示例）
            success = check_result_matches_expected(response, task["expected"])
            
            # 记录详细轨迹
            trace = {
                "task_id": task["id"],
                "task_type": task["type"],
                "input": task["input"],
                "expected": task["expected"],
                "actual": response,
                "success": success,
                "steps": len(agent.get_history()),
                "tokens_used": agent.get_stats()["total_tokens_used"],
                "messages": agent.get_history(),  # 完整的消息历史
                "error": None if success else "输出不符合预期"
            }
            traces.append(trace)
            results.append(success)
            
        except Exception as e:
            # 记录错误轨迹
            trace = {
                "task_id": task["id"],
                "task_type": task["type"],
                "success": False,
                "error": str(e),
                "messages": agent.get_history() if 'agent' in locals() else []
            }
            traces.append(trace)
            results.append(False)
    
    # 计算综合评分
    score = sum(results) / len(results) if results else 0.0
    
    return {
        "score": score,
        "metrics": {
            "total_tasks": len(tasks),
            "successful": sum(results),
            "failed": len(tasks) - sum(results),
        },
        "traces": traces  # 关键：完整的执行轨迹
    }

# 步骤 3: 执行优化
result = optimizer.optimize(
    llm_client=OpenAI(),
    benchmark_tasks=failed_tasks,
    max_iterations=5,
    candidates_per_iter=2,
    initial_harness={
        "system_prompt": "你是 MaxBot...",
        "temperature": 0.7,
    },
    evaluation_fn=evaluate_data_analysis_harness,
)

# 步骤 4: 查看优化结果
print(result.summary())

# 步骤 5: 应用最佳配置
best_harness = optimizer.get_best_harness()
if best_harness and best_harness.score > 0.8:  # 如果改进显著
    print(f"优化成功！评分从 50% 提升到 {best_harness.score:.0%}")
    print(f"最佳配置：{best_harness.config}")
    
    
```

---

## 📊 实际案例：优化代码生成任务

假设我们想优化 MaxBot 在代码生成任务上的表现。

### 步骤 1: 准备基准测试集

```python
# benchmarks/code_generation_tasks.py
CODE_GENERATION_TASKS = [
    {
        "id": "cg_001",
        "description": "简单的函数实现",
        "input": "写一个 Python 函数，计算斐波那契数列的第 n 项",
        "expected_features": ["def fibonacci", "for", "return"],
        "test_input": 10,
        "expected_output": 55,
    },
    {
        "id": "cg_002",
        "description": "类定义",
        "input": "创建一个 Stack 类，支持 push, pop, peek 操作",
        "expected_features": ["class Stack", "def push", "def pop"],
        "test_inputs": [1, 2, 3],
        "expected_outputs": [3, 2, 1],
    },
    {
        "id": "cg_003",
        "description": "数据处理",
        "input": "写一个函数，过滤列表中的偶数并返回平方",
        "expected_features": ["def filter_and_square", "list comprehension"],
        "test_input": [1, 2, 3, 4, 5],
        "expected_output": [1, 9, 25],
    },
]
```

### 步骤 2: 定义评估函数

```python
def evaluate_code_generation(harness_config, tasks):
    """评估代码生成能力"""
    from maxbot.core.agent_loop import Agent, AgentConfig
    
    config = AgentConfig(**harness_config)
    agent = Agent(config=config)
    
    results = []
    traces = []
    
    for task in tasks:
        try:
            # 生成代码
            response = agent.chat(task["input"])
            
            # 检查是否包含预期特性
            features_found = sum(
                1 for feature in task["expected_features"]
                if feature.lower() in response.lower()
            )
            
            # 综合评分
            feature_score = features_found / len(task["expected_features"])
            success = feature_score > 0.7
            
            # 记录轨迹
            trace = {
                "task_id": task["id"],
                "description": task["description"],
                "input": task["input"],
                "output": response,
                "features_found": features_found,
                "success": success,
                "messages": agent.get_history(),
            }
            traces.append(trace)
            results.append(success)
            
        except Exception as e:
            trace = {
                "task_id": task["id"],
                "success": False,
                "error": str(e),
            }
            traces.append(trace)
            results.append(False)
    
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

### 步骤 3: 运行优化

```python
from maxbot.knowledge import HarnessOptimizer
from benchmarks.code_generation_tasks import CODE_GENERATION_TASKS

optimizer = HarnessOptimizer(
    project_root="/path/to/maxbot",
    work_dir=".harness_opt_code_gen",
)

# 初始配置
initial_config = {
    "system_prompt": (
        "你是 MaxBot，一个擅长编程的 AI 智能体。"
        "你的任务是生成高质量、可执行的 Python 代码。"
    ),
    "temperature": 0.7,
    "max_iterations": 50,
}

print("开始优化代码生成能力...")

result = optimizer.optimize(
    llm_client=OpenAI(),
    benchmark_tasks=CODE_GENERATION_TASKS,
    max_iterations=8,
    candidates_per_iter=3,
    initial_harness=initial_config,
    evaluation_fn=evaluate_code_generation,
    convergence = 0.02,
)

print("\n" + "=" * 60)
print("优化结果")
print("=" * 60)
print(result.summary())

# 查看最佳配置
best = optimizer.get_best_harness()
if best:
    print(f"\n最佳配置:")
    print(f"  评分: {best.score:.2%}")
    print(f"  System Prompt:\n{best.config['system_prompt']}")
    print(f"  Temperature: {best.config.get('temperature', 'N/A')}")
    print(f"  Max Iterations: {best.config.get('max_iterations', 'N/A')}")
```

---

## 🔍 如何判断需要优化？

### 观察指标

1. **任务失败率高**
   ```python
   # 在日常使用中记录失败率
   failure_rate = failed_tasks / total_tasks
   if failure_rate > 0.3:  # 失败率超过 30%
       print("失败率过高，建议运行优化")
   ```

2. **Token 消耗过多**
   ```python
   avg_tokens = total_tokens / total_tasks
   if avg_tokens > 10000:  # 平均每个任务超过 10K tokens
       print("Token 消耗过高，建议优化")
   ```

3. **响应时间过长**
   ```python
   avg_time = total_time / total_tasks
   if avg_time > 30:  # 平均响应超过 30 秒
       print("响应时间过长，建议优化")
   ```

4. **用户反馈差**
   ```python
   # 收集用户评分
   user_satisfaction = sum(user_ratings) / len(user_ratings)
   if user_satisfaction < 3.0:  # 满分 5 分
       print("用户满意度低，建议优化")
   ```

---

## 💡 最佳实践

### 1. 从小规模开始

```python
# 先用少量任务快速验证
quick_test_tasks = benchmark_tasks[:5]

result = optimizer.optimize(
    llm_client=client,
    benchmark_tasks=quick_test_tasks,
    max_iterations=2,  # 快速迭代
    candidates_per_iter=1,
    evaluation_fn=evaluation_fn,
)

# 如果效果好，再用完整数据集
if result.best_score > 0.7:
    result = optimizer.optimize(
        llm_client=client,
        benchmark_tasks=benchmark_tasks,  # 完整数据集
        max_iterations=10,
        candidates_per_iter=3,
        evaluation_fn=evaluation_fn,
    )
```

### 2. 保存和加载优化状态

```python
# 保存当前优化状态
import json
state = {
    "current_best": optimizer.get_best_harness().to_dict(),
    "history": optimizer.get_history(),
}
Path("optimization_state.json").write_text(json.dumps(state))

# 加载之前的状态
state = json.loads(Path("optimization_state.json").read_text())
# 继续优化...
```

---

## 🎓 总结

### 什么时候使用优化器？

1. **发现性能瓶颈**：某类任务表现不佳
2. **持续改进**：希望系统自动优化
3. **配置选择**：不确定哪种配置更好
4. **新任务类型**：需要适应新的使用场景

### 使用流程

```
1. 识别问题 → 观察失败率、用户反馈
2. 收集数据 → 准备基准测试集
3. 定义评估 → 实现评估函数
4. 运行优化 → 调用 optimize()
5. 应用结果 → 部署最佳配置
6. 持续监控 → 定期重新优化
```

### 关键成功因素

- ✅ **好的基准测试集**：代表性强、可重复
- ✅ **丰富的执行轨迹**：包含足够信息用于诊断
- ✅ **合理的评估函数**：准确反映实际需求
- ✅ **适当的迭代次数**：平衡效果和成本

希望这个实践指南能帮助你在日常使用中有效应用 Meta-Harness 优化器！
