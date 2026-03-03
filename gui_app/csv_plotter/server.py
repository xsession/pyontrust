"""CSV Plotter — Flask backend.

Serves the SPA from ``web/`` and exposes REST JSON endpoints for CSV
loading, metrics computation, plot-data extraction, layout persistence,
and file management.
"""
from __future__ import annotations

import io
import json
import logging
import math
import os
import pathlib
import time
from typing import Any

import pandas as pd
from flask import Flask, Response, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider


class _SafeJSONProvider(DefaultJSONProvider):
    """JSON provider that converts NaN / Infinity to ``null``.

    Python's ``json`` module outputs bare ``NaN`` / ``Infinity`` tokens
    which are *not* valid JSON and make ``Response.json()`` in the
    browser throw a parse error.
    """

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        kwargs.setdefault("allow_nan", False)
        kwargs.setdefault("default", self._default)
        try:
            return json.dumps(obj, **kwargs)
        except ValueError:
            # Fallback: walk the structure and sanitise NaN / Inf
            return json.dumps(self._sanitise(obj), **kwargs)

    @staticmethod
    def _default(o: Any) -> Any:
        """Handle numpy scalars / arrays that slip through."""
        import numpy as np

        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            v = float(o)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(o, np.ndarray):
            return [None if (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else x for x in o.tolist()]
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    @classmethod
    def _sanitise(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: cls._sanitise(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [cls._sanitise(v) for v in obj]
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

# ---------------------------------------------------------------------------
# Domain module imports (reused as-is from the original csv_plotter)
# ---------------------------------------------------------------------------
from data import (
    compute_timestamp_scale_for_df,
    find_newest_csv,
    read_any_csv,
    read_csv_header,
    sniff_csv_separator,
)
from metrics import compute_signal_metrics

from core.model import PlotState
from core.plotting import render_plot_png

from plot_data.main_series import extract_timeseries_traces
from plot_data.histogram import extract_histogram_traces
from plot_data.abs_check import extract_abs_check_traces
from plot_data.rel_change import extract_rel_change_traces
from plot_data.custom_code import extract_custom_code_traces

from lang import STRINGS

logger = logging.getLogger("csv_plotter.server")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

_HERE = pathlib.Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(_HERE / "web"),
    static_url_path="",
)
app.json_provider_class = _SafeJSONProvider
app.json = _SafeJSONProvider(app)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

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
    # Overlay files: list of {"path": str, "df": DataFrame, "scale": float}
    "overlay_files": [],
    # Layout data
    "layout": {},
    "auto_save_layout": True,
}


def _push_history(path: str) -> None:
    """Add *path* to the history stack (most-recent-first)."""
    h = _state["history"]
    absp = os.path.abspath(path)
    if absp in h:
        h.remove(absp)
    h.insert(0, absp)
    _state["history"] = h[:50]  # cap at 50
    _state["history_index"] = 0


def _load_csv(path: str) -> dict:
    """Load a CSV into ``_state`` and return summary dict."""
    sep = sniff_csv_separator(path)
    df = read_any_csv(path, sep=sep)
    ts_scale = compute_timestamp_scale_for_df(df) if "Timestamp" in df.columns else 1.0

    _state["file_path"] = os.path.abspath(path)
    _state["df"] = df
    _state["columns"] = [str(c) for c in df.columns]
    _state["rows"] = len(df)
    _state["separator"] = sep
    _state["timestamp_scale"] = float(ts_scale)
    try:
        _state["mtime"] = pathlib.Path(path).stat().st_mtime
    except Exception:
        _state["mtime"] = None

    _push_history(path)

    # File size for display
    try:
        file_size = pathlib.Path(path).stat().st_size
    except Exception:
        file_size = None

    return {
        "path": _state["file_path"],
        "columns": _state["columns"],
        "rows": _state["rows"],
        "separator": sep,
        "timestamp_scale": float(ts_scale),
        "file_size": file_size,
    }


def _metrics_for_columns(columns: list[str], x_window: list[float] | None = None) -> dict:
    """Compute signal metrics for the given columns."""
    df = _state["df"]
    if df is None:
        return {}

    results: dict[str, dict | None] = {}
    ts_scale = _state["timestamp_scale"] or 1.0

    for col in columns:
        if col not in df.columns or col == "Timestamp":
            continue
        y = pd.to_numeric(df[col], errors="coerce")
        if "Timestamp" in df.columns:
            x = pd.to_numeric(df["Timestamp"], errors="coerce")
        else:
            x = pd.Series(range(len(df)), dtype=float)

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
        if len(y_clean) == 0:
            results[col] = None
            continue

        tup = compute_signal_metrics(x_clean, y_clean)
        results[col] = {
            "min": tup[0], "max": tup[1], "avg": tup[2], "med": tup[3],
            "p2p": tup[4], "std": tup[5], "rms": tup[6], "crest": tup[7],
            "freq": tup[8], "period": tup[9],
        }
    return results


def _build_dfs_list(subplot_cfg: dict | None = None) -> list[dict]:
    """Build the ``dfs`` list used by plot-data extractors.

    Combines the primary loaded DataFrame with any overlay files.
    """
    result: list[dict] = []
    df = _state["df"]
    if df is None:
        return result

    alignment = "aligned"
    shifts: dict = {}
    file_enabled: dict = {}
    if subplot_cfg:
        alignment = subplot_cfg.get("alignment", "aligned")
        shifts = subplot_cfg.get("file_shifts", {})
        file_enabled = subplot_cfg.get("file_enabled", {})

    # Primary file
    path = _state["file_path"] or ""
    cfg = shifts.get(path, {})
    enabled = file_enabled.get(path, True) if file_enabled else True
    result.append({
        "path": path,
        "df": df,
        "scale": _state["timestamp_scale"],
        "alignment": alignment,
        "x_shift_s": float(cfg.get("x_shift_s", 0.0)) if isinstance(cfg, dict) else 0.0,
        "y_shift": float(cfg.get("y_shift", 0.0)) if isinstance(cfg, dict) else 0.0,
        "enabled": enabled,
    })

    # Overlay files
    for ovl in _state["overlay_files"]:
        ovl_path = ovl.get("path", "")
        cfg = shifts.get(ovl_path, {})
        enabled = file_enabled.get(ovl_path, True) if file_enabled else True
        result.append({
            "path": ovl_path,
            "df": ovl["df"],
            "scale": ovl.get("scale", 1.0),
            "alignment": alignment,
            "x_shift_s": float(cfg.get("x_shift_s", 0.0)) if isinstance(cfg, dict) else 0.0,
            "y_shift": float(cfg.get("y_shift", 0.0)) if isinstance(cfg, dict) else 0.0,
            "enabled": enabled,
        })

    return result


# =========================================================================
# Routes — Static
# =========================================================================

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# =========================================================================
# Routes — CSV Data
# =========================================================================

@app.route("/api/csv/load", methods=["POST"])
def csv_load():
    body = request.get_json(force=True)
    path = body.get("path", "")
    if not path or not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        info = _load_csv(path)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/csv/load-folder", methods=["POST"])
def csv_load_folder():
    body = request.get_json(force=True)
    folder = body.get("folder", "")
    recursive = body.get("recursive", True)
    if not folder or not pathlib.Path(folder).is_dir():
        return jsonify({"error": f"Folder not found: {folder}"}), 404
    try:
        newest = find_newest_csv(folder)
        info = _load_csv(newest)
        _state["folder_path"] = os.path.abspath(folder)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/csv/columns")
def csv_columns():
    return jsonify({"columns": _state["columns"]})


@app.route("/api/csv/info")
def csv_info():
    file_size = None
    if _state["file_path"]:
        try:
            file_size = pathlib.Path(_state["file_path"]).stat().st_size
        except Exception:
            pass
    return jsonify({
        "path": _state["file_path"],
        "folder": _state["folder_path"],
        "rows": _state["rows"],
        "cols": len(_state["columns"]),
        "columns": _state["columns"],
        "separator": _state["separator"],
        "timestamp_scale": _state["timestamp_scale"],
        "mtime": _state["mtime"],
        "file_size": file_size,
    })


@app.route("/api/csv/data", methods=["POST"])
def csv_data():
    """Return column data (downsampled) for the frontend."""
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_range = body.get("x_range")
    max_points = int(body.get("max_points", 5000))

    df = _state["df"]
    if df is None:
        return jsonify({"error": "No CSV loaded"}), 400

    # Build X
    if "Timestamp" in df.columns:
        x = pd.to_numeric(df["Timestamp"], errors="coerce")
    else:
        x = pd.Series(range(len(df)), dtype=float)

    mask = None
    if x_range and len(x_range) == 2:
        lo, hi = float(x_range[0]), float(x_range[1])
        mask = (x >= lo) & (x <= hi)

    series_out: dict[str, list] = {}
    x_out = x if mask is None else x[mask]

    # Downsample
    step = max(1, len(x_out) // max_points) if len(x_out) > max_points else 1
    x_ds = x_out.iloc[::step] if step > 1 else x_out

    for col in columns:
        if col not in df.columns:
            continue
        y = pd.to_numeric(df[col], errors="coerce")
        if mask is not None:
            y = y[mask]
        if step > 1:
            y = y.iloc[::step]
        series_out[col] = y.values.tolist()

    return jsonify({
        "x": x_ds.values.tolist(),
        "series": series_out,
        "total_rows": _state["rows"],
        "returned_points": len(x_ds),
    })


@app.route("/api/csv/metrics", methods=["POST"])
def csv_metrics():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_window = body.get("x_window")
    if _state["df"] is None:
        return jsonify({"error": "No CSV loaded"}), 400
    return jsonify(_metrics_for_columns(columns, x_window))


@app.route("/api/csv/reload", methods=["POST"])
def csv_reload():
    path = _state["file_path"]
    if not path:
        return jsonify({"error": "No file loaded"}), 400
    if not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        info = _load_csv(path)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/csv/check-mtime")
def csv_check_mtime():
    path = _state["file_path"]
    if not path:
        return jsonify({"changed": False})
    try:
        current_mtime = pathlib.Path(path).stat().st_mtime
        changed = _state["mtime"] is None or current_mtime > _state["mtime"]
        return jsonify({"changed": changed, "mtime": current_mtime})
    except Exception:
        return jsonify({"changed": False})


# =========================================================================
# Routes — Overlay
# =========================================================================

@app.route("/api/overlay/add", methods=["POST"])
def overlay_add():
    body = request.get_json(force=True)
    path = body.get("path", "")
    if not path or not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        sep = sniff_csv_separator(path)
        df = read_any_csv(path, sep=sep)
        scale = compute_timestamp_scale_for_df(df) if "Timestamp" in df.columns else 1.0
        _state["overlay_files"].append({
            "path": os.path.abspath(path),
            "df": df,
            "scale": float(scale),
        })
        files_summary = [
            {"path": o["path"], "columns": [str(c) for c in o["df"].columns], "rows": len(o["df"])}
            for o in _state["overlay_files"]
        ]
        return jsonify({"files": files_summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/overlay/<int:idx>", methods=["DELETE"])
def overlay_remove(idx: int):
    if 0 <= idx < len(_state["overlay_files"]):
        _state["overlay_files"].pop(idx)
    files_summary = [
        {"path": o["path"], "columns": [str(c) for c in o["df"].columns], "rows": len(o["df"])}
        for o in _state["overlay_files"]
    ]
    return jsonify({"files": files_summary})


@app.route("/api/overlay/list")
def overlay_list():
    files_summary = [
        {"path": o["path"], "columns": [str(c) for c in o["df"].columns], "rows": len(o["df"])}
        for o in _state["overlay_files"]
    ]
    return jsonify({"files": files_summary})


@app.route("/api/overlay/clear", methods=["POST"])
def overlay_clear():
    _state["overlay_files"] = []
    return jsonify({"files": []})


# =========================================================================
# Routes — Plot Data (for Plotly.js client-side rendering)
# =========================================================================

@app.route("/api/plot-data/timeseries", methods=["POST"])
def plot_data_timeseries():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_window = body.get("x_window")
    max_points = int(body.get("max_points", 5000))
    subplot_cfg = body.get("subplot_cfg")

    dfs = _build_dfs_list(subplot_cfg)
    if not dfs:
        return jsonify({"traces": [], "metrics": {}, "layout": {}})

    def _compute_metrics(x_s: pd.Series, y_s: pd.Series) -> dict | None:
        x_c = x_s.dropna()
        y_c = y_s.dropna()
        idx = x_c.index.intersection(y_c.index)
        if len(idx) == 0:
            return None
        tup = compute_signal_metrics(x_c.loc[idx], y_c.loc[idx])
        return {
            "min": tup[0], "max": tup[1], "avg": tup[2], "med": tup[3],
            "p2p": tup[4], "std": tup[5], "rms": tup[6], "crest": tup[7],
            "freq": tup[8], "period": tup[9],
        }

    result = extract_timeseries_traces(
        dfs=dfs,
        selected_columns=columns,
        x_window=x_window,
        max_points=max_points,
        compute_metrics_fn=_compute_metrics,
    )
    return jsonify(result)


@app.route("/api/plot-data/histogram", methods=["POST"])
def plot_data_histogram():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_window = body.get("x_window")
    nbins = int(body.get("nbins", 50))
    subplot_cfg = body.get("subplot_cfg")

    dfs = _build_dfs_list(subplot_cfg)
    result = extract_histogram_traces(
        dfs=dfs, selected_columns=columns, x_window=x_window, nbins=nbins,
    )
    return jsonify(result)


@app.route("/api/plot-data/abs-check", methods=["POST"])
def plot_data_abs_check():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    barriers = body.get("barriers")
    max_points = int(body.get("max_points", 5000))
    subplot_cfg = body.get("subplot_cfg")

    dfs = _build_dfs_list(subplot_cfg)
    result = extract_abs_check_traces(
        dfs=dfs, selected_columns=columns, barriers=barriers, max_points=max_points,
    )
    return jsonify(result)


@app.route("/api/plot-data/rel-change", methods=["POST"])
def plot_data_rel_change():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    barriers = body.get("barriers")
    max_points = int(body.get("max_points", 5000))
    subplot_cfg = body.get("subplot_cfg")

    dfs = _build_dfs_list(subplot_cfg)
    result = extract_rel_change_traces(
        dfs=dfs, selected_columns=columns, barriers=barriers, max_points=max_points,
    )
    return jsonify(result)


@app.route("/api/plot-data/custom-code", methods=["POST"])
def plot_data_custom_code():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    code = body.get("code", "")
    x_window = body.get("x_window")
    max_points = int(body.get("max_points", 5000))

    df = _state["df"]
    if df is None:
        return jsonify({"traces": [], "layout": {}, "error": "No CSV loaded"})

    result = extract_custom_code_traces(
        df=df, selected_columns=columns, code=code,
        x_window=x_window, max_points=max_points,
    )
    return jsonify(result)


# =========================================================================
# Routes — Plot Rendering (server-side matplotlib for export)
# =========================================================================

@app.route("/api/plot/png", methods=["POST"])
def plot_png():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    width = int(body.get("width", 1200))
    height = int(body.get("height", 700))
    title = body.get("title")

    df = _state["df"]
    if df is None:
        return jsonify({"error": "No CSV loaded"}), 400

    png_bytes = render_plot_png(df, columns, width=width, height=height, title=title)
    return Response(png_bytes, mimetype="image/png")


@app.route("/api/plot/svg", methods=["POST"])
def plot_svg():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    width = int(body.get("width", 1200))
    height = int(body.get("height", 700))
    title = body.get("title")

    df = _state["df"]
    if df is None:
        return jsonify({"error": "No CSV loaded"}), 400

    # Reuse the headless renderer infrastructure
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

    fig = Figure(figsize=(max(2, width / 100), max(2, height / 100)), dpi=100)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(1, 1, 1)

    if "Timestamp" in df.columns:
        x = pd.to_numeric(df["Timestamp"], errors="coerce")
        xlabel = "Timestamp"
    else:
        x = df.index.to_series()
        xlabel = "Index"

    cols = [c for c in columns if c in df.columns] or list(df.columns[:1])
    n = len(df)
    step = max(1, n // 300_000) if n > 300_000 else 1
    if step > 1:
        df_plot = df.iloc[::step]
        x_plot = x.iloc[::step]
    else:
        df_plot = df
        x_plot = x

    for col in cols:
        y = pd.to_numeric(df_plot[col], errors="coerce")
        ax.plot(x_plot, y, label=str(col), linewidth=1.0)

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Value")
    if title:
        ax.set_title(title)
    if len(cols) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="svg")
    return Response(buf.getvalue(), mimetype="image/svg+xml")


# =========================================================================
# Routes — Layout & Settings
# =========================================================================

_LAYOUT_PATH = _HERE / "layout.json"


@app.route("/api/layout")
def layout_get():
    # Try to load from disk first
    if _LAYOUT_PATH.exists():
        try:
            data = json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))
            _state["layout"] = data
            return jsonify(data)
        except Exception:
            pass
    return jsonify(_state.get("layout", {}))


@app.route("/api/layout", methods=["POST"])
def layout_save():
    data = request.get_json(force=True)
    _state["layout"] = data
    try:
        # Atomic write
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})


