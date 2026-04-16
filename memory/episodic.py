"""情景记忆 — SQLite 持久化的历史审计案例库

类比审计师的"案例档案柜": 支持按特征检索相似历史案例,
帮助 Risk Agent 做出更准确的风险判定。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH
from models import RiskAssessment


class EpisodicMemory:
    """SQLite-backed 情景记忆"""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                risk_score REAL NOT NULL,
                anomaly_types TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                community_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_risk_level ON audit_cases(risk_level);
            CREATE INDEX IF NOT EXISTS idx_community ON audit_cases(community_id);
        """)
        self._conn.commit()

    def store_case(self, assessment: RiskAssessment) -> None:
        """存储一条审计案例"""
        self._conn.execute(
            """INSERT INTO audit_cases
               (invoice_no, risk_level, risk_score, anomaly_types, reasoning, community_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                assessment.transaction.transaction.invoice_no,
                assessment.risk_level.value,
                assessment.risk_score,
                json.dumps([a.value for a in assessment.transaction.anomaly_types]),
                assessment.reasoning,
                assessment.transaction.community_id,
                datetime.now().isoformat(),
            ),
        )
        self._conn.commit()

    def find_similar_cases(
        self, anomaly_types: list[str], limit: int = 5
    ) -> list[dict]:
        """按异常类型检索相似历史案例"""
        placeholders = ",".join("?" for _ in anomaly_types)
        rows = self._conn.execute(
            f"""SELECT * FROM audit_cases
                WHERE anomaly_types LIKE '%' || ? || '%'
                ORDER BY created_at DESC LIMIT ?""",
            (anomaly_types[0] if anomaly_types else "", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """返回历史案例统计"""
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN risk_level='high' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN risk_level='medium' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN risk_level='low' THEN 1 ELSE 0 END) as low
               FROM audit_cases"""
        ).fetchone()
        return dict(row) if row else {"total": 0, "high": 0, "medium": 0, "low": 0}

    def close(self) -> None:
        self._conn.close()
