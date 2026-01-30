import os
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
    # New layouts may store {"abs": {...}, "rel": {...}}.
    if isinstance(cfg, dict) and ("abs" in cfg or "rel" in cfg):
        try:
            cfg = cfg.get("abs") if isinstance(cfg.get("abs"), dict) else cfg.get("rel")
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


def _build_barriers_for_x(x: pd.Series, *, target: float, limit_in: float, limit_out: float, start_idx: int, end_idx: int):
    """Return (rmin, rmax, dmax) arrays for the provided 1-based sample-index X."""
    try:
        import numpy as np

        idx = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
        lo = int(min(start_idx, end_idx))
        hi = int(max(start_idx, end_idx))
        lim = np.where((idx >= float(lo)) & (idx <= float(hi)), float(limit_in), float(limit_out))
        rmin = float(target) - lim / 2.0
        rmax = float(target) + lim / 2.0
        dmax = lim
        return rmin, rmax, dmax
    except Exception:
        return None, None, None


def _selection_mask(app, selector) -> pd.Series | None:
    """Return boolean mask for current df based on selector span window (Timestamp axis).

    Uses the same semantics as histogram: x-window is expressed in plotted Timestamp units
    (with x-align mode and per-file x-shift applied).
    """
    try:
        xwin = selector.get_x_window()
    except Exception:
        xwin = None
    if xwin is None:
        return None

    try:
        lo, hi = xwin
        lo = float(lo)
        hi = float(hi)
    except Exception:
        return None

    try:
        df = app.df
    except Exception:
        return None
    if not isinstance(df, pd.DataFrame) or "Timestamp" not in df.columns:
        return None

    try:
        x_align = selector.get_x_alignment_mode()
    except Exception:
        x_align = "aligned"

    try:
        base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
    except Exception:
        base_path = ""

    # Per-file x shift (seconds) converted to Timestamp units using scale.
    try:
        shifts = selector.get_file_shifts()
    except Exception:
        shifts = {}
    cfg = shifts.get(os.path.abspath(str(base_path)), shifts.get(str(base_path), {})) if isinstance(shifts, dict) else {}
    try:
        x_shift_s = float(cfg.get("x_shift_s", 0.0))
    except Exception:
        x_shift_s = 0.0
    try:
        _df_i, scale_i = app._get_df_for_path(str(base_path))
    except Exception:
        scale_i = 1.0
    try:
        denom = float(scale_i) if float(scale_i) != 0.0 else 1.0
    except Exception:
        denom = 1.0
    x_shift_units = float(x_shift_s) / denom

    try:
        x_raw = app._to_numeric_cached(df, str(base_path), "Timestamp")
    except Exception:
        x_raw = pd.to_numeric(df["Timestamp"], errors="coerce")

    if str(x_align or "") == "independent":
        try:
            x0 = float(x_raw.dropna().iloc[0])
        except Exception:
            x0 = 0.0
        x_plot = x_raw - x0
    else:
        x_plot = x_raw

    if x_shift_units:
        try:
            x_plot = x_plot + float(x_shift_units)
        except Exception:
            pass

    try:
        return (x_plot >= lo) & (x_plot <= hi)
    except Exception:
        return None


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


def _min_max_across(app, cols: list[str], *, mask: pd.Series | None = None):
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
            if mask is not None:
                try:
                    s = s.where(mask)
                except Exception:
                    pass
            arr.append(s.to_numpy(dtype=float))
        mat = np.vstack(arr)
        y_min = pd.Series(np.nanmin(mat, axis=0))
        y_max = pd.Series(np.nanmax(mat, axis=0))
        return y_min, y_max
    except Exception:
        det = app.df[cols].apply(pd.to_numeric, errors="coerce")
        if mask is not None:
            try:
                det = det.where(mask)
            except Exception:
                pass
        return det.min(axis=1), det.max(axis=1)


def render_abs_check(app, selector, bottom_area, selected_columns: list[str]) -> None:
    cols = _selected_data_columns(app, selected_columns)
    if len(cols) < 2:
        return

    fig = Figure(figsize=(8, 2.2), dpi=100)
    ax = fig.add_subplot(111)

    full_x = _x_series(app)
    mask = _selection_mask(app, selector)
    x = full_x[mask] if mask is not None else full_x
    y_min, y_max = _min_max_across(app, cols, mask=mask)
    if mask is not None:
        y_min = y_min[mask]
        y_max = y_max[mask]

    ax.plot(x, y_max, label="MAX")
    ax.plot(x, y_min, label="MIN")

    enabled, target, limit_in, limit_out, start_idx, end_idx = _parse_barriers_from_selector(selector)
    if enabled:
        rmin, rmax, _dmax = _build_barriers_for_x(
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

    full_x = _x_series(app)
    mask = _selection_mask(app, selector)
    x = full_x[mask] if mask is not None else full_x
    y_min, y_max = _min_max_across(app, cols, mask=mask)
    if mask is not None:
        y_min = y_min[mask]
        y_max = y_max[mask]
    try:
        y_diff = y_max - y_min
    except Exception:
        y_diff = (y_max.astype(float) - y_min.astype(float))

    ax.plot(x, y_diff, label="MAX-MIN")

    enabled, target, limit_in, limit_out, start_idx, end_idx = _parse_barriers_from_selector(selector)
    if enabled:
        _rmin, _rmax, dmax = _build_barriers_for_x(
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
