from __future__ import annotations

from typing import Any


class ReflectionCritic:
    """Minimal reflection critic for Phase 8 runtime wiring.

    The first implementation is intentionally simple: by default it approves the
    draft, while tests may inject a mock critic or monkeypatch `critique`.
    """

    def critique(self, draft: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "revise": False,
            "feedback": "approved",
            "draft": draft,
            "context": context or {},
        }
