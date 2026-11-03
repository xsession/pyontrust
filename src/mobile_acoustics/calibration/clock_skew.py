"""Per-phone clock-skew calibration with a shared beep.

Each phone's internal clock drifts relative to the others, so raw arrival
times carry an unknown per-channel offset:  A_i = T_emit + d_i/c + skew_i.
Play one short beep (e.g. from the reference phone) while every phone
records; cross-correlate each channel against the reference to get relative
arrival lags, then remove the geometric path difference when the beep source
position is known:

    skew_i - skew_ref = lag_i - (d_i - d_ref)/c

Downstream TDOA matrices are corrected with :func:`apply_skew_correction`:
``t*_ij = t_ij - (skew_i - skew_j)``.
"""

from __future__ import annotations

import numpy as np


def beep_template(freq: float = 1000.0, duration_s: float = 0.5,
                  sample_rate: int = 48000, fade_ms: float = 5.0) -> np.ndarray:
    """Tone burst with short cosine fades - a clean calibration event."""
    n = max(2, int(duration_s * sample_rate))
    t = np.arange(n) / sample_rate
    x = np.sin(2.0 * np.pi * freq * t)
    fade = min(n // 4, max(1, int(fade_ms / 1000.0 * sample_rate)))
    ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade) / fade))
    x[:fade] *= ramp
    x[-fade:] *= ramp[::-1]
    return x


def _cross_lag_samples(x: np.ndarray, y: np.ndarray, max_lag: int) -> int:
    """Delay of ``y`` relative to ``x`` in samples (positive = y arrives later).

    Circular cross-correlation r[k] = sum_m x[k+m] * y[m]; its peak sits at
    k* = -L (mod N) when y is delayed by L, so the wrapped argmax is
    unwrapped and negated.
    """
    n = min(len(x), len(y))
    if n < 4:
        return 0
    x, y = x[:n], y[:n]
    r = np.fft.irfft(np.fft.rfft(x) * np.conj(np.fft.rfft(y)))
    k = int(np.argmax(r))
    lag = k - n if k > n // 2 else k          # unwrap to (-N/2, N/2]
    delay = -lag                              # positive when y arrives later
    return int(max(-max_lag, min(max_lag, delay)))


class ClockSkewCalibrator:
    """Estimate per-channel clock offsets from a shared beep recording."""

    def __init__(self, mic_positions, c: float = 343.0) -> None:
        self.mics = np.asarray(mic_positions, dtype=np.float64).reshape(-1, 3)
        if len(self.mics) < 2:
            raise ValueError("need at least two microphone channels")
        self.c = float(c)

    def arrival_lags_s(self, recordings, sample_rate: int = 48000,
                       ref_channel: int = 0, max_lag_ms: float = 250.0) -> np.ndarray:
        """Relative arrival lags (seconds): lag_i - lag_ref for every channel."""
        xref = np.asarray(recordings[ref_channel], dtype=np.float64)
        max_lag = int(max_lag_ms / 1000.0 * sample_rate)
        lags = np.zeros(len(recordings))
        for i, w in enumerate(recordings):
            if i == ref_channel:
                continue
            lags[i] = _cross_lag_samples(xref, np.asarray(w, dtype=np.float64), max_lag) / sample_rate
        return lags

    def calibrate(self, recordings, sample_rate: int = 48000,
                  source_pos=None, ref_channel: int = 0) -> np.ndarray:
        """Per-channel clock offset in seconds (reference channel = 0).

        ``source_pos`` - beep emitter position (metres). When given, the
        geometric path difference is removed so the result is pure clock
        skew. Without it, raw relative lags are returned (valid when all
        phones sit at equal distance from the beep, e.g. a far-field source).
        """
        lags = self.arrival_lags_s(recordings, sample_rate, ref_channel)
        if source_pos is None:
            return lags - lags[ref_channel]
        p = np.asarray(source_pos, dtype=np.float64).reshape(3)
        d = np.linalg.norm(self.mics - p, axis=1) / self.c          # (M,) travel time
        return (lags - d) - (lags[ref_channel] - d[ref_channel])


def apply_skew_correction(tdoa: np.ndarray, skews: np.ndarray) -> np.ndarray:
    """Remove per-channel clock offsets from an (M,M) TDOA matrix.

    ``t*_ij = t_ij - (skew_i - skew_j)``; the diagonal stays zero and the
    antisymmetry ``t_ij = -t_ji`` is preserved.
    """
    tdoa = np.asarray(tdoa, dtype=np.float64)
    skews = np.asarray(skews, dtype=np.float64).reshape(-1)
    if tdoa.shape != (len(skews), len(skews)):
        raise ValueError("tdoa matrix must be (M,M) with M == len(skews)")
    out = tdoa - (skews[:, None] - skews[None, :])
    np.fill_diagonal(out, 0.0)
    return out


__all__ = ["ClockSkewCalibrator", "beep_template", "apply_skew_correction"]
