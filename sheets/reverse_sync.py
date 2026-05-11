"""
Reverse sync: pull human edits from Google Sheets back into the DB.

The forward sync worker (sheets/sync.py) is the source of truth for the
DB -> Sheet direction. This worker handles the reverse: when a human
manually edits the Status column on the sheet, that change needs to
flow back into `extracted_tasks.status` so the daily digest, the chat
poller, and any future surfaces see the updated state.

Scope:
  - Status column only. Other columns (description, deadline, etc.) are
    intentionally NOT round-tripped — the sheet is the user's working
    surface for those, the DB doesn't need them.
  - "Master Task List" is the canonical surface to read from.

Lookup strategy (post sort-key column):
  The forward sync now re-sorts each tab DESC by hidden col O after
  every push, which makes `sheet_row_all` mappings stale every minute.
  So we no longer look up tasks by row index. Instead:

    1. Read columns A (heading), I (SPOC), C (status) in a single API
       call from the Master tab.
    2. For each row, compute `(normalized_heading, lowercase SPOC)` —
       the same key TaskService uses for merge-dedup.
    3. Match against open tasks in the DB by that key.
    4. If the sheet status differs from the DB, update the DB.

  This is robust to row-position changes (sorts, manual reordering,
  inserts) and to the user adding handwritten rows that don't map to
  any DB row (those just won't match and get skipped).

Failure modes:
  - Sheet API outage: log warning, retry next cycle.
  - Status value the sheet contains isn't a recognised enum: snap to
    closest match, otherwise skip with a logged note.
  - Sheet row whose heading doesn't match any DB task: skipped silently.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from googleapiclient.errors import HttpError

from config import settings
from database import get_db
from services.task_service import normalize_heading
from utils.identifiers import clean_identifier
from utils.logger import get_logger
from utils.retry import retry_call

from .client import (
    SheetsClient,
    TAB_ALL_TASKS,
    USER_VISIBLE_COLS,
    get_sheets_client,
)

logger = get_logger(__name__)

REVERSE_SYNC_INTERVAL_SECONDS = 60

# 1-based indices in the visible 14-column layout (HEADERS in
# sheets/client.py). Kept here as constants so a future header
# reordering only needs one place to update.
_COL_HEADING = 0   # A
_COL_STATUS = 2    # C
_COL_SPOC = 8      # I

_VALID_STATUSES = {"open", "done", "dropped"}
_STATUS_ALIASES = {
    "open": "open",
    "todo": "open",
    "to do": "open",
    "pending": "open",
    "in progress": "open",
    "wip": "open",
    "blocked": "open",
    "done": "done",
    "complete": "done",
    "completed": "done",
    "closed": "done",
    "shipped": "done",
    "dropped": "dropped",
    "cancelled": "dropped",
    "canceled": "dropped",
    "wontfix": "dropped",
    "won't fix": "dropped",
    "skip": "dropped",
}


def _normalise_status(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _VALID_STATUSES:
        return s
    return _STATUS_ALIASES.get(s)


def _col_letter(n: int) -> str:
    """1-based column index -> A1 letter."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


