"""HIL Dashboard blueprint — real-time test execution UI + API.

Mounts at ``/hil/`` and provides:

- ``GET  /hil/``                  → SPA dashboard
- ``POST /hil/api/start``         → start a profile run
- ``POST /hil/api/stop``          → request stop
- ``GET  /hil/api/status``        → current run status
- ``GET  /hil/api/history``       → run history
- ``GET  /hil/api/events/<ch>``   → recent events from a channel
- ``GET  /hil/api/channels``      → list event channels
"""
from __future__ import annotations

import pathlib

from flask import Blueprint, current_app, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "hil"

bp = Blueprint(
    "hil",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/hil/static",
)


# ── SPA ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


# ── Test execution API ──────────────────────────────────────────────────

@bp.route("/api/start", methods=["POST"])
def start_test():
    body = request.get_json(force=True)
    profile_path = body.get("profile")
    if not profile_path:
        return jsonify({"error": "Missing 'profile' field"}), 400

    test_svc = current_app.extensions.get("test_service")
    if test_svc is None:
        return jsonify({"error": "Test service not available"}), 503

    result = test_svc.start_profile(
        profile_path,
        bench_overrides=body.get("bench_overrides"),
        meta=body.get("meta"),
    )
    status_code = 409 if "error" in result else 200
    return jsonify(result), status_code


@bp.route("/api/stop", methods=["POST"])
def stop_test():
    test_svc = current_app.extensions.get("test_service")
    if test_svc is None:
        return jsonify({"error": "Test service not available"}), 503
    return jsonify(test_svc.request_stop())


@bp.route("/api/status")
def status():
    test_svc = current_app.extensions.get("test_service")
    if test_svc is None:
        return jsonify({"error": "Test service not available"}), 503
    return jsonify(test_svc.status())


@bp.route("/api/history")
def history():
    test_svc = current_app.extensions.get("test_service")
    if test_svc is None:
        return jsonify({"error": "Test service not available"}), 503
    limit = request.args.get("limit", 50, type=int)
    return jsonify(test_svc.history(limit=limit))


# ── Event channels ──────────────────────────────────────────────────────

@bp.route("/api/channels")
def channels():
    log_svc = current_app.extensions.get("log_service")
    if log_svc is None:
        return jsonify({"error": "Log service not available"}), 503
    return jsonify(log_svc.list_channels())


@bp.route("/api/events/<channel_name>")
def recent_events(channel_name: str):
    log_svc = current_app.extensions.get("log_service")
    if log_svc is None:
        return jsonify({"error": "Log service not available"}), 503
    n = request.args.get("n", 500, type=int)
    events = log_svc.recent_as_dicts(channel_name, n=n)
    return jsonify(events)
