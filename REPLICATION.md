# REPLICATION.md — Personal-AI-OS

> Auto-generated replication baseline (2026-06-20). Lets a developer or AI agent clone this project to its current state. **Verify and enrich** the sections marked ⚠️ by reading the source — this baseline is extracted from package.json/README/structure only.

- **Last updated:** 2026-06-20 (auto-baseline)
- **Stack (detected):** Python
- **Part of:** Anchit's AI Hustle

---

## 1. Purpose
Purpose not captured in README/package.json — inspect source and update this line.

## 2. Current-state snapshot
- **Top-level structure:**
  - `ARCHITECTURE 2.md`
  - `ARCHITECTURE.md`
  - `CLAUDE 2.md`
  - `CLAUDE.md`
  - `CyberPortfolio.tsx`
  - `HOW_TO_RUN.md`
  - `README.md`
  - `START.bat`
  - `START.command`
  - `STATUS 2.md`
  - `STATUS.md`
  - `__pycache__/`
  - `_stt_check 2.py`
  - `_stt_check.py`
  - `ai/`
  - `chat/`
  - `config/`
  - `control_server.py`
  - `data/`
  - `database/`
  - `gmail/`
  - `logs/`
  - `main.py`
  - `meetings/`
  - `requirements.txt`
  - `scripts/`
  - `services/`
  - `sheets/`
  - `startup/`
  - `storage/`
  - `tasks 2.xlsx`
  - `tasks-corrupt-20260520-201256 2.xlsx`
  - `tasks-corrupt-20260520-201256.xlsx`
  - `tasks.xlsx`
  - `tasks.xlsx.corrupt 2.bak`
  - `tasks.xlsx.corrupt.bak`
  - `token.json`
  - `transcription/`
  - `utils/`
  - `venv/`
- ⚠️ Routes/pages/endpoints + what works now: inspect source and fill in.

## 3. Clone-to-exact-state runbook
```bash
# no package.json — check README for setup
```
**Scripts:**
- (no npm scripts found in package.json)

⚠️ Confirm the exact build/run/deploy sequence against README + CI config. "Replicated at the same level" = the app builds, runs, and all routes/features above work.

## 4. Environment variables
- `LLM_PROVIDER`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SHEET_TAB`
- `POLLING_INTERVAL`
- `GMAIL_QUERY_FILTER`
- `AUDIO_CHUNK_MINUTES`
- `AUDIO_SAMPLE_RATE`
- `AUDIO_INPUT_DEVICE`
- `ENABLE_MEETING_CAPTURE`
- `WHISPER_MODEL`
- `WHISPER_DEVICE`
- `WHISPER_COMPUTE_TYPE`
- `WHISPER_LANGUAGE`
- `DATABASE_PATH`
- `AUDIO_CHUNKS_DIR`
- `TRANSCRIPTS_DIR`
- `LOGS_DIR`
- `GOOGLE_CREDENTIALS_PATH`
- `GOOGLE_TOKEN_PATH`
- `EXPECTED_GOOGLE_ACCOUNT`
- `OAUTH_CHROME_PROFILE`
- `LOG_LEVEL`
- `DAILY_SUMMARY_HOUR`

## 5. Master prompt / Knowledge base
⚠️ If this is an AI/LLM/content app, document its master-prompt contract + domain knowledge here (model the structure on Vahdam-LifeCycle-OS/REPLICATION.md §4–5). Otherwise capture the core domain config a cloner must know.

## 6. Common pitfalls
⚠️ Fill in project-specific gotchas. General: never hardcode secrets (use env), keep deploy config in sync, develop from a non-iCloud git clone (iCloud corrupts .git).

## 7. Where to look next
- README and package.json scripts are the source of truth for setup.
- Cross-reference siblings in "Anchit's AI Hustle" for shared patterns.
