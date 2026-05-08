"""
Background worker that flushes locally-stored tasks to Google Sheets.

The DB is the source of truth — sheets is the surface. If a sheet append
fails, the tasks stay marked unsynced and we'll retry next cycle.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from database import get_db
from utils.logger import get_logger

from .client import SheetsClient, get_sheets_client

logger = get_logger(__name__)

SYNC_INTERVAL_SECONDS = 30
BATCH_SIZE = 50


def _format_timestamp(iso: str) -> str:
    """Make the timestamp readable in the sheet."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        local = dt.astimezone()  # respect the host's local timezone
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso


class SheetsSyncWorker(threading.Thread):
    def __init__(
        self,
        stop_event: threading.Event,
        client: SheetsClient | None = None,
        interval: int = SYNC_INTERVAL_SECONDS,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        super().__init__(name="SheetsSyncWorker", daemon=True)
        self._stop = stop_event
        self._client = client or get_sheets_client()
        self._interval = interval
        self._batch_size = batch_size
        self._db = get_db()

    def run(self) -> None:  # pragma: no cover
        logger.info("SheetsSyncWorker started (interval=%ss)", self._interval)
        # Make sure headers exist before any append.
        try:
            self._client.ensure_headers()
        except Exception:
            logger.exception("Could not bootstrap sheet headers — will retry on next flush.")

        while not self._stop.is_set():
            try:
                self.flush_once()
            except Exception:
                logger.exception("Sheets sync cycle crashed; will retry.")
                self._db.log_event("ERROR", "sheets.sync", "Sync cycle crashed")
            for _ in range(self._interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
        logger.info("SheetsSyncWorker stopped.")

    def flush_once(self) -> int:
        rows_pushed = 0
        while not self._stop.is_set():
            tasks = self._db.unsynced_tasks(limit=self._batch_size)
            if not tasks:
                break

            rows = [
                [
                    _format_timestamp(t["created_at"]),
                    t["source_type"],
                    t["task"],
                    t["deadline"] or "",
                    t["urgency"],
                    t["sender_or_speaker"] or "",
                    t["summary"] or "",
                    t["status"],
                    t["source_ref_id"],
                ]
                for t in tasks
            ]

            first_row = self._client.append_rows(rows)
            self._db.mark_tasks_synced((t["id"] for t in tasks), starting_row=first_row)
            rows_pushed += len(rows)

            # If we got a full batch, loop again — there may be more.
            if len(tasks) < self._batch_size:
                break

        if rows_pushed:
            logger.info("Sheets sync: pushed %d task row(s).", rows_pushed)
        return rows_pushed
