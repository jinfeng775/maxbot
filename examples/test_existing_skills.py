"""
测试技能管理工具 - 操作已存在的技能
"""

from pathlib import Path
import sys

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.tools._registry import registry

# 加载技能管理工具
import maxbot.tools.skill_manager

print("=" * 60)
print("技能管理工具测试 - 已存在的技能")
print("=" * 60)

print("\n📋 测试 1: 列出所有技能")
print("-" * 60)
result = registry.call("list_skills", {"pattern": ""})
print(result)

print("\n📋 测试 2: 查看技能详情")
print("-" * 60)
result = registry.call("get_skill", {"name": "translator_detect_language"})
print(result)

print("\n📋 测试 3: 更新技能")
print("-" * 60)
result = registry.call("update_skill", {
    "name": "translator_detect_language",
    "description": "检测文本语言 - 使用字符分析",
    "tags": "language,detection,auto-extracted"
})
print(result)

print("\n📋 测试 4: 验证更新")
print("-" * 60)
result = registry.call("get_skill", {"name": "translator_detect_language"})
print(result)

print("\n📋 测试 5: 获取技能内容")
print("-" * 60)
result = registry.call("get_skill_content", {"name": "translator_detect_language"})
print(result[:800] + "\n...")

print("\n" + "=" * 60)
print("✅ 所有测试完成！")
print("=" * 60)
