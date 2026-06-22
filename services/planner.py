"""
Reminder + daily-plan engine.

Pure, dependency-light logic that decides:
  * which open tasks are due / overdue, from messy deadline strings,
  * when a task should be nudged (escalating, non-panicky cadence),
  * what today's plan looks like, grouped by workstream.

Everything here is side-effect free and unit-testable. The workers in
`services/planner_workers.py` call these functions and handle DB reads,
activity logging, and (when Google is connected) outbound mail/chat.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as _dateparser

# How close (in days) counts as "due soon".
SOON_WINDOW_DAYS = 3

# Minimum hours between reminders for a task, by proximity bucket. Closer /
# overdue tasks are nudged more often; distant ones get a single gentle ping.
_REMIND_COOLDOWN_HOURS = {
    "overdue": 20,
    "today": 20,
    "soon": 44,
    "later": 24 * 7,
}

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def parse_deadline(raw: Optional[str], *, today: Optional[date] = None) -> Optional[date]:
    """Best-effort parse of a deadline string (ISO or natural language).

    Returns a date, or None when nothing date-like can be recovered.
    """
    if not raw:
        return None
    today = today or date.today()
    s = raw.strip().lower()
    if not s or s in ("none", "n/a", "tbd", "asap", "-"):
        # ASAP is urgent but not a date — caller treats it via urgency.
        return None

    # Relative phrases first (cheap, unambiguous).
    if "today" in s or "eod" in s or "end of day" in s:
        return today
    if "tomorrow" in s:
        return today + timedelta(days=1)
    if "day after" in s:
        return today + timedelta(days=2)
    if "end of week" in s or "eow" in s or "this week" in s:
        # Friday of the current week.
        return today + timedelta(days=(4 - today.weekday()) % 7)
    if "next week" in s:
        return today + timedelta(days=7)
    m = re.search(r"in (\d+) day", s)
    if m:
        return today + timedelta(days=int(m.group(1)))
    for name, idx in _WEEKDAYS.items():
        if name in s:
            return today + timedelta(days=(idx - today.weekday()) % 7 or 7)

    # Fall back to a real date parse (handles ISO + "12 May", "May 12 2026", etc).
    try:
        dt = _dateparser.parse(raw, default=datetime(today.year, today.month, today.day))
        return dt.date()
    except (ValueError, OverflowError, TypeError):
        return None


def proximity(deadline: Optional[date], *, today: Optional[date] = None) -> str:
    """Bucket a deadline relative to today: overdue|today|soon|later|none."""
    if deadline is None:
        return "none"
    today = today or date.today()
    delta = (deadline - today).days
    if delta < 0:
        return "overdue"
    if delta == 0:
        return "today"
    if delta <= SOON_WINDOW_DAYS:
        return "soon"
    return "later"


def _hours_since(iso_ts: Optional[str], *, now: datetime) -> Optional[float]:
    if not iso_ts:
        return None
    try:
        prev = _dateparser.parse(iso_ts)
    except (ValueError, TypeError):
        return None
    if prev.tzinfo is not None:
        prev = prev.replace(tzinfo=None)
    return (now - prev).total_seconds() / 3600.0


# Varied, non-panicky reminder tones keyed by proximity. The index rotates by
# task id so the same task doesn't always read identically — calm, not naggy.
_TONES = {
    "overdue": [
        "Quick nudge — this one slipped past its date. Still on?",
        "Circling back: this was due {when}. Want to close it out or push the date?",
        "No stress — flagging that this is past due. What's the latest?",
    ],
    "today": [
        "On the radar for today: {task}.",
        "Today's the day for this one. Need anything to land it?",
        "Heads up — this is due today.",
    ],
    "soon": [
        "Coming up {when}: {task}.",
        "Gentle heads-up — this is due {when}.",
        "On the horizon ({when}). No rush yet.",
    ],
    "later": [
        "Future you's plate: {task}, due {when}.",
    ],
    "none": [
        "High-priority and date-less — worth pinning a day to it: {task}.",
        "This one's important but has no deadline yet. When can it land?",
    ],
}


def reminder_tone(prox: str, *, when: str, task: str, salt: int = 0) -> str:
    opts = _TONES.get(prox) or _TONES["soon"]
    return opts[salt % len(opts)].format(when=when, task=task)


@dataclass
class Reminder:
    task_id: int
    task: str
    workstream: str
    proximity: str
    deadline: Optional[date]
    message: str
    spoc: str = ""


def _due_phrase(deadline: Optional[date], prox: str, *, today: date) -> str:
    if deadline is None:
        return "soon"
    if prox == "overdue":
        d = (today - deadline).days
        return f"{d} day{'s' if d != 1 else ''} ago"
    if prox == "today":
        return "today"
    delta = (deadline - today).days
    if delta == 1:
        return "tomorrow"
    return deadline.strftime("%a %d %b")


def reminders_due(tasks, *, now: Optional[datetime] = None, today: Optional[date] = None) -> list[Reminder]:
    """From open task rows, return the ones that should be nudged right now.

    `tasks` are mapping-like rows with: id, task, deadline, urgency, status,
    sender_or_speaker, last_reminder_sent_at, and (optionally) workstream.
    """
    now = now or datetime.now()
    today = today or now.date()
    out: list[Reminder] = []
    for t in tasks:
        if (t["status"] or "open") != "open":
            continue
        dl = parse_deadline(t["deadline"], today=today)
        prox = proximity(dl, today=today)
        urg = str(t["urgency"] or "").lower()
        # Distant deadlines: no proactive nudge yet — they'll surface as they
        # near. No deadline at all: only nudge Critical/High (so a date gets set).
        if prox == "later":
            continue
        if prox == "none" and urg not in ("critical", "high"):
            continue
        cooldown = _REMIND_COOLDOWN_HOURS.get(prox, 24 * 7)
        since = _hours_since(_row(t, "last_reminder_sent_at"), now=now)
        if since is not None and since < cooldown:
            continue
        when = _due_phrase(dl, prox, today=today)
        msg = reminder_tone(prox, when=when, task=t["task"], salt=int(t["id"]))
        out.append(Reminder(
            task_id=int(t["id"]),
            task=t["task"],
            workstream=_row(t, "workstream") or "Vahdam",
            proximity=prox,
            deadline=dl,
            message=msg,
            spoc=_row(t, "sender_or_speaker"),
        ))
    return out


@dataclass
class DailyPlan:
    date: str
    by_workstream: dict = field(default_factory=dict)  # ws -> list[dict]
    text: str = ""

    @property
    def total(self) -> int:
        return sum(len(v) for v in self.by_workstream.values())


_URGENCY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_daily_plan(tasks, *, today: Optional[date] = None) -> DailyPlan:
    """Today's priorities: overdue + due-today + due-soon + high-urgency,
    grouped by workstream and ordered by (proximity, urgency)."""
    today = today or date.today()
    plan = DailyPlan(date=today.isoformat())
    prox_rank = {"overdue": 0, "today": 1, "soon": 2, "later": 3, "none": 4}
    picked = []
    for t in tasks:
        if (t["status"] or "open") != "open":
            continue
        dl = parse_deadline(t["deadline"], today=today)
        prox = proximity(dl, today=today)
        urg = str(t["urgency"] or "Medium").lower()
        # Include if it has any near-term pressure OR is high/critical.
        if prox in ("overdue", "today", "soon") or urg in ("critical", "high"):
            picked.append((prox, urg, dl, t))

    picked.sort(key=lambda x: (prox_rank.get(x[0], 9), _URGENCY_RANK.get(x[1], 9)))
    for prox, urg, dl, t in picked:
        ws = _row(t, "workstream") or "Vahdam"
        plan.by_workstream.setdefault(ws, []).append({
            "id": int(t["id"]),
            "task": t["task"],
            "proximity": prox,
            "deadline": dl.isoformat() if dl else None,
            "urgency": t["urgency"] or "Medium",
            "spoc": _row(t, "sender_or_speaker"),
        })

    # Human-readable plan text.
    lines = [f"Plan for {today.strftime('%A %d %b %Y')}"]
    if not plan.total:
        lines.append("\nNothing pressing today — clear runway. 🎯")
    for ws, items in plan.by_workstream.items():
        lines.append(f"\n■ {ws} ({len(items)})")
        for it in items:
            tag = {"overdue": "⚠ overdue", "today": "due today",
                   "soon": "due soon", "later": "", "none": ""}.get(it["proximity"], "")
            suffix = f" — {tag}" if tag else ""
            if it["spoc"]:
                suffix += f" · {it['spoc']}"
            lines.append(f"  • {it['task']}{suffix}")
    plan.text = "\n".join(lines)
    return plan


def _row(row, key: str) -> str:
    """Tolerant accessor — rows may or may not carry every column."""
    try:
        v = row[key]
    except (IndexError, KeyError):
        return ""
    return v if v is not None else ""
