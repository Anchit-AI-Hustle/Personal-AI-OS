"""
Faster-Whisper engine wrapper.

The model is loaded lazily — first transcription pays the cost. We use
`int8` on CPU by default which keeps RAM under ~1GB for the `base`
model and runs fine on laptop hardware.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str]
    language_probability: Optional[float]
    duration: Optional[float]
    segments: list[dict] = field(default_factory=list)


class WhisperEngine:
    def __init__(
        self,
        model: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        self._model_name = model or settings.whisper_model
        self._device = device or settings.whisper_device
        self._compute_type = compute_type or settings.whisper_compute_type
        self._language = language or settings.whisper_language  # None = auto-detect
        self._model: Optional[WhisperModel] = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> WhisperModel:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                logger.info(
                    "Loading Faster-Whisper model=%s device=%s compute_type=%s",
                    self._model_name,
                    self._device,
                    self._compute_type,
                )
                self._model = WhisperModel(
                    self._model_name,
                    device=self._device,
                    compute_type=self._compute_type,
                )
        return self._model

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        model = self._ensure_loaded()

        # Hindi-English code-switched audio works best with `language=None`
        # (auto-detect per chunk). Translation is OFF — we keep the original
        # language so Claude can read both Hindi and English.
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=self._language,  # None lets Whisper detect
            task="transcribe",
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        text_parts: list[str] = []
        seg_dicts: list[dict] = []
        for seg in segments_iter:
            text_parts.append(seg.text.strip())
            seg_dicts.append(
                {
                    "start": float(seg.start) if seg.start is not None else None,
                    "end": float(seg.end) if seg.end is not None else None,
                    "text": seg.text.strip(),
                }
            )

        full_text = " ".join(p for p in text_parts if p).strip()
        return TranscriptionResult(
            text=full_text,
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            duration=getattr(info, "duration", None),
            segments=seg_dicts,
        )


_singleton: Optional[WhisperEngine] = None
_lock = threading.Lock()


def get_whisper_engine() -> WhisperEngine:
    global _singleton
    if _singleton is None:
        with _lock:
            if _singleton is None:
                _singleton = WhisperEngine()
    return _singleton
