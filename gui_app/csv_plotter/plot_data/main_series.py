"""Time-series trace extraction for Plotly.js rendering.

Extracts JSON-serialisable trace data from a loaded DataFrame,
supporting multi-file overlays, X-alignment, per-file shifts,
downsampling, and signal metrics computation.
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from .checks_common import (
    build_x_series,
    data_columns,
    downsample_series,
    lttb_downsample,
    numeric_col,
)


def extract_timeseries_traces(
    *,
    dfs: list[dict],
    selected_columns: list[str],
    x_window: list[float] | None = None,
    max_points: int = 5_000,
    compute_metrics_fn: Any = None,
) -> dict:
    """Return Plotly-ready traces + metrics for a time-series subplot.

    Parameters
    ----------
    dfs : list[dict]
        Each entry: ``{"path": str, "df": DataFrame, "scale": float,
        "alignment": str, "x_shift_s": float, "y_shift": float, "enabled": bool}``
    selected_columns : list[str]
        Columns to plot.
    x_window : list[float] | None
        ``[lo, hi]`` zoom window (in plotted x-units).  ``None`` = full range.
    max_points : int
        Maximum points per trace (LTTB downsampled).
    compute_metrics_fn : callable | None
        ``fn(x_series, y_series) -> dict`` for signal metrics.

    Returns
    -------
    dict  ``{"traces": [...], "metrics": {...}, "layout": {...}}``
    """
    traces: list[dict] = []
    metrics: dict[str, dict | None] = {}
    multiple_files = sum(1 for d in dfs if d.get("enabled", True)) > 1

    for file_info in dfs:
        if not file_info.get("enabled", True):
            continue
        df = file_info["df"]
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue

        path = str(file_info.get("path", ""))
        scale = float(file_info.get("scale", 1.0))
        alignment = str(file_info.get("alignment", "aligned"))
        x_shift_s = float(file_info.get("x_shift_s", 0.0))
        y_shift = float(file_info.get("y_shift", 0.0))
        base_name = os.path.basename(path)

        x = build_x_series(df, alignment=alignment, x_shift_s=x_shift_s, timestamp_scale=scale)
        cols = data_columns(df, selected_columns)

        for col in cols:
            y = pd.to_numeric(df[col], errors="coerce")
            if y_shift:
                y = y + y_shift

            # Stats use the full (or windowed) data before downsampling
            x_stats = x.copy()
            y_stats = y.copy()
            if x_window and len(x_window) == 2:
                try:
                    lo, hi = float(x_window[0]), float(x_window[1])
                    mask = (x >= lo) & (x <= hi)
                    x_stats = x.where(mask)
                    y_stats = y.where(mask)
                except Exception:
                    pass

            sig_name = f"{base_name}:{col}" if multiple_files else col

            if compute_metrics_fn:
                try:
                    metrics[sig_name] = compute_metrics_fn(x_stats, y_stats)
                except Exception:
                    metrics[sig_name] = None

            # Downsample for transfer
            x_plot = x.dropna()
            y_plot = y.loc[x_plot.index]
            valid = y_plot.notna()
            x_plot = x_plot[valid]
            y_plot = y_plot[valid]

            if len(x_plot) > max_points and max_points > 3:
                x_arr, y_arr = lttb_downsample(
                    x_plot.values.astype(float),
                    y_plot.values.astype(float),
                    target=max_points,
                )
            else:
                x_arr = x_plot.values.astype(float)
                y_arr = y_plot.values.astype(float)

            traces.append({
                "x": x_arr.tolist(),
                "y": y_arr.tolist(),
                "name": sig_name,
                "type": "scatter",
                "mode": "lines",
            })

    layout: dict[str, Any] = {"title": "Time Series"}
    if x_window and len(x_window) == 2:
        layout["xaxis"] = {"range": [float(x_window[0]), float(x_window[1])]}

    return {"traces": traces, "metrics": metrics, "layout": layout}
