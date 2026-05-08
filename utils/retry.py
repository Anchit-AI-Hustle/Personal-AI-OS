"""
Retry helper built on tenacity.

We expose a single function `retry_call` so call sites stay readable; the
underlying tenacity primitives are still available for advanced use.
"""
from __future__ import annotations

from typing import Callable, TypeVar

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .logger import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


def retry_call(
    fn: Callable[..., T],
    *args,
    attempts: int = 5,
    base: float = 1.0,
    max_wait: float = 60.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> T:
    """
    Run `fn(*args, **kwargs)` with exponential backoff.

    The retry stops after `attempts` failed tries. Sleeps grow as
    base, base*2, base*4, ... capped at `max_wait`.
    """
    retrying = Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=base, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        reraise=True,
        before_sleep=before_sleep_log(logger, 30),  # WARNING
    )
    for attempt in retrying:
        with attempt:
            return fn(*args, **kwargs)
    # Unreachable — `reraise=True` ensures we either return or raise above.
    raise RuntimeError("retry_call exited without producing a value")
