from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class TraceStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write_trace(self, payload: dict[str, Any]) -> str:
        trace_id = payload.get("trace_id") or str(uuid.uuid4())
        record = dict(payload)
        record.setdefault("trace_id", trace_id)
        record.setdefault("created_at", time.time())
        path = self.base_dir / f"{trace_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return trace_id

    def read_trace(self, trace_id: str) -> dict[str, Any]:
        path = self.base_dir / f"{trace_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        files = sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [json.loads(path.read_text(encoding="utf-8")) for path in files[:limit]]
