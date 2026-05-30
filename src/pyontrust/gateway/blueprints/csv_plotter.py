"""CSV Plotter gateway blueprint.

Mounts at ``/csv/`` and serves the unified CSV Plotter frontend together
with a subplot-aware REST API.
"""

from __future__ import annotations

import json
import logging
import math
import os
import pathlib
import platform
import string
import tempfile
from typing import Any

import pandas as pd
from flask import Blueprint, Response, jsonify, request, send_from_directory

from pyontrust.analysis.csv_reader import compute_timestamp_scale
from pyontrust.analysis.metrics import compute_signal_metrics
from pyontrust.csv_plotter import (
    PanelFileEntry,
    PlotScene,
    PlotSeriesScene,
    build_abs_check_panel_payload,
    build_browser_plot_model,
    build_custom_panel_payload,
    build_detector_panel_payload,
    build_histogram_panel_payload,
    build_rel_change_panel_payload,
    build_spectrum_panel_payload,
    build_stats_panel_payload,
    build_x_series,
    cli_base_path,
    default_cli_output_stem,
    default_selected_columns,
    find_newest_signal_file,
    format_window_bound_for_filename,
    numeric_signal_columns,
    read_signal_file,
    render_combined_browser_export_image,
    render_panel_payload_image,
    render_plot_scene_image,
    series_color,
    supported_signal_suffixes,
    write_dataframe_export,
)

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "csv"

bp = Blueprint(
    "csv_plotter",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/csv/static",
)

logger = logging.getLogger("pyontrust.gateway.csv_plotter")

_LAYOUT_PATH = pathlib.Path("layout.json")
_TIME_SERIES_MODES = {"Time series", "AF-10047: Control vs Module"}
_PLOT_MODES = [
    "Time series",
    "AF-10047: Control vs Module",
    "Histogram",
    "Spectrum",
    "Absolute check",
    "Relative change",
    "Custom code",
    "Detector map",
    "Statistics",
]
_MODE_ALIASES = {mode.lower(): mode for mode in _PLOT_MODES}
_MODE_ALIASES.update(
    {
        "detector": "Detector map",
        "detector map": "Detector map",
        "abs": "Absolute check",
        "absolute": "Absolute check",
        "absolute check": "Absolute check",
        "rel": "Relative change",
        "relative": "Relative change",
        "relative change": "Relative change",
        "custom": "Custom code",
        "custom code": "Custom code",
        "hist": "Histogram",
        "histogram": "Histogram",
        "spectrum": "Spectrum",
        "stats": "Statistics",
        "statistics": "Statistics",
        "af-10047": "AF-10047: Control vs Module",
        "control vs module": "AF-10047: Control vs Module",
    }
)


def _default_barrier_config() -> dict[str, dict[str, Any]]:
    return {
        "abs": {
            "enabled": False,
            "target": 0.0,
            "limit_in": 0.0,
            "limit_out": 0.0,
            "start_idx": 0,
            "end_idx": 0,
        },
        "rel": {
            "enabled": False,
            "target": 0.0,
            "limit_in": 0.0,
            "limit_out": 0.0,
            "start_idx": 0,
            "end_idx": 0,
        },
    }


def _default_detector_config() -> dict[str, Any]:
    return {
        "rows": 4,
        "cols": 4,
        "mapping": "Row-major",
        "reducer": "Mean",
        "signal_map": "",
    }


def _new_subplot(df: pd.DataFrame | None = None, *, index: int | None = None) -> dict[str, Any]:
    subplot_index = int(index or _state["next_subplot_id"])
    selected = default_selected_columns(df) if isinstance(df, pd.DataFrame) and not df.empty else []
    subplot = {
        "id": f"subplot-{subplot_index}",
        "title": f"Plot {subplot_index}",
        "mode": "Time series",
        "selected_columns": list(selected),
        "x_window": None,
        "y_limits": [None, None],
        "x_align": "aligned",
        "show_trigger_markers": True,
        "triggers": [],
        "histogram_bins": 30,
        "spectrum_baseline_cutoff": None,
        "barrier_config": _default_barrier_config(),
        "custom_code": "",
        "detector_config": _default_detector_config(),
        "overlays": [],
    }
    _state["next_subplot_id"] = max(_state["next_subplot_id"], subplot_index + 1)
    return subplot


_state: dict[str, Any] = {
    "file_path": None,
    "folder_path": None,
    "df": None,
    "columns": [],
    "rows": 0,
    "separator": None,
    "timestamp_scale": 1.0,
    "mtime": None,
    "history": [],
    "history_index": -1,
    "layout": {},
    "subplots": [],
    "active_subplot_id": None,
    "next_subplot_id": 1,
}
_state["subplots"] = [_new_subplot()]
_state["active_subplot_id"] = "subplot-1"


def _json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _canonical_mode(value: Any) -> str:
    text = str(value or "Time series").strip()
    return _MODE_ALIASES.get(text.lower(), "Time series")


