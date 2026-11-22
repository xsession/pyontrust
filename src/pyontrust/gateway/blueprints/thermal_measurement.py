"""Thermal blueprint — Seek Thermal live view, zones, measurement, tracking.

Thin HTTP layer; the logic lives in services:

* :mod:`pyontrust.services.thermal_live`     — shared camera, ownership
  arbitration, rendering, latest-frame feed, zone statistics
* :mod:`pyontrust.services.thermal_job`      — background measurement job
* :mod:`pyontrust.services.thermal_tracking` — long-term point/patch logging

Routes (under ``/thermal``)
---------------------------
Page / state
    GET  /                       dashboard (static SPA in ``web/thermal``)
    GET  /api/state              everything the dashboard renders, in one snapshot
    GET  /api/status             camera, calibration, flat-field, job states
Regions (single source of truth for zones *and* tracking selections)
    GET  /api/regions | POST /api/regions
    PATCH /api/regions/<id> | DELETE /api/regions/<id>
Live view
    GET  /api/stream             MJPEG live video (``<img src>``)
    GET  /api/stream_meta        metadata of the latest streamed frame
    GET  /api/frame              one frame as base64 PNG + metadata
    POST /api/zone_readings      min/mean/max °C per rectangle (latest frame)
Measurement
    POST /api/start              start a measurement job
    GET  /api/progress           job progress
    POST /api/stop               abort the job
    GET  /api/result             latest result
    GET  /api/reports            saved HTML reports
    GET  /api/report/<name>      download a report
Tracking
    POST /api/tracking/start | GET /api/tracking/status
    POST /api/tracking/stop  | GET /api/tracking/export.csv
Camera tools
    POST /api/capture_single     one analysed frame (zones, verdict)
    POST /api/calibrate          one-point reference offset (or clear)
    POST /api/flat_field         learn / clear the flat-field map

The GUI works with the real Seek camera only.  The simulated camera is a
test double (``PYONTRUST_ALLOW_SIMULATION=1``, set by the test suite) and is
refused otherwise.
"""
from __future__ import annotations

import logging
import pathlib
import time
from typing import Any

from flask import (Blueprint, Response, jsonify, request, send_file,
                   send_from_directory, stream_with_context)

from pyontrust.services.thermal_job import MeasurementJob
from pyontrust.services.thermal_regions import RegionError, RegionStore, region_readings
from pyontrust.services.thermal_live import (CameraArbiter, FrameError, LiveCamera, LiveFeed,
                                             camera_config, mjpeg_part, render_frame,
                                             status_jpeg, zone_stats)
from pyontrust.services.thermal_tracking import TrackingSession

logger = logging.getLogger("pyontrust.gateway.thermal_measurement")

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "thermal"
_REPORT_DIR = pathlib.Path("test_reports")  # relative to the server's working dir

bp = Blueprint("thermal_measurement", __name__,
               static_folder=str(_WEB_DIR), static_url_path="/static")

# ── Process-wide state (one camera per gateway) ─────────────────────────
_job = MeasurementJob()
_tracking = TrackingSession()
_live = LiveCamera()
_feed = LiveFeed()
_arbiter = CameraArbiter(_live, _tracking, lambda: _job.running)
_regions = RegionStore()

_SIM_DISABLED_MSG = ("The simulated thermal camera has been removed — connect the "
                     "Seek Thermal camera (USB 289D).")


# ── helpers ─────────────────────────────────────────────────────────────

def _body() -> dict[str, Any]:
    data = request.get_json(force=True, silent=True)
    return data if isinstance(data, dict) else {}


def _error(message: str, status: int, **extra: Any) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": message, **extra}), status


def _sim_allowed() -> bool:
    """Simulated cameras exist only as test doubles (see core.simulation_guard)."""
    from pyontrust.core.simulation_guard import allowed

    return allowed()


def _wants_sim(cam_cfg: Any) -> bool:
    return isinstance(cam_cfg, dict) and str(cam_cfg.get("mode", "")).lower() == "simulated"


def _resolve_mode(mode: str | None) -> str:
    """Real Seek camera, unless the simulator is requested in test mode."""
    return "simulated" if (mode or "").lower() == "simulated" and _sim_allowed() else "seek"


# ═══════════════════════════════════════════════════════════════════════
#  Page / status
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/")
def index() -> Response:
    return bp.send_static_file("index.html")


_CAMERA_CACHE: dict[str, Any] = {"t": 0.0, "value": None}


