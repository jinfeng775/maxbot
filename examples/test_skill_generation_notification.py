"""
测试技能生成通知功能

演示当技能生成时，会自动打印通知
"""

from pathlib import Path
import sys

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.knowledge.capability_extractor import ExtractedCapability
from maxbot.knowledge.skill_factory import SkillFactory

print("=" * 70)
print("测试技能生成通知")
print("=" * 70)

# 定义一个测试能力
test_capability = ExtractedCapability(
    name="test_notification_skill",
    description="测试技能生成通知功能",
    source_file="examples/test_notification.py",
    source_function="test_function",
    parameters={
        "message": {
            "type": "string",
            "description": "测试消息",
        },
    },
    required_params=[],
    tags=["test", "notification"],
    handler_code="""
def handle_test_notification_skill(args, agent):
    '''
    测试技能生成通知

    Args:
        args: 包含 message 的字典
        agent: Agent 实例

    Returns:
        str: 测试结果
    '''
    message = args.get("message", "Hello!")
    return f"✅ 测试成功: {message}"
""",
    confidence=1.0,
)

print("\n📝 定义测试能力:")
print(f"   名称: {test_capability.name}")
print(f"   描述: {test_capability.description}")

print("\n" + "=" * 70)
print("🔧 调用 SkillFactory.generate()...")
print("=" * 70)

# 生成技能（会自动打印通知）
factory = SkillFactory(output_dir="~/.maxbot/skills")
skills = factory.generate([test_capability], overwrite=True)

print("\n" + "=" * 70)
print("✅ 测试完成！")
print("=" * 70)

print(f"\n📊 生成的技能数量: {len(skills)}")
if skills:
    print(f"📦 技能名称: {skills[0].name}")
    print(f"📄 SKILL.md: {skills[0].skill_md_path}")
    print(f"📄 handler.py: {skills[0].handler_path}")