@app.route("/api/layout", methods=["DELETE"])
def layout_clear():
    _state["layout"] = {}
    try:
        if _LAYOUT_PATH.exists():
            _LAYOUT_PATH.unlink()
    except Exception:
        pass
    return jsonify({"success": True})


# =========================================================================
# Routes — History
# =========================================================================

@app.route("/api/history")
def history_get():
    return jsonify({
        "files": _state["history"],
        "index": _state["history_index"],
    })


@app.route("/api/history/navigate", methods=["POST"])
def history_navigate():
    body = request.get_json(force=True)
    direction = body.get("direction", "prev")
    h = _state["history"]
    idx = _state["history_index"]

    if direction == "prev":
        idx = min(idx + 1, len(h) - 1)
    else:
        idx = max(idx - 1, 0)

    _state["history_index"] = idx
    if 0 <= idx < len(h):
        path = h[idx]
        if pathlib.Path(path).is_file():
            try:
                info = _load_csv(path)
                _state["history_index"] = idx  # restore after _load_csv pushes
                return jsonify({"path": path, "index": idx, **info})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    return jsonify({"path": None, "index": idx})


@app.route("/api/history/clear", methods=["POST"])
def history_clear():
    _state["history"] = []
    _state["history_index"] = -1
    return jsonify({"success": True})


