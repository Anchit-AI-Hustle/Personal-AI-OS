"""
Gmail API client.

Wraps the parts of `googleapiclient` we actually need: list, get-full,
markRead, and a helper to flatten a parsed payload back into plain text.
"""
from __future__ import annotations

import base64
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from utils.logger import get_logger
from utils.retry import retry_call

from .auth import get_credentials

logger = get_logger(__name__)


@dataclass
class GmailMessage:
    message_id: str
    thread_id: str
    subject: str
    sender: str
    received_at: str  # ISO 8601 UTC
    snippet: str
    body_text: str
    label_ids: list[str]


def _decode_base64url(data: str) -> bytes:
    if not data:
        return b""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _walk_payload(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield this part and every nested part."""
    yield payload
    for child in payload.get("parts") or []:
        yield from _walk_payload(child)


def _extract_body(payload: dict[str, Any]) -> str:
    """
    Return the best-effort plaintext body. Falls back to text/html stripped
    of tags if no text/plain part is present.
    """
    plain_chunks: list[str] = []
    html_chunks: list[str] = []

    for part in _walk_payload(payload):
        mime_type = part.get("mimeType") or ""
        body = part.get("body") or {}
        data = body.get("data")
        if not data:
            continue
        try:
            decoded = _decode_base64url(data).decode("utf-8", errors="replace")
        except Exception:
            continue
        if mime_type == "text/plain":
            plain_chunks.append(decoded)
        elif mime_type == "text/html":
            html_chunks.append(decoded)

    if plain_chunks:
        return "\n".join(plain_chunks).strip()

    if html_chunks:
        # Crude tag strip — good enough as input for Claude.
        import re
        joined = "\n".join(html_chunks)
        no_tags = re.sub(r"<[^>]+>", " ", joined)
        no_entities = (
            no_tags.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )
        return re.sub(r"\s+", " ", no_entities).strip()

    return ""


def _header(headers: list[dict[str, str]], name: str) -> str:
    target = name.lower()
    for h in headers:
        if (h.get("name") or "").lower() == target:
            return h.get("value") or ""
    return ""


class GmailClient:
    def __init__(self) -> None:
        creds = get_credentials()
        # cache_discovery=False to silence the file_cache warning on Windows.
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # --- listing -------------------------------------------------------------

    def list_message_ids(self, query: str, max_results: int = 100) -> list[tuple[str, str]]:
        """Return list of (message_id, thread_id) matching `query`."""

        def _call() -> list[tuple[str, str]]:
            results: list[tuple[str, str]] = []
            page_token: Optional[str] = None
            while True:
                resp = (
                    self._svc.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        pageToken=page_token,
                        maxResults=min(max_results - len(results), 100),
                    )
                    .execute()
                )
                for m in resp.get("messages", []):
                    results.append((m["id"], m.get("threadId", "")))
                    if len(results) >= max_results:
                        return results
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return results

        return retry_call(_call, attempts=4, exceptions=(HttpError, TimeoutError))

    # --- single message ------------------------------------------------------

    def fetch_message(self, message_id: str) -> GmailMessage:
        def _call() -> dict[str, Any]:
            return (
                self._svc.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

        msg = retry_call(_call, attempts=4, exceptions=(HttpError, TimeoutError))
        payload = msg.get("payload") or {}
        headers = payload.get("headers") or []

        subject = _header(headers, "Subject")
        sender = _header(headers, "From")

        # internalDate is ms since epoch, UTC.
        try:
            ts_ms = int(msg.get("internalDate") or 0)
            received_at = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
        except Exception:
            received_at = datetime.now(timezone.utc).isoformat()

        body_text = _extract_body(payload)
        snippet = msg.get("snippet") or ""

        return GmailMessage(
            message_id=msg["id"],
            thread_id=msg.get("threadId", ""),
            subject=subject,
            sender=sender,
            received_at=received_at,
            snippet=snippet,
            body_text=body_text or snippet,
            label_ids=list(msg.get("labelIds") or []),
        )

    # --- mutations -----------------------------------------------------------

    def mark_as_read(self, message_id: str) -> None:
        def _call() -> None:
            self._svc.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

        try:
            retry_call(_call, attempts=3, exceptions=(HttpError, TimeoutError))
        except Exception:
            logger.warning("Could not mark %s as read — continuing.", message_id)


_singleton: Optional[GmailClient] = None
_lock = threading.Lock()


def get_gmail_client() -> GmailClient:
    global _singleton
    if _singleton is None:
        with _lock:
            if _singleton is None:
                _singleton = GmailClient()
    return _singleton
