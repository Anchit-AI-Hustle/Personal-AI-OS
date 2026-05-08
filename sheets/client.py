"""
Google Sheets API client.

Handles header bootstrapping, batched appends, and counting existing rows
so we can store the row number where each task landed.
"""
from __future__ import annotations

import threading
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from gmail.auth import get_credentials
from utils.logger import get_logger
from utils.retry import retry_call

logger = get_logger(__name__)

# Order matters — these become the sheet's column layout.
HEADERS: list[str] = [
    "Timestamp",
    "Source Type",
    "Task",
    "Deadline",
    "Urgency",
    "Sender/Speaker",
    "Summary",
    "Status",
    "Source Reference ID",
]


class SheetsClient:
    def __init__(self) -> None:
        creds = get_credentials()
        self._svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._sheet_id = settings.google_sheet_id
        self._tab = settings.google_sheet_tab
        self._headers_ready = False
        self._lock = threading.Lock()

    # --- bootstrap -----------------------------------------------------------

    def ensure_headers(self) -> None:
        """Create the tab if missing and write headers if A1 is empty."""
        with self._lock:
            if self._headers_ready:
                return

            self._ensure_tab_exists()

            def _read_a1() -> list:
                resp = (
                    self._svc.spreadsheets()
                    .values()
                    .get(spreadsheetId=self._sheet_id, range=f"'{self._tab}'!A1:I1")
                    .execute()
                )
                return resp.get("values") or []

            existing = retry_call(_read_a1, attempts=3, exceptions=(HttpError, TimeoutError))
            if not existing:
                logger.info("Writing headers to sheet '%s'", self._tab)

                def _write_headers() -> None:
                    self._svc.spreadsheets().values().update(
                        spreadsheetId=self._sheet_id,
                        range=f"'{self._tab}'!A1",
                        valueInputOption="RAW",
                        body={"values": [HEADERS]},
                    ).execute()

                retry_call(_write_headers, attempts=3, exceptions=(HttpError, TimeoutError))

            self._headers_ready = True

    def _ensure_tab_exists(self) -> None:
        def _meta() -> dict:
            return (
                self._svc.spreadsheets()
                .get(spreadsheetId=self._sheet_id)
                .execute()
            )

        meta = retry_call(_meta, attempts=3, exceptions=(HttpError, TimeoutError))
        existing_titles = {
            s["properties"]["title"] for s in meta.get("sheets", [])
        }
        if self._tab in existing_titles:
            return

        logger.info("Creating sheet tab '%s'", self._tab)

        def _add_tab() -> None:
            self._svc.spreadsheets().batchUpdate(
                spreadsheetId=self._sheet_id,
                body={
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {"title": self._tab}
                            }
                        }
                    ]
                },
            ).execute()

        retry_call(_add_tab, attempts=3, exceptions=(HttpError, TimeoutError))

    # --- appends -------------------------------------------------------------

    def append_rows(self, rows: list[list[str]]) -> Optional[int]:
        """
        Append `rows` to the sheet. Returns the 1-based row number where
        the FIRST appended row landed (so callers can store mapping back
        to local task ids).
        """
        if not rows:
            return None
        self.ensure_headers()

        def _call() -> dict:
            return (
                self._svc.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self._sheet_id,
                    range=f"'{self._tab}'!A1",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": rows},
                )
                .execute()
            )

        resp = retry_call(_call, attempts=4, exceptions=(HttpError, TimeoutError))

        # `updates.updatedRange` looks like "Tasks!A57:I59" — parse the start row.
        updated_range = (resp.get("updates") or {}).get("updatedRange")
        first_row: Optional[int] = None
        if updated_range and "!" in updated_range:
            cell_ref = updated_range.split("!", 1)[1]
            start = cell_ref.split(":", 1)[0]
            digits = "".join(ch for ch in start if ch.isdigit())
            if digits:
                first_row = int(digits)

        logger.info(
            "Appended %d row(s) to sheet '%s' starting at row %s",
            len(rows),
            self._tab,
            first_row,
        )
        return first_row

    # --- mutations -----------------------------------------------------------

    def update_status(self, row_number: int, status: str) -> None:
        """Update column H (Status) of the given 1-based row."""
        if row_number is None or row_number < 2:
            return

        def _call() -> None:
            self._svc.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=f"'{self._tab}'!H{row_number}",
                valueInputOption="RAW",
                body={"values": [[status]]},
            ).execute()

        retry_call(_call, attempts=3, exceptions=(HttpError, TimeoutError))


_singleton: Optional[SheetsClient] = None
_lock = threading.Lock()


def get_sheets_client() -> SheetsClient:
    global _singleton
    if _singleton is None:
        with _lock:
            if _singleton is None:
                _singleton = SheetsClient()
    return _singleton
