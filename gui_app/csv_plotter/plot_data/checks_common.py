"""Common helpers shared by plot-data extractors.

Ported from ``plots/plot_checks_common.py`` — pure pandas, zero GUI dependency.
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Downsampling
# ---------------------------------------------------------------------------

def downsample_series(
    x: pd.Series,
    y: pd.Series,
    *,
    max_points: int = 5_000,
) -> tuple[pd.Series, pd.Series]:
    """Downsample *x*/*y* by uniform stride to cap point count."""
    try:
        n = int(len(y))
    except Exception:
        return x, y
    if max_points <= 0 or n <= max_points:
        return x, y
    step = max(1, int((n + max_points - 1) // max_points))
    if step <= 1:
        return x, y
    try:
        return x.iloc[::step], y.iloc[::step]
    except Exception:
        return x, y


def lttb_downsample(
    x: np.ndarray,
    y: np.ndarray,
    *,
    target: int = 5_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Largest-Triangle-Three-Buckets downsampling for visually lossless decimation."""
    n = len(x)
    if n <= target or target < 3:
        return x, y

    out_x = np.empty(target)
    out_y = np.empty(target)
    out_x[0], out_y[0] = x[0], y[0]
    out_x[-1], out_y[-1] = x[-1], y[-1]

    bucket_size = (n - 2) / (target - 2)
    a_idx = 0

    for i in range(1, target - 1):
        avg_start = int((i + 1) * bucket_size) + 1
        avg_end = min(int((i + 2) * bucket_size) + 1, n)
        avg_x = np.mean(x[avg_start:avg_end])
        avg_y = np.mean(y[avg_start:avg_end])

        bucket_start = int(i * bucket_size) + 1
        bucket_end = int((i + 1) * bucket_size) + 1

        max_area = -1.0
        best_idx = bucket_start
        for j in range(bucket_start, min(bucket_end, n)):
            area = abs(
                (x[a_idx] - avg_x) * (y[j] - y[a_idx])
                - (x[a_idx] - x[j]) * (avg_y - y[a_idx])
            )
            if area > max_area:
                max_area = area
                best_idx = j

        out_x[i] = x[best_idx]
        out_y[i] = y[best_idx]
        a_idx = best_idx

    return out_x, out_y


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def numeric_col(df: pd.DataFrame, col: str) -> pd.Series:
    """Convert a DataFrame column to numeric, coercing errors."""
    return pd.to_numeric(df[col], errors="coerce")


def data_columns(df: pd.DataFrame, selected: list[str]) -> list[str]:
    """Filter *selected* to columns present in *df*, excluding Timestamp."""
    df_cols = set(df.columns)
    return [c for c in selected if c != "Timestamp" and c in df_cols]


def build_x_series(
    df: pd.DataFrame,
    *,
    alignment: str = "aligned",
    x_shift_s: float = 0.0,
    timestamp_scale: float = 1.0,
) -> pd.Series:
    """Build an X-axis series from *df*, respecting alignment & shift."""
    if "Timestamp" in df.columns:
        x = pd.to_numeric(df["Timestamp"], errors="coerce")
        if alignment == "independent":
            try:
                x0 = float(x.dropna().iloc[0])
            except Exception:
                x0 = 0.0
            x = x - x0
    else:
        x = pd.Series(range(len(df)), dtype=float)

    denom = float(timestamp_scale) if timestamp_scale and timestamp_scale != 0.0 else 1.0
    if x_shift_s:
        x = x + float(x_shift_s) / denom
    return x


def apply_mask(series: pd.Series, x: pd.Series, x_window: list | None) -> pd.Series:
    """Apply an x-window mask to *series*."""
    if x_window is None or len(x_window) != 2:
        return series
    try:
        lo, hi = float(x_window[0]), float(x_window[1])
        mask = (x >= lo) & (x <= hi)
        return series.where(mask)
    except Exception:
        return series


def parse_barriers(cfg: dict | None) -> tuple[bool, float, float, float, int, int]:
    """Parse barrier config → (enabled, target, limit_in, limit_out, start_idx, end_idx)."""
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return (False, 0.0, 0.0, 0.0, 0, 0)

    def _f(k: str) -> float | None:
        try:
            return float(str(cfg.get(k, "")).strip())
        except Exception:
            return None

    def _i(k: str) -> int | None:
        try:
            return int(float(str(cfg.get(k, "")).strip()))
        except Exception:
            return None

    target = _f("target")
    limit_in = _f("limit_in")
    limit_out = _f("limit_out")
    start_idx = _i("start_idx")
    end_idx = _i("end_idx")

    if any(v is None for v in (target, limit_in, limit_out, start_idx, end_idx)):
        return (False, 0.0, 0.0, 0.0, 0, 0)
    return (True, target, limit_in, limit_out, start_idx, end_idx)  # type: ignore[return-value]
