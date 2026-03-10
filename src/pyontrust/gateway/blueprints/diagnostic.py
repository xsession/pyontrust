"""Diagnostic blueprint — hardware discovery, testing, live data, and reports.

Mounts at ``/diag/`` and provides:

- ``GET  /diag/``                      → diagnostic landing page SPA
- ``GET  /diag/api/scan``              → scan all hardware (parallel probes)
- ``POST /diag/api/test``              → run quick test on a single device
- ``POST /diag/api/test_all``          → test all detected hardware
- ``POST /diag/api/led_blink``         → measure LED blink rate + generate report
- ``POST /diag/api/lux_measure``       → parallel lux measurement + generate report
- ``GET  /diag/api/reports``           → list all HTML test reports
- ``GET  /diag/api/reports/<name>``    → serve a specific report
- ``GET  /diag/api/system``            → system info (OS, Python, packages)
- ``GET  /diag/api/live/<type>/<sensor>`` → single-shot sensor read
- ``GET  /diag/api/live/stream``       → SSE live data stream
- ``POST /diag/api/live/stop``         → stop all active streams
"""
from __future__ import annotations

import json as _json
import pathlib
import platform
import queue
import sys
import threading
import time

from flask import Blueprint, Response, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "diagnostic"

bp = Blueprint(
    "diagnostic",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/static",
)


@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/scan")
def scan():
    """Scan all hardware interfaces and return discovery results."""
    from pyontrust.services.hardware_discovery import discover_all_hardware
    t0 = time.time()
    results = discover_all_hardware(timeout_s=30.0)
    elapsed = round(time.time() - t0, 2)
    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "not_found": sum(1 for r in results if r["status"] == "not_found"),
    }
    return jsonify({"devices": results, "summary": summary,
                    "scan_time_s": elapsed})


@bp.route("/api/test", methods=["POST"])
def test_one():
    """Run a quick test on a single discovered device."""
    from pyontrust.services.hardware_discovery import run_quick_test
    body = request.get_json(force=True)
    if not body:
        return jsonify({"error": "No device data"}), 400
    result = run_quick_test(body)
    return jsonify(result)


@bp.route("/api/test_all", methods=["POST"])
def test_all():
    """Scan + test all connected hardware."""
    from pyontrust.services.hardware_discovery import (
        discover_all_hardware, run_all_tests,
    )
    t0 = time.time()
    hw = discover_all_hardware(timeout_s=30.0)
    hw = run_all_tests(hw)
    elapsed = round(time.time() - t0, 2)

    tested = [h for h in hw if h.get("test_result")]
    passed = sum(1 for h in tested if h["test_result"].get("passed"))
    failed = len(tested) - passed

    return jsonify({
        "devices": hw,
        "test_summary": {
            "tested": len(tested), "passed": passed, "failed": failed,
        },
        "total_time_s": elapsed,
    })


@bp.route("/api/led_blink", methods=["POST"])
def led_blink():
    """Run a live LED blink measurement and return result + report path."""
    from pyontrust.analysis.led_blink import (
        CaptureConfig, RedLEDMaskConfig, measure_led_blink_rate,
    )
    from pyontrust.analysis.test_report import build_led_blink_report

    body = request.get_json(force=True) or {}
    cap_cfg = CaptureConfig(
        device_index=int(body.get("device_index", 0)),
        width=int(body.get("width", 640)),
        height=int(body.get("height", 480)),
        capture_duration_s=float(body.get("duration_s", 8.0)),
        target_fps=float(body.get("fps", 30.0)),
        warmup_frames=int(body.get("warmup", 15)),
    )
    mask_cfg = RedLEDMaskConfig()
    result = measure_led_blink_rate(cap_cfg=cap_cfg, mask_cfg=mask_cfg)

    report_dir = pathlib.Path("test_reports")
    report_path = build_led_blink_report(
        result, cap_cfg=cap_cfg, mask_cfg=mask_cfg,
        output_dir=report_dir,
    )

    return jsonify({
        "result": result.summary(),
        "report_file": str(report_path),
        "report_url": f"/diag/api/reports/{report_path.name}",
    })


