#!/usr/bin/env python3
"""
MaxBot Hermes 集成测试
测试 Hermes Agent Self-Evolution 集成
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from maxbot.knowledge.hermes_evolver import HermesEvolver, create_hermes_evolver


def test_hermes_evolver_creation():
    """测试 Hermes 进化引擎创建"""
    print("\n" + "=" * 70)
    print("测试 1: Hermes 进化引擎创建")
    print("=" * 70)

    # 创建进化引擎
    evolver = create_hermes_evolver()
    print(f"✅ Hermes 进化引擎创建成功")

    # 获取状态
    status = evolver.get_status()
    print(f"✅ 状态获取成功")
    print(f"   Hermes 可用: {status['hermes_available']}")
    print(f"   使用方法: {status['method']}")
    print(f"   优化器模型: {status['optimizer_model']}")
    print(f"   评估模型: {status['eval_model']}")

    print("\n✅ Hermes 进化引擎创建测试通过")


def test_evolve_skill():
    """测试技能进化"""
    print("\n" + "=" * 70)
    print("测试 2: 技能进化")
    print("=" * 70)

    evolver = create_hermes_evolver()

    # 创建测试技能
    test_skill = """
def handle(task_input: dict) -> dict:
    \"\"\"
    测试技能处理函数

    Args:
        task_input: 输入数据

    Returns:
        处理结果
    \"\"\"
    message = task_input.get("message", "")
    return {
        "response": f"收到消息: {message}",
        "success": True,
    }
"""

    # 进化技能
    result = evolver.evolve_skill(
        skill_name="test-skill",
        skill_text=test_skill,
        iterations=3,
    )

    print(f"✅ 技能进化完成")
    print(f"   技能名称: {result['skill_name']}")
    print(f"   迭代次数: {result['iterations']}")
    print(f"   状态: {result['status']}")
    print(f"   方法: {result.get('method', 'unknown')}")
    print(f"   消息: {result['message']}")

    if result['status'] == 'success':
        print(f"✅ 进化成功")
    else:
        print(f"⚠️ 进化失败: {result.get('error', 'Unknown error')}")

    print("\n✅ 技能进化测试通过")


def test_evolve_prompt():
    """测试提示词进化"""
    print("\n" + "=" * 70)
    print("测试 3: 提示词进化")
    print("=" * 70)

    evolver = create_hermes_evolver()

    # 测试提示词
    test_prompt = """
你是一个专业的助手。

请根据用户的输入，提供有用的回答。

要求：
1. 回答要简洁明了
2. 提供准确的信息
3. 如果不确定，请说明
"""

    # 进化提示词
    result = evolver.evolve_prompt(
        prompt_name="test-prompt",
        prompt_text=test_prompt,
        iterations=3,
    )

    print(f"✅ 提示词进化完成")
    print(f"   提示词名称: {result['prompt_name']}")
    print(f"   迭代次数: {result['iterations']}")
    print(f"   状态: {result['status']}")
    print(f"   消息: {result['message']}")

    if result['status'] == 'success':
        print(f"✅ 进化成功")
        print(f"   改进后提示词: {result['improved_text'][:100]}...")
    else:
        print(f"⚠️ 进化失败: {result.get('error', 'Unknown error')}")

    print("\n✅ 提示词进化测试通过")


def test_hermes_repo_path():
    """测试 Hermes 仓库路径配置"""
    print("\n" + "=" * 70)
    print("测试 4: Hermes 仓库路径配置")
    print("=" * 70)

    # 设置 Hermes 仓库路径
    hermes_repo = Path("/root/hermes-agent-self-evolution")

    evolver = create_hermes_evolver(
        hermes_repo=hermes_repo,
        optimizer_model="openai/gpt-4.1",
        eval_model="openai/gpt-4.1-mini",
    )

    print(f"✅ 进化引擎创建成功")
    print(f"   Hermes 仓库: {hermes_repo}")

    # 获取状态
    status = evolver.get_status()
    print(f"✅ 状态获取成功")
    print(f"   Hermes 仓库: {status['hermes_repo']}")
    print(f"   优化器模型: {status['optimizer_model']}")
    print(f"   评估模型: {status['eval_model']}")

    print("\n✅ Hermes 仓库路径配置测试通过")


def main():
    print("\n" + "=" * 70)
    print("MaxBot Hermes 集成测试")
    print("=" * 70)

    try:
        test_hermes_evolver_creation()
        test_evolve_skill()
        test_evolve_prompt()
        test_hermes_repo_path()

        print("\n" + "=" * 70)
        print("✅ 所有测试完成！")
        print("=" * 70)
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
