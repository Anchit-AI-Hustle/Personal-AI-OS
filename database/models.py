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

# The two workstreams every task is routed into (separate sheet tabs +
# dashboard tabs). Keep aligned with ai/prompts.py:WORKSTREAMS_LIST.
WORKSTREAMS = ("Vahdam", "My AI Projects")
DEFAULT_WORKSTREAM = "Vahdam"

# Keep aligned with ai/prompts.py:GROWTH_PILLARS_LIST.
GROWTH_PILLARS = (
    "Acquisition",
    "Conversion",
    "AOV",
    "Retention",
    "Marketplace",
    "Operations",
    "Brand & Content",
    "Margin",
    "Team & Process",
    "Other",
)


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


def normalise_workstream(raw: Optional[str]) -> str:
    """Snap whatever the LLM returned to one of the two known workstreams.

    Defaults to Vahdam — the historical scope — so legacy rows and any
    ambiguous output keep their old behaviour.
    """
    if not raw:
        return DEFAULT_WORKSTREAM
    s = raw.strip().lower()
    # Anything clearly about Anchit's own builds/side-projects.
    ai_markers = ("ai project", "my ai", "personal", "side project", "jarvis",
                  "resume", "portfolio", "personal ai os", "own project")
    if any(m in s for m in ai_markers):
        return "My AI Projects"
    if "vahdam" in s:
        return "Vahdam"
    # Exact match on a known value, else default.
    for w in WORKSTREAMS:
        if w.lower() == s:
            return w
    return DEFAULT_WORKSTREAM


def normalise_growth_pillar(raw: Optional[str]) -> str:
    """Snap whatever Gemini returned to the closest known pillar."""
    if not raw:
        return "Other"
    s = raw.strip()
    # Exact match (case-insensitive).
    for p in GROWTH_PILLARS:
        if p.lower() == s.lower():
            return p
    # Cheap synonym table for common misses.
    syn = {
        "acq": "Acquisition",
        "acquire": "Acquisition",
        "performance marketing": "Acquisition",
        "paid media": "Acquisition",
        "cro": "Conversion",
        "checkout": "Conversion",
        "pdp": "Conversion",
        "upsell": "AOV",
        "bundle": "AOV",
        "gifting": "AOV",
        "ltv": "Retention",
        "subscription": "Retention",
        "loyalty": "Retention",
        "klaviyo": "Retention",
        "amazon": "Marketplace",
        "flipkart": "Marketplace",
        "marketplaces": "Marketplace",
        "ops": "Operations",
        "fulfilment": "Operations",
        "fulfillment": "Operations",
        "customer service": "Operations",
        "cx": "Operations",
        "pr": "Brand & Content",
        "content": "Brand & Content",
        "social": "Brand & Content",
        "influencer": "Brand & Content",
        "cogs": "Margin",
        "freight": "Margin",
        "packaging": "Margin",
        "hiring": "Team & Process",
        "process": "Team & Process",
    }
    low = s.lower()
    for needle, pillar in syn.items():
        if needle in low:
            return pillar
    return "Other"


@dataclass
class ExtractedTask:
    # Short imperative — appears in the "Task Heading" sheet column and is
    # also the dedup key (combined with source_ref_id).
    task_heading: str

    # Longer 1-3 sentence detail of what to do — "Task Description" column.
    task_description: str = ""

    # Why-this-matters rationale — "Why We're Doing This" column.
    rationale: str = ""

    # One of GROWTH_PILLARS — "Growth Pillar" column.
    growth_pillar: str = "Other"

    # One of WORKSTREAMS — decides which sheet tab + dashboard tab this
    # task lands in ("Vahdam" vs "My AI Projects").
    workstream: str = DEFAULT_WORKSTREAM

    # Existing fields, repurposed.
    urgency: str = "Medium"           # -> "Priority" column
    deadline: Optional[str] = None    # -> "Task Deadline" column
    sender_or_speaker: Optional[str] = None  # -> "SPOC" column

    # Email or phone for the SPOC, when the source mentioned one. Falls
    # back to the source-level contact (e.g. the email sender's address)
    # in TaskService if the LLM didn't extract one.
    owner_contact: Optional[str] = None  # -> "SPOC Contact" column

    # Free-text context attached at extraction time (the email/chunk summary).
    summary: Optional[str] = None

    def __post_init__(self) -> None:
        self.task_heading = (self.task_heading or "").strip()
        self.task_description = (self.task_description or "").strip()
        self.rationale = (self.rationale or "").strip()
        self.urgency = normalise_urgency(self.urgency)
        self.growth_pillar = normalise_growth_pillar(self.growth_pillar)
        self.workstream = normalise_workstream(self.workstream)

    @property
    def task(self) -> str:
        """Backward-compatible accessor: heading is what older code called 'task'."""
        return self.task_heading


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
