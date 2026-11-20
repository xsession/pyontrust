"""3D Scan — live stereo depth from two real cameras.

Left / right cameras are any two sources of the shared camera layer
(:mod:`pyontrust.services.camera_sources`) — typically the back cameras of
two Android phones side by side, or two USB cameras.  No simulated scenes.

Routes (under ``/scan3d``)
--------------------------
GET  /api/cameras                         available sources
GET  /api/stream?source=…&rotate=         live MJPEG of one camera
GET  /api/live_stats?source=…             live-feed statistics
GET  /api/intrinsics?source=…&width=      focal length in px from lens + sensor size (phones)
GET  /api/depth_stream?left=…&right=…     live depth video from the newest frame pair
GET  /api/depth_stats                     latest live-depth statistics
POST /api/capture                         {left, right, still, rotate, …} → full analysis of a synchronised pair
POST /api/run                             {left_b64, right_b64, …} → analysis of an uploaded pair (stereo rig)
"""
from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_from_directory, stream_with_context

from pyontrust.services.camera_sources import (_key, _prepare, _source_arg, grab_simultaneous, list_sources,
                                               live_stats as _live_stats, mjpeg_stream)

logger = logging.getLogger("pyontrust.gateway.scan3d")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "scan3d"
bp = Blueprint("scan3d", __name__, static_folder=str(_WEB_DIR), static_url_path="/static")

_DEPTH_LIVE: dict[str, Any] = {"t": 0.0}


def _body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _err(msg: str, status: int) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": msg}), status


def _b64_png(arr: np.ndarray) -> str:
    import cv2

    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return base64.b64encode(buf.tobytes()).decode()


def _decode_image(b64: str) -> np.ndarray:
    import cv2

    img = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image (expected PNG/JPEG)")
    return img


