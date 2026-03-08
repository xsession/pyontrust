"""Lab-bench blueprint — instrument discovery, health, and management.

Mounts at ``/bench/`` and provides:

- ``GET  /bench/``              → bench management SPA
- ``GET  /bench/api/status``    → instrument status list
- ``GET  /bench/api/types``     → available instrument types
- ``POST /bench/api/load``      → load bench config
- ``POST /bench/api/save``      → save bench config
- ``POST /bench/api/connect``   → instantiate all instruments
- ``POST /bench/api/disconnect``→ close all instruments
"""
from __future__ import annotations

import pathlib

from flask import Blueprint, current_app, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "bench"

bp = Blueprint(
    "bench",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/bench/static",
)


@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/status")
def status():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    return jsonify(svc.instrument_status())


@bp.route("/api/summary")
def summary():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    return jsonify(svc.bench_summary())


@bp.route("/api/types")
def types():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    return jsonify(svc.discover_available_types())


@bp.route("/api/load", methods=["POST"])
def load():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    body = request.get_json(force=True)
    path = body.get("path")
    result = svc.load(path=path)
    status_code = 400 if "error" in result else 200
    return jsonify(result), status_code


@bp.route("/api/save", methods=["POST"])
def save():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    body = request.get_json(force=True)
    path = body.get("path")
    result = svc.save(path=path)
    status_code = 400 if "error" in result else 200
    return jsonify(result), status_code


@bp.route("/api/connect", methods=["POST"])
def connect():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    return jsonify(svc.instantiate_all())


@bp.route("/api/disconnect", methods=["POST"])
def disconnect():
    svc = current_app.extensions.get("bench_service")
    if svc is None:
        return jsonify({"error": "Bench service not available"}), 503
    svc.close_all()
    return jsonify({"success": True})
