"""
Microphone capture.

A background thread continuously reads frames from the default input
device using `sounddevice`. Every `AUDIO_CHUNK_MINUTES` minutes the
accumulated audio is flushed to a WAV file and handed to a callback.

Silence handling:
  Whisper hallucinates phrases like "Thank you" repeatedly when fed
  pure silence (a known training-data artifact). To prevent dead-mic
  output from polluting the DB:

    1. On startup, a 1-second probe records from the configured input
       device. If peak amplitude is effectively zero, we log a loud
       warning so the user knows their mic is muted / privacy-blocked
       BEFORE chunks start accumulating with garbage transcripts.

    2. Per chunk, if the peak amplitude is below `_SILENCE_PEAK_THRESHOLD`,
       we still write the WAV (for forensic replay) but mark the chunk
       as "silent" so the downstream pipeline can skip transcription
       entirely.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


# Below this peak amplitude (float32 in [-1, 1]) we treat the chunk as
# silence. 0.005 is conservative: normal speech 30cm from a laptop mic
# peaks around 0.1–0.5; pure noise floor is < 0.001; muted-mic digital
# silence is exactly 0.0.
_SILENCE_PEAK_THRESHOLD = 0.005


@dataclass
class AudioChunk:
    session_id: str
    chunk_index: int
    started_at: str       # ISO 8601 UTC
    ended_at: str         # ISO 8601 UTC
    sample_rate: int
    audio_path: Path
    duration_seconds: float
    is_silent: bool = False    # peak amplitude below _SILENCE_PEAK_THRESHOLD
    peak_amplitude: float = 0.0


OnChunk = Callable[[AudioChunk], None]


def _resolve_input_device(raw: Optional[str]):
    if raw is None or raw.strip() == "":
        return None  # default device
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    return raw  # device name substring


class AudioCapture(threading.Thread):
    """
    Continuously records mic audio and emits a chunk every N minutes.
    Designed to fail soft — if no microphone is available, the thread
    logs a warning and exits cleanly.
    """

    def __init__(
        self,
        on_chunk: OnChunk,
        stop_event: threading.Event,
        *,
        chunk_minutes: Optional[int] = None,
        sample_rate: Optional[int] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(name="AudioCapture", daemon=True)
        self._on_chunk = on_chunk
        self._stop = stop_event
        self._chunk_seconds = (chunk_minutes or settings.audio_chunk_minutes) * 60
        self._sample_rate = sample_rate or settings.audio_sample_rate
        self._output_dir = output_dir or settings.audio_chunks_dir
        self._device = _resolve_input_device(settings.audio_input_device)
        self._block_seconds = 0.5
        self._channels = 1

        self.session_id = datetime.now(timezone.utc).strftime("session-%Y%m%dT%H%M%SZ")
        self._chunk_index = 0
        self._frames_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2048)

    # --- public --------------------------------------------------------------

    def run(self) -> None:  # pragma: no cover
        """
        Outer supervisor loop: as long as the stop event is unset, keep
        the recorder alive. If the device throws (USB mic unplugged,
        Windows audio service hiccup, sample-rate mismatch), back off
        and re-open. The chunk index keeps incrementing across retries
        so file numbering stays unique within a session.
        """
        if not settings.enable_meeting_capture:
            logger.info("Meeting capture disabled by config — AudioCapture exiting.")
            return

        # Startup health check: confirm the configured input device is
        # actually producing signal. Loudly warns on a mute/privacy
        # block so the user fixes it before chunks fill with garbage.
        self._probe_mic_health()

        backoff = 2.0
        max_backoff = 60.0

        while not self._stop.is_set():
            try:
                self._record_loop()
                # Clean exit (stop event) — done.
                return
            except sd.PortAudioError as exc:
                logger.warning(
                    "Audio device error: %s. Retrying in %.0fs...", exc, backoff
                )
            except Exception:
                logger.exception(
                    "AudioCapture loop crashed. Retrying in %.0fs...", backoff
                )

            # Drain any frames that piled up while the stream was broken
            # so we don't write a chunk full of stale buffered audio.
            self._drain_queue()

            # Backoff with cap, sleeping in 1s steps so shutdown is responsive.
            slept = 0.0
            while slept < backoff and not self._stop.is_set():
                time.sleep(1.0)
                slept += 1.0
            backoff = min(backoff * 2, max_backoff)

        logger.info("AudioCapture supervisor exiting.")

    def _drain_queue(self) -> None:
        try:
            while True:
                self._frames_queue.get_nowait()
        except queue.Empty:
            pass

    def _probe_mic_health(self) -> None:
        """
        Record 1 second from the configured device and measure peak
        amplitude. If it's effectively zero, log a HUGE warning — this
        almost always means the mic is hardware-muted, blocked by
        Windows privacy settings, or the wrong device is selected.

        Never raises — failure here is non-fatal; the main record loop
        will start anyway and Whisper will tell us nothing useful but
        the process keeps running.
        """
        try:
            data = sd.rec(
                int(self._sample_rate * 1.0),
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=self._device,
            )
            sd.wait()
            peak = float(np.max(np.abs(data))) if data.size else 0.0
        except Exception as exc:
            logger.warning("Mic health probe failed: %s", exc)
            return

        if peak < _SILENCE_PEAK_THRESHOLD:
            logger.error(
                "==================================================================\n"
                "  MIC HEALTH WARNING — input device %r produced ZERO signal.\n"
                "  Peak amplitude over 1s probe: %.6f (silence floor).\n"
                "\n"
                "  Whisper hallucinates 'Thank you' repeatedly on silent input,\n"
                "  filling the DB with garbage transcripts. Likely causes:\n"
                "    * Windows mic privacy blocking this app\n"
                "        (Settings -> Privacy & security -> Microphone)\n"
                "    * Hardware mute key pressed (often F4 on Dell/Lenovo)\n"
                "    * Wrong input device selected — check available devices and\n"
                "      set AUDIO_INPUT_DEVICE in .env to the correct index/name\n"
                "    * Bluetooth headset disconnected, falling back to silent input\n"
                "\n"
                "  Audio chunks WILL still be recorded but flagged as silent and\n"
                "  skipped by the transcription pipeline until you fix this.\n"
                "==================================================================",
                self._device if self._device is not None else "<system default>",
                peak,
            )
        else:
            logger.info(
                "Mic health probe OK: device=%r peak=%.4f over 1s.",
                self._device if self._device is not None else "<system default>",
                peak,
            )

    # --- internals -----------------------------------------------------------

    def _callback(self, indata, frames, time_info, status):  # pragma: no cover
        # Called from PortAudio's thread — keep it tiny.
        if status:
            logger.debug("Audio status: %s", status)
        try:
            # `indata` is float32 in [-1, 1]; copy because sounddevice reuses the buffer.
            self._frames_queue.put_nowait(indata.copy())
        except queue.Full:
            # Drop the frame — better than blocking the audio callback.
            logger.warning("Audio frame queue full; dropping a frame.")

    def _record_loop(self) -> None:
        logger.info(
            "AudioCapture starting (session=%s, chunk=%ss, sr=%s, device=%r)",
            self.session_id,
            self._chunk_seconds,
            self._sample_rate,
            self._device,
        )

        blocksize = int(self._sample_rate * self._block_seconds)
        chunk_started_at = datetime.now(timezone.utc)
        buffer: list[np.ndarray] = []

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            blocksize=blocksize,
            device=self._device,
            callback=self._callback,
        ):
            while not self._stop.is_set():
                try:
                    block = self._frames_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                buffer.append(block)
                elapsed = (datetime.now(timezone.utc) - chunk_started_at).total_seconds()
                if elapsed >= self._chunk_seconds:
                    self._flush_chunk(buffer, chunk_started_at)
                    buffer = []
                    chunk_started_at = datetime.now(timezone.utc)

            # Final partial chunk on shutdown.
            if buffer:
                self._flush_chunk(buffer, chunk_started_at)

        logger.info("AudioCapture stopped.")

    def _flush_chunk(self, buffer: list[np.ndarray], started_at: datetime) -> None:
        ended_at = datetime.now(timezone.utc)
        if not buffer:
            return

        audio = np.concatenate(buffer, axis=0)
        if audio.size == 0:
            return

        # Mono float32 — mixdown if multichannel.
        if audio.ndim == 2 and audio.shape[1] > 1:
            audio = audio.mean(axis=1, keepdims=True)

        duration = audio.shape[0] / self._sample_rate
        idx = self._chunk_index
        self._chunk_index += 1

        # Peak amplitude — used by the consumer (meeting_service) to
        # decide whether to skip transcription on a silent chunk.
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        is_silent = peak < _SILENCE_PEAK_THRESHOLD

        filename = f"{self.session_id}_chunk_{idx:04d}.wav"
        path = self._output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            sf.write(str(path), audio, self._sample_rate, subtype="PCM_16")
        except Exception:
            logger.exception("Failed to persist audio chunk %s", path)
            return

        if is_silent:
            logger.info(
                "Flushed SILENT audio chunk %d (%.1fs, peak=%.5f) -> %s "
                "[will be skipped by transcription]",
                idx, duration, peak, path.name,
            )
        else:
            logger.info(
                "Flushed audio chunk %d (%.1fs, peak=%.3f) -> %s",
                idx, duration, peak, path.name,
            )

        chunk = AudioChunk(
            session_id=self.session_id,
            chunk_index=idx,
            started_at=started_at.isoformat(),
            ended_at=ended_at.isoformat(),
            sample_rate=self._sample_rate,
            audio_path=path,
            duration_seconds=duration,
            is_silent=is_silent,
            peak_amplitude=peak,
        )
        try:
            self._on_chunk(chunk)
        except Exception:
            logger.exception("on_chunk callback crashed for %s", path.name)
