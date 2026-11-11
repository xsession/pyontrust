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

from flask import Blueprint, jsonify, request, send_from_directory, send_file, current_app

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

# Long-term tracking session (click-selected points/patches over time).
from pyontrust.services.thermal_tracking import TrackingSession  # noqa: E402

_tracking = TrackingSession()


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
#  API: Calibration (one-point reference temperature)
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/calibrate", methods=["POST"])
def calibrate():
    """Set a one-point calibration offset (persistent).

    Body: {"ref_c": 24.0}   → aim the camera at something known to be
                               ref_c °C; all future readings are shifted so
                               the frame median equals ref_c.
          {"clear": true}   → reset the offset to zero.

    The offset is stored in ~/.pyontrust/thermal_calibration.json and applied
    by the SeekThermalCamera instrument layer, so it affects every consumer
    (FlowLab blocks, this dashboard, services) across restarts.
    """
    from pyontrust.instruments import thermal_calibration as tcal

    body = request.get_json(silent=True) or {}

    if body.get("clear"):
        return jsonify({"ok": True, **tcal.clear()})

    try:
        ref_c = float(body.get("ref_c", body.get("reference_c")))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Provide ref_c (number) or clear=true"}), 400
    if not (-60.0 <= ref_c <= 400.0):
        return jsonify({"ok": False, "error": "ref_c out of range"}), 400

    # Grab one frame to measure the current scene median (raw estimate).
    from pyontrust.instruments.seek_thermal import create as create_thermal
    cam = None
    try:
        cam = create_thermal({"mode": "seek"})
        cam.open()
        frame = cam.grab_temperature_frame()  # includes any existing offset
    except Exception as exc:
        logger.warning("Calibration grab failed: %s", exc)
        return jsonify({"ok": False,
                        "error": f"Cannot grab calibration frame (camera connected?): {exc}"}), 502
    finally:
        if cam is not None:
            try:
                cam.close()
            except Exception:
                pass

    import numpy as np
    current = tcal.load_offset_c()
    raw_median = float(np.median(frame)) - current
    offset = round(ref_c - raw_median, 3)
    info = tcal.save_offset(offset, reference_c=ref_c, scene_median_c=raw_median)
    return jsonify({"ok": True, **info})


# ═══════════════════════════════════════════════════════════════════════
#  API: Long-term tracking (click-selected points & patches over time)
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/tracking/start", methods=["POST"])
def tracking_start():
    """Start a tracking session.

    Body: {
        "selections": [{"name": "U3", "type": "patch", "x": 40, "y": 20, "w": 18, "h": 12},
                       {"name": "P1", "type": "point", "x": 100, "y": 60}],
        "interval_s": 1.0
    }
    """
    if _measurement_progress["running"]:
        return jsonify({"ok": False, "error": "A measurement session is running — stop it first"}), 409

    body = request.get_json(silent=True) or {}
    selections = body.get("selections") or []
    interval_s = float(body.get("interval_s", 1.0))

    try:
        res = _tracking.start(selections=selections, interval_s=interval_s)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    except Exception as exc:
        logger.exception("tracking start failed")
        return jsonify({"ok": False, "error": f"Cannot open camera for tracking: {exc}"}), 502

    res["ok"] = True
    return jsonify(res)


@bp.route("/api/tracking/status")
def tracking_status():
    """Running state, latest per-selection values and (downsampled) series."""
    return jsonify(_tracking.status())


@bp.route("/api/tracking/stop", methods=["POST"])
def tracking_stop():
    """Stop the tracking session and release the camera."""
    res = _tracking.stop()
    res["ok"] = True
    return jsonify(res)


@bp.route("/api/tracking/export.csv")
def tracking_export_csv():
    """Download the CSV log of the current/last tracking session."""
    path = _tracking.csv_path
    if path is None or not pathlib.Path(path).exists():
        return jsonify({"ok": False, "error": "No tracking CSV available"}), 404
    return send_file(str(path), as_attachment=True, download_name=pathlib.Path(path).name)


# ═══════════════════════════════════════════════════════════════════════
#  API: Live frame (colourised PNG for the interactive view)
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/frame")
def live_frame():
    """Return one colourised thermal frame as a base64 PNG.

    Used by the tracking tab's live image (click to select points/patches).
    While a tracking session is running, grabs are serialized with its
    sampling loop; otherwise a one-shot camera open/grab/close is used.
    """
    import base64

    import cv2
    import numpy as np

    if _tracking.running:
        try:
            temp = _tracking.grab_for_display()
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
    else:
        from pyontrust.instruments.seek_thermal import create as create_thermal
        cam = None
        try:
            cam = create_thermal({"mode": "seek"})
            cam.open()
            temp = cam.grab_temperature_frame()
        except Exception as exc:
            return jsonify({"ok": False,
                            "error": f"Cannot grab frame (camera connected?): {exc}"}), 502
        finally:
            if cam is not None:
                try:
                    cam.close()
                except Exception:
                    pass

    temp = np.asarray(temp, dtype=np.float32)
    vmin, vmax = float(np.min(temp)), float(np.max(temp))
    norm = ((temp - vmin) / max(vmax - vmin, 1e-3) * 255).clip(0, 255).astype(np.uint8)
    color = cv2.applyColorMap(norm, cv2.COLORMAP_JET)

    # Upscale for easier clicking (native frame is only ~207x154).
    h, w = temp.shape[:2]
    scale = max(1, int(round(640 / w)))
    color_big = cv2.resize(color, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)

    ok, png = cv2.imencode(".png", color_big)
    if not ok:
        return jsonify({"ok": False, "error": "PNG encoding failed"}), 500

    return jsonify({
        "ok": True,
        "image_b64": base64.b64encode(png.tobytes()).decode("ascii"),
        "width": int(w), "height": int(h),          # native resolution (selection coords)
        "display_width": int(w * scale), "display_height": int(h * scale),
        "min_c": round(vmin, 2), "max_c": round(vmax, 2),
    })


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
