"""Use Claude to decide actionability and extract structured tasks from an email."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from config import get_settings
from services.gmail_service import EmailMessage
from utils.logger import get_logger
from utils.retry import with_retry

log = get_logger(__name__)


@dataclass
class ExtractedTask:
    task: str
    deadline: str = ""           # ISO date string or free-form ("EOD Friday")
    urgency: str = "medium"      # high | medium | low
    follow_ups: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    actionable: bool
    summary: str
    tasks: list[ExtractedTask] = field(default_factory=list)


_SYSTEM_PROMPT = """You are an email triage assistant. For each email, decide whether it requires action by the recipient and, if so, extract the concrete tasks.

Return ONLY valid JSON matching this schema:
{
  "actionable": boolean,
  "summary": string,
  "tasks": [
    {
      "task": string,
      "deadline": string,
      "urgency": "high" | "medium" | "low",
      "follow_ups": [string]
    }
  ]
}

Rules:
- "actionable" is true only when the recipient must DO something (reply, decide, deliver, attend, review, pay, sign, etc.). Newsletters, receipts, marketing, automated notifications are NOT actionable.
- "deadline" should be an ISO date (YYYY-MM-DD) when a specific date is implied; otherwise a short phrase ("EOD Friday", "ASAP") or "" if none.
- "urgency": "high" for same-day / explicit urgency / blocker language; "low" for FYI-style asks; "medium" otherwise.
- "follow_ups" lists optional follow-on questions or items the recipient should track. Empty list if none.
- If not actionable, return tasks: [].
- Output JSON only — no prose, no markdown fences."""


class TaskExtractor:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        self._client = anthropic.Anthropic(api_key=api_key or s.anthropic_api_key)
        self._model = model or s.anthropic_model

    # ---------------------------------------------------------------- public
    @with_retry(
        exceptions=(
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ),
        attempts=4,
    )
    def extract(self, email: EmailMessage) -> ExtractionResult:
        user_prompt = self._build_prompt(email)
        log.debug("Calling Claude for %s", email.short_repr())
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return self._parse_response(text)

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _build_prompt(email: EmailMessage) -> str:
        # Truncate body to keep token usage bounded.
        body = (email.body or email.snippet or "").strip()
        if len(body) > 6000:
            body = body[:6000] + "\n...[truncated]"
        return (
            f"From: {email.sender}\n"
            f"Subject: {email.subject}\n"
            f"Received: {email.received_at}\n"
            f"---\n"
            f"{body}\n"
        )

    @staticmethod
    def _parse_response(text: str) -> ExtractionResult:
        raw = text.strip()
        # Strip code fences if the model added them despite instructions.
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```\s*$", "", raw)

        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            # Last-resort: pick out the first {...} block.
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                log.warning("Claude response was not JSON: %s", raw[:200])
                return ExtractionResult(actionable=False, summary="(unparseable response)")
            data = json.loads(match.group(0))

        tasks: list[ExtractedTask] = []
        for t in data.get("tasks", []) or []:
            tasks.append(
                ExtractedTask(
                    task=str(t.get("task", "")).strip(),
                    deadline=str(t.get("deadline", "") or "").strip(),
                    urgency=str(t.get("urgency", "medium") or "medium").strip().lower(),
                    follow_ups=[str(x) for x in (t.get("follow_ups") or [])],
                )
            )

        return ExtractionResult(
            actionable=bool(data.get("actionable", False)),
            summary=str(data.get("summary", "") or "").strip(),
            tasks=tasks,
        )
