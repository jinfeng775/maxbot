from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from maxbot.evals.sample_store import EvalSampleStore


class BenchmarkRegistry:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def register_suite(
        self,
        *,
        suite_name: str,
        tasks: list[dict[str, Any]],
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        suite_id = str(uuid.uuid4())
        created_at_ns = time.time_ns()
        record = {
            "suite_id": suite_id,
            "suite_name": suite_name,
            "source": source,
            "tasks": tasks,
            "metadata": metadata or {},
            "created_at": created_at_ns / 1_000_000_000,
            "created_at_ns": created_at_ns,
        }
        path = self.base_dir / f"{suite_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return suite_id

    def register_from_eval_samples(
        self,
        *,
        sample_store: EvalSampleStore,
        suite_name: str,
        limit: int = 10,
        labels: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        samples = sample_store.list_recent(
            limit=limit,
            labels=labels,
            metadata_filter=metadata_filter,
        )
        tasks = [
            {
                "task_id": sample.get("task_id") or sample["sample_id"],
                "prompt": sample.get("prompt", ""),
                "expected_output": sample.get("response", ""),
                "trace_id": sample.get("trace_id"),
                "metadata": dict(sample.get("metadata") or {}),
            }
            for sample in samples
        ]
        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("source_sample_count", len(tasks))
        merged_metadata.setdefault(
            "selection_policy",
            {
                "labels": list(labels or []),
                "metadata_filter": dict(metadata_filter or {}),
                "limit": limit,
            },
        )
        merged_metadata.setdefault("coverage_summary", self._build_coverage_summary(samples))
        return self.register_suite(
            suite_name=suite_name,
            tasks=tasks,
            source="eval_samples",
            metadata=merged_metadata,
        )

    def auto_assemble_suite(
        self,
        *,
        suite_name: str,
        sample_store: EvalSampleStore,
        selection_policies: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ordered_samples: list[dict[str, Any]] = []
        seen_task_ids: set[str] = set()
        for policy in selection_policies:
            samples = sample_store.list_recent(
                limit=int(policy.get("limit", 10)),
                labels=policy.get("labels"),
                metadata_filter=policy.get("metadata_filter"),
            )
            for sample in samples:
                task_id = sample.get("task_id") or sample.get("sample_id")
                if task_id in seen_task_ids:
                    continue
                seen_task_ids.add(task_id)
                ordered_samples.append(sample)

        tasks = [
            {
                "task_id": sample.get("task_id") or sample["sample_id"],
                "prompt": sample.get("prompt", ""),
                "expected_output": sample.get("response", ""),
                "trace_id": sample.get("trace_id"),
                "metadata": dict(sample.get("metadata") or {}),
            }
            for sample in ordered_samples
        ]
        merged_metadata = dict(metadata or {})
        merged_metadata["assembly_policy"] = {
            "policies_count": len(selection_policies),
            "deduplicated_tasks": len(tasks),
            "selection_policies": selection_policies,
        }
        merged_metadata["coverage_summary"] = self._build_coverage_summary(ordered_samples)
        merged_metadata["source_sample_count"] = len(tasks)
        return self.register_suite(
            suite_name=suite_name,
            tasks=tasks,
            source="auto_assembled_eval_samples",
            metadata=merged_metadata,
        )

    def read_suite(self, suite_id: str) -> dict[str, Any]:
        path = self.base_dir / f"{suite_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_suites(
        self,
        limit: int = 10,
        *,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in self.base_dir.glob("*.json")]
        filtered: list[dict[str, Any]] = []
        for record in records:
            metadata = record.get("metadata") or {}
            if metadata_filter and any(metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            filtered.append(record)
        filtered.sort(
            key=lambda record: (record.get("created_at_ns", 0), record.get("suite_id", "")),
            reverse=True,
        )
        return filtered[:limit]

    def latest(self) -> dict[str, Any] | None:
        recent = self.list_suites(limit=1)
        if not recent:
            return None
        return recent[0]

    def build_task_set(
        self,
        limit: int = 10,
        *,
        suite_metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for suite in self.list_suites(limit=limit, metadata_filter=suite_metadata_filter):
            tasks.extend(suite.get("tasks", []))
        return tasks

    def _build_coverage_summary(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        label_counter: Counter[str] = Counter()
        metadata_counters: dict[str, Counter[str]] = defaultdict(Counter)
        for sample in samples:
            for label in sample.get("labels") or []:
                label_counter[label] += 1
            for key, value in (sample.get("metadata") or {}).items():
                if isinstance(value, (str, int, float, bool)):
                    metadata_counters[str(key)][str(value)] += 1
        return {
            "tasks_total": len(samples),
            "labels": dict(label_counter),
            "metadata": {key: dict(counter) for key, counter in metadata_counters.items()},
        }
