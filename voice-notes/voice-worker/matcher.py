"""
Speaker matching + smart, self-evolving identity assignment.

For each diarized per-file label in a note:
  1. build a voiceprint (ECAPA embedding)
  2. find the nearest known speaker (pgvector cosine via match_speaker RPC)
  3. decide: confident match -> link & auto-name; plausible -> link as a
     SUGGESTION the user can confirm; nothing close -> mint a new provisional
     speaker
  4. fold the embedding into the speaker's running centroid (continuous learning)
  5. infer/raise a name from candidate names (typed by user + addressed in the
     transcript) — but the system only *suggests*; the user confirms in-app.

Confirmation contract with the app:
  - note_speakers.suggested_name set + match_status in ('unknown','auto')  -> show
    a "we think Speaker X is <name> — correct?" card.
  - user taps correct  -> match_status='confirmed', speakers.status='confirmed',
    speakers.name = suggested_name.
  - user edits name    -> app writes speakers.name + match_status='confirmed'.
"""
from __future__ import annotations

import tempfile

import numpy as np

import config
from names import candidate_names
from voiceprint import SpeakerTurns, embed_speaker, to_pgvector, from_pgvector


def _group_turns(segments: list[dict]) -> dict[str, SpeakerTurns]:
    by_label: dict[str, SpeakerTurns] = {}
    for s in segments:
        lbl = s["speaker_label"]
        by_label.setdefault(lbl, SpeakerTurns(label=lbl, spans_ms=[]))
        if s.get("start_ms") is not None and s.get("end_ms") is not None:
            by_label[lbl].spans_ms.append((s["start_ms"], s["end_ms"]))
    return by_label


def _download_audio(sb, audio_path: str) -> str:
    blob = sb.storage.from_(config.STORAGE_BUCKET).download(audio_path)
    suffix = "." + (audio_path.rsplit(".", 1)[-1] if "." in audio_path else "m4a")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(blob)
    tmp.close()
    return tmp.name


def _best_match(sb, user_id: str, vec: np.ndarray):
    res = sb.rpc("match_speaker", {
        "p_user_id": user_id,
        "p_embedding": to_pgvector(vec),
        "p_limit": 3,
    }).execute()
    rows = res.data or []
    return rows[0] if rows else None


def _new_speaker(sb, user_id: str, *, is_self=False, name=None,
                 suggested=None, conf=None) -> str:
    row = {
        "user_id": user_id,
        "is_self": is_self,
        "name": name,
        "status": "confirmed" if (is_self or name) else "provisional",
        "suggested_name": suggested,
        "suggestion_confidence": conf,
        "voiceprint_count": 0,
    }
    out = sb.table("speakers").insert(row).execute()
    return out.data[0]["id"]


def process_note(sb, note: dict) -> None:
    user_id = note["user_id"]
    note_id = note["id"]

    segs = (sb.table("segments")
              .select("speaker_label,start_ms,end_ms,seq")
              .eq("note_id", note_id).order("seq").execute().data) or []
    if not segs:
        sb.table("notes").update({"status": "matched"}).eq("id", note_id).execute()
        return

    by_label = _group_turns(segs)
    names_pool = candidate_names(note.get("transcript_text") or "",
                                 note.get("participant_names"))
    self_only = note.get("participant_mode") == "self"

    audio_file = _download_audio(sb, note["audio_path"])
    used_names: set[str] = set()

    # process the busiest speaker first so the dominant voice claims the
    # strongest candidate name
    order = sorted(by_label.values(),
                   key=lambda t: sum(e - s for s, e in t.spans_ms), reverse=True)

    for turns in order:
        vec = embed_speaker(audio_file, turns)
        if vec is None:
            continue  # too little audio to identify; leave as 'Speaker X'

        speaker_id = None
        suggested = None
        confidence = None
        match_status = "unknown"

        if self_only:
            speaker_id = _ensure_self(sb, user_id)
            match_status = "confirmed"
        else:
            best = _best_match(sb, user_id, vec)
            sim = float(best["similarity"]) if best else 0.0
            if best and sim >= config.SIM_HIGH:
                speaker_id = best["speaker_id"]
                confidence = sim
                if best.get("name"):
                    suggested = best["name"]
                    match_status = "auto"          # confident, known person
            elif best and sim >= config.SIM_LOW:
                speaker_id = best["speaker_id"]    # same voice, but ask to confirm
                confidence = sim
                suggested = best.get("name")
                match_status = "unknown"
            else:
                speaker_id = _new_speaker(sb, user_id)  # brand-new voice

        # ---- name evolution: raise a suggestion if the voice is still nameless
        if not self_only:
            sp = (sb.table("speakers").select("name,suggested_name,status")
                    .eq("id", speaker_id).single().execute().data)
            if sp and not sp.get("name"):
                pick = suggested or _claim_name(names_pool, used_names)
                if pick:
                    suggested = pick
                    used_names.add(pick)
                    # remember the guess on the speaker for cross-note reinforcement
                    sb.table("speakers").update({
                        "suggested_name": pick,
                        "suggestion_confidence": confidence,
                    }).eq("id", speaker_id).execute()
            elif sp and sp.get("name"):
                suggested = sp["name"]

        # ---- persist links + learn (running-mean centroid, computed here)
        _fold_centroid(sb, speaker_id, vec)
        sb.table("voiceprints").upsert({
            "user_id": user_id, "note_id": note_id,
            "speaker_label": turns.label, "speaker_id": speaker_id,
            "embedding": to_pgvector(vec),
        }, on_conflict="note_id,speaker_label").execute()
        sb.table("note_speakers").update({
            "speaker_id": speaker_id,
            "suggested_name": suggested,
            "confidence": confidence,
            "match_status": match_status,
        }).eq("note_id", note_id).eq("speaker_label", turns.label).execute()
        sb.table("segments").update({"speaker_id": speaker_id}) \
            .eq("note_id", note_id).eq("speaker_label", turns.label).execute()

    sb.table("notes").update({"status": "matched"}).eq("id", note_id).execute()


def _ensure_self(sb, user_id: str) -> str:
    found = (sb.table("speakers").select("id")
               .eq("user_id", user_id).eq("is_self", True).limit(1).execute().data)
    if found:
        return found[0]["id"]
    return _new_speaker(sb, user_id, is_self=True, name=config.SELF_NAME)


def _claim_name(pool: list[str], used: set[str]) -> str | None:
    for n in pool:
        if n not in used:
            return n
    return None


def _fold_centroid(sb, speaker_id: str, vec: np.ndarray) -> None:
    """Update the speaker's running-mean centroid: c' = (c*n + v)/(n+1)."""
    row = (sb.table("speakers").select("centroid,voiceprint_count")
             .eq("id", speaker_id).single().execute().data) or {}
    n = row.get("voiceprint_count") or 0
    cur = from_pgvector(row.get("centroid"))
    if cur is None or n == 0:
        new = vec
        count = 1
    else:
        new = (cur * n + vec) / (n + 1)
        count = n + 1
    sb.table("speakers").update({
        "centroid": to_pgvector(new), "voiceprint_count": count,
    }).eq("id", speaker_id).execute()
