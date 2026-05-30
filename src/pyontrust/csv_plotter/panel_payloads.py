from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

from pyontrust.analysis.metrics import compute_signal_spectrum

from .plot_checks_common import build_barriers_for_x
from .plot_custom_code import _normalize_output, _safe_exec
from .plot_detector_map import (
    build_detector_label_grid,
    compute_anger_centroids,
    detector_slot_positions,
    parse_detector_signal_map,
    reduce_detector_series,
)
from .plot_scene import build_stats_rows, build_x_series


@dataclass(frozen=True)
class PanelFileEntry:
    path: str
    label: str
    df: pd.DataFrame
    enabled: bool = True
    x_shift_s: float = 0.0
    y_shift: float = 0.0


def _enabled_entries(entries: list[PanelFileEntry]) -> list[PanelFileEntry]:
    out: list[PanelFileEntry] = []
    for entry in list(entries or []):
        if not isinstance(entry.df, pd.DataFrame) or entry.df.empty:
            continue
        if not bool(entry.enabled):
            continue
        out.append(entry)
    return out


def _effective_x(entry: PanelFileEntry, *, x_align: str = "aligned") -> pd.Series:
    x_series, _x_label, _time_scale = build_x_series(entry.df)
    x_numeric = pd.to_numeric(x_series, errors="coerce")
    mode = str(x_align or "aligned").strip().lower()
    if mode == "independent":
        try:
            finite = x_numeric.dropna()
            if not finite.empty:
                x_numeric = x_numeric - float(finite.iloc[0])
        except Exception:
            pass
    if float(entry.x_shift_s or 0.0):
        try:
            x_numeric = x_numeric + float(entry.x_shift_s)
        except Exception:
            pass
    return x_numeric


def _mask_from_window(x_series: pd.Series, x_window: tuple[float, float] | None) -> pd.Series | None:
    if not isinstance(x_window, tuple) or len(x_window) != 2:
        return None
    try:
        lo = float(min(x_window[0], x_window[1]))
        hi = float(max(x_window[0], x_window[1]))
    except Exception:
        return None
    try:
        return (x_series >= lo) & (x_series <= hi)
    except Exception:
        return None


def _numeric_series(
    df: pd.DataFrame,
    column: str,
    *,
    y_shift: float = 0.0,
    mask: pd.Series | None = None,
) -> pd.Series:
    try:
        y = pd.to_numeric(df[str(column)], errors="coerce")
    except Exception:
        return pd.Series([], dtype=float)
    if float(y_shift or 0.0):
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


def build_histogram_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    bins: int,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    series: list[dict[str, Any]] = []
    for entry in _enabled_entries(file_entries):
        x_series = _effective_x(entry, x_align=x_align)
        mask = _mask_from_window(x_series, x_window)
        for column in [str(col) for col in selected_columns if str(col) in entry.df.columns and str(col) != "Timestamp"]:
            y = _numeric_series(entry.df, column, y_shift=entry.y_shift, mask=mask).dropna()
            if y.empty:
                continue
            try:
                counts, edges = np.histogram(y.to_numpy(dtype=float), bins=max(1, int(bins or 30)))
            except Exception:
                continue
            centers = ((edges[:-1] + edges[1:]) / 2.0).tolist()
            widths = (edges[1:] - edges[:-1]).tolist()
            series.append(
                {
                    "label": f"{entry.label}:{column}" if len(file_entries) > 1 else str(column),
                    "centers": centers,
                    "counts": counts.tolist(),
                    "widths": widths,
                }
            )
    return {"kind": "histogram", "title": "Histogram", "series": series}


