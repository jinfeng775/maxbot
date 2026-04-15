"""
持久记忆系统 — SQLite + FTS5 全文搜索

参考来源：
- Hermes: hermes_state.py — SQLite FTS5 会话搜索
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    key: str
    value: str
    category: str = "memory"       # memory | user | skill | env
    created_at: float = 0.0
    updated_at: float = 0.0


class Memory:
    """
    持久记忆存储

    用法：
        mem = Memory(path="~/.maxbot/memory.db")
        mem.set("user_name", "张三", category="user")
        mem.get("user_name")  # -> "张三"
        mem.search("张三")    # -> [MemoryEntry(...)]
    """

    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path.home() / ".maxbot" / "memory.db"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'memory',
                created_at REAL,
                updated_at REAL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                key, value, category,
                content='memory',
                content_rowid='rowid',
                tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
                INSERT INTO memory_fts(rowid, key, value, category)
                VALUES (new.rowid, new.key, new.value, new.category);
            END;

            CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, key, value, category)
                VALUES ('delete', old.rowid, old.key, old.value, old.category);
            END;

            CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN
                INSERT INTO memory_fts(memory_fts, rowid, key, value, category)
                VALUES ('delete', old.rowid, old.key, old.value, old.category);
                INSERT INTO memory_fts(rowid, key, value, category)
                VALUES (new.rowid, new.key, new.value, new.category);
            END;
        """)
        self._conn.commit()

    def set(self, key: str, value: str, category: str = "memory") -> None:
        now = time.time()
        self._conn.execute("""
            INSERT INTO memory (key, value, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                updated_at = excluded.updated_at
        """, (key, value, category, now, now))
        self._conn.commit()

    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM memory WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def delete(self, key: str) -> bool:
        cursor = self._conn.execute("DELETE FROM memory WHERE key = ?", (key,))
        self._conn.commit()
        return cursor.rowcount > 0

    def list_all(self, category: str | None = None) -> list[MemoryEntry]:
        if category:
            rows = self._conn.execute(
                "SELECT * FROM memory WHERE category = ? ORDER BY updated_at DESC",
                (category,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memory ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """全文搜索（FTS5 + LIKE 回退）"""
        # 先尝试 FTS5
        try:
            rows = self._conn.execute("""
                SELECT m.* FROM memory m
                JOIN memory_fts f ON m.rowid = f.rowid
                WHERE memory_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
            if rows:
                return [self._row_to_entry(r) for r in rows]
        except Exception:
            pass
        # LIKE 回退（支持中文）
        like_q = f"%{query}%"
        rows = self._conn.execute("""
            SELECT * FROM memory
            WHERE key LIKE ? OR value LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (like_q, like_q, limit)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def export_text(self, category: str | None = None) -> str:
        """导出为文本格式（注入 system prompt 用）"""
        entries = self.list_all(category)
        if not entries:
            return ""
        lines = ["# 持久记忆"]
        for e in entries:
            lines.append(f"- [{e.category}] {e.key}: {e.value}")
        return "\n".join(lines)

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            key=row["key"],
            value=row["value"],
            category=row["category"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self):
        self._conn.close()
