"""Phase 3: LearningLoop 错误学习回归测试"""

import tempfile
from pathlib import Path

from maxbot.learning import LearningConfig, LearningLoop


def test_on_error_sync_learns_error_solution_instinct():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LearningConfig(
            store_path=str(Path(tmpdir) / "observations"),
            instincts_db_path=str(Path(tmpdir) / "instincts.db"),
            learning_loop_async=False,
            enable_logging=False,
            auto_approve=True,
            enable_error_tracking=True,
        )
        learning_loop = LearningLoop(config=config)

        learning_loop.on_error(
            error="pytest failed: exit code 1",
            context={
                "user_message": "请修复测试失败",
                "tool_name": "terminal",
                "tool_args": {"command": "pytest -q"},
                "tool_result": {"error": "exit code 1"},
                "resolution": "检查失败测试并重新运行",
            },
        )

        instincts = learning_loop.store.get_all_instincts()
        assert len(instincts) == 1

        instinct = instincts[0]
        assert instinct.pattern_type == "error_solution"
        assert instinct.pattern_data["error"] == "pytest failed: exit code 1"
        assert instinct.pattern_data["resolution"] == "检查失败测试并重新运行"
        assert instinct.pattern_data["tool_name"] == "terminal"

        stats = learning_loop.get_learning_stats()["learning_stats"]
        assert stats["total_instincts_learned"] == 1
        assert stats["learning_loop_count"] == 1
        assert stats["last_learning_time"] is not None