def build_spectrum_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    baseline_cutoff: float | None = None,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    series: list[dict[str, Any]] = []
    for entry in _enabled_entries(file_entries):
        x_series = _effective_x(entry, x_align=x_align)
        mask = _mask_from_window(x_series, x_window)
        x_use = x_series.where(mask) if mask is not None else x_series
        for column in [str(col) for col in selected_columns if str(col) in entry.df.columns and str(col) != "Timestamp"]:
            y_use = _numeric_series(entry.df, column, y_shift=entry.y_shift, mask=mask)
            freqs, magnitudes, baseline = compute_signal_spectrum(x_use, y_use, baseline_cutoff=baseline_cutoff)
            if len(freqs) == 0:
                continue
            label = f"{entry.label}:{column}" if len(file_entries) > 1 else str(column)
            if baseline is not None and baseline_cutoff is not None:
                label = f"{label} (base {baseline:.2f})"
            series.append({"label": label, "x": freqs.tolist(), "y": magnitudes.tolist()})
    return {"kind": "spectrum", "title": "Spectrum", "xLabel": "Frequency (Hz)", "yLabel": "Magnitude", "series": series}


def _barrier_payload(barrier_config: dict[str, Any] | None, kind: str) -> dict[str, Any] | None:
    if not isinstance(barrier_config, dict):
        return None
    cfg = barrier_config.get(kind) if isinstance(barrier_config.get(kind), dict) else barrier_config
    if not isinstance(cfg, dict):
        return None
    try:
        enabled = bool(cfg.get("enabled"))
        target = float(str(cfg.get("target", "")).strip())
        limit_in = float(str(cfg.get("limit_in", "")).strip())
        limit_out = float(str(cfg.get("limit_out", "")).strip())
        start_idx = int(float(str(cfg.get("start_idx", "")).strip()))
        end_idx = int(float(str(cfg.get("end_idx", "")).strip()))
    except Exception:
        enabled = False
        target = limit_in = limit_out = 0.0
        start_idx = end_idx = 0
    if not enabled:
        return None
    return {
        "enabled": True,
        "target": target,
        "limitIn": limit_in,
        "limitOut": limit_out,
        "startIdx": start_idx,
        "endIdx": end_idx,
    }


def build_abs_check_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    barrier_config: dict[str, Any] | None = None,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    series: list[dict[str, Any]] = []
    for entry in _enabled_entries(file_entries):
        x_main = _effective_x(entry, x_align=x_align)
        mask = _mask_from_window(x_main, x_window)
        for column in [str(col) for col in selected_columns if str(col) in entry.df.columns and str(col) != "Timestamp"]:
            y = _numeric_series(entry.df, column, y_shift=entry.y_shift, mask=mask).dropna()
            if y.empty:
                continue
            try:
                x_plot = pd.Series(pd.to_numeric(y.index, errors="coerce") + 1, index=y.index)
            except Exception:
                x_plot = pd.Series(range(1, len(y) + 1), index=y.index, dtype=float)
            series.append({
                "label": f"{entry.label}:{column}" if len(file_entries) > 1 else str(column),
                "x": pd.to_numeric(x_plot, errors="coerce").dropna().tolist(),
                "y": pd.to_numeric(y, errors="coerce").dropna().tolist(),
            })
    barrier = _barrier_payload(barrier_config, "abs")
    barrier_lines = []
    if barrier and series:
        max_len = max((len(item["x"]) for item in series), default=0)
        x_ref = pd.Series(range(1, max_len + 1), dtype=float)
        rmin, rmax, _dmax = build_barriers_for_x(
            x_ref,
            target=barrier["target"],
            limit_in=barrier["limitIn"],
            limit_out=barrier["limitOut"],
            start_idx=barrier["startIdx"],
            end_idx=barrier["endIdx"],
        )
        if rmin is not None and rmax is not None:
            barrier_lines = [
                {"label": "min barrier", "x": x_ref.tolist(), "y": np.asarray(rmin, dtype=float).tolist()},
                {"label": "max barrier", "x": x_ref.tolist(), "y": np.asarray(rmax, dtype=float).tolist()},
            ]
    return {"kind": "abs", "title": "Absolute range check", "series": series, "barriers": barrier_lines}


