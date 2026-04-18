"""
存储模块 - 持久化学到的本能

功能：
- 保存本能到数据库
- 加载本能
- 更新本能使用统计
- 清理过期本能
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import sqlite3
import json
from pathlib import Path


@dataclass
class Instinct:
    """学到的本能记录"""
    id: str
    name: str
    pattern_type: str  # tool_sequence, error_solution, user_preference
    pattern_data: Dict[str, Any]
    validation_score: Dict[str, Any]
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    invalidated_at: Optional[datetime] = None
    quality_state: str = "active"
    tags: List[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pattern_type": self.pattern_type,
            "pattern_data": self.pattern_data,
            "validation_score": self.validation_score,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "invalidated_at": self.invalidated_at.isoformat() if self.invalidated_at else None,
            "quality_state": self.quality_state,
            "tags": self.tags,
            "description": self.description,
            "enabled": self.enabled,
        }


class InstinctStore:
    """本能存储"""

    def __init__(self, db_path: str = "~/.maxbot/instincts.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS instincts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_data TEXT NOT NULL,
                    validation_score TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT,
                    invalidated_at TEXT,
                    quality_state TEXT DEFAULT 'active',
                    tags TEXT,
                    description TEXT,
                    enabled INTEGER DEFAULT 1
                )
                """
            )

            self._ensure_column(cursor, "invalidated_at", "TEXT")
            self._ensure_column(cursor, "quality_state", "TEXT DEFAULT 'active'")

            cursor.execute("UPDATE instincts SET quality_state = 'active' WHERE quality_state IS NULL OR quality_state = ''")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pattern_type ON instincts(pattern_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_enabled ON instincts(enabled)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_used ON instincts(last_used_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_state ON instincts(quality_state)")
            conn.commit()

    def _ensure_column(self, cursor, column_name: str, column_definition: str):
        cursor.execute("PRAGMA table_info(instincts)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE instincts ADD COLUMN {column_name} {column_definition}"
            )

    def save_instinct(
        self,
        pattern_id: str,
        name: str,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        validation_score: Dict[str, Any],
        tags: List[str] = None,
        description: str = "",
    ) -> Instinct:
        now = datetime.now()
        tags = tags or []

        duplicate = self._find_duplicate(pattern_type, pattern_data)
        target_id = duplicate.id if duplicate else pattern_id
        existing = self.get_instinct(target_id)
        quality_state = self._derive_quality_state(validation_score, existing)
        enabled = quality_state != "invalidated"
        invalidated_at = now if quality_state == "invalidated" else None

        if existing:
            merged_pattern_data = self._merge_pattern_data(existing.pattern_data, pattern_data)
            merged_validation = self._merge_validation_score(existing.validation_score, validation_score)
            merged_tags = sorted(set(existing.tags) | set(tags))
            usage_count = existing.usage_count
            success_count = existing.success_count
            failure_count = existing.failure_count
            created_at = existing.created_at
            last_used_at = existing.last_used_at
            if existing.invalidated_at and quality_state == "active":
                invalidated_at = None
            elif existing.invalidated_at and quality_state != "active":
                invalidated_at = existing.invalidated_at

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE instincts
                    SET name = ?, pattern_type = ?, pattern_data = ?, validation_score = ?,
                        updated_at = ?, last_used_at = ?, invalidated_at = ?, quality_state = ?,
                        tags = ?, description = ?, enabled = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        pattern_type,
                        json.dumps(merged_pattern_data, ensure_ascii=False),
                        json.dumps(merged_validation, ensure_ascii=False),
                        now.isoformat(),
                        last_used_at.isoformat() if last_used_at else None,
                        invalidated_at.isoformat() if invalidated_at else None,
                        quality_state,
                        json.dumps(merged_tags, ensure_ascii=False),
                        description or existing.description,
                        1 if enabled else 0,
                        existing.id,
                    ),
                )
                if duplicate and duplicate.id != pattern_id:
                    cursor.execute("DELETE FROM instincts WHERE id = ?", (pattern_id,))
                conn.commit()

            return Instinct(
                id=existing.id,
                name=name,
                pattern_type=pattern_type,
                pattern_data=merged_pattern_data,
                validation_score=merged_validation,
                usage_count=usage_count,
                success_count=success_count,
                failure_count=failure_count,
                created_at=created_at,
                updated_at=now,
                last_used_at=last_used_at,
                invalidated_at=invalidated_at,
                quality_state=quality_state,
                tags=merged_tags,
                description=description or existing.description,
                enabled=enabled,
            )

        instinct = Instinct(
            id=pattern_id,
            name=name,
            pattern_type=pattern_type,
            pattern_data=pattern_data,
            validation_score=validation_score,
            tags=tags,
            description=description,
            created_at=now,
            updated_at=now,
            invalidated_at=invalidated_at,
            quality_state=quality_state,
            enabled=enabled,
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO instincts (
                    id, name, pattern_type, pattern_data, validation_score,
                    usage_count, success_count, failure_count,
                    created_at, updated_at, last_used_at, invalidated_at,
                    quality_state, tags, description, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instinct.id,
                    instinct.name,
                    instinct.pattern_type,
                    json.dumps(instinct.pattern_data, ensure_ascii=False),
                    json.dumps(instinct.validation_score, ensure_ascii=False),
                    instinct.usage_count,
                    instinct.success_count,
                    instinct.failure_count,
                    instinct.created_at.isoformat(),
                    instinct.updated_at.isoformat(),
                    None,
                    instinct.invalidated_at.isoformat() if instinct.invalidated_at else None,
                    instinct.quality_state,
                    json.dumps(instinct.tags, ensure_ascii=False),
                    instinct.description,
                    1 if instinct.enabled else 0,
                ),
            )
            conn.commit()

        return instinct

    def get_instinct(self, instinct_id: str) -> Optional[Instinct]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, pattern_type, pattern_data, validation_score,
                       usage_count, success_count, failure_count,
                       created_at, updated_at, last_used_at, invalidated_at,
                       quality_state, tags, description, enabled
                FROM instincts
                WHERE id = ?
                """,
                (instinct_id,),
            )
            row = cursor.fetchone()
            return self._row_to_instinct(row) if row else None

    def get_all_instincts(
        self,
        pattern_type: Optional[str] = None,
        enabled_only: bool = True,
        limit: Optional[int] = None,
    ) -> List[Instinct]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = (
                "SELECT id, name, pattern_type, pattern_data, validation_score, "
                "usage_count, success_count, failure_count, created_at, updated_at, "
                "last_used_at, invalidated_at, quality_state, tags, description, enabled "
                "FROM instincts WHERE 1=1"
            )
            params: List[Any] = []
            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)
            if enabled_only:
                query += " AND enabled = 1"
            query += " ORDER BY created_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, params)
            return [self._row_to_instinct(row) for row in cursor.fetchall()]

    def record_instinct_usage(self, instinct_id: str, success: bool = True):
        instinct = self.get_instinct(instinct_id)
        if not instinct:
            return

        now = datetime.now()
        success_count = instinct.success_count + (1 if success else 0)
        failure_count = instinct.failure_count + (0 if success else 1)
        usage_count = instinct.usage_count + 1
        total_attempts = success_count + failure_count
        success_rate = success_count / max(total_attempts, 1)
        quality_state = instinct.quality_state
        enabled = instinct.enabled
        invalidated_at = instinct.invalidated_at

        if total_attempts >= 3 and success_rate < 0.34:
            quality_state = "invalidated"
            enabled = False
            invalidated_at = now
        elif total_attempts >= 3 and success_rate < 0.6:
            quality_state = "degraded"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE instincts
                SET usage_count = ?, success_count = ?, failure_count = ?,
                    last_used_at = ?, invalidated_at = ?, quality_state = ?, enabled = ?
                WHERE id = ?
                """,
                (
                    usage_count,
                    success_count,
                    failure_count,
                    now.isoformat(),
                    invalidated_at.isoformat() if invalidated_at else None,
                    quality_state,
                    1 if enabled else 0,
                    instinct_id,
                ),
            )
            conn.commit()

    def disable_instinct(self, instinct_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE instincts SET enabled = 0, quality_state = 'invalidated', invalidated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), instinct_id),
            )
            conn.commit()

    def enable_instinct(self, instinct_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE instincts SET enabled = 1, quality_state = 'active', invalidated_at = NULL WHERE id = ?",
                (instinct_id,),
            )
            conn.commit()

    def delete_instinct(self, instinct_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM instincts WHERE id = ?", (instinct_id,))
            conn.commit()

    def cleanup_old_instincts(self, days: int = 90, max_count: int = 1000):
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM instincts
                WHERE (
                    (last_used_at IS NOT NULL AND last_used_at < ?)
                    OR (invalidated_at IS NOT NULL AND invalidated_at < ?)
                    OR (quality_state = 'invalidated' AND created_at < ?)
                )
                """,
                (cutoff_date.isoformat(), cutoff_date.isoformat(), cutoff_date.isoformat()),
            )
            deleted_count += cursor.rowcount

            cursor.execute("SELECT COUNT(*) FROM instincts")
            total_count = cursor.fetchone()[0]
            if total_count > max_count:
                overflow = total_count - max_count
                cursor.execute(
                    """
                    DELETE FROM instincts
                    WHERE id IN (
                        SELECT id FROM instincts
                        ORDER BY COALESCE(last_used_at, created_at) ASC
                        LIMIT ?
                    )
                    """,
                    (overflow,),
                )
                deleted_count += cursor.rowcount

            conn.commit()
        return deleted_count

    def get_statistics(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM instincts")
            total_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM instincts WHERE enabled = 1")
            enabled_count = cursor.fetchone()[0]
            cursor.execute("SELECT pattern_type, COUNT(*) FROM instincts GROUP BY pattern_type")
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT SUM(usage_count), SUM(success_count), SUM(failure_count) FROM instincts"
            )
            usage_stats = cursor.fetchone()
            cursor.execute("SELECT quality_state, COUNT(*) FROM instincts GROUP BY quality_state")
            by_quality = {row[0]: row[1] for row in cursor.fetchall()}
            return {
                "total_count": total_count,
                "enabled_count": enabled_count,
                "by_type": by_type,
                "by_quality": by_quality,
                "total_usage": usage_stats[0] or 0,
                "total_success": usage_stats[1] or 0,
                "total_failure": usage_stats[2] or 0,
            }

    def _find_duplicate(self, pattern_type: str, pattern_data: Dict[str, Any]) -> Optional[Instinct]:
        signature = pattern_data.get("signature")
        if not signature:
            return None
        for instinct in self.get_all_instincts(pattern_type=pattern_type, enabled_only=False):
            if instinct.pattern_data.get("signature") == signature:
                return instinct
        return None

    def _derive_quality_state(self, validation_score: Dict[str, Any], existing: Optional[Instinct]) -> str:
        overall = validation_score.get("overall") or validation_score.get("score") or 0.0
        if overall < 0.5:
            return "invalidated"
        if existing and existing.quality_state == "degraded" and overall < 0.7:
            return "degraded"
        return "active"

    def _merge_pattern_data(self, current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(current)
        merged.update(incoming)

        current_evidence = dict(current.get("evidence", {}))
        incoming_evidence = dict(incoming.get("evidence", {}))
        if current_evidence or incoming_evidence:
            merged_evidence = dict(current_evidence)
            merged_evidence.update(incoming_evidence)
            merged["evidence"] = merged_evidence

        return merged

    def _merge_validation_score(self, current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(current)
        for key, value in incoming.items():
            if isinstance(value, (int, float)) and isinstance(merged.get(key), (int, float)):
                merged[key] = max(float(merged[key]), float(value))
            else:
                merged[key] = value
        return merged

    def _row_to_instinct(self, row: tuple) -> Instinct:
        return Instinct(
            id=row[0],
            name=row[1],
            pattern_type=row[2],
            pattern_data=json.loads(row[3]),
            validation_score=json.loads(row[4]),
            usage_count=row[5],
            success_count=row[6],
            failure_count=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
            last_used_at=datetime.fromisoformat(row[10]) if row[10] else None,
            invalidated_at=datetime.fromisoformat(row[11]) if row[11] else None,
            quality_state=row[12] or "active",
            tags=json.loads(row[13]) if row[13] else [],
            description=row[14],
            enabled=bool(row[15]),
        )