@bp.route("/api/lux_measure", methods=["POST"])
def lux_measure():
    """Run a parallel lux measurement and return result + report path."""
    from pyontrust.analysis.lux_measurement import (
        LuxCaptureConfig, measure_parallel_lux,
    )
    from pyontrust.analysis.lux_report import build_lux_report

    body = request.get_json(force=True) or {}
    cfg = LuxCaptureConfig(
        device_index=int(body.get("device_index", 0)),
        width=int(body.get("width", 640)),
        height=int(body.get("height", 480)),
        target_fps=float(body.get("fps", 30.0)),
        warmup_frames=int(body.get("warmup", 15)),
        torch_on_s=float(body.get("torch_on_s", 3.0)),
        torch_off_s=float(body.get("torch_off_s", 3.0)),
        n_cycles=int(body.get("n_cycles", 3)),
        pre_capture_s=float(body.get("pre_capture_s", 1.0)),
        android_mode=str(body.get("android_mode", "simulated")),
        android_sample_rate_hz=float(body.get("android_rate_hz", 10.0)),
        lux_scale=float(body.get("lux_scale", 2.0)),
        lux_offset=float(body.get("lux_offset", 0.0)),
    )
    use_real = cfg.android_mode != "simulated"
    result = measure_parallel_lux(cfg, use_real_torch=use_real)

    report_dir = pathlib.Path("test_reports")
    report_path = build_lux_report(
        result, cfg=cfg, output_dir=report_dir,
    )

    return jsonify({
        "result": result.summary(),
        "report_file": str(report_path),
        "report_url": f"/diag/api/reports/{report_path.name}",
    })


@bp.route("/api/reports")
def list_reports():
    """List all generated HTML test reports."""
    report_dir = pathlib.Path("test_reports")
    if not report_dir.is_dir():
        return jsonify([])
    reports = []
    for f in sorted(report_dir.glob("*.html"), reverse=True):
        reports.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "created": f.stat().st_ctime,
            "url": f"/diag/api/reports/{f.name}",
        })
    return jsonify(reports)


@bp.route("/api/reports/<filename>")
def get_report(filename):
    """Serve a specific HTML test report."""
    report_dir = pathlib.Path("test_reports").resolve()
    # Path-traversal guard
    safe_name = pathlib.Path(filename).name
    target = report_dir / safe_name
    if not target.is_file():
        return jsonify({"error": "Report not found"}), 404
    return send_from_directory(str(report_dir), safe_name, mimetype="text/html")


@bp.route("/api/system")
def system_info():
    """Return system and environment info."""
    info = {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "arch": platform.machine(),
        "python": sys.version,
        "python_path": sys.executable,
    }
    # Check key packages
    pkgs = {}
    for pkg in ["numpy", "cv2", "serial", "flask", "scipy",
                "pylink", "SoapySDR", "seekcamera", "pyontrust"]:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", getattr(mod, "VERSION", "installed"))
            pkgs[pkg] = str(ver)
        except ImportError:
            pkgs[pkg] = None
    info["packages"] = pkgs
    return jsonify(info)


# ═══════════════════════════════════════════════════════════════════════
#  Live data streaming
# ═══════════════════════════════════════════════════════════════════════

# Global registry of active streams keyed by a client-generated or
# auto-assigned ID.  Each entry holds a threading.Event that, when set,
# tells the generator to stop.
_active_streams: dict[str, threading.Event] = {}


def _read_sensor_once(
    hw_type: str, sensor: str, device_serial: str | None = None,
    mode: str = "auto",
) -> dict:
    """Read a single sensor sample.

    *hw_type* is the hardware category (``android_sensors``, ``webcam``,
    ``ad3_dwf``, etc.).  *sensor* is the specific sensor name
    (``accelerometer``, ``light``, ``frame``, …).
    """
    if hw_type == "android_sensors":
        from pyontrust.instruments.android_sensors import (
            AndroidSensorInstrument,
        )
        # Pick mode: if a real device serial is provided and ADB works, use adb
        if mode == "auto":
            from pyontrust.instruments.android_sensors import _adb_available
            mode = "adb" if _adb_available() else "simulated"

        inst = AndroidSensorInstrument(mode=mode)
        inst.open()
        try:
            if sensor == "battery":
                return inst.read_battery()
            elif sensor == "gps":
                return inst.read_gps()
            elif sensor == "microphone":
                return inst.read_microphone(duration_s=0.5, sample_rate=16000)
            else:
                # Map sensor name to the specific read method
                reader = getattr(inst, f"read_{sensor}", None)
                if reader is not None:
                    return reader(duration_s=0.2)
                # Fallback: try the underlying impl's read_sensor
                if inst._impl is not None:
                    return inst._impl.read_sensor(sensor, duration_s=0.2)
                return {"error": f"Unknown sensor: {sensor}"}
        finally:
            inst.close()

    elif hw_type == "webcam":
        try:
            import cv2
            import numpy as np

            idx = int(sensor) if sensor.isdigit() else 0
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return {"error": f"Cannot open camera #{idx}"}
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return {"error": "Empty frame"}

            # Compute summary statistics per channel
            b, g, r = cv2.split(frame)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            brightness = float(np.mean(hsv[:, :, 2]))
            return {
                "sensor": f"webcam_{idx}",
                "width": frame.shape[1],
                "height": frame.shape[0],
                "brightness": round(brightness, 2),
                "mean_r": round(float(np.mean(r)), 2),
                "mean_g": round(float(np.mean(g)), 2),
                "mean_b": round(float(np.mean(b)), 2),
                "timestamp": time.time(),
            }
        except ImportError:
            return {"error": "opencv-python not installed"}

    elif hw_type == "ad3_dwf":
        return {"error": "DWF live read not yet implemented", "sensor": sensor}

    return {"error": f"Unknown hw_type: {hw_type}", "sensor": sensor}


