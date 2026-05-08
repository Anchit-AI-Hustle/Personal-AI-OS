"""
Thin wrapper around the Google Gemini API.

Uses the modern `google-genai` SDK and asks Gemini to return
`application/json` directly so the extractor can parse without dealing
with markdown fences.
"""
from __future__ import annotations

import threading
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from config import settings
from utils.logger import get_logger
from utils.retry import retry_call

logger = get_logger(__name__)

# Errors worth retrying — transient network / 5xx / rate limits.
# `APIError` is the parent class for ClientError + ServerError + others.
_RETRYABLE: tuple[type[BaseException], ...] = (
    genai_errors.APIError,
    TimeoutError,
    ConnectionError,
)


class GeminiClient:
    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.llm_model
        self._client = genai.Client(api_key=settings.llm_api_key)
        logger.info("Gemini client initialised (model=%s)", self.model)

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> str:
        """Single-turn JSON completion. Returns the response text."""

        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )

        def _call() -> str:
            response = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config=config,
            )
            text = (response.text or "").strip()
            if not text:
                # Gemini sometimes returns empty when the prompt is too restrictive
                # or hits a safety filter — surface that as an error so retry kicks in.
                raise RuntimeError("Gemini returned empty response")
            return text

        return retry_call(_call, attempts=4, base=2.0, max_wait=30.0, exceptions=_RETRYABLE)


_singleton: Optional[GeminiClient] = None
_lock = threading.Lock()


def get_llm_client() -> GeminiClient:
    global _singleton
    if _singleton is None:
        with _lock:
            if _singleton is None:
                _singleton = GeminiClient()
    return _singleton