def _push_history(path: str) -> None:
    history = list(_state.get("history") or [])
    absolute_path = os.path.abspath(path)
    if absolute_path in history:
        history.remove(absolute_path)
    history.insert(0, absolute_path)
    _state["history"] = history[:50]
    _state["history_index"] = 0


def _normalize_window(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        lo = float(value[0])
        hi = float(value[1])
    except Exception:
        return None
    if not math.isfinite(lo) or not math.isfinite(hi) or lo == hi:
        return None
    return [float(min(lo, hi)), float(max(lo, hi))]


def _normalize_y_limits(value: Any) -> list[float | None]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return [None, None]
    out: list[float | None] = []
    for item in value:
        try:
            numeric = None if item in (None, "") else float(item)
        except Exception:
            numeric = None
        out.append(numeric if numeric is not None and math.isfinite(numeric) else None)
    return out


def _normalize_triggers(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in list(value or []):
        if not isinstance(item, dict):
            continue
        try:
            x_value = float(item.get("x_value", item.get("xValue")))
        except Exception:
            continue
        out.append(
            {
                "x_value": x_value,
                "label": str(item.get("label") or f"Trigger {len(out) + 1}"),
                "active": bool(item.get("active")),
            }
        )
    return out


def _normalize_barrier_config(value: Any) -> dict[str, dict[str, Any]]:
    result = _default_barrier_config()
    if not isinstance(value, dict):
        return result
    for key in ("abs", "rel"):
        source = value.get(key)
        if not isinstance(source, dict):
            continue
        target = result[key]
        target["enabled"] = bool(source.get("enabled"))
        for field in ("target", "limit_in", "limit_out"):
            try:
                target[field] = float(source.get(field, target[field]))
            except Exception:
                pass
        for field in ("start_idx", "end_idx"):
            try:
                target[field] = int(float(source.get(field, target[field])))
            except Exception:
                pass
    return result


def _normalize_detector_config(value: Any) -> dict[str, Any]:
    result = _default_detector_config()
    if not isinstance(value, dict):
        return result
    try:
        result["rows"] = max(1, min(128, int(float(value.get("rows", result["rows"])))))
    except Exception:
        pass
    try:
        result["cols"] = max(1, min(128, int(float(value.get("cols", result["cols"])))))
    except Exception:
        pass
    result["mapping"] = str(value.get("mapping") or result["mapping"])
    result["reducer"] = str(value.get("reducer") or result["reducer"])
    result["signal_map"] = str(value.get("signal_map") or result["signal_map"])
    return result


def _selected_columns(df: pd.DataFrame | None, requested: Any) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    available = {str(column) for column in numeric_signal_columns(df)}
    selected = [str(column) for column in list(requested or []) if str(column) in available]
    return selected or default_selected_columns(df)


def _overlay_summary_items(overlays: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for index, overlay in enumerate(list(overlays or [])):
        df = overlay.get("df")
        if not isinstance(df, pd.DataFrame):
            continue
        summary.append(
            {
                "index": index,
                "path": overlay.get("path"),
                "label": overlay.get("label") or pathlib.Path(str(overlay.get("path") or "overlay")).stem,
                "enabled": bool(overlay.get("enabled", True)),
                "x_shift_s": float(overlay.get("x_shift_s") or 0.0),
                "y_shift": float(overlay.get("y_shift") or 0.0),
                "columns": [str(column) for column in df.columns],
                "rows": int(len(df)),
            }
        )
    return summary


def _subplot_public_state(subplot: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": subplot["id"],
        "title": subplot["title"],
        "mode": subplot["mode"],
        "selected_columns": list(subplot.get("selected_columns") or []),
        "x_window": subplot.get("x_window"),
        "y_limits": list(subplot.get("y_limits") or [None, None]),
        "x_align": subplot.get("x_align") or "aligned",
        "show_trigger_markers": bool(subplot.get("show_trigger_markers", True)),
        "triggers": list(subplot.get("triggers") or []),
        "histogram_bins": int(subplot.get("histogram_bins") or 30),
        "spectrum_baseline_cutoff": subplot.get("spectrum_baseline_cutoff"),
        "barrier_config": subplot.get("barrier_config") or _default_barrier_config(),
        "custom_code": str(subplot.get("custom_code") or ""),
        "detector_config": subplot.get("detector_config") or _default_detector_config(),
        "overlays": _overlay_summary_items(list(subplot.get("overlays") or [])),
    }


def _sanitize_subplot(subplot: dict[str, Any], df: pd.DataFrame | None) -> dict[str, Any]:
    clean = _new_subplot(df)
    clean["id"] = str(subplot.get("id") or clean["id"])
    clean["title"] = str(subplot.get("title") or clean["title"])
    clean["mode"] = _canonical_mode(subplot.get("mode"))
    clean["selected_columns"] = _selected_columns(df, subplot.get("selected_columns"))
    clean["x_window"] = _normalize_window(subplot.get("x_window"))
    clean["y_limits"] = _normalize_y_limits(subplot.get("y_limits"))
    clean["x_align"] = "independent" if str(subplot.get("x_align") or "aligned").lower() == "independent" else "aligned"
    clean["show_trigger_markers"] = bool(subplot.get("show_trigger_markers", True))
    clean["triggers"] = _normalize_triggers(subplot.get("triggers"))
    try:
        clean["histogram_bins"] = max(1, min(512, int(float(subplot.get("histogram_bins", clean["histogram_bins"])))))
    except Exception:
        pass
    try:
        cutoff_value = subplot.get("spectrum_baseline_cutoff")
        clean["spectrum_baseline_cutoff"] = None if cutoff_value in (None, "") else float(cutoff_value)
    except Exception:
        clean["spectrum_baseline_cutoff"] = None
    clean["barrier_config"] = _normalize_barrier_config(subplot.get("barrier_config"))
    clean["custom_code"] = str(subplot.get("custom_code") or "")
    clean["detector_config"] = _normalize_detector_config(subplot.get("detector_config"))

    overlays: list[dict[str, Any]] = []
    for overlay in list(subplot.get("overlays") or []):
        if not isinstance(overlay, dict):
            continue
        overlay_df = overlay.get("df")
        if not isinstance(overlay_df, pd.DataFrame):
            continue
        overlays.append(
            {
                "path": overlay.get("path"),
                "label": str(overlay.get("label") or pathlib.Path(str(overlay.get("path") or "overlay")).stem),
                "enabled": bool(overlay.get("enabled", True)),
                "x_shift_s": float(overlay.get("x_shift_s") or 0.0),
                "y_shift": float(overlay.get("y_shift") or 0.0),
                "df": overlay_df,
            }
        )
    clean["overlays"] = overlays
    return clean


def _ensure_subplots() -> list[dict[str, Any]]:
    if not _state.get("subplots"):
        _state["subplots"] = [_new_subplot(_state.get("df"))]
    df = _state.get("df")
    _state["subplots"] = [_sanitize_subplot(subplot, df) for subplot in list(_state.get("subplots") or [])]
    active_id = _state.get("active_subplot_id")
    if not any(subplot["id"] == active_id for subplot in _state["subplots"]):
        _state["active_subplot_id"] = _state["subplots"][0]["id"]
    return _state["subplots"]


def _get_subplot(subplot_id: str | None = None) -> dict[str, Any]:
    subplots = _ensure_subplots()
    requested = subplot_id or _state.get("active_subplot_id")
    for subplot in subplots:
        if subplot["id"] == requested:
            return subplot
    return subplots[0]


def _resolve_subplot_request() -> dict[str, Any]:
    subplot_id = request.args.get("subplot_id")
    if not subplot_id:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            subplot_id = body.get("subplot_id")
    return _get_subplot(str(subplot_id) if subplot_id else None)


def _read_loaded_file(path: str) -> dict[str, Any]:
    df = read_signal_file(path)
    timestamp_scale = 1.0
    if "Timestamp" in df.columns:
        try:
            timestamp_scale = float(compute_timestamp_scale(df) or 1.0)
        except Exception:
            timestamp_scale = 1.0

    _state["file_path"] = os.path.abspath(path)
    _state["df"] = df
    _state["columns"] = [str(column) for column in df.columns]
    _state["rows"] = int(len(df))
    _state["separator"] = None
    _state["timestamp_scale"] = float(timestamp_scale)
    try:
        _state["mtime"] = cli_base_path(path).stat().st_mtime
    except Exception:
        _state["mtime"] = None
    _push_history(path)
    _ensure_subplots()

    try:
        file_size = cli_base_path(path).stat().st_size
    except Exception:
        file_size = None

    return {
        "path": _state["file_path"],
        "columns": _state["columns"],
        "rows": _state["rows"],
        "separator": _state["separator"],
        "timestamp_scale": _state["timestamp_scale"],
        "file_size": file_size,
    }


def _time_series_scene(subplot: dict[str, Any]) -> PlotScene:
    primary_df = _state.get("df")
    if not isinstance(primary_df, pd.DataFrame):
        return PlotScene(title=subplot["title"], x_label="Sample", y_label="Signal", time_scale=False, series=[])

    selected = _selected_columns(primary_df, subplot.get("selected_columns"))
    entries = _panel_file_entries(subplot)
    scene_series: list[PlotSeriesScene] = []
    x_label = "Sample"
    time_scale = False
    color_index = 0

    for entry in entries:
        x_raw, current_x_label, current_time_scale = build_x_series(entry.df)
        x_series = pd.to_numeric(x_raw, errors="coerce")
        if subplot.get("x_align") == "independent":
            finite_x = x_series.dropna()
            if not finite_x.empty:
                x_series = x_series - float(finite_x.iloc[0])
        if float(entry.x_shift_s or 0.0):
            x_series = x_series + float(entry.x_shift_s)

        if current_x_label:
            x_label = current_x_label
        time_scale = time_scale or bool(current_time_scale)

        available_columns = [column for column in selected if column in entry.df.columns]
        for column in available_columns:
            y_series = pd.to_numeric(entry.df[column], errors="coerce")
            if float(entry.y_shift or 0.0):
                y_series = y_series + float(entry.y_shift)
            frame = pd.DataFrame({"x": x_series, "y": y_series}).dropna()
            if frame.empty:
                continue
            label = str(column)
            if entry.label != "Primary":
                label = f"{entry.label}:{column}"
            scene_series.append(
                PlotSeriesScene(
                    label=label,
                    color=series_color(color_index),
                    x_values=frame["x"].astype(float).tolist(),
                    y_values=frame["y"].astype(float).tolist(),
                )
            )
            color_index += 1

    return PlotScene(
        title=str(subplot.get("title") or "CSV Plotter"),
        x_label=x_label,
        y_label="Signal",
        time_scale=time_scale,
        series=scene_series,
    )


def _panel_file_entries(subplot: dict[str, Any]) -> list[PanelFileEntry]:
    primary_df = _state.get("df")
    if not isinstance(primary_df, pd.DataFrame):
        return []

    entries = [
        PanelFileEntry(
            path=str(_state.get("file_path") or ""),
            label="Primary",
            df=primary_df,
            enabled=True,
            x_shift_s=0.0,
            y_shift=0.0,
        )
    ]
    for overlay in list(subplot.get("overlays") or []):
        overlay_df = overlay.get("df")
        if not isinstance(overlay_df, pd.DataFrame):
            continue
        entries.append(
            PanelFileEntry(
                path=str(overlay.get("path") or ""),
                label=str(overlay.get("label") or pathlib.Path(str(overlay.get("path") or "overlay")).stem),
                df=overlay_df,
                enabled=bool(overlay.get("enabled", True)),
                x_shift_s=float(overlay.get("x_shift_s") or 0.0),
                y_shift=float(overlay.get("y_shift") or 0.0),
            )
        )
    return entries


def _window_tuple(subplot: dict[str, Any]) -> tuple[float, float] | None:
    x_window = subplot.get("x_window")
    if isinstance(x_window, list) and len(x_window) == 2:
        try:
            return (float(x_window[0]), float(x_window[1]))
        except Exception:
            return None
    return None


def _y_limits_tuple(subplot: dict[str, Any]) -> tuple[float | None, float | None] | None:
    y_limits = subplot.get("y_limits")
    if isinstance(y_limits, list) and len(y_limits) == 2:
        return (y_limits[0], y_limits[1])
    return None


def _panel_payload(subplot: dict[str, Any]) -> dict[str, Any]:
    entries = _panel_file_entries(subplot)
    selected = list(subplot.get("selected_columns") or [])
    x_window = _window_tuple(subplot)
    x_align = str(subplot.get("x_align") or "aligned")
    mode = subplot.get("mode")

    if mode == "Histogram":
        return build_histogram_panel_payload(
            entries,
            selected,
            bins=int(subplot.get("histogram_bins") or 30),
            x_window=x_window,
            x_align=x_align,
        )
    if mode == "Spectrum":
        return build_spectrum_panel_payload(
            entries,
            selected,
            baseline_cutoff=subplot.get("spectrum_baseline_cutoff"),
            x_window=x_window,
            x_align=x_align,
        )
    if mode == "Absolute check":
        return build_abs_check_panel_payload(
            entries,
            selected,
            barrier_config=subplot.get("barrier_config"),
            x_window=x_window,
            x_align=x_align,
        )
    if mode == "Relative change":
        return build_rel_change_panel_payload(
            entries,
            selected,
            barrier_config=subplot.get("barrier_config"),
            x_window=x_window,
            x_align=x_align,
        )
    if mode == "Custom code":
        return build_custom_panel_payload(
            entries,
            selected,
            code=str(subplot.get("custom_code") or ""),
            x_window=x_window,
            x_align=x_align,
        )
    if mode == "Detector map":
        return build_detector_panel_payload(
            entries,
            selected,
            detector_config=subplot.get("detector_config"),
            x_window=x_window,
            x_align=x_align,
        )
    return build_stats_panel_payload(entries, selected, x_window=x_window, x_align=x_align)


def _metrics_for_columns(columns: list[str], x_window: list[float] | None = None) -> dict[str, dict[str, Any] | None]:
    df = _state.get("df")
    if not isinstance(df, pd.DataFrame):
        return {}

    results: dict[str, dict[str, Any] | None] = {}
    for column in columns:
        if column not in df.columns or column == "Timestamp":
            continue
        y = pd.to_numeric(df[column], errors="coerce")
        x = (
            pd.to_numeric(df["Timestamp"], errors="coerce")
            if "Timestamp" in df.columns
            else pd.Series(range(len(df)), dtype=float)
        )
        if x_window and len(x_window) == 2:
            try:
                lo, hi = float(x_window[0]), float(x_window[1])
                mask = (x >= lo) & (x <= hi)
                x = x.where(mask)
                y = y.where(mask)
            except Exception:
                pass
        y_clean = y.dropna()
        x_clean = x.loc[y_clean.index]
        if y_clean.empty:
            results[column] = None
            continue
        metrics = compute_signal_metrics(x_clean, y_clean)
        results[column] = {
            "min": metrics[0],
            "max": metrics[1],
            "avg": metrics[2],
            "med": metrics[3],
            "p2p": metrics[4],
            "std": metrics[5],
            "rms": metrics[6],
            "crest": metrics[7],
            "freq": metrics[8],
            "period": metrics[9],
        }
    return results


def _app_state() -> dict[str, Any]:
    file_size = None
    file_path = _state.get("file_path")
    if file_path:
        try:
            file_size = cli_base_path(file_path).stat().st_size
        except Exception:
            file_size = None
    return {
        "path": file_path,
        "folder": _state.get("folder_path"),
        "rows": _state.get("rows"),
        "cols": len(_state.get("columns") or []),
        "columns": list(_state.get("columns") or []),
        "separator": _state.get("separator"),
        "timestamp_scale": _state.get("timestamp_scale"),
        "mtime": _state.get("mtime"),
        "file_size": file_size,
        "supported_extensions": list(supported_signal_suffixes()),
        "modes": list(_PLOT_MODES),
        "active_subplot_id": _state.get("active_subplot_id"),
        "subplots": [_subplot_public_state(subplot) for subplot in _ensure_subplots()],
    }


def _render_mode_response(subplot: dict[str, Any], *, fmt: str, width: int, height: int) -> Response:
    fmt_normalized = str(fmt or "png").strip().lower()
    if subplot.get("mode") in _TIME_SERIES_MODES:
        scene = _time_series_scene(subplot)
        payload = render_plot_scene_image(
            scene,
            fmt=fmt_normalized,
            width=width,
            height=height,
            x_window=_window_tuple(subplot),
            y_limits=_y_limits_tuple(subplot),
            show_triggers=bool(subplot.get("show_trigger_markers", True)),
        )
    else:
        payload = render_panel_payload_image(_panel_payload(subplot), fmt=fmt_normalized, width=width, height=height)
    mime = "image/svg+xml" if fmt_normalized == "svg" else "image/png"
    return Response(payload, mimetype=mime)


def _filtered_primary_frame(subplot: dict[str, Any]) -> pd.DataFrame:
    df = _state.get("df")
    if not isinstance(df, pd.DataFrame):
        raise RuntimeError("No signal file loaded")
    selected = [column for column in list(subplot.get("selected_columns") or []) if column in df.columns]
    columns = list(selected)
    if "Timestamp" in df.columns:
        columns = ["Timestamp", *columns]
    export_df = df.loc[:, columns] if columns else df.copy()
    x_window = _window_tuple(subplot)
    if x_window and "Timestamp" in export_df.columns:
        x_numeric = pd.to_numeric(export_df["Timestamp"], errors="coerce")
        mask = (x_numeric >= x_window[0]) & (x_numeric <= x_window[1])
        export_df = export_df.loc[mask.fillna(False)]
    return export_df.reset_index(drop=True)


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/app-state")
def app_state() -> Response:
    return jsonify(_app_state())


@bp.route("/api/modes")
def modes() -> Response:
    return jsonify({"modes": list(_PLOT_MODES)})


@bp.route("/api/csv/load", methods=["POST"])
def csv_load() -> Response:
    body = _json_body()
    path = str(body.get("path") or "").strip()
    if not path or not cli_base_path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        return jsonify(_read_loaded_file(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/csv/load-folder", methods=["POST"])
def csv_load_folder() -> Response:
    body = _json_body()
    folder = str(body.get("folder") or "").strip()
    if not folder or not pathlib.Path(folder).is_dir():
        return jsonify({"error": f"Folder not found: {folder}"}), 404
    try:
        newest = find_newest_signal_file(folder)
        info = _read_loaded_file(newest)
        _state["folder_path"] = os.path.abspath(folder)
        return jsonify(info)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/csv/reload", methods=["POST"])
def csv_reload() -> Response:
    path = _state.get("file_path")
    if not path:
        return jsonify({"error": "No file loaded"}), 400
    if not cli_base_path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        return jsonify(_read_loaded_file(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/csv/check-mtime")
def csv_check_mtime() -> Response:
    path = _state.get("file_path")
    if not path:
        return jsonify({"changed": False})
    try:
        current_mtime = cli_base_path(path).stat().st_mtime
        changed = _state.get("mtime") is None or current_mtime > _state.get("mtime")
        return jsonify({"changed": changed, "mtime": current_mtime})
    except Exception:
        return jsonify({"changed": False})


@bp.route("/api/csv/columns")
def csv_columns() -> Response:
    return jsonify({"columns": list(_state.get("columns") or [])})


@bp.route("/api/csv/info")
def csv_info() -> Response:
    return jsonify(_app_state())


@bp.route("/api/csv/data", methods=["POST"])
def csv_data() -> Response:
    body = _json_body()
    subplot = _get_subplot(body.get("subplot_id"))
    df = _state.get("df")
    if not isinstance(df, pd.DataFrame):
        return jsonify({"error": "No CSV loaded"}), 400

    columns = _selected_columns(df, body.get("columns") or subplot.get("selected_columns"))
    x_range = _normalize_window(body.get("x_range") or subplot.get("x_window"))
    max_points = max(100, int(body.get("max_points") or 5000))

    x = (
        pd.to_numeric(df["Timestamp"], errors="coerce")
        if "Timestamp" in df.columns
        else pd.Series(range(len(df)), dtype=float)
    )
    mask = None
    if x_range:
        mask = (x >= x_range[0]) & (x <= x_range[1])
    x_out = x if mask is None else x[mask]
    step = max(1, len(x_out) // max_points) if len(x_out) > max_points else 1
    x_ds = x_out.iloc[::step] if step > 1 else x_out

    series_out: dict[str, list[Any]] = {}
    for column in columns:
        y = pd.to_numeric(df[column], errors="coerce")
        if mask is not None:
            y = y[mask]
        if step > 1:
            y = y.iloc[::step]
        series_out[column] = y.tolist()

    return jsonify(
        {
            "x": x_ds.tolist(),
            "series": series_out,
            "total_rows": int(_state.get("rows") or 0),
            "returned_points": len(x_ds),
        }
    )


@bp.route("/api/csv/metrics", methods=["POST"])
def csv_metrics() -> Response:
    body = _json_body()
    subplot = _get_subplot(body.get("subplot_id"))
    if not isinstance(_state.get("df"), pd.DataFrame):
        return jsonify({"error": "No CSV loaded"}), 400
    columns = _selected_columns(_state.get("df"), body.get("columns") or subplot.get("selected_columns"))
    x_window = _normalize_window(body.get("x_window") or subplot.get("x_window"))
    return jsonify(_metrics_for_columns(columns, x_window))


@bp.route("/api/subplots")
def subplots_list() -> Response:
    return jsonify({"active_subplot_id": _state.get("active_subplot_id"), "subplots": [_subplot_public_state(item) for item in _ensure_subplots()]})


@bp.route("/api/subplots", methods=["POST"])
def subplots_create() -> Response:
    body = _json_body()
    subplot = _new_subplot(_state.get("df"))
    subplot["title"] = str(body.get("title") or subplot["title"])
    subplot["mode"] = _canonical_mode(body.get("mode"))
    subplot["selected_columns"] = _selected_columns(_state.get("df"), body.get("selected_columns"))
    _state["subplots"].append(subplot)
    _state["active_subplot_id"] = subplot["id"]
    _ensure_subplots()
    return jsonify({"subplot": _subplot_public_state(subplot), "active_subplot_id": subplot["id"]})


@bp.route("/api/subplots/import", methods=["POST"])
def subplots_import() -> Response:
    body = _json_body()
    imported = []
    for item in list(body.get("subplots") or []):
        if isinstance(item, dict):
            imported.append(_sanitize_subplot(item, _state.get("df")))
    _state["subplots"] = imported or [_new_subplot(_state.get("df"))]
    try:
        next_id = max(int(str(item["id"]).split("-")[-1]) for item in _state["subplots"]) + 1
    except Exception:
        next_id = len(_state["subplots"]) + 1
    _state["next_subplot_id"] = max(_state["next_subplot_id"], next_id)
    requested_active = str(body.get("active_subplot_id") or "")
    _state["active_subplot_id"] = requested_active or _state["subplots"][0]["id"]
    _ensure_subplots()
    return jsonify({"active_subplot_id": _state.get("active_subplot_id"), "subplots": [_subplot_public_state(item) for item in _state["subplots"]]})


@bp.route("/api/subplots/<subplot_id>")
def subplot_get(subplot_id: str) -> Response:
    subplot = _get_subplot(subplot_id)
    _state["active_subplot_id"] = subplot["id"]
    return jsonify({"subplot": _subplot_public_state(subplot)})


@bp.route("/api/subplots/<subplot_id>", methods=["PATCH"])
def subplot_patch(subplot_id: str) -> Response:
    subplot = _get_subplot(subplot_id)
    body = _json_body()
    updates = dict(subplot)
    updates.update({key: value for key, value in body.items() if key != "id"})
    clean = _sanitize_subplot(updates, _state.get("df"))
    clean["id"] = subplot["id"]
    for index, candidate in enumerate(_state["subplots"]):
        if candidate["id"] == subplot["id"]:
            _state["subplots"][index] = clean
            break
    _state["active_subplot_id"] = clean["id"]
    return jsonify({"subplot": _subplot_public_state(clean)})


@bp.route("/api/subplots/<subplot_id>", methods=["DELETE"])
def subplot_delete(subplot_id: str) -> Response:
    _state["subplots"] = [item for item in _ensure_subplots() if item["id"] != subplot_id]
    if not _state["subplots"]:
        _state["subplots"] = [_new_subplot(_state.get("df"))]
    _state["active_subplot_id"] = _state["subplots"][0]["id"]
    return jsonify({"active_subplot_id": _state.get("active_subplot_id"), "subplots": [_subplot_public_state(item) for item in _state["subplots"]]})


@bp.route("/api/subplots/<subplot_id>/scene")
def subplot_scene(subplot_id: str) -> Response:
    subplot = _get_subplot(subplot_id)
    scene = _time_series_scene(subplot)
    model = build_browser_plot_model(
        scene,
        x_window=_window_tuple(subplot),
        active_series=(subplot.get("selected_columns") or [None])[0],
        y_limits=_y_limits_tuple(subplot),
        show_trigger_markers=bool(subplot.get("show_trigger_markers", True)),
    )
    return jsonify({"subplot": _subplot_public_state(subplot), "scene": model})


@bp.route("/api/subplots/<subplot_id>/panel")
def subplot_panel(subplot_id: str) -> Response:
    subplot = _get_subplot(subplot_id)
    return jsonify({"subplot": _subplot_public_state(subplot), "payload": _panel_payload(subplot)})


@bp.route("/api/subplots/<subplot_id>/render")
def subplot_render(subplot_id: str) -> Response:
    subplot = _get_subplot(subplot_id)
    width = max(320, int(request.args.get("width", 1200)))
    height = max(240, int(request.args.get("height", 700)))
    fmt = str(request.args.get("fmt", "png"))
    try:
        return _render_mode_response(subplot, fmt=fmt, width=width, height=height)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/subplots/<subplot_id>/export-data", methods=["POST"])
def subplot_export_data(subplot_id: str) -> Response:
    subplot = _get_subplot(subplot_id)
    body = _json_body()
    fmt = str(body.get("format") or "csv").strip().lower()
    try:
        export_df = _filtered_primary_frame(subplot)
        suffix = ".jsonl" if fmt == "ndjson" else f".{fmt}"
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        handle.close()
        try:
            write_dataframe_export(export_df, handle.name, fmt)
            payload = pathlib.Path(handle.name).read_bytes()
        finally:
            try:
                pathlib.Path(handle.name).unlink(missing_ok=True)
            except Exception:
                pass
        file_stem = default_cli_output_stem(str(_state.get("file_path") or "signal"), _state.get("df"))
        x_window = _window_tuple(subplot)
        if x_window:
            file_stem = f"{file_stem}_{format_window_bound_for_filename(x_window[0])}_{format_window_bound_for_filename(x_window[1])}"
        download_name = f"{file_stem}{suffix}"
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    mime_map = {
        "csv": "text/csv",
        "txt": "text/plain",
        "json": "application/json",
        "jsonl": "application/x-ndjson",
        "ndjson": "application/x-ndjson",
        "parquet": "application/octet-stream",
        "feather": "application/octet-stream",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "h5": "application/octet-stream",
        "hdf": "application/octet-stream",
        "hdf5": "application/octet-stream",
        "npz": "application/octet-stream",
        "mat": "application/octet-stream",
        "tdms": "application/octet-stream",
    }
    response = Response(payload, mimetype=mime_map.get(fmt, "application/octet-stream"))
    response.headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return response


@bp.route("/api/export/combined", methods=["POST"])
def export_combined() -> Response:
    body = _json_body()
    fmt = str(body.get("format") or "png").strip().lower()
    width = max(320, int(body.get("width") or 1400))
    height_per_plot = max(200, int(body.get("height_per_plot") or 420))
    requested_ids = {str(item) for item in list(body.get("subplot_ids") or [])}
    items: list[dict[str, Any]] = []
    for subplot in _ensure_subplots():
        if requested_ids and subplot["id"] not in requested_ids:
            continue
        if subplot.get("mode") in _TIME_SERIES_MODES:
            items.append(
                {
                    "kind": "scene",
                    "title": subplot.get("title"),
                    "scene": _time_series_scene(subplot),
                    "x_window": _window_tuple(subplot),
                    "y_limits": _y_limits_tuple(subplot),
                    "show_triggers": bool(subplot.get("show_trigger_markers", True)),
                }
            )
        else:
            items.append({"kind": "payload", "title": subplot.get("title"), "payload": _panel_payload(subplot)})
    if not items:
        return jsonify({"error": "No subplots available for export"}), 400
    try:
        payload = render_combined_browser_export_image(items, fmt=fmt, width=width, height_per_plot=height_per_plot)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    mime = "image/svg+xml" if fmt == "svg" else "image/png"
    response = Response(payload, mimetype=mime)
    response.headers["Content-Disposition"] = f'attachment; filename="csv_plotter_combined.{fmt}"'
    return response


@bp.route("/api/overlay/add", methods=["POST"])
def overlay_add() -> Response:
    body = _json_body()
    subplot = _get_subplot(body.get("subplot_id"))
    path = str(body.get("path") or "").strip()
    if not path or not cli_base_path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        overlay_df = read_signal_file(path)
        subplot["overlays"].append(
            {
                "path": os.path.abspath(path),
                "label": str(body.get("label") or pathlib.Path(path).stem),
                "enabled": bool(body.get("enabled", True)),
                "x_shift_s": float(body.get("x_shift_s") or 0.0),
                "y_shift": float(body.get("y_shift") or 0.0),
                "df": overlay_df,
            }
        )
        return jsonify({"files": _overlay_summary_items(subplot["overlays"])})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/overlay/<int:idx>", methods=["PATCH"])
def overlay_patch(idx: int) -> Response:
    subplot = _resolve_subplot_request()
    if not 0 <= idx < len(subplot["overlays"]):
        return jsonify({"error": "Overlay not found"}), 404
    body = _json_body()
    overlay = subplot["overlays"][idx]
    overlay["label"] = str(body.get("label") or overlay.get("label") or pathlib.Path(str(overlay.get("path") or "overlay")).stem)
    overlay["enabled"] = bool(body.get("enabled", overlay.get("enabled", True)))
    try:
        overlay["x_shift_s"] = float(body.get("x_shift_s", overlay.get("x_shift_s", 0.0)) or 0.0)
    except Exception:
        pass
    try:
        overlay["y_shift"] = float(body.get("y_shift", overlay.get("y_shift", 0.0)) or 0.0)
    except Exception:
        pass
    return jsonify({"files": _overlay_summary_items(subplot["overlays"])})


@bp.route("/api/overlay/<int:idx>", methods=["DELETE"])
def overlay_remove(idx: int) -> Response:
    subplot = _resolve_subplot_request()
    if 0 <= idx < len(subplot["overlays"]):
        subplot["overlays"].pop(idx)
    return jsonify({"files": _overlay_summary_items(subplot["overlays"])})


@bp.route("/api/overlay/list")
def overlay_list() -> Response:
    subplot = _get_subplot(request.args.get("subplot_id"))
    return jsonify({"files": _overlay_summary_items(subplot["overlays"])})


@bp.route("/api/overlay/clear", methods=["POST"])
def overlay_clear() -> Response:
    subplot = _resolve_subplot_request()
    subplot["overlays"] = []
    return jsonify({"files": []})


@bp.route("/api/layout")
def layout_get() -> Response:
    if _LAYOUT_PATH.exists():
        try:
            data = json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))
            _state["layout"] = data
            return jsonify(data)
        except Exception:
            logger.debug("Failed to parse stored csv_plotter layout", exc_info=True)
    return jsonify(_state.get("layout") or {})


@bp.route("/api/layout", methods=["POST"])
def layout_save() -> Response:
    data = _json_body()
    _state["layout"] = data
    try:
        tmp = _LAYOUT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            tmp.replace(_LAYOUT_PATH)
        except Exception:
            _LAYOUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"success": True})


@bp.route("/api/layout", methods=["DELETE"])
def layout_clear() -> Response:
    _state["layout"] = {}
    try:
        if _LAYOUT_PATH.exists():
            _LAYOUT_PATH.unlink()
    except Exception:
        logger.debug("Failed to remove csv_plotter layout file", exc_info=True)
    return jsonify({"success": True})


@bp.route("/api/history")
def history_get() -> Response:
    return jsonify({"files": _state.get("history") or [], "index": _state.get("history_index", -1)})


@bp.route("/api/history/navigate", methods=["POST"])
def history_navigate() -> Response:
    body = _json_body()
    direction = str(body.get("direction") or "prev")
    history = list(_state.get("history") or [])
    index = int(_state.get("history_index", -1))
    if direction == "prev":
        index = min(index + 1, len(history) - 1)
    else:
        index = max(index - 1, 0)
    _state["history_index"] = index
    if 0 <= index < len(history):
        path = history[index]
        if cli_base_path(path).is_file():
            try:
                info = _read_loaded_file(path)
                _state["history_index"] = index
                return jsonify({"path": path, "index": index, **info})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
    return jsonify({"path": None, "index": index})


@bp.route("/api/history/clear", methods=["POST"])
def history_clear() -> Response:
    _state["history"] = []
    _state["history_index"] = -1
    return jsonify({"success": True})


@bp.route("/api/browse/roots")
def browse_roots() -> Response:
    roots: list[dict[str, str]] = []
    if platform.system() == "Windows":
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if pathlib.Path(drive).exists():
                roots.append({"name": f"{letter}:", "path": drive})
    else:
        roots.append({"name": "/", "path": "/"})
    return jsonify({"roots": roots})


@bp.route("/api/folder/browse")
def folder_browse() -> Response:
    path = request.args.get("path", "")
    if not path or not pathlib.Path(path).is_dir():
        return jsonify({"error": "Invalid path"}), 400

    folder_path = pathlib.Path(path).resolve()
    parent = str(folder_path.parent) if folder_path.parent != folder_path else None
    supported = set(supported_signal_suffixes())

    files: list[dict[str, Any]] = []
    folders: list[dict[str, str]] = []
    try:
        for entry in sorted(folder_path.iterdir(), key=lambda candidate: candidate.name.lower()):
            try:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    folders.append({"name": entry.name, "path": str(entry)})
                    continue
                if entry.suffix.lower() not in supported:
                    continue
                stat = entry.stat()
                files.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                )
            except (PermissionError, OSError):
                continue
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"path": str(folder_path), "parent": parent, "files": files, "folders": folders})
