"""SQLite-backed deduplication store for processed Gmail message IDs."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from utils.logger import get_logger

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_emails (
    message_id   TEXT PRIMARY KEY,
    thread_id    TEXT,
    subject      TEXT,
    sender       TEXT,
    processed_at TEXT NOT NULL,
    actionable   INTEGER NOT NULL DEFAULT 0,
    task_count   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_emails(processed_at);
"""


class ProcessedEmailStore:
    """Thread-safe wrapper around a small SQLite db tracking message IDs."""

    def __init__(self, db_path: Path):
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
        log.debug("SQLite schema ensured at %s", self._db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # check_same_thread=False + a process-wide lock makes this safe under APScheduler.
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        try:
            yield conn
        finally:
            conn.close()

    def is_processed(self, message_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM processed_emails WHERE message_id = ? LIMIT 1",
                (message_id,),
            )
            return cur.fetchone() is not None

    def filter_unprocessed(self, message_ids: Iterable[str]) -> list[str]:
        ids = list(message_ids)
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"SELECT message_id FROM processed_emails WHERE message_id IN ({placeholders})",
                ids,
            )
            seen = {row[0] for row in cur.fetchall()}
        return [i for i in ids if i not in seen]

    def mark_processed(
        self,
        message_id: str,
        *,
        thread_id: str | None = None,
        subject: str | None = None,
        sender: str | None = None,
        actionable: bool = False,
        task_count: int = 0,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_emails
                  (message_id, thread_id, subject, sender, processed_at, actionable, task_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    thread_id,
                    subject,
                    sender,
                    datetime.now(timezone.utc).isoformat(),
                    1 if actionable else 0,
                    int(task_count),
                ),
            )
            conn.commit()