# =========================================================================
# Routes — Utilities
# =========================================================================

@app.route("/api/strings")
def get_strings():
    return jsonify(STRINGS)


@app.route("/api/browse/roots")
def browse_roots():
    """Return available filesystem roots (drive letters on Windows, / on Unix)."""
    import platform
    roots: list[dict] = []
    if platform.system() == "Windows":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if pathlib.Path(drive).exists():
                roots.append({"name": f"{letter}:", "path": drive})
    else:
        roots.append({"name": "/", "path": "/"})
    return jsonify({"roots": roots})


@app.route("/api/folder/browse")
def folder_browse():
    path = request.args.get("path", "")
    if not path or not pathlib.Path(path).is_dir():
        return jsonify({"error": "Invalid path"}), 400

    p = pathlib.Path(path).resolve()
    parent = str(p.parent) if p.parent != p else None

    files: list[dict] = []
    folders: list[dict] = []
    try:
        for entry in sorted(p.iterdir(), key=lambda e: e.name.lower()):
            try:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    folders.append({"name": entry.name, "path": str(entry)})
                elif entry.suffix.lower() == ".csv":
                    st = entry.stat()
                    files.append({
                        "name": entry.name,
                        "path": str(entry),
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    })
            except (PermissionError, OSError):
                continue
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"path": str(p), "parent": parent, "files": files, "folders": folders})


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5200, debug=True)
