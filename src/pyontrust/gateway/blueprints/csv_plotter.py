"""CSV Plotter blueprint — migrated from standalone server.py.

Mounts at ``/csv/`` and provides the full CSV Plotter REST API plus
serves the SPA from ``web/csv/``.

This blueprint is a thin adapter — it delegates all heavy work to
:mod:`pyontrust.analysis.csv_reader` and
:mod:`pyontrust.analysis.metrics`.
"""
from __future__ import annotations

import io
import json
import logging
import math
import os
import pathlib
import platform
import string
import time
from typing import Any

import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "csv"

bp = Blueprint(
    "csv_plotter",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/csv/static",
)

logger = logging.getLogger("pyontrust.gateway.csv_plotter")

# ── In-memory state (per-worker process) ────────────────────────────────

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
    "overlay_files": [],
    "layout": {},
}

_LAYOUT_PATH = pathlib.Path("layout.json")


# ── Internal helpers ────────────────────────────────────────────────────

def _push_history(path: str) -> None:
    h = _state["history"]
    absp = os.path.abspath(path)
    if absp in h:
        h.remove(absp)
    h.insert(0, absp)
    _state["history"] = h[:50]
    _state["history_index"] = 0


def _load_csv(path: str) -> dict:
    from pyontrust.analysis.csv_reader import (
        compute_timestamp_scale,
        read_any_csv,
        sniff_csv_separator,
    )

    sep = sniff_csv_separator(path)
    df = read_any_csv(path, sep=sep)
    ts_scale = compute_timestamp_scale(df) if "Timestamp" in df.columns else 1.0

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
    from pyontrust.analysis.metrics import compute_signal_metrics

    df = _state["df"]
    if df is None:
        return {}

    results: dict[str, dict | None] = {}
    for col in columns:
        if col not in df.columns or col == "Timestamp":
            continue
        y = pd.to_numeric(df[col], errors="coerce")
        x = (
            pd.to_numeric(df["Timestamp"], errors="coerce")
            if "Timestamp" in df.columns
            else pd.Series(range(len(df)), dtype=float)
        )

        if x_window and len(x_window) == 2:
            try:
                lo, hi = float(x_window[0]), float(x_window[1])
                mask = (x >= lo) & (x <= hi)
                x, y = x.where(mask), y.where(mask)
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


# ── SPA ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


# ── CSV Data routes ─────────────────────────────────────────────────────

