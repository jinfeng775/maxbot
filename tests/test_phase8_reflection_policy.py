from maxbot.reflection.policy import ReflectionPolicy


def test_policy_triggers_for_high_risk_level_even_without_many_tools():
    policy = ReflectionPolicy(
        enabled=True,
        max_revisions=2,
        min_output_chars=10,
        high_risk_tool_threshold=3,
        apply_to_task_types=["default"],
    )

    decision = policy.should_reflect(
        task_type="default",
        output_text="这是一个足够长的输出，用于触发高风险反思。",
        tool_calls=0,
        metadata={"risk_level": "high"},
    )

    assert decision.enabled is True
    assert decision.reason == "high_risk_level"



def test_policy_treats_wildcard_task_type_as_enabled():
    policy = ReflectionPolicy(
        enabled=True,
        max_revisions=1,
        min_output_chars=10,
        high_risk_tool_threshold=2,
        apply_to_task_types=["*"],
    )

    decision = policy.should_reflect(
        task_type="analysis",
        output_text="这是一个足够长的分析输出。",
        tool_calls=3,
        metadata={},
    )

    assert decision.enabled is True
    assert decision.reason == "high_risk_tool_usage"