def build_rel_change_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    barrier_config: dict[str, Any] | None = None,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    series: list[dict[str, Any]] = []
    for entry in _enabled_entries(file_entries):
        x_main = _effective_x(entry, x_align=x_align)
        mask = _mask_from_window(x_main, x_window)
        for column in [str(col) for col in selected_columns if str(col) in entry.df.columns and str(col) != "Timestamp"]:
            y = _numeric_series(entry.df, column, y_shift=entry.y_shift, mask=mask).dropna()
            if y.empty:
                continue
            try:
                p2p = float(y.max()) - float(y.min())
            except Exception:
                continue
            try:
                x_plot = pd.Series(pd.to_numeric(y.index, errors="coerce") + 1, index=y.index)
            except Exception:
                x_plot = pd.Series(range(1, len(y) + 1), index=y.index, dtype=float)
            x_values = pd.to_numeric(x_plot, errors="coerce").dropna().tolist()
            series.append({
                "label": f"{entry.label}:{column}" if len(file_entries) > 1 else str(column),
                "x": x_values,
                "y": [p2p] * len(x_values),
            })
    barrier = _barrier_payload(barrier_config, "rel")
    barrier_lines = []
    if barrier and series:
        max_len = max((len(item["x"]) for item in series), default=0)
        x_ref = pd.Series(range(1, max_len + 1), dtype=float)
        _rmin, _rmax, dmax = build_barriers_for_x(
            x_ref,
            target=barrier["target"],
            limit_in=barrier["limitIn"],
            limit_out=barrier["limitOut"],
            start_idx=barrier["startIdx"],
            end_idx=barrier["endIdx"],
        )
        if dmax is not None:
            barrier_lines = [{"label": "diff barrier", "x": x_ref.tolist(), "y": np.asarray(dmax, dtype=float).tolist()}]
    return {"kind": "rel", "title": "Relative change", "series": series, "barriers": barrier_lines}


def build_custom_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    code: str,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    entries = _enabled_entries(file_entries)
    if not entries:
        return {"kind": "custom", "title": "Custom", "series": [], "error": None}
    entry = entries[0]
    x_main = _effective_x(entry, x_align=x_align)
    mask = _mask_from_window(x_main, x_window)
    if mask is not None:
        try:
            x = x_main.where(mask).dropna()
            df_use = entry.df.loc[x.index]
        except Exception:
            x = x_main.dropna()
            df_use = entry.df
    else:
        x = x_main.dropna()
        df_use = entry.df

    signals: dict[str, pd.Series] = {}
    for column in [str(col) for col in selected_columns if str(col) in entry.df.columns and str(col) != "Timestamp"]:
        y = _numeric_series(entry.df, column, y_shift=entry.y_shift, mask=mask)
        try:
            signals[column] = y.loc[x.index]
        except Exception:
            signals[column] = y.dropna()

    try:
        namespace = _safe_exec(code)
        if callable(namespace.get("transform")):
            out = namespace["transform"](x=x, signals=signals, df=df_use)
        elif "out" in namespace:
            out = namespace.get("out")
        else:
            raise RuntimeError("Define transform(x, signals, df) or set variable 'out'.")
        series_map = _normalize_output(out, index=x.index, x=x)
    except Exception as exc:
        return {"kind": "custom", "title": "Custom", "series": [], "error": str(exc)}

    series: list[dict[str, Any]] = []
    for name, values in (series_map or {}).items():
        try:
            y_plot = pd.to_numeric(values.loc[x.index], errors="coerce")
        except Exception:
            y_plot = pd.to_numeric(values, errors="coerce")
        frame = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": y_plot}).dropna()
        if frame.empty:
            continue
        series.append({"label": str(name), "x": frame["x"].tolist(), "y": frame["y"].tolist()})
    return {"kind": "custom", "title": "Custom", "series": series, "error": None}


