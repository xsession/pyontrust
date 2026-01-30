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


def render_rel_change(app, selector, bottom_area, selected_columns: list[str]) -> None:
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
            p2p = float(y.max()) - float(y.min())
        except Exception:
            continue
        try:
            ax.plot(x, [p2p] * len(x), label=f"{col} (p2p={p2p:.3g})")
        except Exception:
            ax.plot(x, [p2p] * len(x), label=str(col))

    enabled, target, limit_in, limit_out, start_idx, end_idx = parse_barriers_from_selector(selector, kind="rel")
    if enabled:
        _rmin, _rmax, dmax = build_barriers_for_x(
            x,
            target=float(target),
            limit_in=float(limit_in),
            limit_out=float(limit_out),
            start_idx=int(start_idx),
            end_idx=int(end_idx),
        )
        if dmax is not None:
            try:
                ax.plot(x, dmax, color="red", linewidth=1.6, label="diff barrier")
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

    ax.set_title("Relative change")
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
