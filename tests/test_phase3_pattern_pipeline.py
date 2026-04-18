from datetime import datetime, timedelta

from maxbot.learning import PatternExtractor
from maxbot.learning.observer import Observation, ToolCall, ToolResult


BASE_TIME = datetime(2026, 4, 18, 12, 0, 0)


def _make_observation(
    session_id: str,
    index: int,
    *,
    user_message: str,
    tool_names: list[str],
    success: bool,
    error: str | None = None,
    context: dict | None = None,
) -> Observation:
    timestamp = BASE_TIME + timedelta(minutes=index)
    tool_calls = [
        ToolCall(
            tool_name=name,
            arguments={"step": idx},
            timestamp=timestamp + timedelta(seconds=idx),
            call_id=f"{session_id}-{index}-{idx}",
        )
        for idx, name in enumerate(tool_names, start=1)
    ]
    tool_results = [
        ToolResult(
            tool_name=name,
            success=success if idx == len(tool_names) else True,
            duration=0.5,
            error=error if idx == len(tool_names) else None,
            result_data={"ok": success if idx == len(tool_names) else True},
            timestamp=timestamp + timedelta(seconds=idx, milliseconds=200),
            call_id=f"{session_id}-{index}-{idx}",
        )
        for idx, name in enumerate(tool_names, start=1)
    ]
    return Observation(
        session_id=session_id,
        timestamp=timestamp,
        user_message=user_message,
        tool_calls=tool_calls,
        tool_results=tool_results,
        success=success,
        context=context or {},
    )


def test_pattern_extractor_aggregates_observations_into_three_pattern_types():
    extractor = PatternExtractor(min_occurrence_count=2, pattern_threshold="low")

    observations = [
        _make_observation(
            "session-a",
            1,
            user_message="请用中文详细分析代码",
            tool_names=["search_files", "read_file", "patch"],
            success=True,
            context={"response_language": "zh", "communication_style": "detailed"},
        ),
        _make_observation(
            "session-a",
            2,
            user_message="请用中文详细分析代码",
            tool_names=["search_files", "read_file", "patch"],
            success=True,
            context={"response_language": "zh", "communication_style": "detailed"},
        ),
        _make_observation(
            "session-a",
            3,
            user_message="修复 pytest 失败",
            tool_names=["terminal"],
            success=False,
            error="pytest failed: exit code 1",
            context={"response_language": "zh"},
        ),
        _make_observation(
            "session-a",
            4,
            user_message="修复 pytest 失败",
            tool_names=["search_files", "read_file", "terminal"],
            success=True,
            context={"response_language": "zh", "resolution": "检查失败测试并重新运行"},
        ),
        _make_observation(
            "session-b",
            5,
            user_message="请用中文详细分析代码",
            tool_names=["terminal"],
            success=False,
            error="pytest failed: exit code 1",
            context={"response_language": "zh"},
        ),
        _make_observation(
            "session-b",
            6,
            user_message="请用中文详细分析代码",
            tool_names=["search_files", "read_file", "terminal"],
            success=True,
            context={"response_language": "zh", "resolution": "检查失败测试并重新运行"},
        ),
    ]

    aggregated = extractor.aggregate_observations(observations)
    assert aggregated["total_observations"] == 6
    assert aggregated["successful_observations"] == 4
    assert aggregated["failed_observations"] == 2
    assert len(aggregated["error_events"]) == 2

    patterns = extractor.extract_patterns(observations)
    pattern_types = {pattern.pattern_type for pattern in patterns}
    assert {"tool_sequence", "error_solution", "user_preference"}.issubset(pattern_types)

    for pattern in patterns:
        assert "signature" in pattern.data
        assert "match_context" in pattern.data
        assert "action" in pattern.data
        assert "evidence" in pattern.data

    tool_pattern = next(pattern for pattern in patterns if pattern.pattern_type == "tool_sequence")
    assert tool_pattern.data["match_context"]["tool_sequence"] == ["search_files", "read_file", "patch"]

    error_pattern = next(pattern for pattern in patterns if pattern.pattern_type == "error_solution")
    assert error_pattern.data["match_context"]["error_signature"].startswith("pytest failed")
    assert error_pattern.data["action"]["resolution_summary"] == "检查失败测试并重新运行"

    preference_pattern = next(pattern for pattern in patterns if pattern.pattern_type == "user_preference")
    assert preference_pattern.data["match_context"]["preference_value"] == "zh"


def test_pattern_extractor_respects_thresholds_and_filters_noise():
    extractor = PatternExtractor(min_occurrence_count=3, pattern_threshold="medium")

    observations = [
        _make_observation(
            "noise-session",
            1,
            user_message="偶发一次的请求",
            tool_names=["terminal", "patch"],
            success=True,
            context={"response_language": "zh"},
        ),
        _make_observation(
            "noise-session",
            2,
            user_message="另一个不同请求",
            tool_names=["search_files"],
            success=False,
            error="temporary runtime hiccup",
        ),
    ]

    assert extractor.extract_patterns(observations) == []
