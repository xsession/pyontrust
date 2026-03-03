import os

import pandas as pd
import numpy as np

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


def render_histogram(app, selector, bottom_area, selected_columns: list[str]) -> None:
    if not selected_columns:
        return

    hist_fig = Figure(figsize=(8, 2.2), dpi=100)
    hist_ax = hist_fig.add_subplot(111)

    plotted_any = False

    try:
        file_paths = selector.get_files()
    except Exception:
        file_paths = []

    # Prefer enabled overlay files only.
    try:
        if hasattr(selector, "is_file_enabled"):
            file_paths = [p for p in (file_paths or []) if selector.is_file_enabled(str(p))]
    except Exception:
        pass

    if not file_paths:
        try:
            if isinstance(app.last_loaded_file, str) and app.last_loaded_file:
                file_paths = [app.last_loaded_file]
        except Exception:
            file_paths = []

    x_align = "aligned"
    try:
        x_align = selector.get_x_alignment_mode()
    except Exception:
        x_align = "aligned"

    try:
        shifts = selector.get_file_shifts()
    except Exception:
        shifts = {}

    xwin = selector.get_x_window()
    multiple_files = len(file_paths) > 1

    for fp in file_paths:
        df_i, scale_i = app._get_df_for_path(str(fp), selector)
        if not isinstance(df_i, pd.DataFrame):
            continue

        has_ts = "Timestamp" in df_i.columns

        # Timestamp is only required for time-based x-window semantics; histogram itself can
        # still be computed without it. When Timestamp is missing, use index-based x for masking.
        x_plot = None
        if has_ts:
            try:
                x_raw = app._to_numeric_cached(df_i, str(fp), "Timestamp")
            except Exception:
                x_raw = pd.to_numeric(df_i["Timestamp"], errors="coerce")
            if x_align == "independent":
                try:
                    x0 = float(x_raw.dropna().iloc[0])
                except Exception:
                    x0 = 0.0
                x_plot = x_raw - x0
            else:
                x_plot = x_raw

        cfg = shifts.get(os.path.abspath(str(fp)), shifts.get(str(fp), {})) if isinstance(shifts, dict) else {}

        try:
            x_shift_s = float(cfg.get("x_shift_s", 0.0))
        except Exception:
            x_shift_s = 0.0

        try:
            denom = float(scale_i) if float(scale_i) != 0.0 else 1.0
        except Exception:
            denom = 1.0

        mask = None
        if x_plot is not None:
            x_shift_units = float(x_shift_s) / denom
            try:
                x_plot = x_plot + x_shift_units
            except Exception:
                pass

            if xwin is not None:
                try:
                    lo, hi = xwin
                    mask = (x_plot >= lo) & (x_plot <= hi)
                except Exception:
                    mask = None
        else:
            # No Timestamp: still honor the highlighted segment if present by masking on index.
            if xwin is not None:
                try:
                    lo, hi = xwin
                    x_idx = pd.to_numeric(df_i.index, errors="coerce")
                    # Keep existing (seconds-based) shift semantics for consistency with main plot behavior.
                    try:
                        x_shift_units = float(x_shift_s) / denom
                    except Exception:
                        x_shift_units = 0.0
                    if x_shift_units:
                        try:
                            x_idx = x_idx + float(x_shift_units)
                        except Exception:
                            pass
                    mask = (x_idx >= float(lo)) & (x_idx <= float(hi))
                except Exception:
                    mask = None

        base_name = os.path.basename(str(fp))

        for col in selected_columns:
            if col == "Timestamp":
                continue
            if col not in df_i.columns:
                continue

            try:
                y = app._to_numeric_cached(df_i, str(fp), str(col))
            except Exception:
                y = pd.to_numeric(df_i[col], errors="coerce")

            try:
                y_shift = float(cfg.get("y_shift", 0.0))
            except Exception:
                y_shift = 0.0

            if y_shift:
                try:
                    y = y + float(y_shift)
                except Exception:
                    pass

            if mask is not None:
                try:
                    y = y.where(mask)
                except Exception:
                    pass

            y = y.dropna()
            if len(y) == 0:
                continue

            label = str(col)
            if multiple_files:
                label = f"{base_name}:{col}"

            bins = selector.get_hist_bins()

            counts, edges = app._histogram_cached(
                path=str(fp),
                col=str(col),
                y=y,
                bins=int(bins),
                xwin=xwin,
                x_align=str(x_align or ""),
                x_shift_s=float(x_shift_s),
                y_shift=float(y_shift),
            )

            patches = None
            if counts is not None and edges is not None:
                try:
                    centers = (edges[:-1] + edges[1:]) / 2.0
                    widths = (edges[1:] - edges[:-1])
                    bars = hist_ax.bar(
                        centers,
                        counts,
                        width=widths,
                        alpha=0.45,
                        label=label,
                        align='center',
                    )
                    patches = getattr(bars, "patches", None)
                except Exception:
                    patches = None

            if patches is None:
                try:
                    _n, _bins, patches = hist_ax.hist(y, bins=bins, alpha=0.45, label=label)
                except Exception:
                    patches = None

            for p in (patches or []):
                try:
                    p._csv_plotter_column = str(col)
                    # Make bars clickable so users can toggle highlight from the histogram.
                    try:
                        p.set_picker(True)
                    except Exception:
                        pass
                except Exception:
                    pass
            plotted_any = True

    hist_ax.set_title("Histogram")
    hist_ax.grid(True)

    if plotted_any:
        hist_fig.subplots_adjust(right=0.72)
        hist_ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, frameon=True)

    try:
        app._apply_mpl_theme(hist_fig, [hist_ax])
    except Exception:
        pass

    hist_canvas = FigureCanvasTkAgg(hist_fig, master=bottom_area)
    hist_canvas.draw()
    hist_canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    # Ensure global highlight logic also touches histogram bars.
    try:
        if hasattr(app, "plot_canvases"):
            app.plot_canvases.append(hist_canvas)
    except Exception:
        pass

    # Cross-select highlight: clicking a bar toggles the channel highlight everywhere.
    try:
        hist_canvas.mpl_connect('pick_event', lambda evt, aa=hist_ax, c=hist_canvas: app._on_pick(evt, aa, c))
    except Exception:
        pass
