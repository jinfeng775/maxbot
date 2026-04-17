"""
测试技能注册功能

创建一个可用的技能并测试注册
"""

from pathlib import Path
import sys

# 添加 maxbot 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from maxbot.knowledge.capability_extractor import ExtractedCapability
from maxbot.knowledge.skill_factory import SkillFactory
from maxbot.knowledge.sandbox_validator import batch_validate
from maxbot.knowledge.auto_register import AutoRegister
from maxbot.tools._registry import registry

print("=" * 70)
print("测试技能注册功能")
print("=" * 70)

# 定义一个可用的能力
capability = ExtractedCapability(
    name="say_hello",
    description="向指定的人打招呼",
    source_file="examples/test_skill_registration.py",
    source_function="say_hello",
    parameters={
        "name": {
            "type": "string",
            "description": "要打招呼的人名",
        },
    },
    required_params=[],
    tags=["test", "greeting"],
    handler_code="""
def handle_say_hello(args, agent):
    '''
    向指定的人打招呼

    Args:
        args: 包含 name 的字典
        agent: Agent 实例（可选）

    Returns:
        str: 打招呼的消息
    '''
    name = args.get("name", "朋友")
    return f"你好，{name}！很高兴见到你！"
""",
    confidence=1.0,
)

print("\n📝 定义能力:")
print(f"   名称: {capability.name}")
print(f"   描述: {capability.description}")

# 步骤 1: 生成技能
print("\n" + "=" * 70)
print("步骤 1: 生成技能")
print("=" * 70)

factory = SkillFactory()
skills = factory.generate([capability], overwrite=True)

if skills:
    print(f"✅ 技能生成成功: {skills[0].name}")
else:
    print("❌ 技能生成失败")
    sys.exit(1)

# 步骤 2: 验证安全性
print("\n" + "=" * 70)
print("步骤 2: 验证安全性")
print("=" * 70)

validations = batch_validate([capability])

for validation in validations:
    if validation.is_valid:
        print(f"✅ 验证通过: {validation.capability.name}")
    else:
        print(f"❌ 验证失败: {validation.capability.name}")

# 步骤 3: 注册到工具系统
print("\n" + "=" * 70)
print("步骤 3: 注册到工具系统")
print("=" * 70)

auto_register = AutoRegister(tool_registry=registry)
registrations = auto_register.register_validated(validations, toolset="test")

for reg in registrations:
    if reg.success:
        print(f"✅ 注册成功: {reg.tool_name}")
        print(f"   Toolset: {reg.toolset}")
    else:
        print(f"❌ 注册失败: {reg.tool_name}")
        print(f"   错误: {reg.error}")

# 步骤 4: 测试调用
print("\n" + "=" * 70)
print("步骤 4: 测试调用技能")
print("=" * 70)

# 检查是否已注册
tool = registry.get("say_hello")
if tool:
    print(f"✅ 技能已注册")
    print(f"   描述: {tool.description}")
    print(f"   Toolset: {tool.toolset}")
    print(f"   参数: {list(tool.parameters.keys())}")

    # 调用技能
    print("\n🧪 调用测试:")
    result = registry.call("say_hello", {"name": "张三"})
    print(f"   结果: {result}")

    result = registry.call("say_hello", {"name": "李四"})
    print(f"   结果: {result}")
else:
    print("❌ 技能未注册")

print("\n" + "=" * 70)
print("✅ 测试完成！")
print("=" * 70)

# 显示所有已注册的工具
print("\n📊 当前已注册的工具:")
print("-" * 70)
for toolset in ["builtin", "absorbed", "test"]:
    tools = registry.list_tools(toolset=toolset)
    if tools:
        print(f"\n📦 {toolset} ({len(tools)} 个工具):")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description[:40]}")
