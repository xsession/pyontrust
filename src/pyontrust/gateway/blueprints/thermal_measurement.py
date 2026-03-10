"""Thermal measurement blueprint — Seek Thermal camera measurement dashboard.

Provides REST API and single-page dashboard for running thermal
measurement sessions (continuous, soak, delta, gradient) with the
Seek Thermal camera (libseek / seekcamera / simulated).

Routes
------
GET  /thermal/                    — Dashboard SPA
GET  /thermal/api/status          — Camera and service status
POST /thermal/api/start           — Start a measurement session
GET  /thermal/api/progress        — Poll measurement progress
POST /thermal/api/stop            — Abort running measurement
GET  /thermal/api/result          — Latest result
GET  /thermal/api/reports         — List saved HTML reports
GET  /thermal/api/report/<name>   — Download a report
POST /thermal/api/capture_single  — Single-frame capture
"""

from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from typing import Any

from flask import Blueprint, jsonify, request, send_from_directory, current_app

logger = logging.getLogger("pyontrust.gateway.thermal_measurement")

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "thermal"

bp = Blueprint(
    "thermal_measurement",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/thermal/static",
)

# ── Module-level state ───────────────────────────────────────────────
_measurement_thread: threading.Thread | None = None
_measurement_lock = threading.Lock()
_measurement_progress: dict[str, Any] = {
    "running": False,
    "frame": 0,
    "total": 0,
    "latest_snapshot": None,
    "elapsed_s": 0.0,
}
_last_result: dict[str, Any] | None = None
_abort_event = threading.Event()


# ═══════════════════════════════════════════════════════════════════════
#  Dashboard
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/")
def index():
    return bp.send_static_file("index.html")


# ═══════════════════════════════════════════════════════════════════════
#  API: Status
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/status")
def status():
    """Return camera availability and current measurement state."""
    camera_status = "unknown"
    camera_info: dict[str, Any] = {}

    # Try to detect camera
    try:
        from pyontrust.instruments.libseek_driver import detect_camera, list_cameras
        detected = detect_camera()
        if detected:
            camera_status = "connected"
            cams = list_cameras()
            camera_info = cams[0] if cams else {"type": detected}
        else:
            camera_status = "not_connected"
    except ImportError:
        camera_status = "no_driver"

    return jsonify({
        "camera_status": camera_status,
        "camera_info": camera_info,
        "measurement_running": _measurement_progress["running"],
        "simulated_available": True,
    })


# ═══════════════════════════════════════════════════════════════════════
#  API: Start measurement
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/start", methods=["POST"])
def start_measurement():
    """Start a thermal measurement session.

    JSON body:
        {
            "mode": "continuous" | "soak" | "delta" | "gradient",
            "duration_s": 30.0,
            "capture_interval_s": 0.5,
            "camera": {"mode": "simulated", ...},
            "zones": [...],
            "board_id": "PCB-001",
            ...
        }
    """
    global _measurement_thread, _last_result

    with _measurement_lock:
        if _measurement_progress["running"]:
            return jsonify({"error": "Measurement already running"}), 409

    body = request.get_json(force=True, silent=True) or {}

    # Reset
    _abort_event.clear()
    _measurement_progress.update({
        "running": True,
        "frame": 0,
        "total": 0,
        "latest_snapshot": None,
        "elapsed_s": 0.0,
        "mode": body.get("mode", "continuous"),
        "start_time": time.time(),
    })
    _last_result = None

    _measurement_thread = threading.Thread(
        target=_run_measurement_thread,
        args=(body,),
        name="thermal-measurement",
        daemon=True,
    )
    _measurement_thread.start()

    return jsonify({"status": "started", "mode": body.get("mode", "continuous")})


def _run_measurement_thread(config_dict: dict[str, Any]) -> None:
    """Background thread that runs the measurement."""
    global _last_result

    try:
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement

        def _progress(frame_idx: int, total: int, snapshot: dict[str, Any]) -> None:
            _measurement_progress["frame"] = frame_idx
            _measurement_progress["total"] = total
            _measurement_progress["latest_snapshot"] = snapshot
            _measurement_progress["elapsed_s"] = time.time() - _measurement_progress.get("start_time", time.time())

            if _abort_event.is_set():
                raise KeyboardInterrupt("Measurement aborted by user")

        result = run_thermal_measurement(config_dict, progress_cb=_progress)

        # Save report
        report_path = result.write_report()
        result_dict = result.to_dict()
        result_dict["report_path"] = str(report_path)
        _last_result = result_dict

        logger.info("Thermal measurement complete: %s", "PASS" if result.passed else "FAIL")

    except KeyboardInterrupt:
        logger.info("Thermal measurement aborted by user")
        _last_result = {"aborted": True, "message": "Measurement aborted by user"}
    except Exception as exc:
        logger.exception("Thermal measurement failed")
        _last_result = {"error": str(exc)}
    finally:
        _measurement_progress["running"] = False


# ═══════════════════════════════════════════════════════════════════════
#  API: Progress
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/progress")
def progress():
    """Poll measurement progress."""
    return jsonify({
        "running": _measurement_progress["running"],
        "frame": _measurement_progress["frame"],
        "total": _measurement_progress["total"],
        "elapsed_s": round(_measurement_progress.get("elapsed_s", 0.0), 1),
        "latest_snapshot": _measurement_progress.get("latest_snapshot"),
    })


# ═══════════════════════════════════════════════════════════════════════
#  API: Stop
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/stop", methods=["POST"])
def stop_measurement():
    """Abort a running measurement."""
    if not _measurement_progress["running"]:
        return jsonify({"status": "not_running"})

    _abort_event.set()
    return jsonify({"status": "stopping"})


# ═══════════════════════════════════════════════════════════════════════
#  API: Result
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/result")
def result():
    """Return the latest measurement result."""
    if _last_result is None:
        return jsonify({"status": "no_result"}), 404
    return jsonify(_last_result)


# ═══════════════════════════════════════════════════════════════════════
#  API: Single capture
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/capture_single", methods=["POST"])
def capture_single():
    """Capture a single thermal frame and return analysis."""
    body = request.get_json(force=True, silent=True) or {}

    from pyontrust.services.thermal_service import ThermalService

    cam_cfg = body.get("camera", {"mode": "simulated"})
    zones_cfg = body.get("zones", [])

    svc = ThermalService(config_dict={
        "camera": cam_cfg,
        "zones": zones_cfg,
    })

    try:
        svc.open()
        snap = svc.capture()
        info = svc.get_camera_info()
        return jsonify({
            "snapshot": snap.to_dict(),
            "camera_info": info,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        svc.close()


# ═══════════════════════════════════════════════════════════════════════
#  API: Reports
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/reports")
def list_reports():
    """List saved thermal measurement HTML reports."""
    report_dir = pathlib.Path("test_reports")
    if not report_dir.exists():
        return jsonify({"reports": []})

    reports = []
    for f in sorted(report_dir.glob("thermal_measurement_*.html"), reverse=True):
        reports.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": f.stat().st_mtime,
        })

    return jsonify({"reports": reports})


@bp.route("/api/report/<name>")
def download_report(name: str):
    """Download a specific report file."""
    report_dir = pathlib.Path("test_reports").resolve()
    return send_from_directory(str(report_dir), name)
