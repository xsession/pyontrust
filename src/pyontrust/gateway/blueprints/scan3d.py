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
POST /api/align                           {left, right, rotate, ref_distance_mm?} → auto-align the pair
GET  /api/align?left=…&right=…&rotate=    current alignment of a pair
POST /api/align/clear                     {left, right, rotate} → forget it

Alignment (:mod:`pyontrust.analysis.stereo_align`) compensates how the two
cameras sit: different lenses (scale), roll, vertical offset and the
disparity window.  It is applied to live depth and captures, stored per
camera pair, and — with ``track=1`` on the depth stream — re-estimated every
few seconds so a nudged phone is followed automatically.
POST /api/capture                         {left, right, still, rotate, …} → full analysis of a synchronised pair
POST /api/run                             {left_b64, right_b64, …} → analysis of an uploaded pair (stereo rig)
"""
from __future__ import annotations

import base64
import json
import logging
import threading
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
_ALIGN: dict[str, Any] = {}                 # pair key → PairAlignment
_ALIGN_LOCK = threading.Lock()
_TRACK_EVERY_S = 2.0
_GOOD_INLIERS = 40                         # live auto-alignment needs this many agreeing features


def _check_pair(left: str, right: str) -> None:
    """Two different cameras, and not two cameras of one phone (a phone runs one at a time)."""
    if left == right:
        raise ValueError("Left and right must be two different cameras")
    if left.startswith("phone:") and left.split(":")[1] == right.split(":")[1]:
        raise ValueError("A phone runs one camera at a time — pick cameras on two different phones (or a USB camera)")


def _pair_key(left: str, right: str, rotate: int) -> str:
    return f"{left}|{right}|{int(rotate) % 360}"


def _align_file() -> Path:
    from pyontrust.gateway.context import data_dir

    return data_dir() / "scan3d_alignment.json"


def _align_load() -> None:
    from pyontrust.analysis.stereo_align import PairAlignment

    if _ALIGN.get("_loaded"):
        return
    _ALIGN["_loaded"] = True
    try:
        raw = json.loads(_align_file().read_text())
        for k, v in raw.items():
            _ALIGN[k] = PairAlignment.from_dict(v)
    except (OSError, ValueError, TypeError):
        pass


def _align_save() -> None:
    try:
        f = _align_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in _ALIGN.items() if not k.startswith("_")}
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(f)
    except OSError as exc:  # pragma: no cover - disk full / read-only
        logger.warning("could not store stereo alignment: %s", exc)


def _get_align(key: str) -> Any:
    with _ALIGN_LOCK:
        _align_load()
        return _ALIGN.get(key)


def _set_align(key: str, al: Any, persist: bool = True) -> None:
    with _ALIGN_LOCK:
        _align_load()
        if al is None:
            _ALIGN.pop(key, None)
        else:
            _ALIGN[key] = al
        if persist:
            _align_save()


def _apply_align(left: np.ndarray, right: np.ndarray, al: Any, params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Warp right onto left; returns params with the disparity offset / auto range filled in."""
    left, right = _match_size(left, right)
    p = dict(params)
    if al is None:
        return left, right, p
    h, w = left.shape[:2]
    right = al.warp_right(right, (w, h))
    p["disparity_offset_px"] = al.offset_px(w)
    if str(p.get("num_disp", "auto")) == "auto":
        p["num_disp"] = al.num_disp(w)
    return left, right, p


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
    nd = params.get("num_disp", 96)
    num_disp = 96 if str(nd) == "auto" else int(nd)
    return StereoConfig(fx=fx, fy=float(params.get("fy") or fx),
                        cx=float(params.get("cx") or w / 2), cy=float(params.get("cy") or h / 2),
                        baseline_m=float(params.get("baseline_mm", 120.0)) / 1000.0,
                        num_disp=max(16, (num_disp // 16) * 16), block_size=int(params.get("block_size", 7)),
                        min_disparity=0, disparity_offset_px=float(params.get("disparity_offset_px") or 0.0))


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
    try:
        _check_pair(left_src, right_src)
    except ValueError as exc:
        return _err(str(exc), 400)
    params = request.args.to_dict()
    use_align = params.get("align", "1") != "0"
    track = params.get("track", "0") == "1"
    key = _pair_key(left_src, right_src, rotate)

    def gen():
        from pyontrust.analysis.stereo_align import AlignmentError, blend, estimate_alignment

        analyzer, sig, n, t_fps, t_track = None, None, 0, time.time(), 0.0
        while True:
            t0 = time.time()
            try:
                frames = grab_simultaneous([left_src, right_src])
                left = _prepare(frames[left_src], rotate, width)
                right = _prepare(frames[right_src], rotate, width)
                left, right = _match_size(left, right)
                al = _get_align(key) if use_align else None
                if use_align and track and t0 - t_track >= _TRACK_EVERY_S:
                    # placement guide + automatic alignment that follows a drifting camera
                    t_track = t0
                    try:
                        new = estimate_alignment(left, right)
                        good = new.inliers >= _GOOD_INLIERS and new.residual_px < 1.5 and not new.swapped
                        _DEPTH_LIVE["placement"] = {
                            "ok": good, "inliers": new.inliers, "matches": new.matches, "need": _GOOD_INLIERS,
                            "scale": round(new.scale, 3), "roll_deg": round(new.roll_deg, 2),
                            "ty_px": round(new.ty * left.shape[1], 1), "residual_px": round(new.residual_px, 2),
                            "swapped": new.swapped, "width": int(left.shape[1])}
                        if good:
                            first = al is None
                            al = blend(al, new)
                            _set_align(key, al, persist=first)        # store once established; then follow in memory
                            _DEPTH_LIVE["tracked_t"] = time.time()
                    except AlignmentError as exc:
                        _DEPTH_LIVE["placement"] = {"ok": False, "error": str(exc), "need": _GOOD_INLIERS}
                elif not track:
                    _DEPTH_LIVE.pop("placement", None)
                left, right, p = _apply_align(left, right, al, params)
                if p.get("fx"):   # fx was given for the full-width image: scale to the stream width
                    p["fx"] = float(p["fx"]) * left.shape[1] / float(p.get("fx_width", 1280))
                cfg = _config(p, left.shape)
                if analyzer is None or sig != cfg:
                    analyzer, sig = StereoAnalyzer(cfg), cfg
                res = analyzer.run(left, right)
                img, stats = _depth_colour(res)
                stats["aligned"] = al is not None
                stats["num_disp"] = cfg.num_disp
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
                logger.debug("live depth frame failed", exc_info=True)
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
    try:
        _check_pair(left_src, right_src)
    except ValueError as exc:
        return _err(str(exc), 400)
    still = bool(body.get("still", False))
    try:
        frames = grab_simultaneous([left_src, right_src], still=still)
    except Exception as exc:
        return _err(f"Capture failed: {exc}", 502)
    left = _prepare(frames[left_src], rotate, max_px)
    right = _prepare(frames[right_src], rotate, max_px)
    al = _get_align(_pair_key(left_src, right_src, rotate)) if body.get("align", True) else None
    left, right, params = _apply_align(left, right, al, body)
    if params.get("fx") and params.get("fx_width"):
        params["fx"] = float(params["fx"]) * left.shape[1] / float(params["fx_width"])
    out = _analyse(left, right, params, ("still pair" if still else "live pair") + (" · aligned" if al else ""))
    out["stats"]["aligned"] = al is not None
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


# ═══════════════════════════════════════════════════════════════════════
#  Camera-position compensation (auto-alignment)
# ═══════════════════════════════════════════════════════════════════════

def _pair_args(src: dict[str, Any]) -> tuple[str, str, int]:
    left = _key(_source_arg(src.get("left")))
    right = _key(_source_arg(src.get("right")))
    rotate = int(src.get("rotate", 0) or 0)
    _check_pair(left, right)
    return left, right, rotate


def _al_json(al: Any, width: int | None = None) -> dict[str, Any]:
    d = al.to_dict()
    w = width or al.width or 1280
    d.update(offset_px=round(al.offset_px(w), 1), num_disp=al.num_disp(w), ty_px=round(al.ty * w, 1), at_width=w)
    return d


@bp.route("/api/align", methods=["GET"])
def align_get() -> Response:
    try:
        left, right, rotate = _pair_args(request.args.to_dict())
    except ValueError as exc:
        return _err(str(exc), 400)
    al = _get_align(_pair_key(left, right, rotate))
    return jsonify({"ok": True, "aligned": al is not None, **({"alignment": _al_json(al)} if al else {})})


@bp.route("/api/align/clear", methods=["POST"])
def align_clear() -> Response:
    try:
        left, right, rotate = _pair_args(_body())
    except ValueError as exc:
        return _err(str(exc), 400)
    _set_align(_pair_key(left, right, rotate), None)
    return jsonify({"ok": True})


@bp.route("/api/align", methods=["POST"])
def align_post() -> Response:
    """Estimate how the right camera sits relative to the left and store it.

    A few simultaneous live pairs are tried and the best kept.  With
    ``ref_distance_mm`` (+ fx/baseline) the disparity offset is calibrated so
    the scene median lands at that distance — absolute metric depth.
    """
    from pyontrust.analysis.stereo_align import AlignmentError, epipolar_preview, estimate_alignment

    body = _body()
    try:
        left_src, right_src, rotate = _pair_args(body)
        width = max(480, min(1600, int(body.get("width", 960))))
        tries = max(1, min(5, int(body.get("tries", 3))))
        ref_mm = float(body.get("ref_distance_mm") or 0)
    except (TypeError, ValueError) as exc:
        return _err(str(exc), 400)
    best, best_pair, last_err = None, None, ""
    t0 = time.time()
    for _ in range(tries):
        try:
            frames = grab_simultaneous([left_src, right_src], still=bool(body.get("still", False)))
            left = _prepare(frames[left_src], rotate, width)
            right = _prepare(frames[right_src], rotate, width)
            left, right = _match_size(left, right)
            al = estimate_alignment(left, right)
            if best is None or al.inliers > best.inliers:
                best, best_pair = al, (left, right)
        except AlignmentError as exc:
            last_err = str(exc)
        except Exception as exc:
            return _err(f"Capture failed: {exc}", 502)
        time.sleep(0.15)
    if best is None:
        return _err(last_err or "alignment failed", 422)

    note = None
    if ref_mm > 0:
        fx = float(body.get("fx") or 0) * width / float(body.get("fx_width") or 1280)
        base_mm = float(body.get("baseline_mm") or 0)
        if fx <= 0 or base_mm <= 0:
            return _err("ref_distance_mm needs fx and baseline_mm", 400)
        # stored shift → make the scene's median disparity equal fx·B/Z
        from dataclasses import replace

        from pyontrust.analysis.stereo_align import match_points
        pl, pr = match_points(*best_pair)
        h, w = best_pair[0].shape[:2]
        M = best.matrix(w, h)
        xr_al = M[0, 0] * pr[:, 0] + M[0, 1] * pr[:, 1] + M[0, 2]
        yr_al = M[1, 0] * pr[:, 0] + M[1, 1] * pr[:, 1] + M[1, 2]
        ok = np.abs(yr_al - pl[:, 1]) < 1.5
        if ok.sum() >= 10:
            measured = float(np.median(pl[ok, 0] - xr_al[ok])) + best.offset_px(w)
            wanted = fx * base_mm / ref_mm
            best = replace(best, bias=best.bias + (wanted - measured) / w)
            note = f"depth scale set from the reference: median disparity {measured:.1f} → {wanted:.1f} px"
    _set_align(_pair_key(left_src, right_src, rotate), best)
    left, right = best_pair
    before = epipolar_preview(left, right, None)
    after = epipolar_preview(left, right, best)
    small = lambda im: _prepare(im, 0, 1400)  # noqa: E731
    warn = None
    if best.swapped:
        warn = "The right camera seems to be on the left side — press ⇄ Swap (depth would be inverted)."
    elif best.residual_px > 1.0:
        warn = "Rows still differ by about 1 px — keep the phones still and re-align."
    logger.info("scan3d alignment %s|%s: scale %.3f roll %.2f° ty %.1f px residual %.2f px (%d inliers)",
                left_src, right_src, best.scale, best.roll_deg, best.ty * width, best.residual_px, best.inliers)
    return jsonify({"ok": True, "alignment": _al_json(best, width), "warning": warn, "note": note,
                    "elapsed_s": round(time.time() - t0, 2),
                    "preview": {"before_b64": _b64_jpeg(small(before)), "after_b64": _b64_jpeg(small(after))}})


def _b64_jpeg(arr: np.ndarray, quality: int = 82) -> str:
    import cv2

    ok, buf = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return base64.b64encode(buf.tobytes()).decode() if ok else ""
