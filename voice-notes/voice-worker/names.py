"""
Name inference helpers.

Reuses the existing Personal-AI-OS lexicon (transcription/lexicon.py) for
spelling-correction + canonicalisation, and adds vocative extraction:
pulling out names that speakers use to address each other ("Thanks, Aman",
"Aman, can you..."). These addressed names are strong cues for WHICH human a
recurring voice belongs to, which is how the system "learns" identities
without asking the user every time.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

# make the parent Personal-AI-OS package importable so we reuse its lexicon
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from transcription.lexicon import correct_names, all_canonical_names
except Exception:  # standalone fallback if run outside the repo
    def correct_names(t: str) -> str: return t
    def all_canonical_names() -> list[str]: return []


# Address patterns: a capitalised token next to a comma or greeting/closing.
_VOCATIVE_PATTERNS = [
    re.compile(r"\b(?:thanks|thank you|hi|hey|hello|ok|okay|yes|no|right|so)\s*,?\s+([A-Z][a-z]+)\b"),
    re.compile(r"\b([A-Z][a-z]+)\s*,\s+(?:can|could|would|do|did|are|will|what|why|how|please)\b"),
    re.compile(r"\bover to you\s+([A-Z][a-z]+)\b", re.I),
]

_STOP = {"I", "The", "So", "And", "But", "Yeah", "Well", "Okay", "Ok", "Right",
         "Yes", "No", "Hi", "Hey", "Hello", "Thanks", "Thank", "Please"}


def addressed_names(text: str) -> Counter:
    """Names that appear to be used to address someone, weighted by frequency."""
    text = correct_names(text or "")
    found: Counter = Counter()
    for rx in _VOCATIVE_PATTERNS:
        for m in rx.findall(text):
            name = m if isinstance(m, str) else m[0]
            name = name.strip()
            if name and name not in _STOP:
                found[name] += 1
    return found


def candidate_names(transcript_text: str, provided: list[str] | None) -> list[str]:
    """
    Ordered list of plausible human names for this note:
      1. names the user explicitly typed in the 'others' prompt (highest trust)
      2. names addressed in the transcript (correct_names-normalised)
    """
    out: list[str] = []
    for n in (provided or []):
        n = correct_names(n).strip()
        if n and n not in out:
            out.append(n)
    for n, _ in addressed_names(transcript_text).most_common():
        if n not in out:
            out.append(n)
    return out
