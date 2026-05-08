"""
On-disk artifact storage.

The DB is the searchable source of truth, but we also persist the raw
transcripts as plain text alongside the audio so they can be inspected
manually if anything goes wrong.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import settings


def write_transcript_file(
    *,
    session_id: str,
    chunk_index: int,
    transcript: str,
    summary: Optional[str] = None,
) -> Path:
    """
    Write a single chunk's transcript (and optional summary) to
    `data/transcripts/<session>/chunk_NNNN.txt`. Returns the path.
    """
    base: Path = settings.transcripts_dir / session_id
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"chunk_{chunk_index:04d}.txt"

    parts: list[str] = []
    if summary:
        parts.append("# Summary\n")
        parts.append(summary.strip() + "\n\n")
    parts.append("# Transcript\n")
    parts.append(transcript.strip() + "\n")

    path.write_text("".join(parts), encoding="utf-8")
    return path