@bp.route("/api/live/<hw_type>/<sensor>")
def live_read_once(hw_type: str, sensor: str):
    """Single-shot live read from a device/sensor."""
    mode = request.args.get("mode", "auto")
    serial = request.args.get("serial", None)
    try:
        data = _read_sensor_once(hw_type, sensor, device_serial=serial, mode=mode)
        return jsonify({"ok": True, "data": data, "ts": time.time()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "ts": time.time()}), 500


@bp.route("/api/live/stream")
def live_stream():
    """Server-Sent Events stream for continuous live data.

    Query params:
        hw_type  — hardware type (android_sensors, webcam, …)
        sensor   — sensor name (accelerometer, light, 0, …)
        rate_ms  — sample interval in ms (default 500)
        mode     — "auto", "simulated", "adb" (default auto)
    """
    hw_type = request.args.get("hw_type", "android_sensors")
    sensor = request.args.get("sensor", "accelerometer")
    rate_ms = max(100, int(request.args.get("rate_ms", "500")))
    mode = request.args.get("mode", "auto")
    serial = request.args.get("serial", None)

    stop_evt = threading.Event()
    stream_id = f"{hw_type}_{sensor}_{id(stop_evt)}"
    _active_streams[stream_id] = stop_evt

    def _generate():
        try:
            # For android, keep the instrument open across samples
            inst = None
            if hw_type == "android_sensors":
                from pyontrust.instruments.android_sensors import (
                    AndroidSensorInstrument, _adb_available,
                )
                effective_mode = mode
                if effective_mode == "auto":
                    effective_mode = "adb" if _adb_available() else "simulated"
                inst = AndroidSensorInstrument(mode=effective_mode)
                inst.open()

            seq = 0
            while not stop_evt.is_set():
                t0 = time.time()
                try:
                    if inst is not None:
                        # Android sensor
                        if sensor == "battery":
                            data = inst.read_battery()
                        elif sensor == "gps":
                            data = inst.read_gps()
                        else:
                            reader = getattr(inst, f"read_{sensor}", None)
                            if reader is not None:
                                data = reader(duration_s=0.1)
                            elif inst._impl is not None:
                                data = inst._impl.read_sensor(sensor, duration_s=0.1)
                            else:
                                data = {"error": f"Unknown sensor: {sensor}"}
                    else:
                        data = _read_sensor_once(
                            hw_type, sensor, device_serial=serial, mode=mode,
                        )
                except Exception as exc:
                    data = {"error": str(exc)}

                payload = {"seq": seq, "ts": time.time(), "data": data}
                yield f"data: {_json.dumps(payload)}\n\n"
                seq += 1

                # Sleep for the requested interval minus elapsed time
                elapsed = time.time() - t0
                sleep_s = max(0, rate_ms / 1000.0 - elapsed)
                if sleep_s > 0:
                    stop_evt.wait(sleep_s)
        finally:
            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass
            _active_streams.pop(stream_id, None)

    return Response(
        _generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@bp.route("/api/live/stop", methods=["POST"])
def live_stop():
    """Stop all active SSE streams."""
    count = 0
    for sid, evt in list(_active_streams.items()):
        evt.set()
        count += 1
    _active_streams.clear()
    return jsonify({"stopped": count})
