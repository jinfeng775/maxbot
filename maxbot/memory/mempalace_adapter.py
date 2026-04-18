from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


class MemPalaceAdapter:
    """Minimal CLI adapter for local-first MemPalace retrieval."""

    def __init__(self, palace_path: str | None = None):
        self.palace_path = palace_path

    def is_available(self) -> bool:
        return shutil.which("mempalace") is not None

    def search(self, query: str, wing: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        if not self.is_available():
            return []

        command = ["mempalace", "search", query, "--results", str(limit)]
        if wing:
            command.extend(["--wing", wing])
        if self.palace_path:
            command.extend(["--palace", self.palace_path])

        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return []

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [{"content": line} for line in lines[:limit]]

    def wake_up(self, wing: str | None = None) -> str:
        if not self.is_available():
            return ""

        command = ["mempalace", "wake-up"]
        if wing:
            command.extend(["--wing", wing])
        if self.palace_path:
            command.extend(["--palace", self.palace_path])

        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
