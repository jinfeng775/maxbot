"""
测试禁用通知功能

演示 notify=False 时不会打印通知
"""

from pathlib import Path
import sys

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.knowledge.capability_extractor import ExtractedCapability
from maxbot.knowledge.skill_factory import SkillFactory

print("=" * 70)
print("测试禁用通知功能 (notify=False)")
print("=" * 70)

# 定义一个测试能力
test_capability = ExtractedCapability(
    name="test_silent_skill",
    description="静默生成技能",
    source_file="examples/test_silent.py",
    source_function="silent_function",
    parameters={},
    required_params=[],
    tags=["test", "silent"],
    handler_code="""
def handle_test_silent_skill(args, agent):
    return "静默技能"
""",
    confidence=1.0,
)

print("\n📝 调用 factory.generate(capabilities, notify=False)")
print("预期：不会打印通知\n")

# 生成技能（禁用通知）
factory = SkillFactory(output_dir="~/.maxbot/skills")
skills = factory.generate([test_capability], overwrite=True, notify=False)

print("\n" + "=" * 70)
print("✅ 测试完成！")
print(f"📊 生成的技能数量: {len(skills)}")
if skills:
    print(f"📦 技能名称: {skills[0].name}")
print("=" * 70)
