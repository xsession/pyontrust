from __future__ import annotations

import numpy as np


def rfft_power_db(x: np.ndarray, *, bins: int, window: str = "hann") -> tuple[np.ndarray, np.ndarray]:
    """Return (freq_norm, power_db) for complex baseband.

    freq_norm is in [-0.5, 0.5) where 0 is DC.
    """
    x = x.astype(np.complex64, copy=False)
    if len(x) < bins:
        pad = np.zeros((bins,), dtype=np.complex64)
        pad[: len(x)] = x
        x = pad
    else:
        x = x[:bins]

    if window == "hann":
        w = np.hanning(bins).astype(np.float32)
    else:
        w = np.ones((bins,), dtype=np.float32)

    xw = x * w
    X = np.fft.fftshift(np.fft.fft(xw, n=bins))
    p = (np.abs(X) ** 2).astype(np.float32)
    p = p / max(1e-12, float(np.sum(w**2)))
    p_db = 10.0 * np.log10(np.maximum(p, 1e-20))
    f = (np.arange(bins, dtype=np.float32) / bins) - 0.5
    return f, p_db
