"""Config management blueprint — CRUD for profiles, benches, limits.

Mounts at ``/config/`` and provides:

- ``GET  /config/api/profiles``           → list profiles
- ``GET  /config/api/profiles/<name>``    → read one profile
- ``POST /config/api/profiles/<name>``    → create/update profile
- ``DELETE /config/api/profiles/<name>``  → delete profile
- (same pattern for ``/benches/`` and ``/limits/``)
"""
from __future__ import annotations

import pathlib

from flask import Blueprint, current_app, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "config"

bp = Blueprint(
    "config",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/static",
)


@bp.route("/")
def index():
    """Serve the accessible configuration-management interface."""
    return send_from_directory(str(_WEB_DIR), "index.html")


def _svc():
    return current_app.extensions.get("config_service")


# ── Profiles ────────────────────────────────────────────────────────────

@bp.route("/api/profiles")
def list_profiles():
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    return jsonify(svc.list_profiles())


@bp.route("/api/profiles/<name>")
def read_profile(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    data = svc.read_profile(name)
    if data is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(data)


@bp.route("/api/profiles/<name>", methods=["POST"])
def write_profile(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    body = request.get_json(force=True)
    result = svc.write_profile(name, body)
    status_code = 400 if "error" in result else 200
    return jsonify(result), status_code


@bp.route("/api/profiles/<name>", methods=["DELETE"])
def delete_profile(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    ok = svc.delete_profile(name)
    return jsonify({"deleted": ok}), 200 if ok else 404


# ── Benches ─────────────────────────────────────────────────────────────

@bp.route("/api/benches")
def list_benches():
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    return jsonify(svc.list_benches())


@bp.route("/api/benches/<name>")
def read_bench(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    data = svc.read_bench(name)
    if data is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(data)


@bp.route("/api/benches/<name>", methods=["POST"])
def write_bench(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    body = request.get_json(force=True)
    result = svc.write_bench(name, body)
    status_code = 400 if "error" in result else 200
    return jsonify(result), status_code


@bp.route("/api/benches/<name>", methods=["DELETE"])
def delete_bench(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    ok = svc.delete_bench(name)
    return jsonify({"deleted": ok}), 200 if ok else 404


# ── Limits ──────────────────────────────────────────────────────────────

@bp.route("/api/limits")
def list_limits():
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    return jsonify(svc.list_limits())


@bp.route("/api/limits/<name>")
def read_limits(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    data = svc.read_limits(name)
    if data is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(data)


@bp.route("/api/limits/<name>", methods=["POST"])
def write_limits(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    body = request.get_json(force=True)
    result = svc.write_limits(name, body)
    status_code = 400 if "error" in result else 200
    return jsonify(result), status_code


@bp.route("/api/limits/<name>", methods=["DELETE"])
def delete_limits(name: str):
    svc = _svc()
    if svc is None:
        return jsonify({"error": "Config service not available"}), 503
    ok = svc.delete_limits(name)
    return jsonify({"deleted": ok}), 200 if ok else 404
