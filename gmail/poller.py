"""
Gmail polling loop.

Runs in its own thread. Every `POLLING_INTERVAL` seconds it lists
messages matching `GMAIL_QUERY_FILTER`, skips ones we've seen before,
and forwards new ones to a callback.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from config import settings
from database import get_db
from utils.logger import get_logger

from .client import GmailClient, GmailMessage, get_gmail_client

logger = get_logger(__name__)

OnMessage = Callable[[GmailMessage], None]


class GmailPoller(threading.Thread):
    def __init__(
        self,
        on_message: OnMessage,
        stop_event: threading.Event,
        client: GmailClient | None = None,
        interval: int | None = None,
        query: str | None = None,
    ) -> None:
        super().__init__(name="GmailPoller", daemon=True)
        self._on_message = on_message
        self._stop = stop_event
        self._client = client or get_gmail_client()
        self._interval = interval or settings.polling_interval
        self._query = query or settings.gmail_query_filter
        self._db = get_db()

    def run(self) -> None:  # pragma: no cover — thread entrypoint
        logger.info(
            "GmailPoller started (interval=%ss, query=%r)", self._interval, self._query
        )
        # Tick immediately, then wait between cycles.
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("Gmail poll cycle crashed; will retry next interval.")
                self._db.log_event("ERROR", "gmail.poller", "Poll cycle crashed")
            # Sleep in small increments so shutdown is responsive.
            for _ in range(self._interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
        logger.info("GmailPoller stopped.")

    def _tick(self) -> None:
        ids = self._client.list_message_ids(self._query, max_results=50)
        if not ids:
            logger.debug("Gmail poll: no messages match query.")
            return

        new_ids = [
            (mid, tid) for mid, tid in ids if not self._db.email_already_processed(mid)
        ]
        if not new_ids:
            logger.debug("Gmail poll: %d match, all already processed.", len(ids))
            return

        logger.info("Gmail poll: %d new message(s) to process.", len(new_ids))
        for mid, _tid in new_ids:
            if self._stop.is_set():
                return
            try:
                msg = self._client.fetch_message(mid)
                self._on_message(msg)
            except Exception:
                logger.exception("Failed to process Gmail message id=%s", mid)
                self._db.log_event(
                    "ERROR", "gmail.poller", f"Failed to process {mid}"
                )