def build_detector_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    detector_config: dict[str, Any] | None = None,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    entries = _enabled_entries(file_entries)
    if not entries:
        return {"kind": "detector", "title": "Detector", "rows": 0, "cols": 0, "matrix": [], "labels": [], "centroids": []}
    entry = entries[0]
    cfg = detector_config if isinstance(detector_config, dict) else {}
    try:
        rows = max(1, min(128, int(float(str(cfg.get("rows") or 4)))))
    except Exception:
        rows = 4
    try:
        cols = max(1, min(128, int(float(str(cfg.get("cols") or 4)))))
    except Exception:
        cols = 4
    mapping = str(cfg.get("mapping") or "Row-major")
    reducer = str(cfg.get("reducer") or "Mean")
    signal_map = parse_detector_signal_map(cfg.get("signal_map") or "")

    available = [str(col) for col in selected_columns if str(col) in entry.df.columns and str(col) != "Timestamp"]
    if signal_map:
        available_set = set(available)
        signal_names = [name for name in signal_map if name in available_set]
    else:
        signal_names = available

    capacity = max(1, rows * cols)
    signal_names = signal_names[:capacity]
    label_grid = build_detector_label_grid(signal_names, rows=rows, cols=cols, mapping=mapping)

    x_series = _effective_x(entry, x_align=x_align)
    mask = _mask_from_window(x_series, x_window)

    matrix = np.full((rows, cols), np.nan, dtype=float)
    coords: list[tuple[int, int]] = []
    series_list: list[np.ndarray] = []
    for (r, c), name in zip(detector_slot_positions(rows, cols, mapping), signal_names):
        y = _numeric_series(entry.df, name, y_shift=entry.y_shift, mask=mask)
        matrix[r, c] = reduce_detector_series(y, reducer)
        coords.append((r, c))
        try:
            series_list.append(pd.to_numeric(y, errors="coerce").to_numpy(dtype=float))
        except Exception:
            series_list.append(np.array([], dtype=float))

    if coords and series_list:
        min_len = min((len(arr) for arr in series_list), default=0)
        if min_len > 0:
            values = np.column_stack([arr[:min_len] for arr in series_list])
            coord_arr = np.asarray(coords, dtype=float)
            anger_x, anger_y, anger_energy = compute_anger_centroids(values, coord_arr)
        else:
            anger_x = anger_y = anger_energy = np.array([], dtype=float)
    else:
        anger_x = anger_y = anger_energy = np.array([], dtype=float)

    centroids = [
        {
            "x": float(x_value),
            "y": float(y_value),
            "energy": float(energy),
        }
        for x_value, y_value, energy in zip(anger_x.tolist(), anger_y.tolist(), anger_energy.tolist())
    ]
    return {
        "kind": "detector",
        "title": "Detector",
        "rows": rows,
        "cols": cols,
        "matrix": matrix.tolist(),
        "labels": label_grid,
        "centroids": centroids,
        "mapping": mapping,
        "reducer": reducer,
    }


def build_stats_panel_payload(
    file_entries: list[PanelFileEntry],
    selected_columns: list[str],
    *,
    x_window: tuple[float, float] | None = None,
    x_align: str = "aligned",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for entry in _enabled_entries(file_entries):
        x_series = _effective_x(entry, x_align=x_align)
        mask = _mask_from_window(x_series, x_window)
        df_use = entry.df.loc[mask.fillna(False)] if mask is not None else entry.df
        stats_rows = build_stats_rows(df_use, selected_columns)
        for stats_row in stats_rows:
            rows.append(
                {
                    "source": entry.label,
                    "signal": stats_row[0],
                    "min": stats_row[1],
                    "max": stats_row[2],
                    "avg": stats_row[3],
                    "med": stats_row[4],
                    "p2p": stats_row[5],
                    "std": stats_row[6],
                    "rms": stats_row[7],
                    "crest": stats_row[8],
                    "freq": stats_row[9],
                    "period": stats_row[10],
                }
            )
    return {"kind": "stats", "title": "Statistics", "rows": rows}