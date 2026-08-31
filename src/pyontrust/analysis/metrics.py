"""Signal metrics computation — min, max, avg, RMS, FFT frequency, crest factor.

Migrated from gui_app/csv_plotter/metrics.py. Pure compute — no GUI dependency.
"""

from __future__ import annotations

import logging
import math
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("pyontrust.analysis.metrics")

MetricsTuple = Tuple[str, str, str, str, str, str, str, str, str, str]
_NA_10: MetricsTuple = ("n/a",) * 10
_FFT_MAX_SAMPLES = 20_000
_MIN_FREQ_SAMPLES = 8
_SPECTRUM_MAX_SAMPLES = 131_072


def _fmt(val: float, decimals: int = 3) -> str:
    if not math.isfinite(val):
        return "n/a"
    return f"{val:.{decimals}f}"


def _estimate_frequency_fft(
    xs: np.ndarray,
    ys: np.ndarray,
    dt: float,
) -> tuple[float | None, float | None]:
    t0, t1 = float(xs[0]), float(xs[-1])
    t_uniform = np.arange(t0, t1, dt, dtype=float)
    if t_uniform.size < _MIN_FREQ_SAMPLES:
        return None, None

    y_uniform = np.interp(t_uniform, xs, ys)
    y_uniform -= np.nanmean(y_uniform)

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
    mag[0] = 0.0
    k = int(np.argmax(mag))
    f = float(freqs[k])
    if f <= 0:
        return None, None
    return f, 1.0 / f


def _estimate_frequency_zero_crossing(
    ys: np.ndarray,
    duration: float,
) -> tuple[float | None, float | None]:
    if len(ys) < _MIN_FREQ_SAMPLES or duration <= 0:
        return None, None
    signs = (ys >= 0).astype(np.int8)
    crossings = int(np.sum(signs[1:] != signs[:-1]))
    f = (crossings / 2.0) / duration
    if f <= 0:
        return None, None
    return f, 1.0 / f


def compute_signal_metrics(x: pd.Series, y: pd.Series) -> MetricsTuple:
    """Compute 10 signal metrics from x (time) and y (amplitude).

    Returns (min, max, avg, med, p2p, std, rms, crest, freq, period).
    """
    try:
        ys = pd.to_numeric(y, errors="coerce").dropna()
    except Exception:
        ys = pd.Series([], dtype=float)

    if len(ys) == 0:
        return _NA_10

    try:
        mn = float(ys.min())
        mx = float(ys.max())
        avg = float(ys.mean())
        med = float(ys.median())
        p2p = mx - mn
    except Exception:
        return _NA_10

    try:
        std = float(ys.std(ddof=0))
    except Exception:
        std = float("nan")

    try:
        vals = ys.astype(float).values
        rms_val = float(np.sqrt(np.mean(np.square(vals))))
    except Exception:
        rms_val = float("nan")

    try:
        if math.isfinite(rms_val) and rms_val > 0:
            crest = float(max(abs(mn), abs(mx)) / rms_val)
        else:
            crest = float("nan")
    except Exception:
        crest = float("nan")

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
                freq, period = _estimate_frequency_fft(xs_arr, ys_arr, dt)
                if freq is None:
                    freq, period = _estimate_frequency_zero_crossing(ys_arr, duration)

                if freq is not None and period is not None:
                    freq_s = f"{freq:.3f}"
                    period_s = f"{period:.3f}"
    except Exception:
        pass

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


def compute_signal_spectrum(
    x: pd.Series,
    y: pd.Series,
    *,
    baseline_cutoff: float | None = None,
) -> tuple[np.ndarray, np.ndarray, float | None]:
    """Compute a single-sided magnitude spectrum with DC suppression."""
    try:
        xs_arr = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float, copy=False)
        ys_arr = pd.to_numeric(y, errors="coerce").to_numpy(dtype=float, copy=False)
    except Exception:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    valid = np.isfinite(xs_arr) & np.isfinite(ys_arr)
    if int(np.count_nonzero(valid)) < _MIN_FREQ_SAMPLES:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    xs_arr = xs_arr[valid]
    ys_arr = ys_arr[valid]

    if xs_arr.size > 1 and np.any(np.diff(xs_arr) < 0):
        order = np.argsort(xs_arr, kind="mergesort")
        xs_arr = xs_arr[order]
        ys_arr = ys_arr[order]

    try:
        unique_x, unique_idx = np.unique(xs_arr, return_index=True)
    except Exception:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None
    if unique_x.size < _MIN_FREQ_SAMPLES:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    xs_arr = unique_x
    ys_arr = ys_arr[unique_idx]
    dx = np.diff(xs_arr)
    dx_pos = dx[dx > 0]
    if dx_pos.size == 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    dt = float(np.median(dx_pos))
    if not math.isfinite(dt) or dt <= 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    t0 = float(xs_arr[0])
    t1 = float(xs_arr[-1])
    if not math.isfinite(t0) or not math.isfinite(t1) or t1 <= t0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    try:
        t_uniform = np.arange(t0, t1 + (dt * 0.5), dt, dtype=float)
    except Exception:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None
    if t_uniform.size < _MIN_FREQ_SAMPLES:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    try:
        y_uniform = np.interp(t_uniform, xs_arr, ys_arr)
    except Exception:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    baseline = None
    try:
        if baseline_cutoff is not None and math.isfinite(float(baseline_cutoff)):
            base_samples = y_uniform[y_uniform <= float(baseline_cutoff)]
            if base_samples.size > 0:
                baseline = float(np.nanmean(base_samples))
        if baseline is None:
            baseline = float(np.nanmean(y_uniform))
    except Exception:
        baseline = None

    if baseline is None or not math.isfinite(baseline):
        return np.empty(0, dtype=float), np.empty(0, dtype=float), None

    y_centered = y_uniform - float(baseline)

    if y_centered.size > _SPECTRUM_MAX_SAMPLES:
        step = int(np.ceil(y_centered.size / _SPECTRUM_MAX_SAMPLES))
        if step > 1:
            y_centered = y_centered[::step]
            dt = dt * step

    if y_centered.size < _MIN_FREQ_SAMPLES:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), baseline

    yf = np.fft.rfft(y_centered)
    freqs = np.fft.rfftfreq(y_centered.size, d=dt)
    magnitudes = np.abs(yf) / max(1, y_centered.size)
    if magnitudes.size > 0:
        magnitudes[0] = 0.0
    return freqs, magnitudes, baseline
