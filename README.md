# Personal AI OS

A local, always-on productivity layer for Windows. It watches your inbox
and your microphone, extracts the things you actually need to act on
with Claude, and pushes the resulting task list into a Google Sheet.

```
┌────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Gmail (OAuth)      │     │ Microphone       │     │                 │
│  └─ unread filter  │     │  └─ 2-min chunks │     │  Daily summary  │
└─────────┬──────────┘     └────────┬─────────┘     └────────┬────────┘
          │                         │                        │
          ▼                         ▼                        ▼
   ┌──────────────┐         ┌──────────────────┐    ┌──────────────────┐
   │ EmailService │         │ MeetingPipeline  │    │ DailySummary     │
   │  → Claude    │         │  → Faster-Whisper│    │  → Claude        │
   └──────┬───────┘         │  → Claude        │    └──────────────────┘
          │                 └────────┬─────────┘
          │                          │
          ▼                          ▼
              ┌─────────────────────────────────┐
              │  SQLite (data/personal_ai_os.db)│
              │  • processed_emails             │
              │  • transcript_chunks (FTS5)     │
              │  • extracted_tasks (deduped)    │
              │  • meeting_sessions             │
              │  • daily_summaries              │
              └────────────────┬────────────────┘
                               │
                               ▼
                     ┌────────────────────┐
                     │  Google Sheet      │
                     │  (Tasks tab)       │
                     └────────────────────┘
```

---

## 1. Prerequisites

