# Build Session Transcript — Personal AI OS → Always-On Voice Assistant

> **On-device record.** Faithful log of the working session that produced this
> product direction. **User asks are reproduced faithfully (lightly cleaned from
> voice-to-text); assistant turns are summarised.** Important dialogue is in
> **bold**. Kept local per the project's data principle; export to the personal
> account (anchit.tandon@gmail.com) on request.
> Date: 2026-06-23 · Owner: Anchit Tandon

---

### 1. "Is this working and recording audio now?"
**Assistant (verified live):** No — service not running, no `.env`/`.venv`/`data/`, dashboard dead. **Fresh checkout, never set up on this Mac.** Laid out the setup path.

### 2. PR for the session
Created branch `chore/update-permission-allowlist`; **blocked on GitHub auth** (no `gh`, no SSH, no stored credential). Installed `gh`, ran device-login, **pushed + opened [PR #8]**. Vercel preview comment was just an automated deploy status — nothing to fix.

### 3. "Is it recording now?" (laptop switched on)
**Assistant (verified):** **No — powering on doesn't start it; autostart was never installed and there's no config.** Established the recurring rule: **always verify the live state before reporting.**

### 4. Cost / "it's a simple local task"
**Assistant:** Clarified **nothing here charges you** — mic + Whisper are local/free, Groq is free-tier, gcloud login is free. **Core listen+record is purely local.** Offered local-only vs. Google-sheet paths.

### 5. "Will it work on phone + laptop? For all users?"
**Assistant (honest):** **Recording = laptop only** (mobile OS blocks background mic). **Viewing = phone + laptop.** Currently **single-user**, no accounts. Phone view via the Sheet (live) or a hosted dashboard.

### 6. "Detect Windows vs Mac and run the right command"
**Built + verified:** `install_autostart.py` — **one command auto-detects the OS** (macOS LaunchAgent / Windows Startup / Linux systemd) and installs always-on launch.

### 7. "Fix it / do whatever you want" → got it recording
**Built + verified end-to-end, local-only:** installed Python 3.12 + audio libs + venv + deps; **mic captured live audio; Whisper transcribed real speech**; added `--no-sheets` local-only mode. **Recording → transcription proven working on this Mac, no Google, no cost.**

### 8. Google Sheet / credentials hunt
Found the LLM key in **Vercel** (Gemini — **dead on Workspace accounts**, `limit:0`). User: **"use the Cloud CLI / connectors."** Found the **Sheet ID via the Drive connector** ("AI Task Tracker"); confirmed it last ran on the **Windows** machine, **last entry May 9** (dead ~6 weeks). gcloud ADC shortcut **blocked by Google policy** ("provide your own client ID"). User pasted a **working Groq key** (verified). Remaining blocker: **`credentials.json`**.

### 9. Two work-streams
**Ask:** *"**Smartly divide into two parts — my own AI projects, and Vahdam-related work — two sub-sheets in the same sheet and two tabs in the dashboard.**"* Split rule: **D2C/Vahdam → Vahdam; random projects (resume, Jarvis) → My AI Projects.**
**Built + verified:** classifier replaces the old Vahdam-only gate; `workstream` threaded through prompts → extractor → model → DB; **two-tab dashboard** with live counts. Live Groq test passed.

### 10. Task accuracy & grouping
**Ask:** *"**No detail missed; each task grouped correctly — not five tasks that are really one, or vice versa.**"*
**Built + verified:** granularity rules (no over-split / no over-merge / dedupe / lose-no-detail). Test: a 3-step ask → **one task**; two-owner asks → **two tasks**; repeated mention → **not double-counted**.

### 11. The full autonomous vision
**Ask (verbatim essence):** **phone audio + Google Sheet view + hosted dashboard; no task ever missed; sheet auto-fills; don't depend on me to mark complete — verify it (Google Chat bot); send each person their tasks by mail + chat (from my account to me for now); deadline reminders with 1-click Yes/No, varied non-panicky styles; daily morning email of today's plan; during-day "on track?" check-ins updating remarks + day-wise status; a day-wise activity log (office + AI only); quick note/voice note → dashboard + sheet. "Smart reminder + notemaker product."**
**Assistant:** Mapped it into 3 layers; flagged the **hard dependencies** (credentials.json; an always-on **hosted backend** to receive replies; **phone background audio is impossible** → 1-tap voice note). Honest: **true zero-input completion detection is unreliable → realistic = proactive ask + 1-tap confirm.**

### 12. Activity log
**Built + verified:** `activity_log` table + auto-logging from the voice pipeline — **day-wise, workstream-tagged, office/AI-work only.** Round-trip verified.

### 13. "yes — reminder + daily plan"
**Built + verified:** `planner.py` engine — deadline parsing (ISO + natural language), proximity buckets, **escalating non-panicky reminders with per-task cooldown**, and a **daily plan grouped by workstream**; `ReminderWorker` + `DailyPlanWorker` wired into `main.py`; outbound email is **optional, no-ops without credentials**. Fixed a local-vs-UTC day bug (IST) and silenced the no-credentials path.

### 14. **Local-first principle**
**User:** *"**Whatever uses local functionalities and gives complete data transfer option only to the device it is run on is best.**"* Recorded as a standing principle.

### 15. **The voice-command hook + IP**
**Ask:** *"**Add a hook — listen particularly for instructions it's being given; complete transcription; complete data security, no online storage unless requested (e.g. a Google Doc); permission by audio 'yes' or touch before anything is used.**"* + *"**This idea requires a patent and copyright for business use.**"*
**Built + verified:** instruction-vs-ambient detector + intent classifier; **any off-device write is force-gated behind explicit consent**; wired into the pipeline (local notes act on-device; external = "awaiting consent", **no egress**). Wrote **`INVENTION_DISCLOSURE.md`** (attorney-ready, with honest limits — no software makes copying *impossible*; a patent makes it *legally enforceable*).

### 16. PRD + transcript
Wrote **`PRD.md`** (portable product brief + all asks with important parts in bold). This file is the on-device transcript.

### 17. **Account separation (IP hygiene)**
**User:** *"**After this I'll use only my personal account — this idea came from a task-tracker feature I was building, and I don't want my office-linked account involved, to avoid any allegations or conspiracies against me.**"*
**Assistant:** Recorded the decision — **use `anchit.tandon@gmail.com` only** for the startup product; keep it off the Vahdam account. Honest caveat: **account separation helps, but employment IP-assignment clauses can still apply — worth a quick word with an IP/employment attorney before business use.**

---

## Status snapshot
- **Built & verified (local, on-device):** recording, on-device transcription, workstream split, task grouping, activity log, reminder + daily-plan engine, two-tab dashboard, local-only mode, cross-platform autostart, voice-command hook (+ consent gate).
- **Pending external dependencies:** `credentials.json` (Sheet/email/Chat), a hosted backend (phone dashboard + interactive replies + consent channel), multi-user.
- **IP:** `INVENTION_DISCLOSURE.md` drafted; provisional filing via attorney is the real next step.
- **Account:** product to live on **anchit.tandon@gmail.com**.
