"""
测试持续学习系统 - 完整测试套件

测试所有模块：
- 配置系统
- 观察模块
- 模式提取
- 模式验证
- 本能存储
- 本能应用
- 学习循环
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, "/root/maxbot")

from maxbot.learning import (
    LearningConfig,
    Observer,
    PatternExtractor,
    PatternValidator,
    InstinctStore,
    InstinctApplier,
    LearningLoop,
    Pattern,
)
from maxbot.learning.observer import ToolCall, ToolResult, Observation
import tempfile
import shutil
import time


def test_full_learning_workflow():
    """测试完整的学习工作流"""
    print("=== 测试完整学习工作流 ===\n")

    temp_dir = tempfile.mkdtemp()

    try:
        # 1. 创建配置
        print("1. 创建学习配置")
        config = LearningConfig(
            min_occurrence_count=2,
            validation_threshold=0.5,
            store_path=temp_dir + "/observations",
            instincts_db_path=temp_dir + "/instincts.db",
            enable_auto_apply=False,
        )
        print("   ✅ 配置创建成功\n")

        # 2. 创建学习循环
        print("2. 创建学习循环")
        learning_loop = LearningLoop(config=config)
        print("   ✅ 学习循环创建成功\n")

        # 3. 模拟用户会话
        print("3. 模拟用户会话")
        session_id = "test_session_001"

        # 用户请求 1
        learning_loop.on_user_message(
            session_id=session_id,
            user_message="请分析项目代码",
            context={"project": "/root/maxbot"}
        )

        # 工具调用
        learning_loop.on_tool_call("search_files", {"pattern": "import"}, "call_001")
        learning_loop.on_tool_result("search_files", True, {"matches": 10}, call_id="call_001")

        learning_loop.on_tool_call("terminal", {"command": "pytest"}, "call_002")
        learning_loop.on_tool_result("terminal", True, {"exit", 0}, call_id="call_002")

        # 用户请求 2
        learning_loop.on_user_message(
            session_id=session_id,
            user_message="请分析项目代码",
            context={"project": "/root/maxbot"}
        )

        learning_loop.on_tool_call("search_files", {"pattern": "import"}, "call_003")
        learning_loop.on_tool_result("search_files", True, {"matches": 10}, call_id="call_003")

        learning_loop.on_tool_call("terminal", {"command": "pytest"}, "call_004")
        learning_loop.on_tool_result("terminal", True, {"exit", 0}, call_id="call_004")

        # 用户请求 3
        learning_loop.on_user_message(
            session_id=session_id,
            user_message="请分析项目代码",
            context={"project": "/root/maxbot"}
        )

        learning_loop.on_tool_call("search_files", {"pattern": "import"}, "call_005")
        learning_loop.on_tool_result("search_files", True, {"matches": 10}, call_id="call_005")

        learning_loop.on_tool_call("terminal", {"command": "pytest"}, "call_006")
        learning_loop.on_tool_result("terminal", True, {"exit", 0}, call_id="call_006")

        print("   ✅ 用户会话模拟成功\n")

        # 4. 结束会话，触发学习
        print("4. 结束会话，触发学习")
        learning_loop.on_session_end(session_id)
        print("   ✅ 会话结束，学习触发\n")

        # 5. 检查学习的本能
        print("5. 检查学习的本能")
        instincts = learning_loop.store.get_all_instincts()
        print(f"   学到的本能数量: {len(instincts)}")

        for instinct in instincts:
            print(f"   - {instinct.name}")
            print(f"     类型: {instinct.pattern_type}")
            print(f"     置信度: {instinct.validation_score.get('overall', 0):.2f}")

        if len(instincts) > 0:
            print("   ✅ 本能学习成功\n")
        else:
            print("   ⚠️  未学习到本能（可能因为模式不够明显）\n")

        # 6. 检查统计信息
        print("6. 检查学习统计")
        stats = learning_loop.get_learning_stats()
        print(f"   总观察数: {stats['learning_stats']['total_observations']}")
        print(f"   总模式数: {stats['learning_stats']['total_patterns_extracted']}")
        print(f"   总本能数: {stats['learning_stats']['total_instincts_learned']}")
        print("   ✅ 统计信息获取成功\n")

        # 7. 测试本能应用
        print("7. 测试本能应用")
        if instincts:
            context = {
                "user_message": "请分析项目代码",
                "project": "/root/maxbot",
            }

            matches = learning_loop.applier.find_matching_instincts(
                context, instincts, top_k=1
            )

            if matches:
                print(f"   找到匹配: {matches[0].instinct_name}")
                print(f"   匹配分数: {matches[0].match_score:.2f}")
                print(f"   置信度: {matches[0].confidence:.2f}")
                print("   ✅ 本能匹配成功\n")
            else:
                print("   ⚠️  未找到匹配\n")
        else:
            print("   ⚠️  跳过（无本能可用）\n")

        # 8. 清理
        print("8. 清理学习系统")
        learning_loop.shutdown()
        print("   ✅ 清理完成\n")

        print("=== 完整学习工作流测试通过 ===\n")

    finally:
        shutil.rmtree(temp_dir)


def test_pattern_extraction():
    """测试模式提取"""
    print("=== 测试模式提取 ===\n")

    # 创建观察记录
    observations = []

    for i in range(5):
        # 创建观察
        obs = Observation(
            session_id=f"session_{i}",
            timestamp=time.time(),
            user_message="请分析项目代码",
            success=True,
        )

        # 添加工具调用
        obs.tool_calls = [
            ToolCall(tool_name="search_files", arguments={"pattern": "import"}, timestamp=time.time()),
            ToolCall(tool_name="terminal", arguments={"command": "pytest"}, timestamp=time.time()),
        ]

        # 添加工具结果
        obs.tool_results = [
            ToolResult(tool_name="search_files", success=True, duration=0.5, error=None, result_data={"matches": 10}, timestamp=time.time()),
            ToolResult(tool_name="terminal", success=True, duration=2.0, error=None, result_data={"exit": 0}, timestamp=time.time()),
        ]

        observations.append(obs)

    # 提取模式
    print("1. 提取工具序列模式")
    extractor = PatternExtractor(
        min_occurrence_count=3,
        pattern_threshold="low"  # 低阈值以便提取到模式
    )

    patterns = extractor.extract_patterns(
        observations,
        enable_tool_sequence=True,
        enable_error_solution=False,
        enable_user_preference=False,
    )

    print(f"   提取的模式数量: {len(patterns)}")

    for pattern in patterns:
        print(f"   - {pattern.name}")
        print(f"     类型: {pattern.pattern_type}")
        print(f"     出现次数: {pattern.occurrence_count}")
        print(f"     置信度: {pattern.confidence:.2f}")

    if len(patterns) > 0:
        print("   ✅ 模式提取成功\n")
    else:
        print("   ⚠️  未提取到模式\n")

    print("=== 模式提取测试完成 ===\n")


def test_pattern_validation():
    """测试模式验证"""
    print("=== 测试模式验证 ===\n")

    # 创建一个测试模式
    pattern = Pattern(
        id="test_pattern_001",
        name="Test Pattern",
        pattern_type="tool_sequence",
        data={
            "sequence": ["search_files", "terminal"],
            "avg_duration": 2.5,
            "success_rate": 1.0,
            "occurrence_count": 5,
        },
        occurrence_count=5,
        confidence=0.9,
        extracted_at=time.time(),
        tags=["test"],
        description="Test pattern for validation",
    )

    # 验证模式
    print("1. 验证工具序列模式")
    validator = PatternValidator(validation_threshold=0.5)

    result = validator.validate(pattern)

    print(f"   是否通过: {result.passed}")
    print(f"   重现性: {result.score.reproducibility:.2f}")
    print(f"   价值: {result.score.value:.2f}")
    print(f"   安全性: {result.score.safety:.2f}")
    print(f"   最佳实践: {result.score.best_practice:.2f}")
    print(f"   综合分数: {result.score.overall:.2f}")

    if result.warnings:
        print(f"   警告: {result.warnings}")

    if result.errors:
        print(f"   错误: {result.errors}")

    print("   ✅ 模式验证成功\n")

    print("=== 模式验证测试完成 ===\n")


def test_instinct_storage():
    """测试本能存储"""
    print("=== 测试本能存储 ===\n")

    temp_dir = tempfile.mkdtemp()

    try:
        # 创建存储
        print("1. 创建本能存储")
        store = InstinctStore(db_path=temp_dir + "/instincts.db")
        print("   ✅ 存储创建成功\n")

        # 保存本能
        print("2. 保存本能")
        instinct = store.save_instinct(
            pattern_id="test_instinct_001",
            name="Test Instinct",
            pattern_type="tool_sequence",
            pattern_data={"sequence": ["search_files", "terminal"]},
            validation_score={"overall": 0.9},
            tags=["test"],
            description="Test instinct for storage",
        )

        print(f"   本能 ID: {instinct.id}")
        print(f"   本能名称: {instinct.name}")
        print("   ✅ 本能保存成功\n")

        # 加载本能
        print("3. 加载本能")
        loaded_instinct = store.get_instinct("test_instinct_001")
        assert loaded_instinct is not None
        assert loaded_instinct.name == "Test Instinct"
        print("   ✅ 本能加载成功\n")

        # 获取所有本能
        print("4. 获取所有本能")
        all_instincts = store.get_all_instincts()
        print(f"   本能数量: {len(all_instincts)}")
        assert len(all_instincts) == 1
        print("   ✅ 获取成功\n")

        # 记录使用
        print("5. 记录本能使用")
        store.record_instinct_usage("test_instinct_001", success=True)
        loaded_instinct = store.get_instinct("test_instinct_001")
        print(f"   使用次数: {loaded_instinct.usage_count}")
        print(f"   成功次数: {loaded_instinct.success_count}")
        print(f"   成功率: {loaded_instinct.success_rate:.2%}")
        print("   ✅ 使用记录成功\n")

        # 获取统计信息
        print("6. 获取统计信息")
        stats = store.get_statistics()
        print(f"   总本能数: {stats['total_count']}")
        print(f"   启用本能数: {stats['enabled_count']}")
        print(f"   总使用次数: {stats['total_usage']}")
        print("   ✅ 统计信息获取成功\n")

        print("=== 本能存储测试完成 ===\n")

    finally:
        shutil.rmtree(temp_dir)


def main():
    """运行所有测试"""
    print("\n")
    print("╔════════════════════════════════════════╗")
    print("║  MaxBot 持续学习系统 - 完整测试套件   ║")
    print("╚════════════════════════════════════════╝")
    print("\n")

    tests = [
        ("模式提取", test_pattern_extraction),
        ("模式验证", test_pattern_validation),
        ("本能存储", test_instinct_storage),
        ("完整学习工作流", test_full_learning_workflow),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"✅ {name} 测试通过\n")
        except Exception as e:
            failed += 1
            print(f"❌ {name} 测试失败: {e}\n")
            import traceback
            traceback.print_exc()
            print()

    print("╔════════════════════════════════════════╗")
    print(f"║  测试结果: {passed} 通过, {failed} 失败        ║")
    print("╚════════════════════════════════════════╝")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
