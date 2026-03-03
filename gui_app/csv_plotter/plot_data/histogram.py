"""Histogram trace extraction for Plotly.js rendering."""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from .checks_common import build_x_series, data_columns


def extract_histogram_traces(
    *,
    dfs: list[dict],
    selected_columns: list[str],
    x_window: list[float] | None = None,
    nbins: int = 50,
) -> dict:
    """Return Plotly-ready histogram traces.

    Parameters
    ----------
    dfs : list[dict]
        Same format as ``main_series.extract_timeseries_traces``.
    selected_columns : list[str]
        Columns to histogram.
    x_window : list[float] | None
        Time window to restrict data.
    nbins : int
        Number of histogram bins.

    Returns
    -------
    dict  ``{"traces": [...], "layout": {...}}``
    """
    traces: list[dict] = []
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

            # Apply x window
            if x_window and len(x_window) == 2:
                try:
                    lo, hi = float(x_window[0]), float(x_window[1])
                    mask = (x >= lo) & (x <= hi)
                    y = y.where(mask)
                except Exception:
                    pass

            y = y.dropna()
            if len(y) == 0:
                continue

            sig_name = f"{base_name}:{col}" if multiple_files else col

            # Compute bins server-side for consistent rendering
            y_arr = y.values.astype(float)
            counts, edges = np.histogram(y_arr, bins=nbins)
            bin_centers = ((edges[:-1] + edges[1:]) / 2).tolist()

            traces.append({
                "x": bin_centers,
                "y": counts.tolist(),
                "name": sig_name,
                "type": "bar",
            })

    return {
        "traces": traces,
        "layout": {
            "title": "Histogram",
            "barmode": "overlay",
            "xaxis": {"title": "Value"},
            "yaxis": {"title": "Count"},
        },
    }
