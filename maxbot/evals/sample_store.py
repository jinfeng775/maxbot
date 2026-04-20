from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any


class EvalSampleStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def promote_trace(
        self,
        trace: dict[str, Any],
        *,
        labels: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        sample_id = trace.get("sample_id") or str(uuid.uuid4())
        created_at_ns = time.time_ns()
        normalized_labels = list(labels or [])
        merged_metadata = {
            "session_id": trace.get("session_id"),
            "tool_calls": trace.get("tool_calls", 0),
            "reflection_count": trace.get("reflection_count", 0),
            "revision_count": trace.get("revision_count", 0),
            "labels": normalized_labels,
            **(metadata or {}),
        }
        record = {
            "sample_id": sample_id,
            "trace_id": trace.get("trace_id"),
            "task_id": trace.get("task_id"),
            "prompt": trace.get("user_message", ""),
            "response": trace.get("final_output", ""),
            "labels": normalized_labels,
            "metadata": merged_metadata,
            "created_at": created_at_ns / 1_000_000_000,
            "created_at_ns": created_at_ns,
        }
        path = self.base_dir / f"{sample_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return sample_id

    def read_sample(self, sample_id: str) -> dict[str, Any]:
        path = self.base_dir / f"{sample_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_recent(
        self,
        limit: int = 10,
        *,
        labels: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in self.base_dir.glob("*.json")]
        filtered: list[dict[str, Any]] = []
        required_labels = set(labels or [])
        for record in records:
            record_labels = set(record.get("labels") or [])
            if required_labels and not required_labels.issubset(record_labels):
                continue
            metadata = record.get("metadata") or {}
            if metadata_filter and any(metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            filtered.append(record)
        filtered.sort(
            key=lambda record: (record.get("created_at_ns", 0), record.get("sample_id", "")),
            reverse=True,
        )
        return filtered[:limit]

    def latest(self) -> dict[str, Any] | None:
        recent = self.list_recent(limit=1)
        if not recent:
            return None
        return recent[0]

    def build_benchmark_tasks(
        self,
        limit: int = 10,
        *,
        labels: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for sample in self.list_recent(limit=limit, labels=labels, metadata_filter=metadata_filter):
            tasks.append(
                {
                    "task_id": sample.get("task_id") or sample["sample_id"],
                    "prompt": sample.get("prompt", ""),
                    "expected_output": sample.get("response", ""),
                    "trace_id": sample.get("trace_id"),
                    "metadata": dict(sample.get("metadata") or {}),
                }
            )
        return tasks
