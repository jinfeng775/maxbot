from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RuntimeMetrics:
    task_id: str
    session_id: str | None
    user_message: str
    tool_calls: int = 0
    reflection_count: int = 0
    revision_count: int = 0
    memory_hits: int = 0
    memory_misses: int = 0
    instinct_matches: int = 0
    success: bool = False
    worker_count: int = 0
    elapsed: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeMetricsCollector:
    def __init__(self):
        self._records: list[RuntimeMetrics] = []

    def add(self, metrics: RuntimeMetrics) -> None:
        self._records.append(metrics)

    def summary(self) -> dict[str, Any]:
        return {
            "tasks_total": len(self._records),
            "tool_calls": sum(record.tool_calls for record in self._records),
            "reflection_count": sum(record.reflection_count for record in self._records),
            "revision_count": sum(record.revision_count for record in self._records),
            "memory_hits": sum(record.memory_hits for record in self._records),
            "memory_misses": sum(record.memory_misses for record in self._records),
            "instinct_matches": sum(record.instinct_matches for record in self._records),
            "success_count": sum(1 for record in self._records if record.success),
            "worker_count": sum(record.worker_count for record in self._records),
            "elapsed_total": sum(record.elapsed for record in self._records),
        }

    def latest(self) -> RuntimeMetrics | None:
        if not self._records:
            return None
        return self._records[-1]
