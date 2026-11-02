"""
knowledge/knowledge_base.py

Validated Repair Memory — stores successful (and failed) repair attempts
in a local SQLite database so the fixer can learn from past repairs.

This is NOT a trained ML model. It is a rule-based lookup system.
Calling it "knowledge-based learning" accurately describes the mechanism.

Usage:
    from knowledge.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    matches = kb.search(error_type="NameError", error_msg="name 'x' is not defined")
    kb.store(error_type=..., original_code=..., fixed_code=..., ...)

SECURITY NOTE:
    The database stores code snippets. Do not expose it publicly.
    For production deployment, use a secure database with access controls.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "repair_memory.db"
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS repairs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL    NOT NULL,
    error_type      TEXT    NOT NULL,
    error_message   TEXT,
    original_code   TEXT,
    fixed_code      TEXT,
    repair_strategy TEXT,
    validation_ok   INTEGER DEFAULT 0,
    test_ok         INTEGER DEFAULT 0,
    attempts        INTEGER DEFAULT 1,
    explanation     TEXT,
    confidence      REAL    DEFAULT 0.0
);
"""


class KnowledgeBase:
    """
    SQLite-backed validated repair memory.

    Provides two operations:
    - search(): find similar past repairs
    - store():  save a new repair result
    """

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._ensure_db()

    # ============================================================
    # PUBLIC API
    # ============================================================

    def search(
        self,
        error_type: str,
        error_msg: str = "",
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Search for similar past repairs.

        Matches by error_type first, then ranks by:
        - validation success
        - recency

        Returns up to `limit` results.
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        id, timestamp, error_type, error_message,
                        original_code, fixed_code, repair_strategy,
                        validation_ok, test_ok, attempts,
                        explanation, confidence
                    FROM repairs
                    WHERE error_type = ?
                      AND validation_ok = 1
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (error_type, limit),
                )
                rows = cursor.fetchall()
                columns = [
                    desc[0] for desc in cursor.description
                ]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:
            logger.warning("KnowledgeBase.search failed: %s", exc)
            return []

    def store(
        self,
        error_type: str,
        error_message: str = "",
        original_code: str = "",
        fixed_code: str = "",
        repair_strategy: str = "",
        validation_ok: bool = False,
        test_ok: bool = False,
        attempts: int = 1,
        explanation: str = "",
        confidence: float = 0.0,
    ) -> int | None:
        """
        Store a repair result.

        Returns the row id on success, None on failure.
        """
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO repairs (
                        timestamp, error_type, error_message,
                        original_code, fixed_code, repair_strategy,
                        validation_ok, test_ok, attempts,
                        explanation, confidence
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        time.time(),
                        error_type,
                        error_message,
                        original_code,
                        fixed_code,
                        repair_strategy,
                        1 if validation_ok else 0,
                        1 if test_ok else 0,
                        attempts,
                        explanation,
                        confidence,
                    ),
                )
                conn.commit()
                logger.info(
                    "KnowledgeBase: stored repair id=%s type=%s valid=%s",
                    cursor.lastrowid,
                    error_type,
                    validation_ok,
                )
                return cursor.lastrowid
        except Exception as exc:
            logger.warning("KnowledgeBase.store failed: %s", exc)
            return None

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics about the knowledge base."""
        try:
            with self._connect() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM repairs"
                ).fetchone()[0]
                successful = conn.execute(
                    "SELECT COUNT(*) FROM repairs WHERE validation_ok=1"
                ).fetchone()[0]
                by_type = conn.execute(
                    """
                    SELECT error_type, COUNT(*), SUM(validation_ok)
                    FROM repairs
                    GROUP BY error_type
                    ORDER BY COUNT(*) DESC
                    """
                ).fetchall()
                return {
                    "total_repairs": total,
                    "successful_repairs": successful,
                    "success_rate": (
                        round(successful / total * 100, 1)
                        if total > 0 else 0.0
                    ),
                    "by_error_type": [
                        {
                            "error_type": row[0],
                            "count": row[1],
                            "successful": row[2],
                        }
                        for row in by_type
                    ],
                }
        except Exception as exc:
            logger.warning("KnowledgeBase.get_stats failed: %s", exc)
            return {"total_repairs": 0, "successful_repairs": 0, "success_rate": 0.0, "by_error_type": []}

    def get_all_validated(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return all validated repairs (for UI display)."""
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, timestamp, error_type, repair_strategy,
                           validation_ok, attempts, confidence
                    FROM repairs
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception:
            return []

    # ============================================================
    # INTERNAL
    # ============================================================

    def _ensure_db(self) -> None:
        """Create database and table if they don't exist."""
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            with self._connect() as conn:
                conn.execute(_CREATE_TABLE_SQL)
                conn.commit()
        except Exception as exc:
            logger.warning("KnowledgeBase init failed: %s", exc)

    def _connect(self) -> sqlite3.Connection:
        """Return a new database connection."""
        return sqlite3.connect(self._db_path, timeout=5)
