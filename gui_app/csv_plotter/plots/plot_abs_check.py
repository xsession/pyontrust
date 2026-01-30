import tkinter as tk
from tkinter import ttk

import pandas as pd

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .plot_checks_common import (
    build_barriers_for_x,
    numeric_series_for_col,
    parse_barriers_from_selector,
    parse_limits_from_selector,
    selected_data_columns,
    selection_mask,
    x_series_for_df,
)


def render_abs_check(app, selector, bottom_area, selected_columns: list[str]) -> None:
    try:
        df = app.df
    except Exception:
        return
    if not isinstance(df, pd.DataFrame):
        return

    cols = selected_data_columns(df, selected_columns)
    if len(cols) < 1:
        return

    fig = Figure(figsize=(8, 2.2), dpi=100)
    ax = fig.add_subplot(111)

    full_x = x_series_for_df(df)
    mask = selection_mask(app, selector)
    x = full_x[mask] if mask is not None else full_x

    for col in cols:
        y = numeric_series_for_col(app, selector, str(col), mask=mask)
        if mask is not None:
            try:
                y = y[mask]
            except Exception:
                pass
        try:
            y = y.dropna()
        except Exception:
            pass
        if len(y) == 0:
            continue
        try:
            x_plot = x.loc[y.index]
        except Exception:
            x_plot = x
        ax.plot(x_plot, y, label=str(col))

    enabled, target, limit_in, limit_out, start_idx, end_idx = parse_barriers_from_selector(selector, kind="abs")
    if enabled:
        rmin, rmax, _dmax = build_barriers_for_x(
            x,
            target=float(target),
            limit_in=float(limit_in),
            limit_out=float(limit_out),
            start_idx=int(start_idx),
            end_idx=int(end_idx),
        )
        if rmin is not None and rmax is not None:
            try:
                ax.plot(x, rmax, color="red", linewidth=1.6, label="max barrier")
                ax.plot(x, rmin, color="red", linewidth=1.6, label="min barrier")
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