def _camera_state() -> dict[str, Any]:
    """USB detection (cached 2 s — it enumerates the bus)."""
    if time.time() - _CAMERA_CACHE["t"] < 2.0 and _CAMERA_CACHE["value"] is not None:
        return _CAMERA_CACHE["value"]
    info: dict[str, Any] = {}
    try:
        from pyontrust.instruments.libseek_driver import detect_camera, list_cameras
        detected = detect_camera()
        if detected:
            status_ = "connected"
            cams = list_cameras()
            info = cams[0] if cams else {"type": detected}
        else:
            status_ = "not_connected"
    except ImportError:
        status_ = "no_driver"
    value = {"status": status_, "info": info}
    _CAMERA_CACHE.update(t=time.time(), value=value)
    return value


def _calibration_state() -> dict[str, Any]:
    try:
        from pyontrust.instruments import thermal_calibration as tcal
        return tcal.load_info()
    except Exception:
        return {"calibrated": False, "offset_c": 0.0}


def _flat_field_state(camera_type: str = "compact") -> dict[str, Any]:
    try:
        from pyontrust.instruments.libseek_driver import default_flat_field_path
        ff = default_flat_field_path(camera_type)
        if not ff.is_file():
            return {"saved": False, "set_at": None}
        return {"saved": True,
                "set_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(ff.stat().st_mtime))}
    except Exception:
        return {"saved": False, "set_at": None}


def _result_summary() -> dict[str, Any] | None:
    r = _job.result
    if r is None:
        return None
    if r.get("aborted"):
        return {"outcome": "aborted"}
    if r.get("error"):
        return {"outcome": "error", "error": r["error"]}
    return {"outcome": "pass" if r.get("passed") else "fail", "mode": r.get("mode"),
            "report": pathlib.Path(r["report_path"]).name if r.get("report_path") else None}


@bp.route("/api/state")
def state() -> Response:
    """Everything the dashboard renders, in one snapshot (polled ~1/s).

    ``regions`` carry their live readings (from the latest streamed frame)
    so overlay, table and limit badges all show the same numbers.
    """
    cam = _camera_state()
    regions = _regions.list()
    frame = _feed.frame()
    readings = region_readings(frame, regions) if frame is not None else {}
    tracking = _tracking.status(include_series=False)
    activity = "measuring" if _job.running else "tracking" if tracking["running"] else "idle"
    return jsonify({
        "camera": cam,
        "calibration": _calibration_state(),
        "flat_field": _flat_field_state(str(cam["info"].get("camera_type", "compact"))),
        "live": _feed.meta(),
        "regions": [{**r.to_dict(), "reading": readings.get(r.id)} for r in regions],
        "activity": activity,
        "measurement": {**_job.progress(), "result": _result_summary()},
        "tracking": {k: tracking[k] for k in ("running", "samples", "elapsed_s", "csv_path", "latest")}
                    | {"names": [s["name"] for s in tracking["selections"]]},
    })


@bp.route("/api/status")
def status() -> Response:
    """Camera availability, calibration / flat-field state, job states."""
    cam = _camera_state()
    return jsonify({
        "camera_status": cam["status"],
        "camera_info": cam["info"],
        "calibration": _calibration_state(),
        "flat_field": _flat_field_state(str(cam["info"].get("camera_type", "compact"))),
        "measurement_running": _job.running,
        "tracking_running": _tracking.running,
        "simulated_available": _sim_allowed(),
    })


# ═══════════════════════════════════════════════════════════════════════
#  Regions (zones + tracking selections — one list)
# ═══════════════════════════════════════════════════════════════════════


def _locked_regions() -> tuple[Response, int] | None:
    """Regions are frozen while a session uses them (names = CSV columns)."""
    if _tracking.running or _job.running:
        return _error("Stop the running measurement / tracking before editing regions", 409)
    return None


@bp.route("/api/regions", methods=["GET"])
def regions_list() -> Response:
    return jsonify({"ok": True, "regions": [r.to_dict() for r in _regions.list()]})


@bp.route("/api/regions", methods=["POST"])
def regions_create() -> Response:
    """Body: ``{"kind": "point"|"rect", "x", "y", "w", "h", "name"?, "warn_c"?, "max_c"?}``"""
    if (locked := _locked_regions()) is not None:
        return locked
    try:
        region = _regions.create(_body())
    except RegionError as exc:
        return _error(str(exc), 400)
    return jsonify({"ok": True, "region": region.to_dict()}), 201


@bp.route("/api/regions/<region_id>", methods=["PATCH"])
def regions_update(region_id: str) -> Response:
    if (locked := _locked_regions()) is not None:
        return locked
    try:
        region = _regions.update(region_id, _body())
    except KeyError:
        return _error("No such region", 404)
    except RegionError as exc:
        return _error(str(exc), 400)
    return jsonify({"ok": True, "region": region.to_dict()})


@bp.route("/api/regions/<region_id>", methods=["DELETE"])
def regions_delete(region_id: str) -> Response:
    if (locked := _locked_regions()) is not None:
        return locked
    try:
        _regions.delete(region_id)
    except KeyError:
        return _error("No such region", 404)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════
#  Live view
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/stream")
def live_stream() -> Response:
    """Live MJPEG thermal video (use as ``<img src>``).

    ``annotate=0`` disables the burned-in max/centre markers (the page draws
    its own overlays).  Without a camera the stream shows a status frame and
    keeps retrying, so plugging the camera in starts the video by itself.
    """
    import cv2

    mode = _resolve_mode(request.args.get("mode"))
    annotate = request.args.get("annotate", "1") != "0"

    def gen():
        while True:
            t0 = time.time()
            try:
                temp, source = _arbiter.display_frame(mode)
            except FrameError as exc:
                _feed.set_error(str(exc))
                msg = str(exc).replace(": ", ":\n", 1)
                yield mjpeg_part(status_jpeg(f"No thermal image\n{msg}\nretrying every 2 s ..."))
                time.sleep(2.0)
                continue
            big, meta = render_frame(temp, annotate=annotate,
                                     simulated=_arbiter.is_simulated(source))
            ok, buf = cv2.imencode(".jpg", big, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                continue
            _feed.update(temp, {**meta, "mode": source})
            yield mjpeg_part(buf.tobytes())
            if source == "simulated":  # the real camera paces itself (~9 Hz)
                time.sleep(max(0.0, 0.11 - (time.time() - t0)))

    return Response(stream_with_context(gen()),
                    mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})


@bp.route("/api/stream_meta")
def stream_meta() -> Response:
    """Metadata of the most recent live-stream frame (min/max/fps/error)."""
    return jsonify(_feed.meta())


@bp.route("/api/frame")
def live_frame() -> Response:
    """One colourised frame as base64 PNG + metadata (snapshot API)."""
    import base64

    import cv2

    try:
        temp, source = _arbiter.display_frame(_resolve_mode(request.args.get("mode")))
    except FrameError as exc:
        extra = {"busy": True} if exc.busy else {}
        return _error(str(exc), exc.status, **extra)
    big, meta = render_frame(temp, simulated=_arbiter.is_simulated(source))
    ok, png = cv2.imencode(".png", big)
    if not ok:
        return _error("PNG encoding failed", 500)
    return jsonify({"ok": True, "image_b64": base64.b64encode(png.tobytes()).decode("ascii"),
                    **meta, "mode": source})


@bp.route("/api/frame_raw")
def live_frame_raw() -> Response:
    """One radiometric frame: little-endian float32 °C, row-major.

    For clients that do their own rendering and measuring (the pyontrust
    Thermal Android app).  Size and source travel in headers:
    ``X-Width``, ``X-Height``, ``X-Source``, ``X-Simulated``.
    """
    import numpy as np

    try:
        temp, source = _arbiter.display_frame(_resolve_mode(request.args.get("mode")))
    except FrameError as exc:
        extra = {"busy": True} if exc.busy else {}
        return _error(str(exc), exc.status, **extra)
    arr = np.ascontiguousarray(np.asarray(temp, dtype="<f4"))
    h, w = arr.shape[:2]
    _feed.update(arr, {"width": int(w), "height": int(h), "mode": source,
                       "min_c": round(float(arr.min()), 2), "max_c": round(float(arr.max()), 2)})
    return Response(arr.tobytes(), mimetype="application/octet-stream", headers={
        "X-Width": str(w), "X-Height": str(h), "X-Source": source,
        "X-Simulated": "1" if _arbiter.is_simulated(source) else "0",
        "Cache-Control": "no-store"})


@bp.route("/api/zone_readings", methods=["POST"])
def zone_readings() -> Response:
    """Min / mean / max °C inside each rectangle, from the latest live frame.

    Body: ``{"zones": [{"name": "U3", "x": 40, "y": 20, "w": 18, "h": 12}, ...]}``
    (``width``/``height`` accepted as aliases of ``w``/``h``).
    """
    frame = _feed.frame()
    if frame is None:
        return _error("No live frame yet — is the live feed running?", 409)
    zones = _body().get("zones") or []
    h, w = frame.shape[:2]
    return jsonify({"ok": True, "width": int(w), "height": int(h),
                    "zones": zone_stats(frame, zones if isinstance(zones, list) else [])})


# ═══════════════════════════════════════════════════════════════════════
#  Measurement
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/start", methods=["POST"])
def start_measurement() -> Response:
    """Start a measurement (``mode``, ``duration_s``, ``zones``, limits …)."""
    if _tracking.running:
        return jsonify({"error": "A tracking session holds the camera — stop it first"}), 409
    body = _body()
    if "zones" not in body:
        body["zones"] = _regions.measurement_zones()
    cam_cfg = body.get("camera")
    if cam_cfg is None:
        body["camera"] = {"mode": "seek"}
    elif _wants_sim(cam_cfg) and not _sim_allowed():
        return jsonify({"error": _SIM_DISABLED_MSG}), 400
    from pyontrust.gateway import context
    from pyontrust.gateway.blueprints.station import runs

    actor = context.actor()
    actor["dut"] = actor["dut"] or context.clean(body.get("board_id"))
    run_id = runs().start("thermal", f"measurement:{body.get('mode', 'continuous')}", actor,
                          {"mode": body.get("mode", "continuous"), "duration_s": body.get("duration_s"),
                           "regions": [z.get("name") for z in body.get("zones", [])]})

    def _finished(result: dict[str, Any]) -> None:
        outcome = ("aborted" if result.get("aborted") else "error" if result.get("error")
                   else "pass" if result.get("passed") else "fail")
        runs().finish(run_id, outcome,
                      {k: result.get(k) for k in ("error", "global_max_c", "global_mean_c", "total_frames",
                                                  "fail_reasons") if result.get(k) is not None},
                      [result["report_path"]] if result.get("report_path") else [])

    try:
        # The job opens its own camera instance — free the shared one first.
        _job.start(body, before_launch=_live.release, on_done=_finished)  # job.running blocks re-opens
    except RuntimeError as exc:
        runs().finish(run_id, "error", {"error": str(exc)})
        return jsonify({"error": str(exc)}), 409
    return jsonify({"status": "started", "mode": body.get("mode", "continuous")})


@bp.route("/api/progress")
def progress() -> Response:
    return jsonify(_job.progress())


@bp.route("/api/stop", methods=["POST"])
def stop_measurement() -> Response:
    return jsonify({"status": "stopping" if _job.stop() else "not_running"})


@bp.route("/api/result")
def result() -> Response:
    if _job.result is None:
        return jsonify({"status": "no_result"}), 404
    return jsonify(_job.result)


@bp.route("/api/reports")
def list_reports() -> Response:
    """Saved thermal measurement HTML reports, newest first."""
    if not _REPORT_DIR.exists():
        return jsonify({"reports": []})
    reports = [{"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": f.stat().st_mtime}
               for f in sorted(_REPORT_DIR.glob("thermal_measurement_*.html"), reverse=True)]
    return jsonify({"reports": reports})


@bp.route("/api/report/<name>")
def download_report(name: str) -> Response:
    return send_from_directory(str(_REPORT_DIR.resolve()), name)


# ═══════════════════════════════════════════════════════════════════════
#  Tracking (click-selected points & patches over time)
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/tracking/start", methods=["POST"])
def tracking_start() -> Response:
    """Body: ``{"selections": [{"name","type":"point|patch","x","y","w","h"}], "interval_s": 1}``"""
    if _job.running:
        return _error("A measurement session is running — stop it first", 409)
    body = _body()
    try:
        interval_s = float(body.get("interval_s", 1.0))
    except (TypeError, ValueError):
        return _error("interval_s must be a number", 400)
    cam_body = body.get("camera")
    mode = _resolve_mode(cam_body.get("mode") if isinstance(cam_body, dict) else None)

    if _tracking.running:
        return _error("Tracking is already running", 409)
    selections = body["selections"] if "selections" in body else _regions.tracking_selections()
    try:
        # Tracking holds its own camera instance for the session.
        with _arbiter.handover():
            res = _tracking.start(selections=selections or [], interval_s=interval_s,
                                  camera_cfg=camera_config(mode))
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        logger.exception("tracking start failed")
        return _error(f"Cannot open camera for tracking: {exc}", 502)
    from pyontrust.gateway import context
    from pyontrust.gateway.blueprints.station import runs

    _TRACK_RUN["id"] = runs().start("thermal", "tracking", context.actor(),
                                    {"interval_s": interval_s,
                                     "regions": [s_.get("name") for s_ in selections or []]})
    return jsonify({**res, "ok": True, "camera_mode": mode})


@bp.route("/api/tracking/status")
def tracking_status() -> Response:
    return jsonify(_tracking.status())


_TRACK_RUN: dict[str, str | None] = {"id": None}   # run-registry id of the live session


@bp.route("/api/tracking/stop", methods=["POST"])
def tracking_stop() -> Response:
    res = _tracking.stop()
    run_id, _TRACK_RUN["id"] = _TRACK_RUN["id"], None
    if run_id:
        from pyontrust.gateway.blueprints.station import runs

        runs().finish(run_id, "done", {"samples": res.get("samples")},
                      [res["csv_path"]] if res.get("csv_path") else [])
    return jsonify({**res, "ok": True})


@bp.route("/api/tracking/export.csv")
def tracking_export_csv() -> Response:
    path = _tracking.csv_path
    if path is None or not pathlib.Path(path).exists():
        return _error("No tracking CSV available", 404)
    return send_file(str(path), as_attachment=True, download_name=pathlib.Path(path).name)


# ═══════════════════════════════════════════════════════════════════════
#  Camera tools
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/api/capture_single", methods=["POST"])
def capture_single() -> Response:
    """One analysed frame: global stats, hotspot, per-zone verdicts."""
    from pyontrust.services.thermal_service import ThermalService

    body = _body()
    cam_cfg = body.get("camera") or {"mode": "seek"}
    if _wants_sim(cam_cfg) and not _sim_allowed():
        return jsonify({"error": _SIM_DISABLED_MSG}), 400
    zones = body["zones"] if "zones" in body else _regions.measurement_zones()
    svc = ThermalService(config_dict={"camera": cam_cfg, "zones": zones})
    try:
        if _wants_sim(cam_cfg):
            svc.open()  # tests / CI: private simulated instance
            snap, info = svc.capture(), svc.get_camera_info()
        else:
            # Shared camera — a second USB open would race the live stream.
            with _arbiter.exclusive("seek") as (cam, _source):
                svc.open(camera=cam)
                snap, info = svc.capture(), svc.get_camera_info()
        return jsonify({"snapshot": snap.to_dict(), "camera_info": info})
    except FrameError as exc:
        return jsonify({"error": str(exc)}), exc.status
    except Exception as exc:
        logger.exception("capture_single failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        svc.close()


@bp.route("/api/calibrate", methods=["POST"])
def calibrate() -> Response:
    """One-point calibration.

    ``{"ref_c": 24.0}`` — the camera sees something at ref_c °C: readings are
    shifted so the frame median equals it (persistent, applies to every
    consumer).  ``{"clear": true}`` resets the offset.
    """
    import numpy as np

    from pyontrust.instruments import thermal_calibration as tcal

    body = _body()
    if body.get("clear"):
        return jsonify({"ok": True, **tcal.clear()})
    try:
        ref_c = float(body.get("ref_c", body.get("reference_c")))
    except (TypeError, ValueError):
        return _error("Provide ref_c (number) or clear=true", 400)
    if not -60.0 <= ref_c <= 400.0:
        return _error("ref_c out of range", 400)
    try:
        frame, _source = _arbiter.display_frame("seek")  # includes any existing offset
    except FrameError as exc:
        logger.warning("Calibration grab failed: %s", exc)
        return _error(f"Cannot grab calibration frame: {exc}", exc.status)
    raw_median = float(np.median(frame)) - tcal.load_offset_c()
    info = tcal.save_offset(round(ref_c - raw_median, 3), reference_c=ref_c,
                            scene_median_c=raw_median)
    return jsonify({"ok": True, **info})


@bp.route("/api/flat_field", methods=["POST"])
def flat_field() -> Response:
    """``{"frames": 20}`` learns the flat-field map (aim at a uniform surface);
    ``{"clear": true}`` removes it.  Saved and reused after restarts."""
    if _tracking.running:
        return _error("Stop the running tracking session first", 409)
    body = _body()
    try:
        n_frames = int(body.get("frames", 20))
    except (TypeError, ValueError):
        return _error("frames must be an integer", 400)
    try:
        with _arbiter.exclusive("seek") as (cam, _source):
            if body.get("clear"):
                cam.clear_flat_field()
                return jsonify({"ok": True, "cleared": True})
            info = cam.capture_flat_field(n_frames)
    except FrameError as exc:
        return _error(str(exc), exc.status)
    except Exception as exc:
        logger.warning("Flat-field failed: %s", exc)
        return _error(f"Flat-field failed: {exc}", 502)
    return jsonify({"ok": True, **info})
