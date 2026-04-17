"""
演示如何将"会话轮询限制"功能生成为技能

完整流程：
1. 手动定义能力（或从代码中提取）
2. 生成技能（SKILL.md + handler）
3. 验证安全性
4. 自动注册到工具系统
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

# 步骤 1: 定义能力
conversation_limit_capability = ExtractedCapability(
    name="set_conversation_limit",
    description="设置或查询会话轮询次数限制。超过限制后，Agent 会终止任务并返回提示。",
    source_file="maxbot/core/agent_loop.py",
    source_function="AgentConfig",
    parameters={
        "max_turns": {
            "type": "integer",
            "description": "最大会话轮询次数（默认 40）",
            "minimum": 1,
            "maximum": 1000,
        },
        "reset": {
            "type": "boolean",
            "description": "是否重置当前计数器",
            "default": False,
        },
    },
    required_params=[],
    return_description="返回当前设置或操作结果",
    tags=["session", "limit", "control"],
    # Handler 代码将在生成时自动创建
    handler_code="""# Handler for set_conversation_limit

def handle_set_conversation_limit(args, agent):
    '''
    设置或查询会话轮询次数限制

    Args:
        args: 包含 max_turns 和 reset 的字典
        agent: Agent 实例

    Returns:
        str: 操作结果
    '''
    max_turns = args.get("max_turns")
    reset = args.get("reset", False)

    # 查询当前设置
    if max_turns is None and not reset:
        current = agent.config.max_conversation_turns
        current_count = agent._conversation_turns
        return f"当前设置：最大 {current} 次，已使用 {current_count} 次"

    # 重置计数器
    if reset:
        agent._conversation_turns = 0
        return "✅ 会话轮询计数器已重置"

    # 设置新的限制
    if max_turns:
        old_limit = agent.config.max_conversation_turns
        agent.config.max_conversation_turns = max_turns
        return f"✅ 会话轮询限制已更新：{old_limit} → {max_turns}"

    return "❌ 无效的操作参数"
""",
    confidence=1.0,  # 手动定义，置信度 100%
)

print("=" * 60)
print("步骤 1: 定义能力")
print("=" * 60)
print(f"能力名称: {conversation_limit_capability.name}")
print(f"描述: {conversation_limit_capability.description}")
print(f"参数: {list(conversation_limit_capability.parameters.keys())}")

# 步骤 2: 生成技能
print("\n" + "=" * 60)
print("步骤 2: 生成技能")
print("=" * 60)

skill_output_dir = Path(__file__).parent / ".demo_skills"
factory = SkillFactory(output_dir=skill_output_dir)

skills = factory.generate([conversation_limit_capability], overwrite=True)

if skills:
    skill = skills[0]
    print(f"✅ 技能已生成！")
    print(f"   - SKILL.md: {skill.skill_md_path}")
    print(f"   - Handler: {skill.handler_path}")

    # 显示生成的 SKILL.md 内容
    print(f"\n📄 SKILL.md 内容预览:")
    print("-" * 60)
    skill_md_content = Path(skill.skill_md_path).read_text()
    print(skill_md_content[:500] + "...")
else:
    print("❌ 技能生成失败")
    sys.exit(1)

# 步骤 3: 验证安全性
print("\n" + "=" * 60)
print("步骤 3: 验证安全性")
print("=" * 60)

validations = batch_validate([conversation_limit_capability])

for i, validation in enumerate(validations):
    if validation.is_valid:
        print(f"✅ 验证通过: {validation.capability.name}")
        print(f"   - 语法检查: 通过")
        print(f"   - 安全扫描: 通过")
    else:
        print(f"❌ 验证失败: {validation.capability.name}")
        print(f"   - 错误: {validation.test_output}")

# 步骤 4: 自动注册
print("\n" + "=" * 60)
print("步骤 4: 自动注册到工具系统")
print("=" * 60)

auto_register = AutoRegister(tool_registry=registry)
registrations = auto_register.register_validated(validations, toolset="session_control")

for reg in registrations:
    if reg.success:
        print(f"✅ 注册成功: {reg.tool_name}")
        print(f"   - Toolset: {reg.toolset}")
    else:
        print(f"❌ 注册失败: {reg.tool_name}")
        print(f"   - 错误: {reg.error}")

# 步骤 5: 测试技能
print("\n" + "=" * 60)
print("步骤 5: 测试技能")
print("=" * 60)

from maxbot.core.agent_loop import Agent, AgentConfig

# 创建 Agent
config = AgentConfig()
agent = Agent(config=config)

# 测试查询
print("\n🧪 测试 1: 查询当前设置")
result = registry.call("set_conversation_limit", {"agent": agent})
print(f"结果: {result}")

# 测试设置
print("\n🧪 测试 2: 设置新的限制")
result = registry.call("set_conversation_limit", {"max_turns": 50, "agent": agent})
print(f"结果: {result}")

# 测试重置
print("\n🧪 测试 3: 重置计数器")
agent._conversation_turns = 10  # 先设置一些计数
result = registry.call("set_conversation_limit", {"reset": True, "agent": agent})
print(f"结果: {result}")
print(f"验证: 计数器 = {agent._conversation_turns}")

print("\n" + "=" * 60)
print("🎉 技能生成和注册完成！")
print("=" * 60)
print(f"\n技能文件位置:")
print(f"  - {skill.skill_md_path}")
print(f"  - {skill.handler_path}")
print(f"\n工具已注册到 registry，可以通过 registry.call() 调用")
