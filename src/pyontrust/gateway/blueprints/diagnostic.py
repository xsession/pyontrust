"""Diagnostic blueprint — hardware discovery, testing, and reports.

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
"""
from __future__ import annotations

import pathlib
import platform
import sys
import time

from flask import Blueprint, jsonify, request, send_from_directory

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
