<<<<<<< HEAD
"""
Logging configuration.

Logs to both stdout and a daily-rotating file in `logs/`.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from config import settings

_CONFIGURED = False
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: Optional[str] = None) -> None:
    """Configure root logger. Safe to call multiple times."""
=======
"""Centralized logging configuration. Console + rotating file handler."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    """Configure the root logger once. Idempotent."""
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5
    global _CONFIGURED
    if _CONFIGURED:
        return

<<<<<<< HEAD
    log_level = (level or settings.log_level).upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Wipe any defaults set by libraries.
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file
    log_path: Path = settings.logs_dir / "personal_ai_os.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path, when="midnight", backupCount=14, encoding="utf-8"
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Tame chatty deps.
    for noisy in ("googleapiclient.discovery_cache", "googleapiclient.discovery", "urllib3", "httpx"):
=======
    s = get_settings()
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(s.log_level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        s.log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Quiet noisy third-party loggers.
    for noisy in ("googleapiclient", "google.auth", "urllib3", "httpx"):
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
<<<<<<< HEAD
    if not _CONFIGURED:
        setup_logging()
=======
    setup_logging()
>>>>>>> 7daead1c75c5ad9cf7f78d23d6ae58b1e8a54bc5
    return logging.getLogger(name)
