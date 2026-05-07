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


@dataclass(frozen=True)
class Settings:
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
