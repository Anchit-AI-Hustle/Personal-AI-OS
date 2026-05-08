<<<<<<< HEAD
"""
Personal AI OS — entrypoint.

Boots every background worker and blocks until Ctrl+C / SIGTERM is
received, then shuts everything down cleanly.

    python main.py
=======
"""Entry point for the Personal AI Email Intelligence system.

Usage:
    python main.py                 # Start the 5-minute scheduler loop.
    python main.py --setup-gmail   # Run interactive Gmail OAuth and exit.
    python main.py --once          # Run a single processing cycle and exit.
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5
"""
from __future__ import annotations

import argparse
import signal
import sys
<<<<<<< HEAD
import threading
import time
from typing import Optional

from config import settings  # noqa: F401  -- importing validates env vars
from database import get_db
from gmail import GmailPoller
from meetings import MeetingPipeline
from services import DailySummaryWorker, EmailService
from sheets import SheetsSyncWorker
from utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger("main")


class PersonalAIOS:
    def __init__(self, *, enable_email: bool, enable_meetings: bool) -> None:
        self.stop_event = threading.Event()
        self._enable_email = enable_email
        self._enable_meetings = enable_meetings
        self._gmail_poller: Optional[GmailPoller] = None
        self._sheets_worker: Optional[SheetsSyncWorker] = None
        self._meeting_pipeline: Optional[MeetingPipeline] = None
        self._daily_worker: Optional[DailySummaryWorker] = None

    # --- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        # Make sure the DB exists before any worker tries to write to it.
        get_db()

        if self._enable_email:
            email_service = EmailService()
            self._gmail_poller = GmailPoller(
                on_message=email_service.process_message,
                stop_event=self.stop_event,
            )
            self._gmail_poller.start()
        else:
            logger.info("Email module disabled by flag.")

        # Sheets sync runs regardless — it flushes whatever the other
        # workers wrote, so even a meeting-only run benefits from it.
        self._sheets_worker = SheetsSyncWorker(stop_event=self.stop_event)
        self._sheets_worker.start()

        if self._enable_meetings and settings.enable_meeting_capture:
            self._meeting_pipeline = MeetingPipeline(stop_event=self.stop_event)
            self._meeting_pipeline.start()
        else:
            logger.info("Meeting module disabled by flag or config.")

        self._daily_worker = DailySummaryWorker(
            stop_event=self.stop_event, hour=settings.daily_summary_hour
        )
        self._daily_worker.start()

        logger.info("Personal AI OS is up. Press Ctrl+C to stop.")

    def wait(self) -> None:
        # Block the main thread; daemon threads keep the work going.
        try:
            while not self.stop_event.is_set():
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Ctrl+C received.")

    def shutdown(self) -> None:
        if self.stop_event.is_set():
            return
        logger.info("Shutting down Personal AI OS...")
        self.stop_event.set()

        if self._meeting_pipeline is not None:
            self._meeting_pipeline.shutdown()

        for worker in (self._gmail_poller, self._sheets_worker, self._daily_worker):
            if worker is not None and worker.is_alive():
                worker.join(timeout=10.0)

        # Final flush of any tasks captured at the last second.
        if self._sheets_worker is not None:
            try:
                self._sheets_worker.flush_once()
            except Exception:
                logger.exception("Final sheets flush failed.")

        logger.info("Shutdown complete.")


def _install_signal_handlers(app: PersonalAIOS) -> None:
    def _handle(signum, _frame) -> None:
        logger.info("Received signal %s.", signum)
        app.stop_event.set()

    signal.signal(signal.SIGINT, _handle)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _handle)
        except (ValueError, OSError):
            # SIGTERM can't be installed in some restricted threads on Windows.
            pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Personal AI OS")
    p.add_argument("--no-email", action="store_true", help="disable Gmail polling")
    p.add_argument("--no-meetings", action="store_true", help="disable audio capture")
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))

    app = PersonalAIOS(
        enable_email=not args.no_email,
        enable_meetings=not args.no_meetings,
    )
    _install_signal_handlers(app)

    try:
        app.start()
        app.wait()
    except Exception:
        logger.exception("Fatal error in main loop.")
        return 1
    finally:
        app.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
=======

# pyrefly: ignore [missing-import]
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import get_settings
from database import ProcessedEmailStore
from services.gmail_service import GmailService
from services.pipeline import EmailIntelligencePipeline
from services.sheets_service import SheetsService
from services.task_extractor import TaskExtractor
from utils.logger import get_logger, setup_logging


def _build_pipeline() -> EmailIntelligencePipeline:
    s = get_settings()
    gmail = GmailService()
    gmail.authenticate(interactive=False)  # fail fast if token missing
    sheets = SheetsService()
    extractor = TaskExtractor()
    store = ProcessedEmailStore(s.sqlite_path)
    return EmailIntelligencePipeline(gmail, sheets, extractor, store)


def cmd_setup_gmail() -> int:
    log = get_logger("setup")
    log.info("Starting Gmail OAuth flow...")
    GmailService().authenticate(interactive=True)
    log.info("Gmail authentication complete. Token saved.")
    return 0


def cmd_once() -> int:
    log = get_logger("main")
    pipeline = _build_pipeline()
    stats = pipeline.run_once()
    log.info("One-shot run finished: %s", stats)
    return 0


def cmd_loop() -> int:
    log = get_logger("main")
    s = get_settings()
    pipeline = _build_pipeline()

    # Run immediately so the operator gets feedback on startup,
    # then every POLL_INTERVAL_MINUTES thereafter.
    log.info("Initial run before scheduling...")
    try:
        pipeline.run_once()
    except Exception as e:
        log.exception("Initial run failed: %s", e)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        pipeline.run_once,
        trigger=IntervalTrigger(minutes=s.poll_interval_minutes),
        id="email_poll",
        name="Email intelligence poll",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )

    # Graceful shutdown on Ctrl+C / SIGTERM (Windows: Ctrl+C only).
    def _stop(signum, _frame):
        log.info("Received signal %s, shutting down scheduler", signum)
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _stop)
        except (ValueError, OSError):
            # SIGTERM handler can't be set on the main thread on some Windows setups.
            pass

    log.info("Scheduler started: every %d minute(s)", s.poll_interval_minutes)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="Personal AI Email Intelligence")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--setup-gmail",
        action="store_true",
        help="Run the interactive Gmail OAuth flow and exit.",
    )
    group.add_argument(
        "--once",
        action="store_true",
        help="Run a single processing cycle and exit (useful for testing / cron).",
    )
    args = parser.parse_args(argv)

    if args.setup_gmail:
        return cmd_setup_gmail()
    if args.once:
        return cmd_once()
    return cmd_loop()


if __name__ == "__main__":
    sys.exit(main())
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5
