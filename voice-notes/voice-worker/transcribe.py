"""
AssemblyAI polling + turn-by-turn ingestion + smart tagging.

The edge function submits the job and stores notes.transcript_job_id. Here the
always-on worker polls that job; when complete it writes merged, turn-by-turn
segments, seeds note_speakers, generates tags (Gemini, best-effort), and moves
the note to status='diarized' so voiceprint matching can run.
"""
from __future__ import annotations

import json
import re

import requests

import config

AAI = "https://api.assemblyai.com/v2"


def poll_and_ingest(sb, note: dict) -> bool:
    """Return True if the note reached a terminal state (diarized/failed)."""
    job_id = note.get("transcript_job_id")
    if not job_id:
        _fail(sb, note["id"], "missing transcript_job_id")
        return True

    r = requests.get(f"{AAI}/transcript/{job_id}",
                     headers={"authorization": config.ASSEMBLYAI_API_KEY}, timeout=30)
    tr = r.json()
    status = tr.get("status")
    if status == "error":
        _fail(sb, note["id"], f"assemblyai: {tr.get('error')}")
        return True
    if status != "completed":
        return False  # still processing; try again next tick

    user_id = note["user_id"]
    note_id = note["id"]

    # AssemblyAI utterances are speaker-delimited turns; merge any consecutive
    # same-speaker turns into one block for a clean turn-by-turn transcript.
    merged: list[dict] = []
    for u in tr.get("utterances") or []:
        if merged and merged[-1]["speaker"] == u["speaker"]:
            merged[-1]["text"] += " " + u["text"]
            merged[-1]["end"] = u["end"]
        else:
            merged.append({"speaker": u["speaker"], "start": u["start"],
                           "end": u["end"], "text": u["text"]})

    # idempotent re-ingest
    sb.table("segments").delete().eq("note_id", note_id).execute()
    sb.table("note_speakers").delete().eq("note_id", note_id).execute()

    if merged:
        sb.table("segments").insert([{
            "note_id": note_id, "user_id": user_id, "seq": i,
            "speaker_label": m["speaker"], "start_ms": m["start"],
            "end_ms": m["end"], "text": m["text"].strip(),
        } for i, m in enumerate(merged)]).execute()

    labels = sorted({m["speaker"] for m in merged})
    if labels:
        sb.table("note_speakers").insert([{
            "note_id": note_id, "user_id": user_id,
            "speaker_label": l, "match_status": "unknown",
        } for l in labels]).execute()

    text = tr.get("text") or ""
    heuristic_meeting = len(labels) >= 2 and (tr.get("audio_duration") or 0) > 180
    tagged = _smart_tag(text, len(labels), heuristic_meeting)

    sb.table("notes").update({
        "status": "diarized",
        "transcript_text": text or None,
        "language": tr.get("language_code"),
        "title": tagged.get("title") or _derive_title(text),
        "summary": tagged.get("summary"),
        "tags": tagged.get("tags") or [],
        "is_meeting": tagged.get("is_meeting", heuristic_meeting),
    }).eq("id", note_id).execute()
    return True


def _fail(sb, note_id: str, msg: str) -> None:
    sb.table("notes").update({"status": "failed", "error": msg[:500]}).eq("id", note_id).execute()


def _derive_title(text: str):
    if not text:
        return None
    first = re.split(r"[.!?\n]", text.strip())[0].strip()
    return (first[:61] + "…") if len(first) > 64 else (first or None)


def _smart_tag(text: str, speakers: int, heuristic_meeting: bool) -> dict:
    out = {"title": None, "summary": None, "tags": [], "is_meeting": heuristic_meeting}
    if not config.GEMINI_API_KEY or len(text) < 20:
        return out
    try:
        prompt = (
            f"You label voice notes. There are {speakers} distinct speaker(s).\n"
            'Return STRICT JSON: {"title":"<=8 words","summary":"one sentence",'
            '"tags":["3-6 short lowercase topic tags"],"is_meeting":true|false}.\n'
            "is_meeting=true only if this reads like a multi-person discussion.\n"
            f'TRANSCRIPT:\n"""{text[:6000]}"""'
        )
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={config.GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
            timeout=30,
        )
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        p = json.loads(raw)
        return {
            "title": p.get("title"),
            "summary": p.get("summary"),
            "tags": [str(t) for t in (p.get("tags") or [])][:6],
            "is_meeting": bool(p.get("is_meeting", heuristic_meeting)),
        }
    except Exception:
        return out
