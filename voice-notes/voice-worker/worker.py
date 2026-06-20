"""
Voice-worker poll loop.

Runs alongside the existing Personal-AI-OS Python service (same machine / venv).
Polls Supabase for notes that have been diarized by the edge function and
runs voiceprint matching + smart speaker identification on them.

    python -m voice_worker.worker          # from voice-notes/
    # or, inside voice-notes/voice-worker/:
    python worker.py

Set --once to process the current backlog and exit (useful for cron).
"""
from __future__ import annotations

import argparse
import time
import traceback

from supabase import create_client

import config
from matcher import process_note
from transcribe import poll_and_ingest


def _client():
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)


def _select(sb, status: str, cols: str, limit=10) -> list[dict]:
    return (sb.table("notes").select(cols).eq("status", status)
              .order("recorded_at").limit(limit).execute().data) or []


def run_once(sb) -> int:
    work = 0

    # stage 1: poll AssemblyAI for submitted jobs -> diarized
    for note in _select(sb, "transcribing", "id,user_id,transcript_job_id"):
        try:
            done = poll_and_ingest(sb, note)
            if done:
                print(f"[ok] ingested transcript for {note['id']}")
                work += 1
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            sb.table("notes").update({"status": "failed", "error": str(e)[:500]}) \
              .eq("id", note["id"]).execute()

    # stage 2: voiceprint matching -> matched
    for note in _select(sb, "diarized",
                        "id,user_id,audio_path,transcript_text,participant_mode,participant_names"):
        sb.table("notes").update({"status": "matching"}).eq("id", note["id"]).execute()
        try:
            process_note(sb, note)
            print(f"[ok] matched note {note['id']}")
            work += 1
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            sb.table("notes").update({"status": "failed", "error": str(e)[:500]}) \
              .eq("id", note["id"]).execute()
    return work


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="drain backlog and exit")
    args = ap.parse_args()

    sb = _client()
    print("voice-worker started"
          + (" (once)" if args.once else f" (poll {config.POLL_SECONDS}s)"))
    if args.once:
        run_once(sb)
        return
    while True:
        try:
            n = run_once(sb)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            n = 0
        time.sleep(config.POLL_SECONDS if n == 0 else 1)


if __name__ == "__main__":
    main()
