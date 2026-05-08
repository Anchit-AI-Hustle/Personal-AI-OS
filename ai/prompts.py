"""
Prompt library.

Every prompt asks Claude to return a JSON object inside a ```json fenced
block. The extractor (`ai/extractor.py`) is responsible for parsing.
"""
from __future__ import annotations

from textwrap import dedent

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_SYSTEM_PROMPT = dedent(
    """
    You are an executive assistant analysing a single email on behalf of the
    user. Your job is to identify whether the email demands the user's
    attention and, if so, extract crisp action items.

    Be conservative — newsletters, marketing, automated notifications, and
    pure FYI emails are NOT actionable. Only flag tasks that the *recipient*
    must do something about.

    Always respond with a single JSON object inside a ```json fenced block.
    No commentary outside the block.

    JSON schema:
    {
      "is_actionable": boolean,
      "summary": string,            // 1-2 sentences, plain English
      "tasks": [
        {
          "task": string,           // imperative, e.g. "Reply to Aakash with Q3 numbers"
          "deadline": string|null,  // ISO 8601 date or natural language phrase the email used
          "urgency": "Low" | "Medium" | "High" | "Critical"
        }
      ]
    }

    Urgency rubric:
    - Critical: same-day deadline, an outage, an angry customer, a CEO-level ask
    - High: within 48h, blocking someone, money on the line
    - Medium: this week, normal back-and-forth
    - Low: nice-to-do, no real deadline
    """
).strip()


def build_email_user_prompt(*, sender: str, subject: str, received_at: str, body: str) -> str:
    body_clip = (body or "").strip()
    if len(body_clip) > 12000:
        body_clip = body_clip[:12000] + "\n[... truncated ...]"
    return dedent(
        f"""
        Analyse the following email.

        From: {sender}
        Subject: {subject}
        Received: {received_at}

        --- BODY ---
        {body_clip}
        --- END BODY ---
        """
    ).strip()


# ---------------------------------------------------------------------------
# Meeting / conversation chunk
# ---------------------------------------------------------------------------

MEETING_SYSTEM_PROMPT = dedent(
    """
    You are analysing a 1-3 minute audio transcript chunk from a meeting,
    standup, hallway conversation, or solo voice memo. The audio may mix
    Hindi and English freely.

    Your output must be a single JSON object inside a ```json fenced block.
    No commentary outside.

    JSON schema:
    {
      "summary": string,            // 1-3 sentences capturing what was said
      "tasks": [
        {
          "task": string,
          "deadline": string|null,
          "urgency": "Low" | "Medium" | "High" | "Critical",
          "owner": string|null      // who is supposed to do it, if mentioned
        }
      ],
      "ideas":         [string],    // novel ideas, product/feature concepts
      "blockers":      [string],    // explicit blockers or dependencies
      "opportunities": [string],    // strategic openings, growth angles
      "decisions":     [string],    // explicit decisions made
      "follow_ups":    [string]     // things to revisit later
    }

    Be precise. Empty lists are fine — do not invent items. Translate
    Hindi-only items into English in the JSON, but keep names and product
    terms verbatim.
    """
).strip()


def build_meeting_user_prompt(*, started_at: str, transcript: str) -> str:
    text = (transcript or "").strip()
    if len(text) > 16000:
        text = text[:16000] + "\n[... truncated ...]"
    return dedent(
        f"""
        Analyse the following transcript chunk.

        Started: {started_at}

        --- TRANSCRIPT ---
        {text}
        --- END TRANSCRIPT ---
        """
    ).strip()


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

DAILY_SUMMARY_SYSTEM_PROMPT = dedent(
    """
    You are writing the user's end-of-day strategic briefing based on the
    tasks, meeting summaries, and email summaries collected during the day.

    Output a single JSON object inside a ```json fenced block.

    Schema:
    {
      "summary": string,                    // 4-8 sentence narrative of the day
      "top_priorities_tomorrow": [string],  // ordered, max 5
      "recurring_themes": [string],         // patterns across multiple items
      "strategic_insights": [string],       // non-obvious observations
      "risks": [string]                     // things likely to go wrong
    }

    Be specific. Reference concrete tasks/people/projects. Skip filler.
    """
).strip()


def build_daily_summary_user_prompt(*, date_str: str, payload: str) -> str:
    return dedent(
        f"""
        Date: {date_str}

        Below is everything captured today (tasks, meeting summaries, email
        summaries). Use it to produce the briefing.

        --- DAILY PAYLOAD ---
        {payload}
        --- END PAYLOAD ---
        """
    ).strip()
