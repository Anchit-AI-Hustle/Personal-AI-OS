"""Reusable retry decorator with exponential back-off."""
from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

_log = logging.getLogger("retry")


def with_retry(
    *,
    attempts: int = 5,
    min_wait: float = 2.0,
    max_wait: float = 60.0,
    exceptions: tuple = (Exception,),
):
    """Decorator: retry the wrapped callable with exponential back-off.

    Defaults are tuned for transient network / API failures.
    """
    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(_log, logging.WARNING),
    )
