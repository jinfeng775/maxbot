"""
测试观察模块和配置系统
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, "/root/maxbot")

from maxbot.learning.observer import Observer, Observation, ToolCall, ToolResult
from maxbot.learning.config import LearningConfig, get_config


def test_config():
    """测试配置系统"""
    print("=== 测试配置系统 ===\n")

    # 测试默认配置
    print("1. 测试默认配置")
    config = LearningConfig()
    print(f"   validation_threshold: {config.validation_threshold}")
    print(f"   auto_approve: {config.auto_approve}")
    print(f"   min_safety: {config.min_safety}")
    print(f"   enable_auto_apply: {config.enable_auto_apply}")
    assert config.validation_threshold == 0.7
    assert config.auto_approve == False
    assert config.min_safety == 0.8
    assert config.enable_auto_apply == True
    print("   ✅ 默认配置测试通过\n")

    # 测试保守配置
    print("2. 测试保守配置")
    conservative_config = get_config("conservative")
    print(f"   validation_threshold: {conservative_config.validation_threshold}")
    print(f"   enable_auto_apply: {conservative_config.enable_auto_apply}")
    assert conservative_config.validation_threshold == 0.8
    assert conservative_config.enable_auto_apply == False
    print("   ✅ 保守配置测试通过\n")

    # 测试激进配置
    print("3. 测试激进配置")
    aggressive_config = get_config("aggressive")
    print(f"   validation_threshold: {aggressive_config.validation_threshold}")
    print(f"   auto_approve: {aggressive_config.auto_approve}")
    assert aggressive_config.validation_threshold == 0.5
    assert aggressive_config.auto_approve == True
    print("   ✅ 激进配置测试通过\n")

    # 测试配置验证
    print("4. 测试配置验证")
    valid_config = LearningConfig()
    errors = valid_config.validate()
    print(f"   默认配置错误数: {len(errors)}")
    assert len(errors) == 0
    print("   ✅ 配置验证测试通过\n")

    # 测试无效配置
    print("5. 测试无效配置")
    invalid_config = LearningConfig(validation_threshold=1.5)
    errors = invalid_config.validate()
    print(f"   无效配置错误数: {len(errors)}")
    print(f"   错误消息: {errors}")
    assert len(errors) > 0
    print("   ✅ 无效配置测试通过\n")

    # 测试配置序列化
    print("6. 测试配置序列化")
    config_dict = valid_config.to_dict()
    restored_config = LearningConfig.from_dict(config_dict)
    assert restored_config.validation_threshold == valid_config.validation_threshold
    print("   ✅ 配置序列化测试通过\n")

    print("=== 配置系统测试完成 ===\n")


def test_observer():
    """测试观察模块"""
    print("=== 测试观察模块 ===\n")

    # 创建观察器（使用临时目录）
    import tempfile
    temp_dir = tempfile.mkdtemp()
    print(f"1. 创建观察器（临时目录: {temp_dir}）")
    observer = Observer(store_path=temp_dir)
    print("   ✅ 观察器创建成功\n")

    # 测试开始观察
    print("2. 测试开始观察")
    session_id = "test_session_001"

    observation = observer.start_observation(
        session_id=session_id,
        user_message="请帮我分析这个项目的代码",
        context={"project": "/root/maxbot", "mode": "code_analysis"}
    )

    print(f"   session_id: {observation.session_id}")
    print(f"   user_message: {observation.user_message}")
    print(f"   timestamp: {observation.timestamp}")
    assert observation.session_id == session_id
    assert len(observer.get_session_observations(session_id)) == 1
    print("   ✅ 开始观察测试通过\n")

    # 测试记录工具调用
    print("3. 测试记录工具调用")
    tool_call = observer.record_tool_call(
        tool_name="search_files",
        arguments={"pattern": "import", "target": "content"},
        call_id="call_001"
    )

    print(f"   tool_name: {tool_call.tool_name}")
    print(f"   call_id: {tool_call.call_id}")
    assert tool_call.tool_name == "search_files"
    assert len(observation.tool_calls) == 1
    print("   ✅ 记录工具调用测试通过\n")

    # 测试记录工具结果
    print("4. 测试记录工具结果")
    tool_result = observer.record_tool_result(
        tool_name="search_files",
        success=True,
        result_data={"matches": 10, "files": 5},
        call_id="call_001"
    )

    print(f"   tool_name: {tool_result.tool_name}")
    print(f"   success: {tool_result.success}")
    print(f"   duration: {tool_result.duration:.3f}s")
    assert tool_result.success == True
    assert len(observation.tool_results) == 1
    print("   ✅ 记录工具结果测试通过\n")

    # 测试结束观察
    print("5. 测试结束观察")
    ended_observation = observer.end_observation(success=True)

    print(f"   success: {ended_observation.success}")
    print(f"   tool_calls: {len(ended_observation.tool_calls)}")
    print(f"   tool_results: {len(ended_observation.tool_results)}")
    assert ended_observation.success == True
    print("   ✅ 结束观察测试通过\n")

    # 测试获取会话观察
    print("6. 测试获取会话观察")
    session_obs = observer.get_session_observations(session_id)
    print(f"   会话观察数量: {len(session_obs)}")
    assert len(session_obs) == 1
    print("   ✅ 获取会话观察测试通过\n")

    # 测试加载观察
    print("7. 测试加载观察")
    loaded_obs = observer.load_observations(session_id=session_id)
    print(f"   加载的观察数量: {len(loaded_obs)}")
    assert len(loaded_obs) == 1
    assert loaded_obs[0].session_id == session_id
    print("   ✅ 加载观察测试通过\n")

    # 测试敏感信息过滤
    print("8. 测试敏感信息过滤")
    observer2 = Observer(store_path=temp_dir)
    observation2 = observer2.start_observation(
        session_id="test_session_002",
        user_message="Please set the API key to secret_key_12345",
        context={}
    )

    # 敏感信息应该被过滤
    assert "secret_key_12345" not in observation2.user_message
    print(f"   清理后的消息: {observation2.user_message}")
    print("   ✅ 敏感信息过滤测试通过\n")

    # 清理临时目录
    import shutil
    shutil.rmtree(temp_dir)

    print("=== 观察模块测试完成 ===\n")


def test_end_to_end():
    """端到端测试"""
    print("=== 端到端测试 ===\n")

    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()

    try:
        # 创建观察器
        observer = Observer(store_path=temp_dir)

        # 模拟一个完整的会话
        session_id = "e2e_session_001"

        # 用户请求 1
        obs1 = observer.start_observation(
            session_id=session_id,
            user_message="分析项目的测试覆盖率"
        )

        # 工具调用
        observer.record_tool_call("search_files", {"pattern": "test"}, "call_001")
        observer.record_tool_result("search_files", True, {"matches": 5}, call_id="call_001")

        observer.record_tool_call("terminal", {"command": "pytest"}, "call_002")
        observer.record_tool_result("terminal", True, {"exit_code": 0}, call_id="call_002")

        observer.end_observation(success=True)

        # 用户请求 2
        obs2 = observer.start_observation(
            session_id=session_id,
            user_message="生成测试报告"
        )

        observer.record_tool_call("terminal", {"command": "pytest --cov"}, "call_003")
        observer.record_tool_result("terminal", True, {"coverage": "85%"}, call_id="call_003")

        observer.end_observation(success=True)

        # 用户请求 3（失败）
        obs3 = observer.start_observation(
            session_id=session_id,
            user_message="删除所有测试文件"
        )

        observer.record_tool_call("terminal", {"command": "rm -rf tests"}, "call_004")
        observer.record_tool_result("terminal", False, {"error": "Permission denied"}, call_id="call_004")

        observer.end_observation(success=False)

        # 验证结果
        print("1. 验证会话观察")
        all_obs = observer.get_session_observations(session_id)
        print(f"   总观察数: {len(all_obs)}")
        assert len(all_obs) == 2  # 3 个观察，但失败的不包含

        print("2. 验证包含失败的观察")
        all_obs_with_failed = observer.get_session_observations(session_id, include_failed=True)
        print(f"   包含失败的观察数: {len(all_obs_with_failed)}")
        assert len(all_obs_with_failed) == 3

        print("3. 验证工具调用统计")
        total_calls = sum(len(obs.tool_calls) for obs in all_obs_with_failed)
        total_results = sum(len(obs.tool_results) for obs in all_obs_with_failed)
        print(f"   总工具调用: {total_calls}")
        print(f"   总工具结果: {total_results}")
        assert total_calls == 4
        assert total_results == 4

        print("   ✅ 端到端测试通过\n")

    finally:
        shutil.rmtree(temp_dir)

    print("=== 端到端测试完成 ===\n")


def main():
    """运行所有测试"""
    print("\n")
    print("╔════════════════════════════════════════╗")
    print("║  MaxBot 持续学习系统 - 测试套件        ║")
    print("╚════════════════════════════════════════╝")
    print("\n")

    tests = [
        ("配置系统", test_config),
        ("观察模块", test_observer),
        ("端到端", test_end_to_end),
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