- Windows 10 or 11
- Python 3.11 (3.10+ should work)
- A Google account with Gmail and access to a Google Sheet
- A Google Gemini API key (free tier is fine — get one at https://aistudio.google.com/apikey)

---

## 2. Install

```powershell
# Clone or open the project, then:
cd Personal-AI-OS

# Create + activate a virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Python deps
pip install -r requirements.txt
```

> The `faster-whisper` install pulls down `ctranslate2` and `onnxruntime`
> wheels (~250 MB). The first transcription will also download the
> Whisper model weights into the local HuggingFace cache.

---

## 3. Configure environment

Copy the example file and fill it in:

```powershell
Copy-Item .env.example .env
notepad .env
```

You must set at least:

| Key                  | What                                                |
|----------------------|-----------------------------------------------------|
| `GEMINI_API_KEY`     | from https://aistudio.google.com/apikey             |
| `GOOGLE_SHEET_ID`    | the part of the sheet URL between `/d/` and `/edit` |

Everything else has a sensible default — see `.env.example` for the
list (Gmail filter, polling interval, audio chunk length, Whisper
model, etc.).

---

## 4. Google Cloud setup (Gmail + Sheets)

You need ONE OAuth Desktop client; it covers both Gmail and Sheets.

1. Open https://console.cloud.google.com/ and create / pick a project.
2. **APIs & Services → Library** → enable:
   - **Gmail API**
   - **Google Sheets API**
3. **APIs & Services → OAuth consent screen** → set up a *External* app
   in *Testing* mode and add your own Google account as a test user.
   Required scopes (these will be requested at first run, you don't need
   to pre-approve them in the console for a Testing-mode app):
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify` (so we can mark messages read)
   - `https://www.googleapis.com/auth/spreadsheets`
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON. Save it next to `main.py` as `credentials.json`.

> If your file ends up named `credentials.json.json` (Windows + Chrome
> sometimes appends `.json` to a JSON file you saved), the loader will
> still find it — but it's cleaner to rename it.

5. **Create the destination Sheet:**
   open Google Drive → New → Google Sheets → copy the ID from the URL
   into `GOOGLE_SHEET_ID` in `.env`. The first run will auto-create the
   `Tasks` tab and write the header row.

---

## 5. Gemini API setup

1. Get an API key at https://aistudio.google.com/apikey (this is the
   AI Studio key — it's separate from the Gmail/Sheets OAuth client).
2. Paste it into `GEMINI_API_KEY` in `.env`.
3. The default model is `gemini-2.0-flash`. Free tier covers ~1500
   requests/day, plenty for a single user. Override with `GEMINI_MODEL`
   for `gemini-2.5-flash` or `gemini-2.5-pro` (paid).

---

## 6. Microphone permissions

On Windows 11:

> Settings → Privacy & security → Microphone

- Turn on **Microphone access**
- Turn on **Let apps access your microphone**
- Turn on **Let desktop apps access your microphone**

If the system runs but no chunks ever appear in `data/audio_chunks/`,
the most likely cause is that desktop-app mic access is OFF.

To list available mic devices and pick a specific one:

```powershell
.\.venv\Scripts\Activate.ps1
python -m sounddevice
```

Set `AUDIO_INPUT_DEVICE=<index or name substring>` in `.env`.

---

## 7. First run

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

What happens on the first run:

1. The DB is initialised at `data/personal_ai_os.db`.
2. A browser window pops up for Google OAuth — approve **both**
   Gmail and Sheets scopes. The token is saved to `token.json`.
3. The `Tasks` tab and header row are created in your Google Sheet
   if they're not already there.
4. Faster-Whisper downloads model weights (only once).
5. Workers start logging to `logs/personal_ai_os.log`.

Stop with `Ctrl+C`. Shutdown is graceful — pending sheet pushes are
flushed and the current meeting session is finalised.

---

## 8. CLI flags

```
python main.py --no-email      # disable Gmail polling
python main.py --no-meetings   # disable mic capture (e.g. on a server)
```

---

## 9. Run as a Windows Scheduled Task

So it starts at logon and keeps running while the screen is locked:

```powershell
# from an elevated or normal PowerShell, in the project root:
powershell -ExecutionPolicy Bypass -File startup\install_task.ps1
```

This registers a task called `PersonalAIOS` that:
- triggers at every logon for the current user
- restarts on failure (every minute, up to 999 times)
- has no execution time limit
- ignores battery state

To start it immediately without rebooting:

```powershell
Start-ScheduledTask -TaskName PersonalAIOS
```

Status / logs:

```powershell
Get-ScheduledTask -TaskName PersonalAIOS
Get-Content logs\runner.log -Tail 50
Get-Content logs\personal_ai_os.log -Tail 100 -Wait
```

Remove:

```powershell
powershell -ExecutionPolicy Bypass -File startup\uninstall_task.ps1
```

> **Locked screen behaviour:** because the task's logon type is
> `Interactive` and we don't pass `-RunLevel Highest`, it runs inside
> your normal user session — which means it keeps running while the
> screen is locked. It stops if you fully sign out.

---

## 10. Project layout

```
personal-ai-os/
├── main.py                    # entry point — boots all workers
├── requirements.txt
├── .env.example
├── credentials.json           # (you provide)
│
├── config/
│   └── settings.py            # typed config loaded from .env
│
├── utils/
│   ├── logger.py              # console + rotating file logging
│   └── retry.py               # tenacity-based retry wrapper
│
├── database/
│   ├── schema.sql             # SQLite schema (with FTS5 triggers)
│   ├── db.py                  # high-level DB API
│   └── models.py              # value objects + urgency normaliser
│
├── ai/
│   ├── claude_client.py       # Anthropic SDK wrapper + retries
│   ├── prompts.py             # system + user prompt builders
│   └── extractor.py           # JSON-aware extraction layer
│
├── gmail/
│   ├── auth.py                # shared Google OAuth (Gmail + Sheets)
│   ├── client.py              # list / fetch / mark-read
│   └── poller.py              # background polling thread
│
├── sheets/
│   ├── client.py              # Sheets v4 API + header bootstrap
│   └── sync.py                # batched flush worker
│
├── transcription/
│   ├── audio_capture.py       # sounddevice mic capture, 2-min chunks
│   └── whisper_engine.py      # Faster-Whisper wrapper
│
├── meetings/
│   └── processor.py           # capture → queue → transcribe → extract
│
├── services/
│   ├── email_service.py       # Gmail → Claude → tasks
│   ├── meeting_service.py     # Whisper → Claude → tasks
│   ├── task_service.py        # dedup-aware task persistence
│   └── daily_summary.py       # nightly briefing worker
│
├── storage/
│   └── file_store.py          # transcript .txt files on disk
│
├── startup/
│   ├── run.bat                # launcher Task Scheduler invokes
│   ├── install_task.ps1       # registers the scheduled task
│   └── uninstall_task.ps1
│
├── data/                      # (auto-created) SQLite DB + audio + transcripts
└── logs/                      # (auto-created) rotating log files
```

---

## 11. Google Sheet schema

The `Tasks` tab is created automatically with these columns:

| Column              | Source                                |
|---------------------|---------------------------------------|
| Timestamp           | when the task was extracted (local TZ)|
| Source Type         | `Email` / `Meeting`                   |
| Task                | imperative phrase from Claude         |
| Deadline            | parsed deadline if any                |
| Urgency             | `Low` / `Medium` / `High` / `Critical`|
| Sender/Speaker      | who asked / who owns it               |
| Summary             | 1–2 sentence context                  |
| Status              | `open` / `done` / `dropped`           |
| Source Reference ID | `<gmail-id>` or `<session>:<chunk>`   |

You can change Status manually in the sheet — the row number is stored
locally so future versions can sync the change back.

---

## 12. SQLite tables

- **processed_emails** — every Gmail message we've inspected (dedup gate)
- **meeting_sessions** — one row per recording session
- **transcript_chunks** — per-chunk transcript + summary + insights
- **transcript_search** — FTS5 mirror of transcript_chunks (auto-maintained)
- **extracted_tasks** — every task ever extracted (dedup hash on
  `source_type|source_ref_id|lower(task)` prevents re-pushing)
- **processing_logs** — operational events, useful when running headless
- **daily_summaries** — one row per day with the strategic briefing

Search transcripts manually:

```sql
SELECT session_id, chunk_index, snippet(transcript_search, 2, '[', ']', '...', 12) AS hit
FROM transcript_search
WHERE transcript_search MATCH 'pricing OR onboarding'
ORDER BY rank;
```

---

## 13. Troubleshooting

**OAuth browser opens but says "Access blocked".**
Your OAuth consent screen is in Testing mode but your account is not in
the test-users list. Add yourself under
*OAuth consent screen → Test users*.

**Gmail returns 403 insufficient scopes.**
You consented previously with a narrower scope set. Delete `token.json`
and re-run; the consent flow will request the full scope list.

**Sheets returns 404.**
Either `GOOGLE_SHEET_ID` is wrong, or the Google account that did the
OAuth doesn't have access to that sheet. Open the sheet manually as
the same account.

**No audio chunks appear.**
Verify *Settings → Privacy & security → Microphone* is on for desktop
apps. Run `python -m sounddevice` and confirm an input device exists.
Try setting `AUDIO_INPUT_DEVICE` to a specific index.

**Faster-Whisper crashes on load with `cuDNN` / `cuBLAS` errors.**
You probably set `WHISPER_DEVICE=cuda` without the matching CUDA
runtime. Set it back to `cpu` or install the required CUDA libs.

**Gemini 429 / quota errors.**
The client retries with exponential backoff up to 4 times. The free
tier on `gemini-2.0-flash` is ~1500 requests/day — if you blow past
that, raise `POLLING_INTERVAL` or upgrade the model in `GEMINI_MODEL`.

**`credentials.json` not found.**
The loader also accepts `credentials.json.json` (a common Windows
double-extension). Either rename your file to `credentials.json` or
update `GOOGLE_CREDENTIALS_PATH` in `.env`.

---

## 14. License & data

Everything stays on your machine. Audio, transcripts, and the SQLite
database live under `data/` and are gitignored. Google API tokens are
stored in `token.json` (also gitignored). The only outbound calls are
to:
- Google APIs (Gmail + Sheets)
- Google Gemini API
- HuggingFace (Whisper model download, first run only)
