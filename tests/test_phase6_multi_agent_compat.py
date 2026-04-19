"""Phase 6 compatibility tests for multi_agent package exports."""

from __future__ import annotations

import maxbot.multi_agent as multi_agent_pkg
from maxbot.multi_agent.coordinator import Coordinator as RuntimeCoordinator
from maxbot.multi_agent.worker import WorkerConfig as RuntimeWorkerConfig


def test_package_exports_runtime_worker_config():
    assert hasattr(multi_agent_pkg, "RuntimeWorkerConfig")
    assert multi_agent_pkg.RuntimeWorkerConfig is RuntimeWorkerConfig


def test_package_exports_runtime_coordinator_alias():
    assert hasattr(multi_agent_pkg, "RuntimeCoordinator")
    assert multi_agent_pkg.RuntimeCoordinator is RuntimeCoordinator
