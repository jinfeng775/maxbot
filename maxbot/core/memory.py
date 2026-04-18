"""
持久记忆系统 — SQLite + FTS5 全文搜索

参考来源：
- Hermes: hermes_state.py — SQLite FTS5 会话搜索
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MemoryEntry:
    key: str
    value: str
    category: str = "memory"       # memory | user | skill | env
    scope: str = "global"          # session | project | user | global
    source: str = "manual"         # manual | agent | imported | derived
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None
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
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'memory',
                scope TEXT DEFAULT 'global',
                source TEXT DEFAULT 'manual',
                tags TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                session_id TEXT,
                project_id TEXT,
                user_id TEXT,
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

        self._ensure_column("scope", "TEXT DEFAULT 'global'")
        self._ensure_column("source", "TEXT DEFAULT 'manual'")
        self._ensure_column("tags", "TEXT DEFAULT '[]'")
        self._ensure_column("importance", "REAL DEFAULT 0.5")
        self._ensure_column("session_id", "TEXT")
        self._ensure_column("project_id", "TEXT")
        self._ensure_column("user_id", "TEXT")

        self._conn.execute("UPDATE memory SET scope = 'global' WHERE scope IS NULL OR scope = ''")
        self._conn.execute("UPDATE memory SET source = 'manual' WHERE source IS NULL OR source = ''")
        self._conn.execute("UPDATE memory SET tags = '[]' WHERE tags IS NULL OR tags = ''")
        self._conn.execute("UPDATE memory SET importance = 0.5 WHERE importance IS NULL")
        self._conn.commit()

    def _ensure_column(self, column_name: str, column_definition: str):
        rows = self._conn.execute("PRAGMA table_info(memory)").fetchall()
        existing_columns = {row[1] for row in rows}
        if column_name not in existing_columns:
            self._conn.execute(f"ALTER TABLE memory ADD COLUMN {column_name} {column_definition}")

    def set(
        self,
        key: str,
        value: str,
        category: str = "memory",
        scope: str = "global",
        source: str = "manual",
        tags: list[str] | None = None,
        importance: float = 0.5,
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        now = time.time()
        tags = tags or []
        importance = max(0.0, min(1.0, float(importance)))
        self._conn.execute(
            """
            INSERT INTO memory (
                key, value, category, scope, source, tags, importance,
                session_id, project_id, user_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                scope = excluded.scope,
                source = excluded.source,
                tags = excluded.tags,
                importance = excluded.importance,
                session_id = excluded.session_id,
                project_id = excluded.project_id,
                user_id = excluded.user_id,
                updated_at = excluded.updated_at
        """,
            (
                key,
                value,
                category,
                scope,
                source,
                json.dumps(tags, ensure_ascii=False),
                importance,
                session_id,
                project_id,
                user_id,
                now,
                now,
            ),
        )
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

    def _build_filters(
        self,
        category: str | None = None,
        scope: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> tuple[list[str], list[object]]:
        clauses: list[str] = []
        params: list[object] = []

        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)

        return clauses, params

    def list_all(
        self,
        category: str | None = None,
        scope: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> list[MemoryEntry]:
        clauses, params = self._build_filters(
            category=category,
            scope=scope,
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
        )
        query = "SELECT * FROM memory"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search(
        self,
        query: str,
        limit: int = 10,
        category: str | None = None,
        scope: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> list[MemoryEntry]:
        """全文搜索（FTS5 + LIKE 回退）"""
        # 先尝试 FTS5
        try:
            rows = self._conn.execute(
                """
                SELECT m.* FROM memory m
                JOIN memory_fts f ON m.rowid = f.rowid
                WHERE memory_fts MATCH ?
                LIMIT ?
            """,
                (query, max(limit * 5, limit)),
            ).fetchall()
            entries = [self._row_to_entry(r) for r in rows]
            filtered = self._filter_entries(
                entries,
                category=category,
                scope=scope,
                session_id=session_id,
                project_id=project_id,
                user_id=user_id,
            )
            if filtered:
                return filtered[:limit]
        except Exception:
            pass

        # LIKE 回退（支持中文）
        like_q = f"%{query}%"
        clauses, params = self._build_filters(
            category=category,
            scope=scope,
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
        )
        where_clause = "(key LIKE ? OR value LIKE ?)"
        all_params: list[object] = [like_q, like_q]
        if clauses:
            where_clause += " AND " + " AND ".join(clauses)
            all_params.extend(params)
        all_params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT * FROM memory
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ?
        """,
            all_params,
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def _filter_entries(
        self,
        entries: list[MemoryEntry],
        category: str | None = None,
        scope: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> list[MemoryEntry]:
        filtered: list[MemoryEntry] = []
        for entry in entries:
            if category is not None and entry.category != category:
                continue
            if scope is not None and entry.scope != scope:
                continue
            if session_id is not None and entry.session_id != session_id:
                continue
            if project_id is not None and entry.project_id != project_id:
                continue
            if user_id is not None and entry.user_id != user_id:
                continue
            filtered.append(entry)
        return filtered

    def cleanup_entries(
        self,
        min_importance: float | None = None,
        session_ttl_days: int | float | None = None,
    ) -> int:
        """清理低价值或过期记忆，返回删除条数。"""
        clauses: list[str] = []
        params: list[object] = []

        if min_importance is not None:
            clauses.append("COALESCE(importance, 0.5) < ?")
            params.append(float(min_importance))

        if session_ttl_days is not None:
            cutoff = time.time() - float(session_ttl_days) * 86400
            clauses.append("(scope = 'session' AND COALESCE(updated_at, 0) < ?)")
            params.append(cutoff)

        if not clauses:
            return 0

        cursor = self._conn.execute(
            f"DELETE FROM memory WHERE {' OR '.join(clauses)}",
            params,
        )
        self._conn.commit()
        return max(cursor.rowcount, 0)

    def merge_duplicates(self) -> int:
        """按记忆边界合并重复项，返回合并删除的条数。"""
        entries = self.list_all()
        grouped: dict[tuple[object, ...], list[MemoryEntry]] = {}
        for entry in entries:
            group_key = (
                entry.category,
                entry.scope,
                entry.session_id,
                entry.project_id,
                entry.user_id,
                entry.value,
            )
            grouped.setdefault(group_key, []).append(entry)

        merged = 0
        for duplicates in grouped.values():
            if len(duplicates) <= 1:
                continue

            duplicates.sort(
                key=lambda entry: (
                    float(entry.importance),
                    float(entry.updated_at or 0),
                    float(entry.created_at or 0),
                ),
                reverse=True,
            )
            keeper = duplicates[0]
            extras = duplicates[1:]

            merged_tags = sorted({tag for entry in duplicates for tag in entry.tags})
            merged_importance = max(float(entry.importance) for entry in duplicates)
            merged_updated_at = max(float(entry.updated_at or 0) for entry in duplicates)

            self._conn.execute(
                """
                UPDATE memory
                SET tags = ?, importance = ?, updated_at = ?
                WHERE key = ?
                """,
                (
                    json.dumps(merged_tags, ensure_ascii=False),
                    merged_importance,
                    merged_updated_at,
                    keeper.key,
                ),
            )

            extra_keys = [entry.key for entry in extras]
            placeholders = ", ".join("?" for _ in extra_keys)
            self._conn.execute(
                f"DELETE FROM memory WHERE key IN ({placeholders})",
                extra_keys,
            )
            merged += len(extras)

        if merged:
            self._conn.commit()
        return merged

    def export_text(
        self,
        category: str | None = None,
        scope: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        max_chars: int | None = None,
        dedupe_by_value: bool = False,
    ) -> str:
        """导出为文本格式（注入 system prompt 用）"""
        entries = self.list_all(
            category=category,
            scope=scope,
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
        )
        if not entries:
            return ""
        lines = ["# 持久记忆"]
        total_chars = len(lines[0])
        seen_values: set[str] = set()
        for e in entries:
            if dedupe_by_value and e.value in seen_values:
                continue
            scope_bits = [e.scope]
            if e.category:
                scope_bits.append(f"category={e.category}")
            if e.project_id:
                scope_bits.append(f"project={e.project_id}")
            if e.user_id:
                scope_bits.append(f"user={e.user_id}")
            if e.session_id:
                scope_bits.append(f"session={e.session_id}")
            line = f"- [{' / '.join(scope_bits)}] {e.key}: {e.value}"
            if max_chars is not None and lines and total_chars + len(line) + 1 > max_chars:
                break
            lines.append(line)
            total_chars += len(line) + 1
            if dedupe_by_value:
                seen_values.add(e.value)
        return "\n".join(lines)

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        tags_raw = row["tags"] if "tags" in row.keys() else "[]"
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = []

        return MemoryEntry(
            key=row["key"],
            value=row["value"],
            category=row["category"],
            scope=row["scope"] if "scope" in row.keys() and row["scope"] else "global",
            source=row["source"] if "source" in row.keys() and row["source"] else "manual",
            tags=tags,
            importance=float(row["importance"]) if "importance" in row.keys() and row["importance"] is not None else 0.5,
            session_id=row["session_id"] if "session_id" in row.keys() else None,
            project_id=row["project_id"] if "project_id" in row.keys() else None,
            user_id=row["user_id"] if "user_id" in row.keys() else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self):
        self._conn.close()
