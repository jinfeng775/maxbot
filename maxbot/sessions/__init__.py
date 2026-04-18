"""会话管理"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    session_id: str
    title: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    messages: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SessionStore:
    """SQLite 会话存储"""

    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path.home() / ".maxbot" / "sessions.db"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

        # 持久记忆（与会话存储同目录）
        from maxbot.core.memory import Memory
        self.memory = Memory(path=self.path.parent / "memory.db")

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                messages TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            );
        """)
        self._conn.commit()

    def create(self, session_id: str, title: str = "", metadata: dict | None = None) -> Session:
        now = time.time()
        metadata = metadata or {}
        session = Session(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            metadata=metadata,
        )
        self._conn.execute(
            "INSERT INTO sessions (session_id, title, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, now, now, json.dumps(metadata, ensure_ascii=False)),
        )
        self._conn.commit()
        return session

    def get(self, session_id: str) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return Session(
            session_id=row["session_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            messages=json.loads(row["messages"]),
            metadata=json.loads(row["metadata"]),
        )

    def save_messages(self, session_id: str, messages: list[dict], metadata: dict | None = None):
        now = time.time()
        if metadata is None:
            self._conn.execute(
                "UPDATE sessions SET messages = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(messages, ensure_ascii=False), now, session_id),
            )
        else:
            self._conn.execute(
                "UPDATE sessions SET messages = ?, metadata = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(messages, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), now, session_id),
            )
        self._conn.commit()

    def update_metadata(self, session_id: str, metadata: dict):
        now = time.time()
        self._conn.execute(
            "UPDATE sessions SET metadata = ?, updated_at = ? WHERE session_id = ?",
            (json.dumps(metadata, ensure_ascii=False), now, session_id),
        )
        self._conn.commit()

    def list_sessions(self, limit: int = 20) -> list[Session]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            Session(
                session_id=r["session_id"],
                title=r["title"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    def delete(self, session_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()
        return cursor.rowcount > 0
