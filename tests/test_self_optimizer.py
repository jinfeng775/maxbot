"""
测试 MaxBot 自我优化系统
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from maxbot.knowledge.self_optimizer import SelfOptimizer, OptimizationResult


def test_prompt_optimization():
    """测试提示词优化"""
    print("\n" + "=" * 70)
    print("🧪 测试 1: 提示词优化")
    print("=" * 70)
    
    # 创建优化器
    optimizer = SelfOptimizer(
        project_path="/root/maxbot",
        max_iterations=20,  # 使用较少的迭代次数进行测试
    )
    
    # 测试提示词
    prompt = "你是一个 AI 助手，请回答用户的问题。"
    
    # 优化提示词
    result = optimizer.optimize_prompt(
        prompt_name="test_prompt",
        prompt_text=prompt,
        iterations=10,
    )
    
    print(f"✅ 优化完成")
    print(f"  方法: {result.method}")
    print(f"  迭代次数: {result.iterations}")
    print(f"  最佳分数: {result.best_score:.3f}")
    print(f"  原始长度: {result.metrics.get('initial_length', 0)}")
    print(f"  最终长度: {result.metrics.get('final_length', 0)}")
    print(f"  改进比例: {result.metrics.get('improvement_ratio', 0):.3f}")
    
    print(f"\n📝 改进建议（前 5 个）:")
    for i, suggestion in enumerate(result.suggestions[:5], 1):
        print(f"  {i}. {suggestion}")
    
    print(f"\n📄 优化后的提示词（前 200 字符）:")
    print(f"  {result.improved_text[:200]}...")
    
    return True


def test_skill_optimization():
    """测试技能优化"""
    print("\n" + "=" * 70)
    print("🧪 测试 2: 技能优化")
    print("=" * 70)
    
    # 创建优化器
    optimizer = SelfOptimizer(
        project_path="/root/maxbot",
        max_iterations=20,
    )
    
    # 测试技能
    skill = """def handler():
    # 简单的技能处理函数
    return "Hello, World!"
"""
    
    # 优化技能
    result = optimizer.optimize_skill(
        skill_name="test_skill",
        skill_text=skill,
        iterations=10,
    )
    
    print(f"✅ 优化完成")
    print(f"  方法: {result.method}")
    print(f"  迭代次数: {result.iterations}")
    print(f"  最佳分数: {result.best_score:.3f}")
    print(f"  原始行数: {result.metrics.get('initial_lines', 0)}")
    print(f"  最终行数: {result.metrics.get('final_lines', 0)}")
    print(f"  有文档字符串: {result.metrics.get('has_docstring', False)}")
    print(f"  有注释: {result.metrics.get('has_comments', False)}")
    
    print(f"\n📝 改进建议（前 5 个）:")
    for i, suggestion in enumerate(result.suggestions[:5], 1):
        print(f"  {i}. {suggestion}")
    
    print(f"\n📄 优化后的技能（前 300 字符）:")
    print(f"  {result.improved_text[:300]}...")
    
    return True


def test_code_optimization():
    """测试代码优化"""
    print("\n" + "=" * 70)
    print("🧪 测试 3: 代码优化")
    print("=" * 70)
    
    # 创建优化器
    optimizer = SelfOptimizer(
        project_path="/root/maxbot",
        max_iterations=20,
    )
    
    # 测试代码
    code = """def add(a, b):
    return a + b
"""
    
    # 优化代码
    result = optimizer.optimize_code(
        code_name="test_code",
        code_text=code,
        iterations=10,
    )
    
    print(f"✅ 优化完成")
    print(f"  方法: {result.method}")
    print(f"  迭代次数: {result.iterations}")
    print(f"  最佳分数: {result.best_score:.3f}")
    print(f"  原始行数: {result.metrics.get('initial_lines', 0)}")
    print(f"  最终行数: {result.metrics.get('final_lines', 0)}")
    
    print(f"\n📝 改进建议（前 5 个）:")
    for i, suggestion in enumerate(result.suggestions[:5], 1):
        print(f"  {i}. {suggestion}")
    
    print(f"\n📄 优化后的代码（前 300 字符）:")
    print(f"  {result.improved_text[:300]}...")
    
    return True


def test_custom_eval_function():
    """测试自定义评估函数"""
    print("\n" + "=" * 70)
    print("🧪 测试 4: 自定义评估函数")
    print("=" * 70)
    
    # 创建优化器
    optimizer = SelfOptimizer(
        project_path="/root/maxbot",
        max_iterations=20,
    )
    
    # 自定义评估函数
    def custom_eval(text: str) -> float:
        """自定义评估：奖励包含特定关键词的文本"""
        score = 0.0
        
        keywords = ["优化", "改进", "建议", "分析"]
        for keyword in keywords:
            if keyword in text:
                score += 0.25
        
        return min(score, 1.0)
    
    # 测试提示词
    prompt = "你是一个 AI 助手。"
    
    # 使用自定义评估函数优化
    result = optimizer.optimize_prompt(
        prompt_name="custom_eval_prompt",
        prompt_text=prompt,
        eval_function=custom_eval,
        iterations=10,
    )
    
    print(f"✅ 使用自定义评估函数优化完成")
    print(f"  方法: {result.method}")
    print(f"  迭代次数: {result.iterations}")
    print(f"  最佳分数: {result.best_score:.3f}")
    
    print(f"\n📄 优化后的提示词:")
    print(f"  {result.improved_text}")
    
    return True


def test_early_stop():
    """测试早期停止"""
    print("\n" + "=" * 70)
    print("🧪 测试 5: 早期停止")
    print("=" * 70)
    
    # 创建优化器（设置较小的耐心值）
    optimizer = SelfOptimizer(
        project_path="/root/maxbot",
        max_iterations=100,
        early_stop_patience=3,  # 3 次无改进就停止
    )
    
    # 测试提示词
    prompt = "测试提示词"
    
    # 优化（应该会早期停止）
    result = optimizer.optimize_prompt(
        prompt_name="early_stop_prompt",
        prompt_text=prompt,
        iterations=100,  # 尝试 100 次，但应该会早期停止
    )
    
    print(f"✅ 早期停止测试完成")
    print(f"  方法: {result.method}")
    print(f"  实际迭代次数: {result.iterations}")
    print(f"  最大迭代次数: 100")
    print(f"  是否早期停止: {result.iterations < 100}")
    
    if result.iterations < 100:
        print(f"  ✅ 成功早期停止（节省了 {100 - result.iterations} 次迭代）")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("🚀 MaxBot 自我优化系统测试套件")
    print("=" * 70)
    
    tests = [
        ("提示词优化", test_prompt_optimization),
        ("技能优化", test_skill_optimization),
        ("代码优化", test_code_optimization),
        ("自定义评估函数", test_custom_eval_function),
        ("早期停止", test_early_stop),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            print(f"\n✅ {name}: 通过")
        except Exception as e:
            results.append((name, False))
            print(f"\n❌ {name}: 失败 - {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
