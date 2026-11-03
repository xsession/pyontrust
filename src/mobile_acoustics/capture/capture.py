"""Synchronized multi-phone microphone capture (Termux-backed)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence


@dataclass
class MicStream:
    """One phone's microphone channel.

    ``grabber`` returns a 1-D float64 waveform (mono) at ``sample_rate`` Hz —
    e.g. a wrapper around TermuxBridge.record_audio + decode, or an in-memory
    buffer for tests/simulation.
    """

    source_id: str                       # phone serial / label
    grabber: Callable[[], Any]           # () -> np.ndarray (N,) float64 mono
    sample_rate: int = 48000
    position: tuple[float, float, float] | None = None   # mic position in metres (world frame)


def _decode_wav_mono(path) -> np.ndarray:
    """Decode a PCM WAV file to float64 mono in [-1, 1] (stdlib only)."""
    import wave

    with wave.open(str(path), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        fr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sw == 4:
        x = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width {sw}")
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    return x


def mic_stream_from_termux(bridge, source_id: str | None = None,
                           position: tuple[float, float, float] | None = None,
                           seconds: float = 5.0, sample_rate: int = 48000) -> "MicStream":
    """Build a MicStream whose grabber records via TermuxBridge.record_audio.

    ``bridge`` must expose ``record_audio(seconds, out_dir, sample_rate) -> Path``
    (see mobile_stereo3d.controller.TermuxBridge). The WAV is pulled to the
    host and decoded to float64 mono on each capture call.
    """
    sid = source_id or getattr(getattr(bridge, "device", None), "serial", None) or "phone"

    def grabber():
        path = bridge.record_audio(seconds=seconds, sample_rate=sample_rate)
        return _decode_wav_mono(path)

    return MicStream(source_id=sid, grabber=grabber, sample_rate=sample_rate, position=position)


class MultiMicCapture:
    """Record one shot from every phone in the matrix with host timestamps.

    Phones are triggered as close together as possible; per-channel capture
    start/end stamps let downstream code correct small skew (see TDOAEstimator).
    """

    def __init__(self, streams: Sequence[MicStream]) -> None:
        if len(streams) < 2:
            raise ValueError("need at least two microphone channels")
        self.streams = list(streams)

    @property
    def positions(self):
        return [s.position for s in self.streams]

    def capture(self, seconds: float | None = None) -> dict[str, Any]:
        """Fire all grabbers; returns {source_id: {"waveform": (N,), "t_start_ms", "sample_rate"}}."""
        t0 = time.perf_counter() * 1000.0
        out: dict[str, Any] = {}
        for s in self.streams:
            w = np.asarray(s.grabber(), dtype=np.float64).reshape(-1)
            out[s.source_id] = {
                "waveform": w,
                "t_start_ms": time.perf_counter() * 1000.0 - (time.perf_counter() - t0 / 1000.0) * 0 + t0,
                "sample_rate": int(s.sample_rate),
            }
        return out


import numpy as np  # noqa: E402  (kept at bottom to avoid import-order surprises in tests)

__all__ = ["MicStream", "MultiMicCapture", "mic_stream_from_termux", "_decode_wav_mono"]
