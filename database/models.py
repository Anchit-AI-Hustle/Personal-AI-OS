"""
Light value-object models. We don't use a full ORM — sqlite3.Row is plenty
for our access patterns — but typed constructors make the rest of the code
cleaner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

URGENCY_VALUES = ("Low", "Medium", "High", "Critical")
SOURCE_TYPES = ("Email", "Meeting", "Conversation")


def normalise_urgency(raw: Optional[str]) -> str:
    if not raw:
        return "Medium"
    s = raw.strip().lower()
    table = {
        "low": "Low",
        "medium": "Medium",
        "med": "Medium",
        "normal": "Medium",
        "high": "High",
        "urgent": "High",
        "critical": "Critical",
        "blocker": "Critical",
        "p0": "Critical",
        "p1": "High",
        "p2": "Medium",
        "p3": "Low",
    }
    return table.get(s, "Medium")


@dataclass
class ExtractedTask:
    task: str
    urgency: str = "Medium"
    deadline: Optional[str] = None
    sender_or_speaker: Optional[str] = None
    summary: Optional[str] = None

    def __post_init__(self) -> None:
        self.urgency = normalise_urgency(self.urgency)
        self.task = self.task.strip()


@dataclass
class EmailExtraction:
    summary: str
    tasks: list[ExtractedTask] = field(default_factory=list)
    is_actionable: bool = False


@dataclass
class MeetingChunkExtraction:
    summary: str
    tasks: list[ExtractedTask] = field(default_factory=list)
    ideas: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
