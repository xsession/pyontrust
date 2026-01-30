import tkinter as tk
from tkinter import ttk

import pandas as pd

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


def _parse_limits_from_selector(selector):
    ymin = None
    ymax = None
    try:
        ylim_cfg = selector.get_ylim_config()
    except Exception:
        ylim_cfg = None
    if isinstance(ylim_cfg, dict) and bool(ylim_cfg.get("enabled")):
        ymin_raw = str(ylim_cfg.get("ymin", "")).strip()
        ymax_raw = str(ylim_cfg.get("ymax", "")).strip()
        if ymin_raw:
            try:
                ymin = float(ymin_raw)
            except Exception:
                ymin = None
        if ymax_raw:
            try:
                ymax = float(ymax_raw)
            except Exception:
                ymax = None
    return ymin, ymax


def _parse_barriers_from_selector(selector):
    """Return (enabled, target, limit_in, limit_out, start_idx, end_idx) or disabled."""
    try:
        cfg = selector.get_barrier_config() if hasattr(selector, "get_barrier_config") else None
    except Exception:
        cfg = None
    if not isinstance(cfg, dict) or not bool(cfg.get("enabled")):
        return (False, None, None, None, None, None)

    def _f(key):
        try:
            v = str(cfg.get(key, "")).strip()
            return float(v)
        except Exception:
            return None

    def _i(key):
        try:
            v = str(cfg.get(key, "")).strip()
            return int(float(v))
        except Exception:
            return None

    target = _f("target")
    limit_in = _f("limit_in")
    limit_out = _f("limit_out")
    start_idx = _i("start_idx")
    end_idx = _i("end_idx")

    if target is None or limit_in is None or limit_out is None or start_idx is None or end_idx is None:
        return (False, None, None, None, None, None)
    return (True, float(target), float(limit_in), float(limit_out), int(start_idx), int(end_idx))


def _x_series(app):
    # Use index-based X (1..N) so the barrier start/end indices match the plot.
    try:
        n = int(len(getattr(app, "df", [])))
    except Exception:
        n = 0
    return pd.Series(range(1, max(0, n) + 1))


def _build_barriers(n: int, *, target: float, limit_in: float, limit_out: float, start_idx: int, end_idx: int):
    """Return (rmin, rmax, dmax) arrays length n based on index windows (1-based)."""
    try:
        import numpy as np

        idx = np.arange(1, int(n) + 1, dtype=int)
        lo = int(min(start_idx, end_idx))
        hi = int(max(start_idx, end_idx))
        lim = np.where((idx >= lo) & (idx <= hi), float(limit_in), float(limit_out))
        rmin = float(target) - lim / 2.0
        rmax = float(target) + lim / 2.0
        dmax = lim
        return rmin, rmax, dmax
    except Exception:
        return None, None, None


def _selected_data_columns(app, selected_columns: list[str]) -> list[str]:
    cols = []
    try:
        df_cols = set(getattr(app, "df", pd.DataFrame()).columns)
    except Exception:
        df_cols = set()
    for c in (selected_columns or []):
        if c == "Timestamp":
            continue
        if c in df_cols:
            cols.append(c)
    return cols


def _min_max_across(app, cols: list[str]):
    try:
        import numpy as np

        try:
            base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
        except Exception:
            base_path = ""

        arr = []
        for c in cols:
            try:
                s = app._to_numeric_cached(app.df, str(base_path), str(c))
            except Exception:
                s = pd.to_numeric(app.df[c], errors="coerce")
            arr.append(s.to_numpy(dtype=float))
        mat = np.vstack(arr)
        y_min = pd.Series(np.nanmin(mat, axis=0))
        y_max = pd.Series(np.nanmax(mat, axis=0))
        return y_min, y_max
    except Exception:
        det = app.df[cols].apply(pd.to_numeric, errors="coerce")
        return det.min(axis=1), det.max(axis=1)


def render_abs_check(app, selector, bottom_area, selected_columns: list[str]) -> None:
    cols = _selected_data_columns(app, selected_columns)
    if len(cols) < 2:
        return

    fig = Figure(figsize=(8, 2.2), dpi=100)
    ax = fig.add_subplot(111)

    x = _x_series(app)
    y_min, y_max = _min_max_across(app, cols)

    ax.plot(x, y_max, label="MAX")
    ax.plot(x, y_min, label="MIN")

    enabled, target, limit_in, limit_out, start_idx, end_idx = _parse_barriers_from_selector(selector)
    if enabled:
        rmin, rmax, _dmax = _build_barriers(
            len(x),
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
        ymin, ymax = _parse_limits_from_selector(selector)
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
    ax.legend(loc="best", fontsize=8)

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


def render_rel_change(app, selector, bottom_area, selected_columns: list[str]) -> None:
    cols = _selected_data_columns(app, selected_columns)
    if len(cols) < 2:
        return

    fig = Figure(figsize=(8, 2.2), dpi=100)
    ax = fig.add_subplot(111)

    x = _x_series(app)
    y_min, y_max = _min_max_across(app, cols)
    try:
        y_diff = y_max - y_min
    except Exception:
        y_diff = (y_max.astype(float) - y_min.astype(float))

    ax.plot(x, y_diff, label="MAX-MIN")

    enabled, target, limit_in, limit_out, start_idx, end_idx = _parse_barriers_from_selector(selector)
    if enabled:
        _rmin, _rmax, dmax = _build_barriers(
            len(x),
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
        ymin, ymax = _parse_limits_from_selector(selector)
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
    ax.legend(loc="best", fontsize=8)

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
