"""
Background workers that run the reminder + daily-plan engine (services.planner).

Both are local-first: they always compute and log to the activity_log + task
update trail (no Google needed). When credentials are connected they ALSO email
the plan / reminders via the notifier — which fails gracefully otherwise.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from database import get_db
from utils.logger import get_logger

from . import planner
from .notifier import get_notifier

logger = get_logger(__name__)


def _sleep_interruptible(stop: threading.Event, seconds: float) -> None:
    while seconds > 0 and not stop.is_set():
        step = min(seconds, 5.0)
        time.sleep(step)
        seconds -= step


def _seconds_until_next(hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


class ReminderWorker(threading.Thread):
    """Periodically nudge open tasks whose deadlines are near/overdue."""

    def __init__(self, stop_event: threading.Event, check_minutes: int = 30) -> None:
        super().__init__(name="ReminderWorker", daemon=True)
        self._stop = stop_event
        self._interval = check_minutes * 60
        self._db = get_db()

    def run(self) -> None:  # pragma: no cover
        logger.info("ReminderWorker started (every %d min).", self._interval // 60)
        # Small initial delay so it doesn't fire in the same instant as boot.
        _sleep_interruptible(self._stop, 30)
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Reminder cycle failed.")
            _sleep_interruptible(self._stop, self._interval)
        logger.info("ReminderWorker stopped.")

    def run_once(self) -> int:
        tasks = self._db.open_tasks_for_reminders()
        due = planner.reminders_due(tasks)
        if not due:
            return 0
        notifier = get_notifier()
        sent_ids = []
        for r in due:
            # Local trail (always works): activity log + task update line.
            try:
                self._db.log_activity(
                    text=f"Reminder: {r.message}", workstream=r.workstream,
                    kind="reminder", source_type="Reminder", source_ref=str(r.task_id),
                )
                self._db.append_task_update(r.task_id, f"[reminder] {r.message}")
            except Exception:
                logger.exception("Could not log reminder for task %s", r.task_id)
            # Outbound (best-effort; no-op without credentials).
            try:
                notifier.send_email(
                    subject=f"⏰ {r.proximity.title()}: {r.task[:60]}",
                    text_body=f"{r.message}\n\nTask: {r.task}\nWorkstream: {r.workstream}",
                )
            except Exception:
                logger.exception("Reminder email failed (non-fatal) for %s", r.task_id)
            sent_ids.append(r.task_id)
        self._db.mark_reminder_sent(sent_ids)
        logger.info("Reminder cycle: nudged %d task(s).", len(sent_ids))
        return len(sent_ids)


class DailyPlanWorker(threading.Thread):
    """Each morning, build & log 'what to do today', grouped by workstream."""

    def __init__(self, stop_event: threading.Event, hour: int = 8) -> None:
        super().__init__(name="DailyPlanWorker", daemon=True)
        self._stop = stop_event
        self._hour = hour
        self._db = get_db()

    def run(self) -> None:  # pragma: no cover
        logger.info("DailyPlanWorker started (hour=%02d:00 local).", self._hour)
        while not self._stop.is_set():
            _sleep_interruptible(self._stop, _seconds_until_next(self._hour))
            if self._stop.is_set():
                break
            try:
                self.run_once()
            except Exception:
                logger.exception("Daily plan failed.")
        logger.info("DailyPlanWorker stopped.")

    def run_once(self) -> "planner.DailyPlan":
        tasks = self._db.open_tasks_for_reminders()
        plan = planner.build_daily_plan(tasks)
        # Local trail (always works).
        try:
            self._db.log_activity(
                text=plan.text, workstream="", kind="plan",
                source_type="DailyPlan", source_ref=plan.date,
            )
        except Exception:
            logger.exception("Could not log daily plan.")
        # Outbound (best-effort; no-op without credentials).
        try:
            get_notifier().send_email(
                subject=f"☀️ Today's plan · {plan.date} · {plan.total} item(s)",
                text_body=plan.text,
            )
        except Exception:
            logger.exception("Daily-plan email failed (non-fatal).")
        logger.info("Daily plan built for %s (%d items).", plan.date, plan.total)
        return plan
