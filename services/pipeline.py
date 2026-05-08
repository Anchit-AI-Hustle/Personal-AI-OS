"""End-to-end processing pipeline: Gmail -> dedupe -> Claude -> Sheets -> SQLite."""
from __future__ import annotations

from datetime import datetime, timezone

from config import get_settings
from database import ProcessedEmailStore
from services.gmail_service import EmailMessage, GmailService
from services.sheets_service import SheetsService
from services.task_extractor import ExtractionResult, TaskExtractor
from utils.logger import get_logger

log = get_logger(__name__)


class EmailIntelligencePipeline:
    def __init__(
        self,
        gmail: GmailService,
        sheets: SheetsService,
        extractor: TaskExtractor,
        store: ProcessedEmailStore,
    ):
        self.gmail = gmail
        self.sheets = sheets
        self.extractor = extractor
        self.store = store
        self._settings = get_settings()

    # --------------------------------------------------------------- run
    def run_once(self) -> dict:
        """Single polling cycle. Returns counters for observability."""
        stats = {"fetched": 0, "new": 0, "actionable": 0, "tasks": 0, "errors": 0}

        try:
            ids = self.gmail.list_message_ids(
                query=self._settings.gmail_query,
                max_results=self._settings.gmail_max_results,
            )
        except Exception as e:
            log.exception("Gmail list failed: %s", e)
            stats["errors"] += 1
            return stats

        stats["fetched"] = len(ids)
        if not ids:
            log.info("No messages matched the query this cycle.")
            return stats

        message_ids = [mid for mid, _ in ids]
        new_ids = self.store.filter_unprocessed(message_ids)
        stats["new"] = len(new_ids)
        log.info("%d new message(s) of %d fetched", len(new_ids), len(message_ids))

        rows_to_append: list[list[str]] = []

        for mid in new_ids:
            try:
                email = self.gmail.fetch_message(mid)
            except Exception as e:
                log.exception("Skipping %s after fetch failure: %s", mid, e)
                stats["errors"] += 1
                continue

            try:
                result = self.extractor.extract(email)
            except Exception as e:
                log.exception("Claude extraction failed for %s: %s", mid, e)
                stats["errors"] += 1
                # Do NOT mark as processed — let it retry next cycle.
                continue

            log.info(
                "Processed %s actionable=%s tasks=%d",
                email.short_repr(), result.actionable, len(result.tasks),
            )

            if result.actionable and result.tasks:
                stats["actionable"] += 1
                stats["tasks"] += len(result.tasks)
                rows_to_append.extend(self._rows_for(email, result))

            try:
                self.store.mark_processed(
                    email.message_id,
                    thread_id=email.thread_id,
                    subject=email.subject,
                    sender=email.sender,
                    actionable=result.actionable,
                    task_count=len(result.tasks),
                )
            except Exception as e:
                log.exception("Failed to mark %s as processed: %s", mid, e)
                stats["errors"] += 1

        if rows_to_append:
            try:
                self.sheets.append_rows(rows_to_append)
            except Exception as e:
                log.exception("Sheets append failed: %s", e)
                stats["errors"] += 1

        log.info("Cycle complete: %s", stats)
        return stats

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _rows_for(email: EmailMessage, result: ExtractionResult) -> list[list[str]]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        rows: list[list[str]] = []
        for t in result.tasks:
            rows.append(
                [
                    now,
                    email.received_at,
                    email.sender,
                    email.subject,
                    t.task,
                    t.deadline,
                    t.urgency,
                    "; ".join(t.follow_ups),
                    email.message_id,
                ]
            )
        return rows