class ReverseSyncWorker(threading.Thread):
    """
    Periodically reads the visible columns of "Master Task List" and
    updates the DB for any task whose status was edited by the user.

    Idempotent: if the sheet status already matches the DB, no write.
    Robust to row-position changes after sort operations.
    """

    def __init__(
        self,
        stop_event: threading.Event,
        client: Optional[SheetsClient] = None,
        interval: int = REVERSE_SYNC_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(name="ReverseSyncWorker", daemon=True)
        self._stop = stop_event
        self._client = client or get_sheets_client()
        self._interval = interval
        self._db = get_db()

    def run(self) -> None:  # pragma: no cover
        logger.info("ReverseSyncWorker started (interval=%ss)", self._interval)
        # Wait one interval before the first poll so the forward sync has
        # a chance to bootstrap tabs/headers on a fresh boot.
        for _ in range(self._interval):
            if self._stop.is_set():
                return
            time.sleep(1)

        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception("Reverse sync cycle crashed; will retry.")
            for _ in range(self._interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
        logger.info("ReverseSyncWorker stopped.")

    def poll_once(self) -> int:
        """
        Read every visible row of Master Task List, match by
        (normalized_heading, SPOC) to an open DB task, update DB
        rows whose sheet status has changed. Returns the number
        of DB rows updated this cycle.
        """
        # Read the entire user-visible part of the Master tab in a
        # single API call. We deliberately exclude the hidden sort-key
        # column O — its raw ISO contents aren't useful here.
        end_col = _col_letter(USER_VISIBLE_COLS)
        rng = f"'{TAB_ALL_TASKS}'!A2:{end_col}"

        def _read() -> list:
            resp = (
                self._client._svc.spreadsheets()  # noqa: SLF001
                .values()
                .get(spreadsheetId=settings.google_sheet_id, range=rng)
                .execute()
            )
            return resp.get("values") or []

        try:
            sheet_rows = retry_call(
                _read, attempts=3, exceptions=(HttpError, TimeoutError)
            )
        except HttpError as exc:
            status = getattr(exc.resp, "status", None) if exc.resp else None
            if status in (400, 404):
                logger.warning(
                    "Reverse sync: cannot read tab %r — not found on the Sheet. "
                    "Skipping this cycle.",
                    TAB_ALL_TASKS,
                )
                return 0
            logger.exception("Reverse sync: HTTP error reading Master tab.")
            return 0
        except Exception:
            logger.exception("Reverse sync: could not read Master tab.")
            return 0

        if not sheet_rows:
            return 0

        # Build an index of open DB tasks keyed on (normalized_heading,
        # spoc_lower). One key may legitimately have one row at most —
        # TaskService dedup enforces it.
        db_index: dict[tuple[str, str], dict] = {}
        for r in self._db.fetchall(
            "SELECT id, task, normalized_heading, sender_or_speaker, status "
            "FROM extracted_tasks WHERE status = 'open'"
        ):
            norm = (r["normalized_heading"] or "").lower()
            if not norm:
                # Fall back to deriving it now if the column was never
                # populated (very old rows). Doesn't mutate the DB —
                # just used for this lookup.
                norm = normalize_heading(r["task"] or "").lower()
            spoc_lc = (clean_identifier(r["sender_or_speaker"]) or "").lower()
            db_index[(norm, spoc_lc)] = dict(r)

        updates = 0
        unknown_values: set[str] = set()
        misses = 0

        for row in sheet_rows:
            heading = row[_COL_HEADING] if len(row) > _COL_HEADING else ""
            sheet_status = row[_COL_STATUS] if len(row) > _COL_STATUS else ""
            spoc = row[_COL_SPOC] if len(row) > _COL_SPOC else ""

            heading = (heading or "").strip()
            if not heading:
                continue

            key = (
                normalize_heading(heading).lower(),
                (clean_identifier(spoc) or "").lower(),
            )
            task = db_index.get(key)
            if task is None:
                misses += 1
                continue

            normalised = _normalise_status(sheet_status)
            if normalised is None:
                if sheet_status and sheet_status.strip():
                    unknown_values.add(sheet_status.strip())
                continue
            if normalised == task["status"]:
                continue

            try:
                self._db.update_task_status(int(task["id"]), normalised)
                updates += 1
                logger.info(
                    "Reverse sync: task id=%d (%r) status %r -> %r",
                    task["id"],
                    heading,
                    task["status"],
                    normalised,
                )
            except ValueError:
                logger.debug(
                    "Reverse sync: rejected status %r for task id=%d",
                    normalised, task["id"],
                )

        if unknown_values:
            logger.info(
                "Reverse sync: ignored %d unrecognised status value(s): %s",
                len(unknown_values),
                sorted(unknown_values),
            )
        if misses:
            logger.debug(
                "Reverse sync: %d sheet row(s) didn't match any open DB task "
                "(likely manually-added rows or closed tasks).",
                misses,
            )
        if updates:
            logger.info(
                "Reverse sync: %d task status update(s) pulled from Sheet.", updates
            )
        return updates
