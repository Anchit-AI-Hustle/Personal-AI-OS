# Personal AI OS — Voice Notes & Universal Note-taker

A cross-platform (iOS + Android) capture app that turns talk into organised,
searchable notes — and learns who's speaking over time. It's a new subsystem of
**Personal AI OS**: it shares your Supabase database and reuses the existing
name lexicon, while leaving the Windows task-extractor service untouched.

## What it does

- **Capture anything** — a recorded voice note, a typed note, a pasted link, or
  uploaded files (images, video, music, audio, PDFs, documents). Audio/video
  uploads are auto-transcribed too.
- **Meeting-aware recording** — records for a configurable length (default
  **30 min**). If it senses an ongoing **meeting** (sustained, multi-party
  speech), it keeps recording past the cap and only stops after **10 min of
  continuous silence**. Both thresholds are editable in Settings.
- **Turn-by-turn transcripts** — each speaker's turn in correct sequence;
  consecutive lines by the same person are grouped into one block.
- **Self-evolving voice recognition** — every recording is diarized, and each
  voice gets an ECAPA voiceprint. Recurring voices are matched automatically
  across notes. The app doesn't quiz you every time — once it's confident, it
  surfaces a single card: *"I've learned this voice. I think Speaker B is
  Aman — correct?"* You confirm or correct, and it locks in.
- **"Whose voices?" prompt** — after each note: *Only me* / *Me + others*
  (count + optional names). Names you give become hints the matcher uses.
- **Smart tagging** — title, one-line summary, topic tags, and a meeting flag,
  generated automatically.
- **Instant entry** — double-tap the back of the phone (iOS Back Tap / Android
  Quick Tap) or a home/lock-screen widget jumps straight into a timed recording.
  See `WIDGETS_AND_GESTURES.md`.

## Architecture

```
 ┌──────────────┐   record/upload    ┌───────────────────────────┐
 │  Expo app    │ ─────────────────▶ │  Supabase                 │
 │ (iOS+Android)│  notes/assets      │  Postgres + pgvector      │
 │  mobile/     │ ◀───────────────── │  Storage (audio/media)    │
 └──────┬───────┘   transcript+      │  Edge fn: transcribe      │
        │            speaker cards   └────────────┬──────────────┘
        │ deep link personalaios://record         │ status='diarized'
        ▼                                          ▼
  Back Tap / Quick Tap / widget         ┌────────────────────────────┐
                                        │  voice-worker (Python)      │
   AssemblyAI  ◀── transcribe edge fn   │  ECAPA voiceprints +        │
   (diarization)                        │  smart speaker matching     │
                                        │  runs beside Personal-AI-OS │
                                        └────────────────────────────┘
```

| Folder | What |
|---|---|
| `mobile/` | Expo (React Native + TS) app — recording engine, screens, deep links |
| `supabase/migrations/` | Schema, pgvector, RLS, storage bucket, transcript/feed views, match RPC |
| `supabase/functions/transcribe/` | Edge function: AssemblyAI diarization → turn-by-turn segments + smart tags |
| `voice-worker/` | Python worker: voiceprints + self-evolving speaker identification |
| `WIDGETS_AND_GESTURES.md` | iOS/Android gesture + widget + always-on setup, with honest limits |
| `SETUP.md` | Exact step-by-step commands to stand it all up |

## Privacy
Strict per-user RLS on every table; audio lives in a **private** storage bucket
scoped to your user id. The Python worker uses the service-role key and runs on
**your own machine** alongside Personal AI OS — that key never ships to the phone.

See **SETUP.md** to deploy.
