"""HIL Dashboard blueprint — real-time test execution UI + API.

Mounts at ``/hil/`` and provides:

- ``GET  /hil/``                  → SPA dashboard
- ``GET  /hil/api/profiles``      → available profiles (the default one first)
- ``POST /hil/api/start``         → start a profile run (no profile → the default)
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

@bp.route("/api/profiles")
def profiles():
    from pyontrust.services.test_service import DEFAULT_PROFILE, list_profiles

    return jsonify({"default": DEFAULT_PROFILE, "profiles": list_profiles()})


@bp.route("/api/start", methods=["POST"])
def start_test():
    body = request.get_json(silent=True) or {}
    profile_path = body.get("profile") or ""      # empty → the default profile

    test_svc = current_app.extensions.get("test_service")
    if test_svc is None:
        return jsonify({"error": "Test service not available"}), 503

    result = test_svc.start_profile(
        profile_path,
        bench_overrides=body.get("bench_overrides"),
        meta=body.get("meta"),
    )
    if "error" in result:
        status_code = 404 if "not found" in result["error"] else 409
    else:
        status_code = 200
        try:
            _track_run(test_svc, result.get("run_id", ""), result.get("profile", profile_path))
        except Exception:      # the run has started; station bookkeeping must not turn it into an error
            current_app.logger.warning("HIL run %s not recorded in the run registry",
                                       result.get("run_id"), exc_info=True)
    return jsonify(result), status_code


# ── run registry: HIL runs finish on the service's thread ───────────────
_PENDING: dict[str, str] = {}          # HIL run id -> run-registry id
_LISTENING: set[int] = set()


def _track_run(test_svc, hil_run_id: str, profile_path: str) -> None:
    from pyontrust.gateway import context
    from pyontrust.gateway.blueprints.station import runs

    reg = runs()
    _PENDING[hil_run_id] = reg.start("hil", "profile", context.actor(),
                                     {"profile": profile_path, "hil_run_id": hil_run_id})
    if id(test_svc) in _LISTENING:
        return
    _LISTENING.add(id(test_svc))

    def _on_change(state, info) -> None:
        value = getattr(state, "value", str(state)).lower()
        if value not in ("finished", "error"):
            return
        run_id = _PENDING.pop(str(info.get("run_id", "")), None)
        if run_id:
            reg.finish(run_id, "done" if value == "finished" else "error")

    test_svc.on_state_change(_on_change)


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
