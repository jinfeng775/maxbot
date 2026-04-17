"""
测试技能管理工具

演示:
1. 列出所有技能
2. 查看技能详情
3. 更新技能
4. 重新加载技能
5. 获取技能内容
"""

from pathlib import Path
import sys

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.tools._registry import registry
from maxbot.tools.skill_manager import skill_manager

print("=" * 60)
print("技能管理工具测试")
print("=" * 60)

# 加载技能管理工具
import maxbot.tools.skill_manager

print("\n📋 测试 1: 列出所有技能")
print("-" * 60)
result = registry.call("list_skills", {"pattern": ""})
print(result)

print("\n📋 测试 2: 查看技能详情")
print("-" * 60)
result = registry.call("get_skill", {"name": "set_conversation_limit"})
print(result)

print("\n📋 测试 3: 更新技能")
print("-" * 60)
result = registry.call("update_skill", {
    "name": "set_conversation_limit",
    "description": "管理会话轮询次数限制，防止无限循环",
    "tags": "session,limit,control,important"
})
print(result)

print("\n📋 测试 4: 重新加载技能")
print("-" * 60)
result = registry.call("reload_skill", {"name": "set_conversation_limit"})
print(result)

print("\n📋 测试 5: 获取技能内容（只显示前 200 字符）")
print("-" * 60)
result = registry.call("get_skill_content", {"name": "set_conversation_limit"})
print(result[:500] + "\n...")

print("\n" + "=" * 60)
print("✅ 所有测试完成！")
print("=" * 60)

# 显示所有已注册的工具
print("\n🔧 当前已注册的工具:")
print("-" * 60)
for toolset in ["builtin", "skill_management", "session_control"]:
    tools = registry.list_tools(toolset=toolset)
    if tools:
        print(f"\n📦 {toolset}:")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description[:50]}")
