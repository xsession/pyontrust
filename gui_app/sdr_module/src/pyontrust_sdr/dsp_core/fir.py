from __future__ import annotations

import numpy as np


def design_lowpass(*, cutoff_hz: float, sample_rate_hz: float, taps: int = 101) -> np.ndarray:
    # windowed-sinc (Hann)
    taps = int(taps)
    if taps % 2 == 0:
        taps += 1
    fc = float(cutoff_hz) / float(sample_rate_hz)
    n = np.arange(taps, dtype=np.float32) - (taps - 1) / 2.0
    h = 2.0 * fc * np.sinc(2.0 * fc * n)
    w = np.hanning(taps).astype(np.float32)
    h = (h * w).astype(np.float32)
    h /= max(1e-12, float(np.sum(h)))
    return h.astype(np.float32)


def fir_filter(x: np.ndarray, h: np.ndarray, *, zi: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Streaming FIR; returns (y, zf)."""
    x = x.astype(np.complex64, copy=False)
    h = h.astype(np.float32, copy=False)
    if zi is None:
        zi = np.zeros((len(h) - 1,), dtype=np.complex64)
    xpad = np.concatenate([zi, x])
    y = np.convolve(xpad, h.astype(np.complex64), mode="valid").astype(np.complex64)
    zf = xpad[-(len(h) - 1) :].astype(np.complex64, copy=False)
    return y, zf
