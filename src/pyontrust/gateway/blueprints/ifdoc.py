"""Interface Documentation Control Panel blueprint.

Mounts at ``/ifdoc/`` and provides:

- ``GET  /ifdoc/``                               → SPA control panel
- ``GET  /ifdoc/api/<transport>/<cmd>``           → read / execute
- ``POST /ifdoc/api/<transport>/<cmd>``           → write / execute with params

All API routes return JSON.  When no real hardware drivers are
available the responses indicate "not connected".
"""
from __future__ import annotations

import pathlib

from flask import Blueprint, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "ifdoc"

bp = Blueprint(
    "ifdoc",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/ifdoc/static",
)


# ── SPA ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


# ── Generic catch-all API stubs ─────────────────────────────────────────
#
# These stub routes respond to the API paths used by the SPA panels.
# Replace the bodies with real driver calls once hardware is connected.


@bp.route("/api/<path:path>", methods=["GET"])
def api_read(path: str):
    """Stub: return a helpful message for any GET read request."""
    return jsonify({
        "error": "not_connected",
        "endpoint": path,
        "hint": "Connect hardware drivers to enable live responses.",
    }), 503


@bp.route("/api/<path:path>", methods=["POST"])
def api_write(path: str):
    """Stub: acknowledge any POST write request."""
    body = request.get_json(silent=True) or {}
    return jsonify({
        "error": "not_connected",
        "endpoint": path,
        "params": body,
        "hint": "Connect hardware drivers to enable live responses.",
    }), 503
