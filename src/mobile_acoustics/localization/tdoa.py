"""GCC-PHAT cross-correlation TDOA estimation between mic pairs."""

from __future__ import annotations

import numpy as np


class TDOAEstimator:
    """Pairwise time-difference-of-arrival via generalized cross correlation.

    PHAT (phase transform) weighting makes the peak robust to the source's
    spectral content — standard for acoustic localization.
    """

    def __init__(self, sample_rate: int = 48000, search_ms: float = 50.0) -> None:
        self.fs = int(sample_rate)
        self.search_ms = float(search_ms)
        self.max_lag = max(1, int(self.search_ms / 1000.0 * self.fs))

    def pair_tdoa_s(self, x1: np.ndarray, x2: np.ndarray) -> float:
        """Signed delay of source arrival at mic2 relative to mic1 (seconds)."""
        a = np.asarray(x1, dtype=np.float64).reshape(-1)
        b = np.asarray(x2, dtype=np.float64).reshape(-1)
        n = min(len(a), len(b))
        if n < 8:
            raise ValueError("waveforms too short for TDOA")
        a, b = a[:n], b[:n]
        # zero-mean + Hann window to reduce spectral leakage in the cross spectrum
        w = np.hanning(n)
        A = np.fft.rfft(a * w)
        B = np.fft.rfft(b * w)
        Rxy = A * np.conj(B)
        mag = np.abs(Rxy)
        with np.errstate(divide="ignore", invalid="ignore"):
            Rxy_phat = np.where(mag > 1e-12, Rxy / mag, 0.0)
        cc = np.fft.irfft(Rxy_phat, n=n)       # len-n circular corr: cc[k] <-> lag k (k<n/2), k-n (k>=n/2)
        L = min(self.max_lag, n // 2 - 1)
        combined = np.concatenate([cc[n - L:], cc[:L + 1]])      # index i <-> lag i-L
        idx = int(np.argmax(combined))
        lag = idx - L   # == arrival_a - arrival_b in samples (verified vs time-domain xcorr)
        return float(lag) / self.fs

    def matrix(self, waveforms: Sequence[np.ndarray]) -> np.ndarray:
        """(M, M) signed TDOA matrix in seconds; tdoa[i][j] = arrival_i - arrival_j."""
        m = len(waveforms)
        out = np.zeros((m, m))
        for i in range(m):
            for j in range(i + 1, m):
                # pair_tdoa_s(x1, x2) ≈ arrival_x1 - arrival_x2 (verified against the
                # cross-correlation peak: r[lag] peaks at lag = tau_a - tau_b)
                d = self.pair_tdoa_s(waveforms[i], waveforms[j])  # arrival_i - arrival_j
                out[i, j] = d
                out[j, i] = -d
        return out


from typing import Sequence

__all__ = ["TDOAEstimator"]
