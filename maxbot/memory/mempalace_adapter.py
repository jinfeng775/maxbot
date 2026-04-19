from __future__ import annotations

import shutil
import subprocess
from typing import Any


class MemPalaceAdapter:
    """Minimal CLI adapter for local-first MemPalace retrieval."""

    def __init__(self, palace_path: str | None = None):
        self.palace_path = palace_path

    def is_available(self) -> bool:
        return shutil.which("mempalace") is not None

    def _run(self, *args: str) -> subprocess.CompletedProcess[str] | None:
        if not self.is_available():
            return None

        command = ["mempalace", *args]
        if self.palace_path:
            command.extend(["--palace", self.palace_path])

        return subprocess.run(command, capture_output=True, text=True, timeout=60)

    def search(self, query: str, wing: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        args = ["search", query, "--results", str(limit)]
        if wing:
            args.extend(["--wing", wing])

        result = self._run(*args)
        if result is None or result.returncode != 0:
            return []

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [{"content": line} for line in lines[:limit]]

    def mine(self, wing: str | None = None, source: str | None = None) -> str:
        args = ["mine"]
        if wing:
            args.extend(["--wing", wing])
        if source:
            args.append(source)

        result = self._run(*args)
        if result is None or result.returncode != 0:
            return ""
        return result.stdout.strip()

    def wake_up(self, wing: str | None = None) -> str:
        args = ["wake-up"]
        if wing:
            args.extend(["--wing", wing])

        result = self._run(*args)
        if result is None or result.returncode != 0:
            return ""
        return result.stdout.strip()
