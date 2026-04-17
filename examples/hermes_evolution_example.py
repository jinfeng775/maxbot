#!/usr/bin/env python3
"""
MaxBot Hermes 进化引擎使用示例

演示如何使用 Hermes 进化引擎来进化技能和提示词
"""

from pathlib import Path
from maxbot.knowledge.hermes_evolver import HermesEvolver


def main():
    print("=" * 60)
    print("MaxBot Hermes 进化引擎示例")
    print("=" * 60)

    # 1. 创建进化引擎
    print("\n1. 创建进化引擎")
    evolver = HermesEvolver(
        hermes_repo=Path("/root/hermes-agent-self-evolution"),
        optimizer_model="openai/gpt-4.1",
        eval_model="openai/gpt-4.1-mini",
    )

    # 2. 获取状态
    print("\n2. 获取进化引擎状态")
    status = evolver.get_status()
    print(f"   Hermes 可用: {status['hermes_available']}")
    print(f"   使用方法: {status['method']}")
    print(f"   优化器模型: {status['optimizer_model']}")
    print(f"   评估模型: {status.get('eval_model', 'N/A')}")

    # 3. 进化技能
    print("\n3. 进化技能")
    skill_code = '''
def handler(text: str) -> str:
    """
    简单的文本处理器

    Args:
        text: 输入文本

    Returns:
        处理后的文本
    """
    return text.upper()
'''

    result = evolver.evolve_skill(
        skill_name="text_processor",
        skill_text=skill_code,
        iterations=3,
    )

    print(f"   技能名称: {result['skill_name']}")
    print(f"   迭代次数: {result['iterations']}")
    print(f"   状态: {result['status']}")
    print(f"   方法: {result['method']}")
    if result['status'] == 'success':
        print("   ✅ 进化成功")
        print(f"   改进后技能（前100字符）:")
        improved = result['improved_text']
        print("   " + improved[:100] + "...")
    else:
        print(f"   ❌ 进化失败: {result.get('error', '未知错误')}")

    # 4. 进化提示词
    print("\n4. 进化提示词")
    prompt = """你是一个专业的助手。
请根据用户的输入，提供有用的回答。
要求：
1. 回答要简洁明了
2. 提供准确的信息
3. 如果不确定，请说明
"""

    result = evolver.evolve_prompt(
        prompt_name="assistant_prompt",
        prompt_text=prompt,
        iterations=3,
    )

    print(f"   提示词名称: {result['prompt_name']}")
    print(f"   迭代次数: {result['iterations']}")
    print(f"   状态: {result['status']}")
    if result['status'] == 'success':
        print("   ✅ 进化成功")
        print(f"   改进后提示词:")
        improved = result['improved_text']
        for line in improved.split('\n')[:10]:
            print(f"   {line}")
    else:
        print(f"   ❌ 进化失败: {result.get('error', '未知错误')}")

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
