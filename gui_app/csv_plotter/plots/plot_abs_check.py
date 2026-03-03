import tkinter as tk
from tkinter import ttk

import pandas as pd

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .plot_checks_common import (
    enabled_file_paths,
    downsample_series,
    numeric_series_for_col_for_df,
    parse_barriers_from_selector,
    parse_limits_from_selector,
    selected_data_columns_for_df,
    selection_mask_for_df,
)


def render_abs_check(app, selector, bottom_area, selected_columns: list[str]) -> None:
    file_paths = enabled_file_paths(app, selector)
    if not file_paths:
        return

    fig = Figure(figsize=(8, 2.2), dpi=100)
    ax = fig.add_subplot(111)

    # Track the intended visible x-range (sample index) so zoomed views remain
    # consistent even when we downsample for performance.
    x_min: float | None = None
    x_max: float | None = None

    plotted_any = False
    for fp in file_paths:
        df_i, scale_i = app._get_df_for_path(str(fp), selector)
        if not isinstance(df_i, pd.DataFrame):
            continue

        cols = selected_data_columns_for_df(df_i, selected_columns)
        if not cols:
            continue

        mask = selection_mask_for_df(app, selector, df_i, path=str(fp), scale_to_seconds=float(scale_i or 1.0))

        for col in cols:
            y = numeric_series_for_col_for_df(app, selector, df_i, path=str(fp), col=str(col), mask=mask)
            try:
                y = y.dropna()
            except Exception:
                pass
            if len(y) == 0:
                continue

            # X axis is sample index (1-based). Build it only for the plotted points.
            try:
                x_plot_full = pd.Series(pd.to_numeric(y.index, errors="coerce") + 1)
            except Exception:
                x_plot_full = pd.Series(range(1, len(y) + 1))

            try:
                _lo = float(pd.to_numeric(x_plot_full, errors="coerce").dropna().min())
                _hi = float(pd.to_numeric(x_plot_full, errors="coerce").dropna().max())
                x_min = _lo if x_min is None else min(x_min, _lo)
                x_max = _hi if x_max is None else max(x_max, _hi)
            except Exception:
                pass

            # Downsample to keep Matplotlib responsive on huge CSVs.
            try:
                x_plot, y = downsample_series(x_plot_full, y, max_points=int(getattr(app, "mpl_max_points", 250_000) or 250_000))
            except Exception:
                x_plot = x_plot_full

            label = str(col)
            if len(file_paths) > 1:
                try:
                    import os
                    label = f"{os.path.basename(str(fp))}:{col}"
                except Exception:
                    label = f"{fp}:{col}"
            ax.plot(x_plot, y, label=label)
            plotted_any = True

    if not plotted_any:
        return

    # Make the Abs view follow the main zoom window (mapped to sample index).
    try:
        if x_min is not None and x_max is not None:
            ax.set_xlim(float(x_min), float(x_max))
    except Exception:
        pass

    enabled, target, limit_in, limit_out, start_idx, end_idx = parse_barriers_from_selector(selector, kind="abs")
    if enabled:
        # Draw piecewise-constant barriers without allocating full-length arrays.
        try:
            n = int(len(df_i)) if isinstance(df_i, pd.DataFrame) else 0
        except Exception:
            n = 0
        try:
            lo = int(min(start_idx, end_idx))
            hi = int(max(start_idx, end_idx))
        except Exception:
            lo, hi = 1, 0
        if n > 0:
            lo = max(1, min(int(lo), int(n)))
            hi = max(1, min(int(hi), int(n)))
            if hi < lo:
                lo, hi = hi, lo
            try:
                rmin_out = float(target) - float(limit_out) / 2.0
                rmax_out = float(target) + float(limit_out) / 2.0
                rmin_in = float(target) - float(limit_in) / 2.0
                rmax_in = float(target) + float(limit_in) / 2.0

                xs = [1, lo, lo, hi, hi, n]
                rmin = [rmin_out, rmin_out, rmin_in, rmin_in, rmin_out, rmin_out]
                rmax = [rmax_out, rmax_out, rmax_in, rmax_in, rmax_out, rmax_out]
                ax.plot(xs, rmax, color="red", linewidth=1.6, label="max barrier")
                ax.plot(xs, rmin, color="red", linewidth=1.6, label="min barrier")
            except Exception:
                pass
    else:
        ymin, ymax = parse_limits_from_selector(selector)
        if ymin is not None:
            try:
                ax.axhline(float(ymin), color="red", linestyle="--", linewidth=1.2, label="min limit")
            except Exception:
                pass
        if ymax is not None:
            try:
                ax.axhline(float(ymax), color="red", linestyle="--", linewidth=1.2, label="max limit")
            except Exception:
                pass

    ax.set_title("Absolute range check")
    ax.grid(True)

    try:
        handles, labels = ax.get_legend_handles_labels()
    except Exception:
        handles, labels = [], []
    if labels:
        try:
            fig.subplots_adjust(right=0.72)
        except Exception:
            pass
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, frameon=True)

    try:
        app._apply_mpl_theme(fig, [ax])
    except Exception:
        pass

    frame = ttk.Frame(bottom_area)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    try:
        if hasattr(app, "plot_canvases"):
            app.plot_canvases.append(canvas)
    except Exception:
        pass
