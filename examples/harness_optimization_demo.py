"""
Harness 优化示例

演示如何在 MaxBot 中使用 Meta-Harness 风格的优化器
"""

from pathlib import Path
from openai import OpenAI
import sys

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.knowledge.harness_optimizer import HarnessOptimizer, HarnessCandidate


def mock_evaluation_fn(harness_config: dict, tasks: list[dict]) -> dict:
    """
    模拟评估函数

    在实际使用中，这里应该：
    1. 使用 harness_config 创建 Agent 实例
    2. 在所有任务上运行 Agent
    3. 收集执行轨迹和指标
    4. 返回评分和详细结果

    Args:
        harness_config: Harness 配置（system_prompt, tool_configs 等）
        tasks: 基准测试任务列表

    Returns:
        {
            "score": float,  # 综合评分
            "metrics": {...},  # 详细指标
            "traces": [...],  # 执行轨迹
        }
    """
    import random
    import time

    print(f"  评估 harness: {harness_config.get('name', 'unknown')}")

    # 模拟执行
    time.sleep(0.5)

    # 基于配置生成模拟评分
    # 更长的 system_prompt 通常会提高性能（模拟）
    base_score = 0.5
    if "system_prompt" in harness_config:
        prompt_length = len(harness_config["system_prompt"])
        base_score += min(prompt_length / 1000, 0.3)

    # 添加随机性
    score = min(base_score + random.uniform(-0.05, 0.05), 0.95)

    # 模拟执行轨迹
    traces = []
    for task in tasks[:3]:  # 只记录前 3 个任务的轨迹
        trace = {
            "task_id": task.get("id", "unknown"),
            "success": random.random() < score,
            "steps": random.randint(1, 10),
            "tokens_used": random.randint(100, 1000),
            "error": None if random.random() < score else "模拟错误",
        }
        traces.append(trace)

    return {
        "score": score,
        "metrics": {
            "total_tasks": len(tasks),
            "successful": int(score * len(tasks)),
            "avg_tokens": sum(t["tokens_used"] for t in traces) / len(traces) if traces else 0,
        },
        "traces": traces,
    }


def main():
    """主函数"""
    print("=" * 60)
    print("Meta-Harness 风格优化器演示")
    print("=" * 60)

    # 1. 创建 LLM 客户端
    # 注意：需要设置 OPENAI_API_KEY 环境变量
    try:
        client = OpenAI()
    except Exception as e:
        print(f"❌ 无法创建 OpenAI 客户端: {e}")
        print("   请确保设置了 OPENAI_API_KEY 环境变量")
        return

    # 2. 创建优化器
    optimizer = HarnessOptimizer(
        project_root=Path(__file__).parent.parent,
        work_dir=Path(__file__).parent / ".harness_opt_demo",
    )

    print(f"\n📁 工作目录: {optimizer.work_dir}")

    # 3. 定义基准测试任务
    benchmark_tasks = [
        {"id": f"task_{i}", "description": f"示例任务 {i}"}
        for i in range(10)
    ]
    print(f"📋 基准测试任务: {len(benchmark_tasks)} 个")

    # 4. 定义初始 harness
    initial_harness = {
        "name": "initial",
        "system_prompt": (
            "你是 MaxBot，一个由用户自主开发的 AI 智能体。"
            "你的能力包括：代码编辑、文件操作、Shell 命令执行。"
        ),
        "temperature": 0.7,
        "max_iterations": 50,
    }
    print(f"\n🎯 初始 Harness:")
    print(f"   - System Prompt 长度: {len(initial_harness['system_prompt'])} 字符")
    print(f"   - Temperature: {initial_harness['temperature']}")

    # 5. 执行优化
    print("\n🚀 开始优化...")
    print("-" * 60)

    result = optimizer.optimize(
        llm_client=client,
        benchmark_tasks=benchmark_tasks,
        max_iterations=5,  # 演示用，实际可以更多
        candidates_per_iter=2,
        initial_harness=initial_harness,
        evaluation_fn=mock_evaluation_fn,
        convergence_threshold=0.02,
    )

    # 6. 显示结果
    print("\n" + "=" * 60)
    print("📊 优化结果")
    print("=" * 60)
    print(result.summary())

    # 7. 获取最佳 harness
    best = optimizer.get_best_harness()
    if best:
        print("\n🏆 最佳 Harness:")
        print(f"   - ID: {best.candidate_id}")
        print(f"   - 评分: {best.score:.2%}")
        print(f"   - 配置: {json.dumps(best.config, indent=4, ensure_ascii=False)}")

    # 8. 保存最佳 harness
    if best:
        output_file = Path(__file__).parent / "best_harness.json"
        import json
        output_file.write_text(json.dumps(best.to_dict(), indent=2, ensure_ascii=False))
        print(f"\n💾 最佳 harness 已保存到: {output_file}")


if __name__ == "__main__":
    import json
    main()
