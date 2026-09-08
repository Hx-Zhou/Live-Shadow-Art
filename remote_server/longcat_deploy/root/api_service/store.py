from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_status_created
                    ON jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def set_state(self, **values: Any) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for key, value in values.items():
                encoded = json.dumps(value, ensure_ascii=False)
                connection.execute(
                    "INSERT INTO service_state(key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, encoded),
                )
            connection.commit()

    def get_state(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute("SELECT key, value FROM service_state").fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}

    def pending_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchone()
        return int(row["count"])

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        task_id = uuid4().hex
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs(task_id, status, created_at, updated_at, request_json) "
                "VALUES (?, 'queued', ?, ?, ?)",
                (task_id, now, now, json.dumps(request, ensure_ascii=False)),
            )
        return self.require(task_id)

    def require(self, task_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            queue_position = None
            if row["status"] == "queued":
                position = connection.execute(
                    "SELECT COUNT(*) AS count FROM jobs "
                    "WHERE status = 'queued' AND created_at <= ?",
                    (row["created_at"],),
                ).fetchone()
                queue_position = int(position["count"])
        return self._decode(row, queue_position)

    def claim_next(self) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            changed = connection.execute(
                "UPDATE jobs SET status = 'running', updated_at = ? "
                "WHERE task_id = ? AND status = 'queued'",
                (now, row["task_id"]),
            ).rowcount
            connection.commit()
            if changed != 1:
                return None
        return self.require(row["task_id"])

    def finish(self, task_id: str, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'succeeded', updated_at = ?, result_json = ?, error = NULL "
                "WHERE task_id = ?",
                (utc_now(), json.dumps(result, ensure_ascii=False), task_id),
            )

    def fail(self, task_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', updated_at = ?, error = ? WHERE task_id = ?",
                (utc_now(), error[:4000], task_id),
            )

    def recover_interrupted(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status = 'queued', updated_at = ?, "
                "error = 'Requeued after worker restart' WHERE status = 'running'",
                (utc_now(),),
            )
        return cursor.rowcount

    @staticmethod
    def _decode(row: sqlite3.Row, queue_position: int | None) -> dict[str, Any]:
        return {
            "task_id": row["task_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "request": json.loads(row["request_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
            "queue_position": queue_position,
        }

