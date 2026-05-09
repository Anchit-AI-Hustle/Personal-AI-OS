"""
Glue between the Gmail layer, the AI extractor, and the task service.

`process_message` is the callback that the Gmail poller invokes for every
new message.

Special routing: when the user uses WhatsApp's "Export chat -> Email"
feature, the resulting email is detected by subject and routed to the
WhatsApp extraction path instead of the regular email one. Tasks land
in the "Tasks From WhatsApp" tab.
"""
from __future__ import annotations

import re
from typing import Optional

from ai import get_extractor
from ai import QuotaExhaustedError
from database import get_db
from gmail.client import GmailMessage, get_gmail_client
from utils.logger import get_logger

from .task_service import TaskService

logger = get_logger(__name__)

# RFC 5322 address parser, lenient: pulls the bare email out of values like
# "Aman Kumar <aman@vahdam.com>" or just "aman@vahdam.com".
_EMAIL_RE = re.compile(r'<([^>]+@[^>]+)>|([^\s<>"]+@[^\s<>"]+)')

# WhatsApp's native "Export chat" feature mails the chat with a subject
# of the form "WhatsApp Chat with <name-or-group>" (iOS) or, on some
# Android builds, just "WhatsApp Chat - <name>". Match both leniently.
_WHATSAPP_SUBJECT_RE = re.compile(
    r"^\s*whatsapp\s+chat\s*(?:with|-|–|—)?\s*(.*)$",
    re.IGNORECASE,
)


def _detect_whatsapp_export(subject: Optional[str]) -> Optional[str]:
    """Return the chat partner name if `subject` is a WhatsApp export, else None."""
    if not subject:
        return None
    m = _WHATSAPP_SUBJECT_RE.match(subject)
    if not m:
        return None
    partner = (m.group(1) or "").strip().strip('"').strip("'")
    return partner or "(unknown chat)"


def _extract_email_address(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = _EMAIL_RE.search(raw)
    if not m:
        return None
    return (m.group(1) or m.group(2)).strip()


class EmailService:
    def __init__(self, task_service: Optional[TaskService] = None) -> None:
        self._extractor = get_extractor()
        self._db = get_db()
        self._tasks = task_service or TaskService()
        self._gmail = get_gmail_client()

    def process_message(self, msg: GmailMessage) -> None:
        if self._db.email_already_processed(msg.message_id):
            logger.debug("Email %s already processed; skipping.", msg.message_id)
            return

        logger.info(
            "Processing email id=%s from=%r subject=%r",
            msg.message_id,
            msg.sender,
            msg.subject,
        )

        # WhatsApp export forwards take a separate code path so they
        # land in the WhatsApp tab with the right source labelling.
        wa_partner = _detect_whatsapp_export(msg.subject)
        if wa_partner is not None:
            self._process_whatsapp_export(msg, wa_partner)
            return

        try:
            extraction = self._extractor.extract_from_email(
                sender=msg.sender,
                subject=msg.subject,
                received_at=msg.received_at,
                body=msg.body_text,
            )
        except QuotaExhaustedError:
            # Don't mark the email as processed — we want to retry it once
            # quota recovers. Re-raise so the poller stops the current
            # batch immediately instead of looping through dozens of
            # messages with the same outcome.
            raise
        except Exception:
            logger.exception("Gemini extraction failed for email %s", msg.message_id)
            self._db.record_processed_email(
                gmail_message_id=msg.message_id,
                thread_id=msg.thread_id,
                subject=msg.subject,
                sender=msg.sender,
                received_at=msg.received_at,
                summary=None,
                status="failed",
            )
            return

        new_tasks = 0
        if extraction.is_actionable and extraction.tasks:
            new_tasks = self._tasks.save_email_tasks(
                gmail_message_id=msg.message_id,
                sender=msg.sender,
                email_summary=extraction.summary,
                tasks=extraction.tasks,
                received_at=msg.received_at,
                thread_id=msg.thread_id,
                sender_email=_extract_email_address(msg.sender),
            )

        self._db.record_processed_email(
            gmail_message_id=msg.message_id,
            thread_id=msg.thread_id,
            subject=msg.subject,
            sender=msg.sender,
            received_at=msg.received_at,
            summary=extraction.summary,
            status="processed" if extraction.is_actionable else "skipped",
        )

        logger.info(
            "Email %s -> actionable=%s, %d new task(s)",
            msg.message_id,
            extraction.is_actionable,
            new_tasks,
        )

    def _process_whatsapp_export(self, msg: GmailMessage, chat_partner: str) -> None:
        """
        Handle a WhatsApp "Export chat" forward. The body is the chat log;
        we hand it to the WhatsApp prompt and route extracted tasks to the
        WhatsApp source.
        """
        logger.info(
            "Email %s detected as WhatsApp export (chat=%r); routing.",
            msg.message_id,
            chat_partner,
        )
        try:
            extraction = self._extractor.extract_from_whatsapp(
                chat_partner=chat_partner,
                exported_at=msg.received_at,
                chat_log=msg.body_text,
            )
        except QuotaExhaustedError:
            raise
        except Exception:
            logger.exception(
                "WhatsApp extraction failed for email %s", msg.message_id
            )
            self._db.record_processed_email(
                gmail_message_id=msg.message_id,
                thread_id=msg.thread_id,
                subject=msg.subject,
                sender=msg.sender,
                received_at=msg.received_at,
                summary=None,
                status="failed",
            )
            return

        new_tasks = 0
        if extraction.tasks:
            new_tasks = self._tasks.save_whatsapp_tasks(
                gmail_message_id=msg.message_id,
                chat_partner=chat_partner,
                chat_summary=extraction.summary,
                tasks=extraction.tasks,
                exported_at=msg.received_at,
                thread_id=msg.thread_id,
            )

        # Always record the email so we don't re-process the same export.
        self._db.record_processed_email(
            gmail_message_id=msg.message_id,
            thread_id=msg.thread_id,
            subject=msg.subject,
            sender=msg.sender,
            received_at=msg.received_at,
            summary=extraction.summary,
            status="processed" if new_tasks else "skipped",
        )

        logger.info(
            "WhatsApp export %s -> %d new task(s) (chat=%r)",
            msg.message_id,
            new_tasks,
            chat_partner,
        )
