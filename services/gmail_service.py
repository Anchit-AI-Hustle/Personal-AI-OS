"""Gmail API integration: OAuth flow, listing messages, parsing bodies."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import get_settings
from utils.logger import get_logger
from utils.retry import with_retry

log = get_logger(__name__)

# Read-only scope is sufficient: we only fetch metadata + bodies.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class EmailMessage:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    received_at: str  # RFC 2822 date header value
    snippet: str
    body: str

    def short_repr(self) -> str:
        return f"<Email id={self.message_id} from={self.sender!r} subj={self.subject!r}>"


class GmailService:
    """Thin wrapper around the Gmail API with OAuth handling."""

    def __init__(
        self,
        oauth_client_path: Path | None = None,
        token_path: Path | None = None,
    ):
        s = get_settings()
        self._client_path = oauth_client_path or s.gmail_oauth_client_path
        self._token_path = token_path or s.gmail_token_path
        self._service = None

    # ------------------------------------------------------------------ auth
    def authenticate(self, *, interactive: bool = True) -> None:
        """Build/refresh credentials and cache the Gmail service handle.

        Pass interactive=False in production runs to fail fast if no token
        exists yet (the operator must run --setup-gmail beforehand).
        """
        creds: Credentials | None = None
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)

        if creds and creds.valid:
            pass
        elif creds and creds.expired and creds.refresh_token:
            log.info("Refreshing expired Gmail token")
            creds.refresh(Request())
            self._token_path.write_text(creds.to_json(), encoding="utf-8")
        else:
            if not interactive:
                raise RuntimeError(
                    f"No valid Gmail token at {self._token_path}. "
                    "Run `python main.py --setup-gmail` first."
                )
            if not self._client_path.exists():
                raise FileNotFoundError(
                    f"OAuth client secrets not found at {self._client_path}. "
                    "Download from Google Cloud Console (OAuth 2.0 Client ID, Desktop app)."
                )
            log.info("Launching OAuth flow for Gmail")
            flow = InstalledAppFlow.from_client_secrets_file(str(self._client_path), SCOPES)
            creds = flow.run_local_server(port=0)
            self._token_path.write_text(creds.to_json(), encoding="utf-8")
            log.info("Saved Gmail token to %s", self._token_path)

        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            self.authenticate(interactive=False)
        return self._service

    # ----------------------------------------------------------------- list
    @with_retry(exceptions=(HttpError, ConnectionError, TimeoutError))
    def list_message_ids(self, query: str, max_results: int) -> list[tuple[str, str]]:
        """Return [(message_id, thread_id), ...] for messages matching `query`."""
        resp = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        msgs = resp.get("messages", []) or []
        log.info("Gmail returned %d message ids for query %r", len(msgs), query)
        return [(m["id"], m.get("threadId", "")) for m in msgs]

    # ------------------------------------------------------------------ get
    @with_retry(exceptions=(HttpError, ConnectionError, TimeoutError))
    def fetch_message(self, message_id: str) -> EmailMessage:
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        return self._parse(msg)

    def fetch_many(self, message_ids: Iterable[str]) -> list[EmailMessage]:
        out: list[EmailMessage] = []
        for mid in message_ids:
            try:
                out.append(self.fetch_message(mid))
            except Exception as e:
                log.exception("Failed to fetch message %s: %s", mid, e)
        return out

    # ---------------------------------------------------------------- parse
    @staticmethod
    def _header(headers: list[dict], name: str) -> str:
        name_l = name.lower()
        for h in headers:
            if h.get("name", "").lower() == name_l:
                return h.get("value", "") or ""
        return ""

    @classmethod
    def _extract_body(cls, payload: dict) -> str:
        """Walk the MIME tree and return the best plain-text body."""
        if not payload:
            return ""

        mime = payload.get("mimeType", "")
        body = payload.get("body", {}) or {}
        data = body.get("data")

        if mime == "text/plain" and data:
            return cls._decode(data)

        # Walk children; prefer text/plain, fall back to text/html stripped.
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for part in payload.get("parts", []) or []:
            sub = cls._extract_body(part)
            if not sub:
                continue
            if part.get("mimeType") == "text/html":
                html_parts.append(sub)
            else:
                plain_parts.append(sub)

        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            # Naive HTML strip — Claude tolerates noise, no need for bs4.
            import re

            joined = "\n".join(html_parts)
            return re.sub(r"<[^>]+>", " ", joined)
        if data:
            return cls._decode(data)
        return ""

    @staticmethod
    def _decode(data: str) -> str:
        try:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
        except Exception:
            return ""

    @classmethod
    def _parse(cls, msg: dict) -> EmailMessage:
        payload = msg.get("payload", {}) or {}
        headers = payload.get("headers", []) or []
        return EmailMessage(
            message_id=msg["id"],
            thread_id=msg.get("threadId", ""),
            sender=cls._header(headers, "From"),
            subject=cls._header(headers, "Subject"),
            received_at=cls._header(headers, "Date"),
            snippet=msg.get("snippet", "") or "",
            body=cls._extract_body(payload),
        )
