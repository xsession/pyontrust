"""FlowLab blueprint — LabVIEW-style visual dataflow experiment designer.

Mounts at ``/flowlab/`` and provides:

- ``GET  /flowlab/``              → block-diagram SPA
- ``POST /flowlab/api/execute``   → execute a diagram (topological sort)
- ``POST /flowlab/api/save``      → persist diagram JSON
- ``GET  /flowlab/api/load``      → retrieve saved diagram
- ``POST /flowlab/api/stop``      → request execution abort
- ``GET  /flowlab/api/blocks``    → available block types
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from pyontrust.gateway.flowlab_engine import FlowLabEngine
from pyontrust.gateway.hil_flowlab_converter import diagram_to_hil, hil_to_diagram

logger = logging.getLogger("pyontrust.gateway.flowlab")

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "flowlab"
_SAVE_DIR = pathlib.Path(".") / "flowlab_diagrams"
_HIL_DIR = pathlib.Path(".") / "profiles"

bp = Blueprint(
    "flowlab",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/static",
)

# Shared engine instance per process
_engine: FlowLabEngine | None = None
_lock = threading.Lock()


def _get_engine() -> FlowLabEngine:
    global _engine
    if _engine is None:
        _engine = FlowLabEngine()
    return _engine


# ── SPA ──────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


# ── Execute diagram ──────────────────────────────────────────────────

@bp.route("/api/execute", methods=["POST"])
def execute():
    body = request.get_json(force=True)
    if not body or "blocks" not in body:
        return jsonify({"error": "Invalid diagram — missing 'blocks'"}), 400

    engine = _get_engine()
    with _lock:
        result = engine.execute(body)
    return jsonify(result)


@bp.route("/api/stop", methods=["POST"])
def stop():
    engine = _get_engine()
    engine.request_stop()
    return jsonify({"stopped": True})


# ── Save / Load ──────────────────────────────────────────────────────

@bp.route("/api/save", methods=["POST"])
def save():
    body = request.get_json(force=True)
    name = body.get("name", "autosave")
    diagram = body.get("diagram", {})

    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = _SAVE_DIR / f"{name}.json"
    path.write_text(json.dumps(diagram, indent=2), encoding="utf-8")
    logger.info("FlowLab diagram saved: %s", path)
    return jsonify({"success": True, "path": str(path)})


@bp.route("/api/load")
def load():
    name = request.args.get("name", "autosave")
    path = _SAVE_DIR / f"{name}.json"
    if not path.exists():
        return jsonify({"diagram": None})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return jsonify({"diagram": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/list")
def list_diagrams():
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(_SAVE_DIR.glob("*.json"))
    return jsonify({"diagrams": [f.stem for f in files]})


# ── Block catalogue (mirror of JS catalogue for tooling) ─────────────

@bp.route("/api/blocks")
def block_types():
    engine = _get_engine()
    return jsonify({"blocks": list(engine.block_registry.keys())})


# ── HIL ↔ FlowLab conversion ─────────────────────────────────────────

@bp.route("/api/export_hil", methods=["POST"])
def export_hil():
    """Convert the current FlowLab diagram to a HIL test profile JSON.

    Accepts:
        {"diagram": {...}, "name": "optional_name"}
    Returns:
        {"profile": {...HIL profile JSON...}}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    # Allow overriding name
    name = body.get("name", "flowlab_export")
    diagram["name"] = name

    try:
        profile = diagram_to_hil(diagram)
        return jsonify({"profile": profile})
    except Exception as exc:
        logger.exception("HIL export failed")
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/save_hil", methods=["POST"])
def save_hil():
    """Export diagram as HIL profile and save to profiles/ directory.

    Accepts:
        {"diagram": {...}, "name": "profile_name"}
    Returns:
        {"success": true, "path": "profiles/profile_name.json", "profile": {...}}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    name = body.get("name", "flowlab_export")

    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    diagram["name"] = name

    try:
        profile = diagram_to_hil(diagram)

        _HIL_DIR.mkdir(parents=True, exist_ok=True)
        path = _HIL_DIR / f"{name}.json"
        path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        logger.info("HIL profile saved: %s", path)
        return jsonify({"success": True, "path": str(path), "profile": profile})
    except Exception as exc:
        logger.exception("HIL save failed")
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/import_hil", methods=["POST"])
def import_hil():
    """Import a HIL test profile and convert to a FlowLab diagram.

    Accepts:
        {"profile": {...HIL profile JSON...}}
      OR
        {"name": "profile_name"}  (load from profiles/ directory)
    Returns:
        {"diagram": {...FlowLab diagram...}}
    """
    body = request.get_json(force=True)

    profile = body.get("profile")
    if not profile:
        # Try loading from file
        name = body.get("name", "")
        if not name:
            return jsonify({"error": "Provide 'profile' JSON or 'name' to load from disk"}), 400

        path = _HIL_DIR / f"{name}.json"
        if not path.exists():
            return jsonify({"error": f"Profile not found: {path}"}), 404
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return jsonify({"error": f"Failed to load profile: {exc}"}), 500

    try:
        diagram = hil_to_diagram(profile)
        return jsonify({"diagram": diagram})
    except Exception as exc:
        logger.exception("HIL import failed")
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/hil_profiles")
def list_hil_profiles():
    """List available HIL profile JSON files from profiles/ directory."""
    _HIL_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(_HIL_DIR.glob("*.json"))
    profiles = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles.append({
                "name": f.stem,
                "description": data.get("description", ""),
                "steps": len(data.get("steps", data.get("actions", []))),
            })
        except Exception:
            profiles.append({"name": f.stem, "description": "(parse error)", "steps": 0})
    return jsonify({"profiles": profiles})


@bp.route("/api/run_hil", methods=["POST"])
def run_hil():
    """Export diagram to HIL, then execute via /hil/api/start.

    Accepts:
        {"diagram": {...}}
    Returns:
        {"profile": {...}, "execution": "started"|"error"}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    try:
        # Convert diagram to profile
        name = body.get("name", "flowlab_hil_run")
        diagram["name"] = name
        profile = diagram_to_hil(diagram)

        # Save as temp profile
        _HIL_DIR.mkdir(parents=True, exist_ok=True)
        path = _HIL_DIR / f"_flowlab_run.json"
        path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        # Try to start via test service
        try:
            from pyontrust.services.test_service import TestService
            svc = current_app.config.get("test_service")
            if svc and isinstance(svc, TestService):
                result = svc.start_profile(str(path))
                return jsonify({
                    "profile": profile,
                    "execution": "started",
                    "run_id": result.get("run_id") if isinstance(result, dict) else str(result),
                })
            else:
                return jsonify({
                    "profile": profile,
                    "execution": "no_test_service",
                    "message": "Profile exported but TestService not available. Use /hil/ to run manually.",
                    "profile_path": str(path),
                })
        except Exception as exc:
            logger.warning("Could not auto-start HIL run: %s", exc)
            return jsonify({
                "profile": profile,
                "execution": "saved_only",
                "message": f"Profile saved to {path}. Start via HIL dashboard.",
                "profile_path": str(path),
            })

    except Exception as exc:
        logger.exception("Run as HIL failed")
        return jsonify({"error": str(exc)}), 500
