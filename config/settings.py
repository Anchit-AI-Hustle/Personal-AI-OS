<<<<<<< HEAD
"""
Centralised configuration loaded from environment variables (.env).

Importing `settings` validates required keys at startup so the rest of the
codebase can rely on the values being present.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env once, the first time this module is imported.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key, default)
    if val is None:
        return None
    val = val.strip()
    return val if val != "" else None


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {key} must be an int, got {raw!r}") from exc


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def _resolve_path(raw: Optional[str], default_relative: str) -> Path:
    if raw is None:
        raw = default_relative
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()
=======
"""Centralized configuration loaded from environment variables / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return val
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5


@dataclass(frozen=True)
class Settings:
<<<<<<< HEAD
    # LLM (Google Gemini)
    llm_api_key: str
    llm_model: str

    # Google Sheets
    google_sheet_id: str
    google_sheet_tab: str

    # Gmail
    polling_interval: int
    gmail_query_filter: str

    # Audio
    audio_chunk_minutes: int
    audio_sample_rate: int
    audio_input_device: Optional[str]
    enable_meeting_capture: bool

    # Whisper
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    whisper_language: Optional[str]

    # Paths
    project_root: Path
    database_path: Path
    audio_chunks_dir: Path
    transcripts_dir: Path
    logs_dir: Path
    google_credentials_path: Path
    google_token_path: Path

    # Logging
    log_level: str

    # Daily summary
    daily_summary_hour: int

    # OAuth scopes
    oauth_scopes: tuple = field(
        default=(
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/spreadsheets",
        )
    )

    def ensure_directories(self) -> None:
        for p in (
            self.audio_chunks_dir,
            self.transcripts_dir,
            self.logs_dir,
            self.database_path.parent,
        ):
            p.mkdir(parents=True, exist_ok=True)


def _load() -> Settings:
    api_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Copy .env.example to .env and fill it in. "
            "Get a key at https://aistudio.google.com/apikey"
        )

    sheet_id = _env("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is missing in .env")
    # Tolerate users pasting the chunk after `/d/` from the sheet URL.
    if sheet_id.startswith("d/"):
        sheet_id = sheet_id[2:]

    # Some users save the file as `credentials.json.json` by accident — handle that.
    creds_path_raw = _env("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    creds_path = _resolve_path(creds_path_raw, "./credentials.json")
    if not creds_path.exists():
        legacy = creds_path.with_suffix(creds_path.suffix + ".json")
        if legacy.exists():
            creds_path = legacy

    return Settings(
        llm_api_key=api_key,
        llm_model=_env("GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash",
        google_sheet_id=sheet_id,
        google_sheet_tab=_env("GOOGLE_SHEET_TAB", "Tasks") or "Tasks",
        polling_interval=_env_int("POLLING_INTERVAL", 300),
        gmail_query_filter=_env(
            "GMAIL_QUERY_FILTER", "is:unread newer_than:2d"
        ) or "is:unread newer_than:2d",
        audio_chunk_minutes=_env_int("AUDIO_CHUNK_MINUTES", 2),
        audio_sample_rate=_env_int("AUDIO_SAMPLE_RATE", 16000),
        audio_input_device=_env("AUDIO_INPUT_DEVICE"),
        enable_meeting_capture=_env_bool("ENABLE_MEETING_CAPTURE", True),
        whisper_model=_env("WHISPER_MODEL", "base") or "base",
        whisper_device=_env("WHISPER_DEVICE", "cpu") or "cpu",
        whisper_compute_type=_env("WHISPER_COMPUTE_TYPE", "int8") or "int8",
        whisper_language=_env("WHISPER_LANGUAGE"),
        project_root=PROJECT_ROOT,
        database_path=_resolve_path(_env("DATABASE_PATH"), "./data/personal_ai_os.db"),
        audio_chunks_dir=_resolve_path(_env("AUDIO_CHUNKS_DIR"), "./data/audio_chunks"),
        transcripts_dir=_resolve_path(_env("TRANSCRIPTS_DIR"), "./data/transcripts"),
        logs_dir=_resolve_path(_env("LOGS_DIR"), "./logs"),
        google_credentials_path=creds_path,
        google_token_path=_resolve_path(_env("GOOGLE_TOKEN_PATH"), "./token.json"),
        log_level=(_env("LOG_LEVEL", "INFO") or "INFO").upper(),
        daily_summary_hour=_env_int("DAILY_SUMMARY_HOUR", 21),
    )


settings = _load()
settings.ensure_directories()
=======
    google_sheet_id: str
    google_sheet_tab: str
    google_credentials_path: Path

    gmail_oauth_client_path: Path
    gmail_token_path: Path
    gmail_query: str
    gmail_max_results: int

    anthropic_api_key: str
    anthropic_model: str

    poll_interval_minutes: int

    sqlite_path: Path

    log_level: str
    log_file: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    sqlite_path = _resolve(os.getenv("SQLITE_PATH", "./data/email_intel.db"))
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    log_file = _resolve(os.getenv("LOG_FILE", "./email_intelligence.log"))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        google_sheet_id=_require("GOOGLE_SHEET_ID"),
        google_sheet_tab=os.getenv("GOOGLE_SHEET_TAB", "Tasks"),
        google_credentials_path=_resolve(os.getenv("GOOGLE_CREDENTIALS", "./credentials.json")),
        gmail_oauth_client_path=_resolve(os.getenv("GMAIL_OAUTH_CLIENT", "./client_secret.json")),
        gmail_token_path=_resolve(os.getenv("GMAIL_TOKEN_PATH", "./token.json")),
        gmail_query=os.getenv("GMAIL_QUERY", "is:unread in:inbox newer_than:1d"),
        gmail_max_results=int(os.getenv("GMAIL_MAX_RESULTS", "25")),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5"),
        poll_interval_minutes=int(os.getenv("POLL_INTERVAL_MINUTES", "5")),
        sqlite_path=sqlite_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_file=log_file,
    )
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5