def _config(params: dict[str, Any], shape: tuple[int, ...]) -> Any:
    """StereoConfig from request params; principal point defaults to the image centre."""
    from pyontrust.analysis.stereo import StereoConfig

    h, w = shape[:2]
    fx = float(params.get("fx") or 0) or 0.9 * w            # sensible fallback, never a fake scene
    num_disp = int(params.get("num_disp", 96))
    return StereoConfig(fx=fx, fy=float(params.get("fy") or fx),
                        cx=float(params.get("cx") or w / 2), cy=float(params.get("cy") or h / 2),
                        baseline_m=float(params.get("baseline_mm", 120.0)) / 1000.0,
                        num_disp=max(16, (num_disp // 16) * 16), block_size=int(params.get("block_size", 7)),
                        min_disparity=0)


def _match_size(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two different phones may deliver different sizes: bring right to left's size."""
    import cv2

    if right.shape[:2] != left.shape[:2]:
        right = cv2.resize(right, (left.shape[1], left.shape[0]), interpolation=cv2.INTER_AREA)
    return left, right


def _depth_colour(res: Any) -> tuple[np.ndarray, dict[str, Any]]:
    import cv2

    valid, depth = res.valid_mask, res.depth_m
    with np.errstate(invalid="ignore"):
        dmin = float(np.nanpercentile(depth[valid], 2)) if valid.any() else None
        dmax = float(np.nanpercentile(depth[valid], 98)) if valid.any() else None
        dmed = float(np.nanmedian(depth[valid])) if valid.any() else None
    lo, hi = (dmin, dmax) if (dmin is not None and dmax and dmax > dmin) else (0.0, 1.0)
    norm = np.clip((depth - lo) / (hi - lo), 0.0, 1.0)
    img = cv2.applyColorMap(((1 - np.nan_to_num(norm)) * 255).astype(np.uint8), cv2.COLORMAP_TURBO)  # near = warm
    img[~valid] = 0
    stats = {"valid_pct": round(100.0 * float(valid.mean()), 1), "n_points": int(valid.sum()),
             "depth_min_m": dmin, "depth_max_m": dmax, "depth_median_m": dmed}
    return img, stats


def _analyse(left: np.ndarray, right: np.ndarray, params: dict[str, Any], mode: str) -> dict[str, Any]:
    import cv2

    from pyontrust.analysis.stereo import StereoAnalyzer

    left, right = _match_size(left, right)
    cfg = _config(params, left.shape)
    t0 = time.time()
    res = StereoAnalyzer(cfg).run(left, right)
    depth_img, stats = _depth_colour(res)
    disp = np.where(res.disparity_px > 0, res.disparity_px, 0.0)
    disp_img = cv2.applyColorMap((np.clip(disp / max(1e-6, float(disp.max() or 1)), 0, 1) * 255).astype(np.uint8),
                                 cv2.COLORMAP_JET)
    h, w = depth_img.shape[:2]
    stats.update(mode=mode, width=int(w), height=int(h), fx_px=round(cfg.fx, 1),
                 baseline_mm=cfg.baseline_m * 1000.0, elapsed_s=round(time.time() - t0, 3))
    logger.info("scan3d %s: %.1f%% matched in %.3fs", mode, stats["valid_pct"], stats["elapsed_s"])
    return {"ok": True, "stats": stats,
            "images": {"left_b64": _b64_png(res.left_rect), "right_b64": _b64_png(res.right_rect),
                       "depth_b64": _b64_png(depth_img), "disparity_b64": _b64_png(disp_img)}}


# ═══════════════════════════════════════════════════════════════════════
#  Routes
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/cameras")
def cameras() -> Response:
    try:
        return jsonify({"ok": True, "cameras": list_sources(bool(request.args.get("refresh")))})
    except ImportError:
        return _err("OpenCV (cv2) is not installed", 500)


@bp.route("/api/stream")
def stream() -> Response:
    try:
        return mjpeg_stream(_key(_source_arg(request.args.get("source"))), int(request.args.get("rotate", 0)))
    except ValueError as exc:
        return _err(str(exc), 400)


@bp.route("/api/live_stats")
def live_stats() -> Response:
    return jsonify(_live_stats(request.args.get("source", "")))


@bp.route("/api/intrinsics")
def intrinsics() -> Response:
    """fx in pixels for an image of ``width`` px: focal_mm / sensor_width_mm × width."""
    try:
        src = _source_arg(request.args.get("source"))
        width = int(request.args.get("width", 1280))
    except ValueError as exc:
        return _err(str(exc), 400)
    if src[0] != "phone":
        return jsonify({"ok": True, "known": False, "note": "USB camera: enter fx from a calibration"})
    from pyontrust.instruments import phone_camera as pc

    try:
        cam = next(c for c in pc.cameras(src[1]) if str(c["id"]) == src[2])
    except StopIteration:
        return _err("camera not found on the phone", 404)
    except Exception as exc:
        return _err(str(exc), 502)
    sensor = (cam.get("sensor_mm") or [0, 0])[0]
    if not cam.get("focal_mm") or not sensor:
        return jsonify({"ok": True, "known": False, "note": "phone does not report focal length / sensor size"})
    return jsonify({"ok": True, "known": True, "fx_px": round(cam["focal_mm"] / sensor * width, 1),
                    "focal_mm": cam["focal_mm"], "sensor_mm": cam["sensor_mm"], "width": width})


@bp.route("/api/depth_stream")
def depth_stream() -> Response:
    """Live depth video: SGBM on the newest left/right live frames (~5 fps at 640 px)."""
    import cv2

    from pyontrust.analysis.stereo import StereoAnalyzer

    try:
        left_src = _key(_source_arg(request.args.get("left")))
        right_src = _key(_source_arg(request.args.get("right")))
        rotate = int(request.args.get("rotate", 0))
        width = max(320, min(1280, int(request.args.get("width", 640))))
    except ValueError as exc:
        return _err(str(exc), 400)
    if left_src == right_src:
        return _err("Left and right must be two different cameras", 400)
    params = request.args.to_dict()

    def gen():
        analyzer, n, t_fps = None, 0, time.time()
        while True:
            t0 = time.time()
            try:
                frames = grab_simultaneous([left_src, right_src])
                left = _prepare(frames[left_src], rotate, width)
                right = _prepare(frames[right_src], rotate, width)
                left, right = _match_size(left, right)
                if analyzer is None or analyzer.cfg.cx * 2 != left.shape[1]:
                    p = dict(params)
                    if p.get("fx"):   # fx was given for the full-width image: scale to the stream width
                        p["fx"] = float(p["fx"]) * left.shape[1] / float(p.get("fx_width", 1280))
                    analyzer = StereoAnalyzer(_config(p, left.shape))
                res = analyzer.run(left, right)
                img, stats = _depth_colour(res)
                n += 1
                if time.time() - t_fps >= 1.0:
                    _DEPTH_LIVE["fps"] = round(n / (time.time() - t_fps), 1)
                    n, t_fps = 0, time.time()
                _DEPTH_LIVE.update(stats, t=time.time(), error=None, compute_ms=round((time.time() - t0) * 1000))
                ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(buf)).encode()
                           + b"\r\n\r\n" + buf.tobytes() + b"\r\n")
            except Exception as exc:
                _DEPTH_LIVE.update(t=time.time(), error=str(exc))
                time.sleep(1.0)
            time.sleep(max(0.0, 0.2 - (time.time() - t0)))

    return Response(stream_with_context(gen()), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})


