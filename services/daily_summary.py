"""
Daily strategic summary worker.

Once a day at `DAILY_SUMMARY_HOUR` local time we feed Claude everything
captured that day and store the resulting briefing in `daily_summaries`.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from ai import get_extractor
from database import get_db
from utils.logger import get_logger

logger = get_logger(__name__)


def _seconds_until_next(hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


class DailySummaryWorker(threading.Thread):
    def __init__(self, stop_event: threading.Event, hour: int) -> None:
        super().__init__(name="DailySummaryWorker", daemon=True)
        self._stop = stop_event
        self._hour = hour
        self._db = get_db()
        self._extractor = get_extractor()

    def run(self) -> None:  # pragma: no cover
        logger.info("DailySummaryWorker started (hour=%02d:00 local).", self._hour)
        while not self._stop.is_set():
            wait = _seconds_until_next(self._hour)
            # Sleep in 5s chunks so we shut down quickly on stop.
            while wait > 0 and not self._stop.is_set():
                step = min(wait, 5.0)
                time.sleep(step)
                wait -= step
            if self._stop.is_set():
                break
            try:
                self.run_once()
            except Exception:
                logger.exception("Daily summary failed.")
                self._db.log_event("ERROR", "daily_summary", "Run failed")
        logger.info("DailySummaryWorker stopped.")

    def run_once(self) -> None:
        today = datetime.now().date()
        date_str = today.isoformat()

        # DB timestamps are stored in UTC (isoformat with +00:00). Convert
        # local midnight to UTC so string >= comparisons are well-ordered.
        local_midnight = datetime(today.year, today.month, today.day).astimezone()
        since_iso = local_midnight.astimezone(timezone.utc).isoformat()

        tasks = self._db.recent_tasks(since_iso=since_iso)
        chunk_summaries = self._db.fetchall(
            """
            SELECT session_id, chunk_index, summary
              FROM transcript_chunks
             WHERE created_at >= ?
               AND summary IS NOT NULL
             ORDER BY created_at ASC
            """,
            (since_iso,),
        )
        emails = self._db.fetchall(
            """
            SELECT subject, sender, summary, status
              FROM processed_emails
             WHERE processed_at >= ?
               AND summary IS NOT NULL
             ORDER BY processed_at ASC
            """,
            (since_iso,),
        )

        if not tasks and not chunk_summaries and not emails:
            logger.info("No activity for %s; skipping daily summary.", date_str)
            return

        lines: list[str] = []
        if tasks:
            lines.append("## Tasks captured today")
            for t in tasks:
                lines.append(
                    f"- [{t['urgency']}] ({t['source_type']}) {t['task']}"
                    + (f" — due {t['deadline']}" if t['deadline'] else "")
                    + (f" — {t['sender_or_speaker']}" if t['sender_or_speaker'] else "")
                )

        if emails:
            lines.append("\n## Emails")
            for e in emails:
                lines.append(f"- {e['sender']} | {e['subject']} -> {e['summary']}")

        if chunk_summaries:
            lines.append("\n## Meeting / conversation snippets")
            for c in chunk_summaries:
                lines.append(f"- [{c['session_id']} #{c['chunk_index']}] {c['summary']}")

        payload = "\n".join(lines)
        result = self._extractor.daily_summary(date_str=date_str, payload=payload)
        summary_text = result.get("summary") or "(empty)"
        self._db.upsert_daily_summary(date_str, summary_text, result)
        logger.info("Daily summary written for %s (%d chars).", date_str, len(summary_text))
