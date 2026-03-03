"""Relative-change trace extraction for Plotly.js rendering."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .checks_common import data_columns, downsample_series, parse_barriers


def extract_rel_change_traces(
    *,
    dfs: list[dict],
    selected_columns: list[str],
    barriers: dict | None = None,
    max_points: int = 5_000,
) -> dict:
    """Return Plotly traces for relative (peak-to-peak) change view."""
    traces: list[dict] = []
    multiple_files = sum(1 for d in dfs if d.get("enabled", True)) > 1
    max_n = 0

    for file_info in dfs:
        if not file_info.get("enabled", True):
            continue
        df = file_info["df"]
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue

        path = str(file_info.get("path", ""))
        y_shift = float(file_info.get("y_shift", 0.0))
        base_name = os.path.basename(path)
        cols = data_columns(df, selected_columns)

        for col in cols:
            y = pd.to_numeric(df[col], errors="coerce")
            if y_shift:
                y = y + y_shift
            y = y.dropna()
            if len(y) == 0:
                continue

            p2p = float(y.max()) - float(y.min())
            x_idx = pd.Series(range(1, len(y) + 1), dtype=float)
            max_n = max(max_n, len(y))

            x_ds, _ = downsample_series(x_idx, y, max_points=max_points)
            sig_name = f"{base_name}:{col}" if multiple_files else col

            traces.append({
                "x": x_ds.values.tolist(),
                "y": [p2p] * len(x_ds),
                "name": f"{sig_name} (p2p={p2p:.3g})",
                "type": "scatter",
                "mode": "lines",
            })

    # Barrier dmax line
    enabled, target, limit_in, limit_out, start_idx, end_idx = parse_barriers(barriers)
    if enabled and max_n > 0:
        lo = min(start_idx, end_idx)
        hi = max(start_idx, end_idx)
        xs = list(range(1, max_n + 1))
        dmax = [limit_in if lo <= i <= hi else limit_out for i in xs]
        traces.append({
            "x": xs, "y": dmax, "name": "Δmax barrier",
            "type": "scatter", "mode": "lines",
            "line": {"color": "rgba(243,139,168,0.6)", "dash": "dash"},
        })

    return {
        "traces": traces,
        "layout": {
            "title": "Relative Change (P2P)",
            "xaxis": {"title": "Sample Index"},
            "yaxis": {"title": "Peak-to-Peak"},
        },
    }
