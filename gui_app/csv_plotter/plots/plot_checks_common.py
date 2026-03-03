import os

import pandas as pd


def downsample_series(x: pd.Series, y: pd.Series, *, max_points: int = 250_000) -> tuple[pd.Series, pd.Series]:
    """Downsample x/y by uniform stride to cap point count.

    Keeps original index alignment and avoids allocating large temporary arrays.
    """
    try:
        n = int(len(y))
    except Exception:
        return x, y
    if max_points <= 0 or n <= max_points:
        return x, y
    try:
        step = int((n + max_points - 1) // max_points)
    except Exception:
        step = 1
    if step <= 1:
        return x, y
    try:
        return x.iloc[::step], y.iloc[::step]
    except Exception:
        return x, y


def parse_limits_from_selector(selector):
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


def parse_barriers_from_selector(selector, *, kind: str | None = None):
    """Return (enabled, target, limit_in, limit_out, start_idx, end_idx) or disabled.

    `kind` selects which barrier config to use when the selector stores
    independent barriers (e.g. {"abs": {...}, "rel": {...}}).
    """
    try:
        cfg = selector.get_barrier_config() if hasattr(selector, "get_barrier_config") else None
    except Exception:
        cfg = None

    if isinstance(cfg, dict) and ("abs" in cfg or "rel" in cfg) and kind:
        try:
            sub = cfg.get(str(kind))
        except Exception:
            sub = None
        if isinstance(sub, dict):
            cfg = sub

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


def x_series_for_df(df):
    try:
        n = int(len(df))
    except Exception:
        n = 0
    return pd.Series(range(1, max(0, n) + 1))


def build_barriers_for_x(x: pd.Series, *, target: float, limit_in: float, limit_out: float, start_idx: int, end_idx: int):
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


def selected_data_columns(df, selected_columns: list[str]) -> list[str]:
    cols = []
    try:
        df_cols = set(df.columns)
    except Exception:
        df_cols = set()
    for c in (selected_columns or []):
        if c == "Timestamp":
            continue
        if c in df_cols:
            cols.append(c)
    return cols


def selected_data_columns_for_df(df, selected_columns: list[str]) -> list[str]:
    """Like selected_data_columns, but against an arbitrary df."""
    cols = []
    try:
        df_cols = set(df.columns)
    except Exception:
        df_cols = set()
    for c in (selected_columns or []):
        if c == "Timestamp":
            continue
        if c in df_cols:
            cols.append(c)
    return cols


def enabled_file_paths(app, selector) -> list[str]:
    """Return enabled overlay file paths for a selector, with fallback to loaded file."""
    paths: list[str] = []
    try:
        paths = list(selector.get_files() or [])
    except Exception:
        paths = []

    if not paths:
        try:
            if isinstance(getattr(app, "last_loaded_file", None), str) and app.last_loaded_file:
                paths = [app.last_loaded_file]
        except Exception:
            paths = []

    try:
        if hasattr(selector, "is_file_enabled"):
            paths = [p for p in paths if bool(selector.is_file_enabled(str(p)))]
    except Exception:
        pass

    return [str(p) for p in paths if p]


def selection_mask_for_df(app, selector, df, *, path: str, scale_to_seconds: float | None = None) -> pd.Series | None:
    """Return boolean mask for df based on selector span window (Timestamp axis).

    This mirrors selection_mask() but operates on an arbitrary dataframe/path.
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

    if not isinstance(df, pd.DataFrame):
        return None

    try:
        x_align = selector.get_x_alignment_mode()
    except Exception:
        x_align = "aligned"

    try:
        shifts = selector.get_file_shifts()
    except Exception:
        shifts = {}
    cfg = shifts.get(os.path.abspath(str(path)), shifts.get(str(path), {})) if isinstance(shifts, dict) else {}
    try:
        x_shift_s = float(cfg.get("x_shift_s", 0.0))
    except Exception:
        x_shift_s = 0.0

    try:
        denom = float(scale_to_seconds) if scale_to_seconds and float(scale_to_seconds) != 0.0 else 1.0
    except Exception:
        denom = 1.0
    x_shift_units = float(x_shift_s) / denom

    # Build x in the same units as the plotted main axis:
    # - Prefer Timestamp when available.
    # - Otherwise fall back to a simple index-based x.
    if "Timestamp" in df.columns:
        try:
            x_raw = app._to_numeric_cached(df, str(path), "Timestamp")
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
    else:
        try:
            x_plot = pd.to_numeric(df.index, errors="coerce")
        except Exception:
            x_plot = pd.Series(range(len(df)))

    if x_shift_units:
        try:
            x_plot = x_plot + float(x_shift_units)
        except Exception:
            pass

    try:
        return (x_plot >= lo) & (x_plot <= hi)
    except Exception:
        return None


def numeric_series_for_col_for_df(app, selector, df, *, path: str, col: str, mask: pd.Series | None = None) -> pd.Series:
    """Read df[col] as numeric series, applying per-file y_shift and optional mask."""
    try:
        y = app._to_numeric_cached(df, str(path), str(col))
    except Exception:
        try:
            y = pd.to_numeric(df[str(col)], errors="coerce")
        except Exception:
            return pd.Series([], dtype=float)

    try:
        shifts = selector.get_file_shifts()
    except Exception:
        shifts = {}
    cfg = shifts.get(os.path.abspath(str(path)), shifts.get(str(path), {})) if isinstance(shifts, dict) else {}
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
    return y


def selection_mask(app, selector) -> pd.Series | None:
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
        _df_i, scale_i = app._get_df_for_path(str(base_path), selector)
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


def min_max_across(app, cols: list[str], *, mask: pd.Series | None = None):
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


def current_file_cfg(app, selector) -> tuple[str, dict]:
    """Return (base_path, cfg) for the currently-loaded file, using selector file shifts."""
    try:
        base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
    except Exception:
        base_path = ""

    try:
        shifts = selector.get_file_shifts()
    except Exception:
        shifts = {}

    cfg = shifts.get(os.path.abspath(str(base_path)), shifts.get(str(base_path), {})) if isinstance(shifts, dict) else {}
    if not isinstance(cfg, dict):
        cfg = {}
    return str(base_path), cfg


def numeric_series_for_col(app, selector, col: str, *, mask: pd.Series | None = None) -> pd.Series:
    """Read column as numeric series, applying per-file y_shift and optional mask."""
    base_path, cfg = current_file_cfg(app, selector)

    try:
        y = app._to_numeric_cached(app.df, str(base_path), str(col))
    except Exception:
        try:
            y = pd.to_numeric(app.df[str(col)], errors="coerce")
        except Exception:
            y = pd.Series(dtype=float)

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

    return y