@bp.route("/api/depth_stats")
def depth_stats() -> Response:
    d = dict(_DEPTH_LIVE)
    d["ok"] = True
    d["active"] = time.time() - d.get("t", 0.0) < 3.0
    return jsonify(d)


@bp.route("/api/capture", methods=["POST"])
def capture_pair() -> Response:
    """Grab left + right at the same moment (live frames or full-res stills) and analyse."""
    body = _body()
    try:
        left_src = _key(_source_arg(body.get("left")))
        right_src = _key(_source_arg(body.get("right")))
        rotate = int(body.get("rotate", 0))
        max_px = int(body.get("max_px", 1600))
    except (TypeError, ValueError) as exc:
        return _err(str(exc), 400)
    if left_src == right_src:
        return _err("Left and right must be two different cameras", 400)
    still = bool(body.get("still", False))
    try:
        frames = grab_simultaneous([left_src, right_src], still=still)
    except Exception as exc:
        return _err(f"Capture failed: {exc}", 502)
    left = _prepare(frames[left_src], rotate, max_px)
    right = _prepare(frames[right_src], rotate, max_px)
    if body.get("fx") and body.get("fx_width"):
        body["fx"] = float(body["fx"]) * left.shape[1] / float(body["fx_width"])
    out = _analyse(left, right, body, "still pair" if still else "live pair")
    from pyontrust.gateway import context
    from pyontrust.gateway.blueprints.station import runs

    runs().record("scan3d", "stereo", "done", context.actor(),
                  {**out["stats"], "left": left_src, "right": right_src})
    return jsonify(out)


@bp.route("/api/run", methods=["POST"])
def run_scan() -> Response:
    """Analyse an uploaded stereo pair (images from a calibrated stereo rig)."""
    body = _body()
    if str(body.get("mode", "upload")) != "upload":
        return _err("Simulated scenes were removed — use live cameras (/api/capture) or upload a real pair", 400)
    left_b64, right_b64 = str(body.get("left_b64") or ""), str(body.get("right_b64") or "")
    if not left_b64 or not right_b64:
        return _err("upload mode requires left_b64 and right_b64", 400)
    try:
        left, right = _decode_image(left_b64), _decode_image(right_b64)
    except ValueError as exc:
        return _err(str(exc), 400)
    return jsonify(_analyse(left, right, body, "upload"))
