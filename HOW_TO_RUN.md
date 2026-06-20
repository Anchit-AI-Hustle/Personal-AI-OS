# ▶ How to run Personal AI OS

This is the "play button." It starts the engine that **listens (mic + Gmail +
Google Chat), extracts tasks with AI, and pushes them into your Google Sheet** —
and keeps it running so nothing is missed.

---

## The one-click way

**macOS:** double-click **`START.command`** in Finder.
**Windows:** double-click **`START.bat`**.

That opens **http://localhost:8800** — the control dashboard — and starts the
engine automatically. You'll see a green **ENGINE RUNNING** pill, your task
counts, the **unsynced backlog** number, and **Open Google Sheet** / **Open Task
Board** buttons.

> Keep that window open. Closing it stops the engine. To stop early, click
> **■ Stop** on the dashboard or close the window.

If a browser tab doesn't open on its own, just go to **http://localhost:8800**.

---

## What "the page" gives you

| On the dashboard | Meaning |
|---|---|
| **ENGINE RUNNING** (green, pulsing) | Listening + syncing right now |
| **Uptime** | How long it's been running this session |
| **Total tasks captured** | Rows in the local task DB |
| **Unsynced backlog** | Tasks not yet pushed to the Sheet. **Should sit at 0.** If it climbs and stays up, the Sheet sync is stuck — click **↻ Restart**. |
| **Auto-restarts** | How many times the supervisor revived the engine after a crash |
| **Start / Stop / Restart** | Manual control |

The supervisor restarts the engine automatically if it ever crashes (with
backoff), so a single fault can't silently stop task capture.

---

## First-time setup (only once)

If you've never run it on this machine:

```bash
# from the Personal-AI-OS folder
python -m venv .venv

# activate it
.venv\Scripts\Activate.ps1      # Windows PowerShell
source .venv/bin/activate        # macOS / Linux

pip install -r requirements.txt
```

Then make sure these exist in the folder:

1. **`.env`** — must contain at least `GROQ_API_KEY` (or `GEMINI_API_KEY`) and
   `GOOGLE_SHEET_ID`. For microphone listening, keep **`ENABLE_MEETING_CAPTURE=true`**.
2. **`credentials.json`** — your Google OAuth desktop client (Gmail + Sheets).
   The first run opens a browser to grant access and writes `token.json`.

After that, the one-click launcher is all you need.

---

## "Working all the time" (survives logout / reboot)

The launcher runs while its window is open. To have it **start by itself on
every boot/login** (Windows):

```powershell
# one-time, from the project folder in PowerShell
.\startup\install_task.ps1      # registers a Task Scheduler job (auto-restart x999)
.\startup\uninstall_task.ps1    # to remove it later
```

On macOS, add `START.command` to **System Settings → General → Login Items** so
it launches at login.

---

## Quick troubleshooting

- **Dashboard says "control server unreachable"** → the launcher window was
  closed or Python errored; re-run `START`. Check `logs/runner.log`.
- **Engine flips to "DOWN — restarting…" repeatedly** → open `logs/runner.log`;
  usually a missing key in `.env` or `credentials.json`, or a bad venv.
- **Unsynced backlog keeps growing** → Sheet/network issue; click **Restart**.
  The backlog drains once sync recovers (nothing is lost — it's stored locally
  first).
- **No mic tasks appearing** → confirm `ENABLE_MEETING_CAPTURE=true` in `.env`
  and that the mic input device is correct (`AUDIO_INPUT_DEVICE`).

---

*Advanced: run without the launcher with `python control_server.py`
(`--port 8800`, `--no-engine` to show the dashboard without starting the engine).*
