"""
End-to-end meeting pipeline.

Audio capture runs in one thread (`AudioCapture`) and pushes chunks into
a queue. A worker thread drains the queue and runs the transcription +
extraction pipeline via `MeetingService`. This separation keeps the
PortAudio callback path latency-tight, regardless of how slow Whisper or
Claude are on a given chunk.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from services import MeetingService
from transcription import AudioCapture, AudioChunk
from utils.logger import get_logger

logger = get_logger(__name__)


class _ChunkWorker(threading.Thread):
    def __init__(
        self,
        chunks: "queue.Queue[Optional[AudioChunk]]",
        service: MeetingService,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name="MeetingChunkWorker", daemon=True)
        self._chunks = chunks
        self._service = service
        self._stop = stop_event

    def run(self) -> None:  # pragma: no cover
        logger.info("MeetingChunkWorker started.")
        while True:
            try:
                chunk = self._chunks.get(timeout=1.0)
            except queue.Empty:
                if self._stop.is_set():
                    break
                continue

            if chunk is None:  # poison pill
                break
            try:
                self._service.process_chunk(chunk)
            except Exception:
                logger.exception("Failed to process meeting chunk.")
            finally:
                self._chunks.task_done()
        logger.info("MeetingChunkWorker stopped.")


class MeetingPipeline:
    """Wires up AudioCapture + worker + MeetingService."""

    def __init__(self, stop_event: threading.Event) -> None:
        self._stop = stop_event
        self._service = MeetingService()
        self._chunks: "queue.Queue[Optional[AudioChunk]]" = queue.Queue(maxsize=64)
        self._capture: Optional[AudioCapture] = None
        self._worker: Optional[_ChunkWorker] = None

    def start(self) -> None:
        self._capture = AudioCapture(self._on_chunk, self._stop)
        self._worker = _ChunkWorker(self._chunks, self._service, self._stop)
        self._capture.start()
        self._worker.start()
        logger.info("MeetingPipeline started.")

    def _on_chunk(self, chunk: AudioChunk) -> None:
        try:
            self._chunks.put(chunk, timeout=2.0)
        except queue.Full:
            logger.error(
                "Meeting chunk queue full — dropping chunk %d (consider a faster Whisper config).",
                chunk.chunk_index,
            )

    def shutdown(self, timeout: float = 30.0) -> None:
        # AudioCapture sees the stop event from main loop. We just wait for
        # the worker to drain and finalize.
        if self._capture is not None and self._capture.is_alive():
            self._capture.join(timeout=timeout)

        # Drain any remaining chunks.
        deadline = time.time() + timeout
        while not self._chunks.empty() and time.time() < deadline:
            time.sleep(0.5)

        # Send poison pill to worker.
        try:
            self._chunks.put_nowait(None)
        except queue.Full:
            pass

        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=timeout)

        # Finalize the session.
        if self._capture is not None:
            try:
                self._service.finalize_session(self._capture.session_id)
            except Exception:
                logger.exception("Could not finalize meeting session on shutdown.")
        logger.info("MeetingPipeline shutdown complete.")
