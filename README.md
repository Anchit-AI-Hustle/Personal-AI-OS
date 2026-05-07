# Personal AI Email Intelligence

## Overview
This project monitors a Gmail inbox, extracts actionable tasks from incoming emails using Anthropic Claude, and syncs the extracted information to a Google Sheet. Processed email IDs are stored in a local SQLite database to avoid duplicate processing. The system includes robust logging, retry handling, and a modular architecture.

## Features
- Poll Gmail every **5 minutes** for new unread messages.
- Identify actionable emails and extract:
  - **Task** description
  - **Deadline**
  - **Urgency** (high/medium/low)
  - **Sender** email address
  - **Follow‑ups** (optional list)
- Append extracted rows to a Google Sheet.
- Persist processed email IDs in SQLite to prevent duplicates.
- Structured logging for debugging and monitoring.
- Automatic retries with exponential back‑off.
- Fully Windows‑compatible and written in pure Python.

## Project Structure
```
personal-ai-os/
│
├─ main.py                 # entry point & scheduler
├─ requirements.txt        # Python dependencies
├─ .env.example            # example environment file
├─ README.md                # this file
│
├─ config/                 # configuration package (optional)
│   └─ __init__.py
│
├─ utils/                  # helper utilities
│   ├─ logger.py           # centralized logger setup
│   └─ retry.py            # retry decorator using tenacity
│
├─ services/               # core service modules
│   ├─ gmail_service.py    # Gmail API integration
│   ├─ sheets_service.py   # Google Sheets API integration
│   └─ task_extractor.py   # Claude LLM extraction logic
│
├─ database/               # SQLite persistence layer
│   └─ db.py               # simple wrapper around SQLite
│
└─ credentials.json        # Google Service‑Account credentials (must be placed manually)
```

## Prerequisites
1. **Python 3.10+** installed and added to `PATH`.
2. A **Google Cloud project** with the following APIs enabled:
   - Gmail API
   - Google Sheets API
3. **OAuth client credentials** for Gmail (saved as `token.json` after the first run) – see *Authentication* below.
4. A **Google Service‑Account** JSON file (`credentials.json`) with access to the target spreadsheet. Place this file in the project root.
5. **Anthropic Claude API key** – sign up at https://console.anthropic.com and obtain a key.

## Installation
```powershell
# Clone the repo (if not already cloned)
git clone https://github.com/yourusername/personal-ai-os.git
cd personal-ai-os

# (Optional) create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Configuration
Create a copy of `.env.example` named `.env` and fill in the values:
```
# Google Sheet ID (the part after /d/ in the Sheet URL)
GOOGLE_SHEET_ID=your_google_sheet_id

# Path to the service‑account credentials (relative to project root)
GOOGLE_CREDENTIALS=./credentials.json

# Anthropic API key
ANTHROPIC_API_KEY=sk-ant-....

# Optional: Gmail OAuth token path (default token.json)
GMAIL_TOKEN_PATH=./token.json
```

## First‑time Gmail Authentication
Run the script once; it will open a browser window to grant the required Gmail scopes. After granting access, a `token.json` file will be created automatically.
```powershell
python main.py --setup-gmail
```

## Running the Application
```powershell
python main.py
```
The scheduler will start and poll the inbox every 5 minutes. Logs are written to the console and to `email_intelligence.log` in the project root.

## Troubleshooting
- **Missing credentials** – Ensure `credentials.json` is present and the service account has *Editor* access to the target spreadsheet.
- **Authentication errors** – Delete `token.json` and rerun `python main.py --setup-gmail` to re‑authenticate.
- **Rate limiting** – The retry logic uses exponential back‑off; if you still hit limits, consider reducing the polling frequency.

## License
MIT License – feel free to modify and use commercially.
