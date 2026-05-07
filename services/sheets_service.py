"""Append extracted tasks to a Google Sheet via gspread (service account)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, WorksheetNotFound

from config import get_settings
from utils.logger import get_logger
from utils.retry import with_retry

log = get_logger(__name__)

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW = [
    "Processed At (UTC)",
    "Email Received",
    "Sender",
    "Subject",
    "Task",
    "Deadline",
    "Urgency",
    "Follow-ups",
    "Gmail Message ID",
]


class SheetsService:
    def __init__(
        self,
        sheet_id: str | None = None,
        credentials_path: Path | None = None,
        worksheet_name: str | None = None,
    ):
        s = get_settings()
        self._sheet_id = sheet_id or s.google_sheet_id
        self._creds_path = credentials_path or s.google_credentials_path
        self._tab = worksheet_name or s.google_sheet_tab
        self._client: gspread.Client | None = None
        self._worksheet: gspread.Worksheet | None = None

    # -------------------------------------------------------------- connect
    def _connect(self) -> gspread.Worksheet:
        if self._worksheet is not None:
            return self._worksheet

        if not self._creds_path.exists():
            raise FileNotFoundError(
                f"Service-account credentials not found at {self._creds_path}"
            )

        creds = Credentials.from_service_account_file(
            str(self._creds_path), scopes=SHEETS_SCOPES
        )
        self._client = gspread.authorize(creds)
        spreadsheet = self._client.open_by_key(self._sheet_id)

        try:
            ws = spreadsheet.worksheet(self._tab)
        except WorksheetNotFound:
            log.info("Creating worksheet tab %r", self._tab)
            ws = spreadsheet.add_worksheet(title=self._tab, rows=1000, cols=len(HEADER_ROW))
            ws.append_row(HEADER_ROW, value_input_option="USER_ENTERED")

        # Ensure header row exists & matches.
        first_row = ws.row_values(1)
        if first_row != HEADER_ROW:
            log.info("Initializing header row on tab %r", self._tab)
            ws.update("A1", [HEADER_ROW], value_input_option="USER_ENTERED")

        self._worksheet = ws
        return ws

    # --------------------------------------------------------------- append
    @with_retry(exceptions=(APIError, ConnectionError, TimeoutError))
    def append_rows(self, rows: Sequence[Sequence[str]]) -> None:
        if not rows:
            return
        ws = self._connect()
        ws.append_rows(list(rows), value_input_option="USER_ENTERED")
        log.info("Appended %d row(s) to sheet %s/%s", len(rows), self._sheet_id, self._tab)
