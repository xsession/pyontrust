"""Signal metrics computation for the CSV Plotter.

This module is **pure-compute** — it has no GUI or Tk dependency and is
fully unit-testable in isolation.  All public functions accept plain
pandas / numpy objects and return plain Python values.

Metrics returned by :func:`compute_signal_metrics`:
    0. min
    1. max
    2. avg (mean)
    3. med (median)
    4. p2p (peak-to-peak)
    5. std (population standard deviation)
    6. rms (root-mean-square)
    7. crest (crest factor = peak / rms)
    8. freq (dominant frequency, FFT-based, Hz)
    9. period (1/freq, seconds)
"""

from __future__ import annotations

import logging
import math
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("csv_plotter.metrics")

# Type alias for the 10-string metrics tuple
MetricsTuple = Tuple[str, str, str, str, str, str, str, str, str, str]

_NA_10: MetricsTuple = ("n/a",) * 10

# Maximum FFT length before decimation (keeps compute cost bounded)
_FFT_MAX_SAMPLES = 20_000
# Minimum samples for meaningful frequency estimation
_MIN_FREQ_SAMPLES = 8


def _fmt(val: float, decimals: int = 3) -> str:
    """Format a float for display; returns ``"n/a"`` for NaN / ±Inf."""
    if not math.isfinite(val):
        return "n/a"
    return f"{val:.{decimals}f}"


def _estimate_frequency_fft(
    xs: np.ndarray,
    ys: np.ndarray,
    dt: float,
) -> tuple[float | None, float | None]:
    """FFT-based dominant frequency estimation.

    Returns ``(freq_hz, period_s)`` or ``(None, None)`` on failure.
    """
    t0, t1 = float(xs[0]), float(xs[-1])
    t_uniform = np.arange(t0, t1, dt, dtype=float)
    if t_uniform.size < _MIN_FREQ_SAMPLES:
        return None, None

    y_uniform = np.interp(t_uniform, xs, ys)
    y_uniform -= np.nanmean(y_uniform)

    # Decimate to keep FFT cost bounded
    n_u = t_uniform.size
    if n_u > _FFT_MAX_SAMPLES:
        step = int(np.ceil(n_u / _FFT_MAX_SAMPLES))
        if step > 1:
            y_uniform = y_uniform[::step]
            dt = dt * step

    yf = np.fft.rfft(y_uniform)
    freqs = np.fft.rfftfreq(len(y_uniform), d=dt)
    if freqs.size <= 1:
        return None, None

    mag = np.abs(yf)
    mag[0] = 0.0  # ignore DC component
    k = int(np.argmax(mag))
    f = float(freqs[k])
    if f <= 0:
        return None, None
    return f, 1.0 / f


def _estimate_frequency_zero_crossing(
    ys: np.ndarray,
    duration: float,
) -> tuple[float | None, float | None]:
    """Zero-crossing fallback when FFT fails.

    Returns ``(freq_hz, period_s)`` or ``(None, None)`` on failure.
    """
    if len(ys) < _MIN_FREQ_SAMPLES or duration <= 0:
        return None, None
    signs = (ys >= 0).astype(np.int8)
    crossings = int(np.sum(signs[1:] != signs[:-1]))
    f = (crossings / 2.0) / duration
    if f <= 0:
        return None, None
    return f, 1.0 / f


def compute_signal_metrics(
    x: pd.Series,
    y: pd.Series,
) -> MetricsTuple:
    """Compute 10 signal metrics from *x* (time) and *y* (amplitude).

    Returns a 10-tuple of human-readable strings.  Individual metrics
    that cannot be computed are ``"n/a"``; the function never raises.

    Parameters
    ----------
    x : pd.Series
        Time / x-axis series (must be numeric or coercible).
    y : pd.Series
        Signal / y-axis series.

    Returns
    -------
    MetricsTuple
        ``(min, max, avg, med, p2p, std, rms, crest, freq, period)``
    """
    # -- Coerce y to numeric --
    try:
        ys = pd.to_numeric(y, errors="coerce").dropna()
    except Exception:
        logger.debug("Failed to coerce y to numeric", exc_info=True)
        ys = pd.Series([], dtype=float)

    if len(ys) == 0:
        logger.debug("Empty series after numeric coercion — returning all n/a")
        return _NA_10

    # -- Basic statistics --
    try:
        mn = float(ys.min())
        mx = float(ys.max())
        avg = float(ys.mean())
        med = float(ys.median())
        p2p = mx - mn
    except Exception:
        logger.warning("Basic stats computation failed", exc_info=True)
        return _NA_10

    # -- Standard deviation (population) --
    try:
        std = float(ys.std(ddof=0))
    except Exception:
        logger.debug("std computation failed", exc_info=True)
        std = float("nan")

    # -- RMS --
    try:
        vals = ys.astype(float).values
        rms_val = float(np.sqrt(np.mean(np.square(vals))))
    except Exception:
        logger.debug("RMS computation failed", exc_info=True)
        rms_val = float("nan")

    # -- Crest factor --
    try:
        if math.isfinite(rms_val) and rms_val > 0:
            crest = float(max(abs(mn), abs(mx)) / rms_val)
        else:
            crest = float("nan")
    except Exception:
        logger.debug("Crest factor computation failed", exc_info=True)
        crest = float("nan")

    # -- Frequency / period estimation --
    freq_s = "n/a"
    period_s = "n/a"

    try:
        xs_raw = pd.to_numeric(x, errors="coerce")
        ys_raw = pd.to_numeric(y, errors="coerce")
        d = pd.DataFrame({"x": xs_raw, "y": ys_raw}).dropna().sort_values("x")

        if len(d) >= _MIN_FREQ_SAMPLES:
            xs_arr = d["x"].to_numpy(dtype=float)
            ys_arr = d["y"].to_numpy(dtype=float)

            dx = np.diff(xs_arr)
            dx_pos = dx[dx > 0]
            dt = float(np.median(dx_pos)) if len(dx_pos) > 0 else 0.0
            duration = float(xs_arr[-1] - xs_arr[0])

            if dt > 0 and duration > 0 and len(ys_arr) >= _MIN_FREQ_SAMPLES:
                # Primary: FFT
                freq, period = _estimate_frequency_fft(xs_arr, ys_arr, dt)
                if freq is None:
                    # Fallback: zero-crossing
                    freq, period = _estimate_frequency_zero_crossing(ys_arr, duration)

                if freq is not None and period is not None:
                    freq_s = f"{freq:.3f}"
                    period_s = f"{period:.3f}"
    except Exception:
        logger.debug("Frequency estimation failed", exc_info=True)

    return (
        _fmt(mn),
        _fmt(mx),
        _fmt(avg),
        _fmt(med),
        _fmt(p2p),
        _fmt(std),
        _fmt(rms_val),
        _fmt(crest, 2),
        freq_s,
        period_s,
    )