@bp.route("/api/csv/load", methods=["POST"])
def csv_load():
    body = request.get_json(force=True)
    path = body.get("path", "")
    if not path or not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        return jsonify(_load_csv(path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/csv/load-folder", methods=["POST"])
def csv_load_folder():
    from pyontrust.analysis.csv_reader import find_newest_csv

    body = request.get_json(force=True)
    folder = body.get("folder", "")
    if not folder or not pathlib.Path(folder).is_dir():
        return jsonify({"error": f"Folder not found: {folder}"}), 404
    try:
        newest = find_newest_csv(folder)
        info = _load_csv(newest)
        _state["folder_path"] = os.path.abspath(folder)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/csv/columns")
def csv_columns():
    return jsonify({"columns": _state["columns"]})


@bp.route("/api/csv/info")
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


@bp.route("/api/csv/data", methods=["POST"])
def csv_data():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_range = body.get("x_range")
    max_points = int(body.get("max_points", 5000))

    df = _state["df"]
    if df is None:
        return jsonify({"error": "No CSV loaded"}), 400

    x = (
        pd.to_numeric(df["Timestamp"], errors="coerce")
        if "Timestamp" in df.columns
        else pd.Series(range(len(df)), dtype=float)
    )

    mask = None
    if x_range and len(x_range) == 2:
        lo, hi = float(x_range[0]), float(x_range[1])
        mask = (x >= lo) & (x <= hi)

    x_out = x if mask is None else x[mask]
    step = max(1, len(x_out) // max_points) if len(x_out) > max_points else 1
    x_ds = x_out.iloc[::step] if step > 1 else x_out

    series_out: dict[str, list] = {}
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


@bp.route("/api/csv/metrics", methods=["POST"])
def csv_metrics():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_window = body.get("x_window")
    if _state["df"] is None:
        return jsonify({"error": "No CSV loaded"}), 400
    return jsonify(_metrics_for_columns(columns, x_window))


@bp.route("/api/csv/reload", methods=["POST"])
def csv_reload():
    path = _state["file_path"]
    if not path:
        return jsonify({"error": "No file loaded"}), 400
    if not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        return jsonify(_load_csv(path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/csv/check-mtime")
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


# ── Overlay routes ──────────────────────────────────────────────────────

@bp.route("/api/overlay/add", methods=["POST"])
def overlay_add():
    from pyontrust.analysis.csv_reader import (
        compute_timestamp_scale,
        read_any_csv,
        sniff_csv_separator,
    )

    body = request.get_json(force=True)
    path = body.get("path", "")
    if not path or not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404
    try:
        sep = sniff_csv_separator(path)
        df = read_any_csv(path, sep=sep)
        scale = compute_timestamp_scale(df) if "Timestamp" in df.columns else 1.0
        _state["overlay_files"].append({
            "path": os.path.abspath(path), "df": df, "scale": float(scale),
        })
        return jsonify({"files": _overlay_summary()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/overlay/<int:idx>", methods=["DELETE"])
def overlay_remove(idx: int):
    if 0 <= idx < len(_state["overlay_files"]):
        _state["overlay_files"].pop(idx)
    return jsonify({"files": _overlay_summary()})


@bp.route("/api/overlay/list")
def overlay_list():
    return jsonify({"files": _overlay_summary()})


@bp.route("/api/overlay/clear", methods=["POST"])
def overlay_clear():
    _state["overlay_files"] = []
    return jsonify({"files": []})


def _overlay_summary() -> list[dict]:
    return [
        {"path": o["path"], "columns": [str(c) for c in o["df"].columns], "rows": len(o["df"])}
        for o in _state["overlay_files"]
    ]


# ── Layout ──────────────────────────────────────────────────────────────

@bp.route("/api/layout")
def layout_get():
    if _LAYOUT_PATH.exists():
        try:
            data = json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))
            _state["layout"] = data
            return jsonify(data)
        except Exception:
            pass
    return jsonify(_state.get("layout", {}))


@bp.route("/api/layout", methods=["POST"])
def layout_save():
    data = request.get_json(force=True)
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})


@bp.route("/api/layout", methods=["DELETE"])
def layout_clear():
    _state["layout"] = {}
    try:
        if _LAYOUT_PATH.exists():
            _LAYOUT_PATH.unlink()
    except Exception:
        pass
    return jsonify({"success": True})


# ── History ─────────────────────────────────────────────────────────────

@bp.route("/api/history")
def history_get():
    return jsonify({"files": _state["history"], "index": _state["history_index"]})


@bp.route("/api/history/navigate", methods=["POST"])
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
                _state["history_index"] = idx
                return jsonify({"path": path, "index": idx, **info})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    return jsonify({"path": None, "index": idx})


@bp.route("/api/history/clear", methods=["POST"])
def history_clear():
    _state["history"] = []
    _state["history_index"] = -1
    return jsonify({"success": True})


# ── Utilities ───────────────────────────────────────────────────────────

@bp.route("/api/browse/roots")
def browse_roots():
    roots: list[dict] = []
    if platform.system() == "Windows":
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if pathlib.Path(drive).exists():
                roots.append({"name": f"{letter}:", "path": drive})
    else:
        roots.append({"name": "/", "path": "/"})
    return jsonify({"roots": roots})


@bp.route("/api/folder/browse")
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
                        "name": entry.name, "path": str(entry),
                        "size": st.st_size, "mtime": st.st_mtime,
                    })
            except (PermissionError, OSError):
                continue
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"path": str(p), "parent": parent, "files": files, "folders": folders})
