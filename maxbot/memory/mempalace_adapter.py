from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import MemPalace palace functions if available
try:
    from mempalace.palace import (
        build_closet_lines,
        get_closets_collection,
        get_collection,
        purge_file_closets,
        upsert_closet_lines,
        mine_lock,
    )
    _MEMPALACE_AVAILABLE = True
except ImportError:
    _MEMPALACE_AVAILABLE = False


class MemPalaceAdapter:
    """Minimal CLI adapter for local-first MemPalace retrieval."""

    def __init__(self, palace_path: str | None = None):
        self.palace_path = palace_path or os.path.expanduser("~/.mempalace/palace")

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

    def _store_session_via_cli_mine(
        self,
        messages: list[dict[str, Any]],
        session_id: str,
        wing: str = "conversations",
        room: str = "general",
    ) -> bool:
        if not self.is_available():
            return False

        with tempfile.TemporaryDirectory(prefix="mempalace-session-") as tmp:
            export_dir = Path(tmp)
            export_file = export_dir / f"{session_id}.jsonl"
            payload = {
                "session_id": session_id,
                "wing": wing,
                "room": room,
                "messages": messages,
            }
            export_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = self._run("mine", str(export_dir), "--mode", "convos", "--wing", wing)
            return result is not None and result.returncode == 0

    def store_message(
        self,
        role: str,
        content: str,
        session_id: str,
        wing: str = "conversations",
        room: str = "general",
    ) -> bool:
        """Store a single message in MemPalace.

        Args:
            role: Message role (user/assistant/system/tool)
            content: Message content
            session_id: Session identifier
            wing: Wing name (default: conversations)
            room: Room name (default: general)

        Returns:
            True if successful, False otherwise
        """
        if not _MEMPALACE_AVAILABLE:
            return self._store_session_via_cli_mine(
                [{"role": role, "content": content}],
                session_id=session_id,
                wing=wing,
                room=room,
            )

        try:
            # Create drawer ID from session ID
            drawer_id = self._session_drawer_id(session_id)

            # Format message
            timestamp = datetime.now(timezone.utc).isoformat()
            message_text = f"[{role}] {timestamp}\n{content}\n"

            # Get collections
            drawers_col = get_collection(self.palace_path)
            closets_col = get_closets_collection(self.palace_path)

            # Build metadata
            drawer_meta = {
                "wing": wing,
                "room": room,
                "source_session": session_id,
                "role": role,
                "filed_at": timestamp,
            }

            # Store in drawers (full content)
            with mine_lock(session_id):
                drawers_col.upsert(
                    documents=[message_text],
                    ids=[drawer_id],
                    metadatas=[drawer_meta],
                )

                # Build and store closets (compressed/indexed)
                closet_id_base = self._session_closet_id_base(session_id)
                closet_lines = build_closet_lines(
                    session_id, [drawer_id], message_text, wing, room
                )

                if closet_lines:
                    closet_meta = {
                        "wing": wing,
                        "room": room,
                        "source_session": session_id,
                        "filed_at": timestamp,
                    }
                    purge_file_closets(closets_col, session_id)
                    upsert_closet_lines(closets_col, closet_id_base, closet_lines, closet_meta)

            return True
        except Exception as e:
            print(f"MemPalace store_message error: {e}")
            return False

    def store_session(
        self,
        messages: list[dict[str, Any]],
        session_id: str,
        wing: str = "conversations",
        room: str = "general",
    ) -> bool:
        """Store a full session in MemPalace.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            session_id: Session identifier
            wing: Wing name (default: conversations)
            room: Room name (default: general)

        Returns:
            True if successful, False otherwise
        """
        if not _MEMPALACE_AVAILABLE:
            return self._store_session_via_cli_mine(messages, session_id=session_id, wing=wing, room=room)

        try:
            # Create drawer ID from session ID
            drawer_id = self._session_drawer_id(session_id)

            # Format session as text
            timestamp = datetime.now(timezone.utc).isoformat()
            session_text = self._format_session_messages(messages)

            # Get collections
            drawers_col = get_collection(self.palace_path)
            closets_col = get_closets_collection(self.palace_path)

            # Build metadata
            drawer_meta = {
                "wing": wing,
                "room": room,
                "source_session": session_id,
                "message_count": len(messages),
                "filed_at": timestamp,
            }

            # Store in drawers (full content)
            with mine_lock(session_id):
                drawers_col.upsert(
                    documents=[session_text],
                    ids=[drawer_id],
                    metadatas=[drawer_meta],
                )

                # Build and store closets (compressed/indexed)
                closet_id_base = self._session_closet_id_base(session_id)
                closet_lines = build_closet_lines(
                    session_id, [drawer_id], session_text, wing, room
                )

                if closet_lines:
                    closet_meta = {
                        "wing": wing,
                        "room": room,
                        "source_session": session_id,
                        "filed_at": timestamp,
                    }
                    purge_file_closets(closets_col, session_id)
                    upsert_closet_lines(closets_col, closet_id_base, closet_lines, closet_meta)

            return True
        except Exception as e:
            print(f"MemPalace store_session error: {e}")
            return False

    def _session_drawer_id(self, session_id: str) -> str:
        """Generate stable drawer ID from session ID."""
        suffix = hashlib.sha256(f"session|{session_id}".encode()).hexdigest()[:24]
        return f"drawer_session_{suffix}"

    def _session_closet_id_base(self, session_id: str) -> str:
        """Generate stable closet ID base from session ID."""
        suffix = hashlib.sha256(f"session|{session_id}".encode()).hexdigest()[:24]
        return f"closet_session_{suffix}"

    def _format_session_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages as readable text."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            if timestamp:
                lines.append(f"[{role}] {timestamp}")
            else:
                lines.append(f"[{role}]")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)
