"""
Voiceprint extraction.

For each diarized speaker label in a note we concatenate that speaker's
audio turns and compute a single 192-dim ECAPA-TDNN embedding (SpeechBrain).
The embedding is L2-normalised so cosine similarity == dot product.

The ECAPA model is downloaded once and cached locally on first run.
ffmpeg must be on PATH (pydub uses it).
"""
from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass

import numpy as np

_CLASSIFIER = None  # lazy singleton


def _get_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is None:
        # imported lazily so the module can be imported without torch present
        from speechbrain.inference.speaker import EncoderClassifier
        _CLASSIFIER = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=os.path.join(tempfile.gettempdir(), "ecapa_voxceleb"),
            run_opts={"device": os.getenv("VOICEPRINT_DEVICE", "cpu")},
        )
    return _CLASSIFIER


@dataclass
class SpeakerTurns:
    label: str               # 'A','B',...
    spans_ms: list[tuple[int, int]]


def embed_speaker(audio_path: str, turns: SpeakerTurns,
                  min_ms: int = 1500) -> np.ndarray | None:
    """
    Concatenate the speaker's turns, resample to 16k mono, return a unit-norm
    192-d embedding. Returns None if there is too little usable audio.
    """
    import torch
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    clip = AudioSegment.silent(duration=0)
    for (start, end) in turns.spans_ms:
        if end <= start:
            continue
        clip += audio[start:end]

    if len(clip) < min_ms:
        return None

    clip = clip.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    buf = io.BytesIO()
    clip.export(buf, format="wav")
    buf.seek(0)

    import soundfile as sf
    wav, _sr = sf.read(buf, dtype="float32")
    signal = torch.tensor(wav).unsqueeze(0)  # [1, time]

    emb = _get_classifier().encode_batch(signal).squeeze().detach().cpu().numpy()
    norm = np.linalg.norm(emb)
    if norm == 0:
        return None
    return (emb / norm).astype(np.float32)


def to_pgvector(vec: np.ndarray) -> str:
    """Format a numpy vector as a pgvector literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec.tolist()) + "]"


def from_pgvector(val) -> np.ndarray | None:
    """Parse a pgvector value (string '[..]' or list) back to a numpy array."""
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return np.asarray(val, dtype=np.float32)
    s = str(val).strip().lstrip("[").rstrip("]")
    if not s:
        return None
    return np.asarray([float(x) for x in s.split(",")], dtype=np.float32)
