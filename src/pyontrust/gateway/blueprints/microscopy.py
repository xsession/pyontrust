"""Microscopy — live multi-camera focus stacking and depth-from-focus.

Real cameras only (no synthetic data):

* ``phone:<adb serial>:<camera id>`` — any back camera of an Android phone
  running the pyontrust camera app (live MJPEG ~25 fps, full-res stills,
  **manual focus** → automatic focus sweeps with metric plane distances);
* ``usb:<index>`` — USB microscope / UVC camera (OpenCV).

Several sources work at once: live feeds side by side, one *Capture* takes
a still from every selected camera simultaneously, and each camera keeps its
own stack and result.

Routes (under ``/micro``)
-------------------------
GET  /api/cameras                     available sources (phones' back cameras + USB)
GET  /api/stream?source=…&rotate=     live MJPEG (phones: relayed as-is)
GET  /api/live_stats?source=…         size / fps / focus sharpness of the live feed
POST /api/capture                     {sources:[…], rotate, max_px} → one still per source
POST /api/sweep                       {sources:[phone…], n_frames, near_mm, far_mm, …}
GET  /api/stack                       per-source stacks (count, thumbs, sharpness, z)
POST /api/stack/clear | /api/stack/undo   {source?}
POST /api/run                         {sources?, step_um, z0_um, px_um, align}
GET  /api/export/<slot>/<key>         downloads of the last run
POST /api/release                     release the USB camera
"""
from __future__ import annotations

import base64
import concurrent.futures as cf
import logging
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory

logger = logging.getLogger("pyontrust.gateway.microscopy")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "micro"
bp = Blueprint("microscopy", __name__, static_folder=str(_WEB_DIR), static_url_path="/static")

_RUNS_DIR = Path(tempfile.gettempdir()) / "pyontrust_micro"
_KEEP_RUNS = 10
_MAX_STACK = 32


from pyontrust.services.camera_sources import (  # noqa: E402  (shared camera layer)
    MAX_SOURCES as _MAX_SOURCES, _camera, _key, _live_frame, _prepare, _sharpness, _source_arg,
    _sources_arg, _still, list_sources, live_stats as _live_stats, mjpeg_stream)


def _json_body() -> dict[str, Any]:
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


def _b64_jpeg(arr: np.ndarray, quality: int = 80) -> str:
    import cv2

    ok, buf = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode()


def _thumb(arr: np.ndarray, width: int = 160) -> str:
    import cv2

    h, w = arr.shape[:2]
    small = cv2.resize(arr, (width, max(1, int(h * width / max(w, 1)))), interpolation=cv2.INTER_AREA)
    return _b64_jpeg(small, quality=70)


# ═══════════════════════════════════════════════════════════════════════
#  Stacks (one per source)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class _Stack:
    frames: list[np.ndarray] = field(default_factory=list)
    sharpness: list[float] = field(default_factory=list)
    z_mm: list[float | None] = field(default_factory=list)    # focus distance per plane (sweeps)


_STACKS: dict[str, _Stack] = {}
_STACK_LOCK = threading.Lock()
_LAST: list[dict[str, Any]] = []            # last run, one slot per source


def _add_frame(source: str, frame: np.ndarray, z_mm: float | None = None) -> int:
    with _STACK_LOCK:
        st = _STACKS.setdefault(source, _Stack())
        if st.frames and st.frames[0].shape != frame.shape:
            raise ValueError(f"{source}: frame size {frame.shape[1]}x{frame.shape[0]} differs from its stack "
                             f"({st.frames[0].shape[1]}x{st.frames[0].shape[0]}) — clear the stack first")
        if len(st.frames) >= _MAX_STACK:
            raise ValueError(f"{source}: stack is full ({_MAX_STACK} frames)")
        st.frames.append(frame)
        st.sharpness.append(_sharpness(frame))
        st.z_mm.append(z_mm)
        return len(st.frames)


def _parallel(sources: list[str], fn) -> dict[str, Any]:
    """Run ``fn(source)`` for every source at the same time; errors per source."""
    results: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=len(sources)) as ex:
        futs = {s: ex.submit(fn, s) for s in sources}
        for s, fut in futs.items():
            try:
                results[s] = {"ok": True, **(fut.result() or {})}
            except Exception as exc:
                results[s] = {"ok": False, "error": str(exc)}
    return results


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
    """Live MJPEG of one source (phones relayed as-is)."""
    try:
        src = _source_arg(request.args.get("source"), request.args.get("device"))
        return mjpeg_stream(_key(src), int(request.args.get("rotate", 0)))
    except ValueError as exc:
        return _err(str(exc), 400)


@bp.route("/api/live_stats")
def live_stats() -> Response:
    return jsonify(_live_stats(request.args.get("source", "")))


@bp.route("/api/preview")
def preview() -> Response:
    try:
        src = _source_arg(request.args.get("source"), request.args.get("device"))
        frame = _prepare(_live_frame(src), request.args.get("rotate", 0), request.args.get("max_px", 1280))
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _err(str(exc), 502)
    h, w = frame.shape[:2]
    return jsonify({"ok": True, "image_b64": _b64_jpeg(frame), "width": int(w), "height": int(h),
                    "sharpness": round(_sharpness(frame), 1)})


@bp.route("/api/capture", methods=["POST"])
def capture() -> Response:
    """One still from every selected source — taken simultaneously."""
    body = _json_body()
    try:
        sources = _sources_arg(body)
        rotate, max_px = body.get("rotate", 0), body.get("max_px", 0)
        _prepare(np.zeros((2, 2, 3), np.uint8), rotate, max_px)
    except ValueError as exc:
        return _err(str(exc), 400)

    def one(source: str) -> dict[str, Any]:
        frame = _prepare(_still(_source_arg(source)), rotate, max_px)
        count = _add_frame(source, frame)
        return {"count": count, "thumb": _thumb(frame), "sharpness": round(_sharpness(frame), 1)}

    results = _parallel(sources, one)
    ok = any(r["ok"] for r in results.values())
    return jsonify({"ok": ok, "results": results,
                    **({} if ok else {"error": "; ".join(r["error"] for r in results.values())})}), (200 if ok else 502)


@bp.route("/api/sweep", methods=["POST"])
def sweep() -> Response:
    """Automatic focus bracketing on phone cameras (in parallel).

    Planes are spaced evenly in *distance* from ``far_mm`` to ``near_mm`` so
    the height map gets a uniform metric step; each phone's lens is driven
    to 1/distance diopters, allowed to settle, then a full-res still taken.
    """
    from pyontrust.instruments import phone_camera as pc

    body = _json_body()
    try:
        sources = _sources_arg(body)
        n = max(2, min(_MAX_STACK, int(body.get("n_frames", 8))))
        near = float(body.get("near_mm", 100))
        far = float(body.get("far_mm", 300))
        settle = max(0.1, min(3.0, float(body.get("settle_ms", 400)) / 1000))
        rotate, max_px = body.get("rotate", 0), body.get("max_px", 0)
        _prepare(np.zeros((2, 2, 3), np.uint8), rotate, max_px)
    except (TypeError, ValueError) as exc:
        return _err(str(exc), 400)
    if not 10 <= near < far <= 100000:
        return _err("Need 10 ≤ near_mm < far_mm", 400)
    if any(not s.startswith("phone:") for s in sources):
        return _err("Focus sweeps need phone cameras (USB microscopes have no lens control — capture planes by hand)", 400)
    distances = [far + (near - far) * i / (n - 1) for i in range(n)]     # far → near

    def one(source: str) -> dict[str, Any]:
        _, serial, cam = _source_arg(source)
        pc.stream(serial, cam)                                         # make sure this camera is open
        with _STACK_LOCK:
            _STACKS.pop(source, None)                                  # a sweep is a fresh stack
        try:
            for z in distances:
                pc.set_focus(serial, "manual", 1000.0 / z)
                time.sleep(settle)
                _add_frame(source, _prepare(pc.capture(serial, cam), rotate, max_px), z_mm=round(z, 3))
        finally:
            pc.set_focus(serial, "continuous")
        return {"count": len(distances)}

    t0 = time.time()
    results = _parallel(sources, one)
    ok = all(r["ok"] for r in results.values())
    return jsonify({"ok": ok, "results": results, "distances_mm": [round(z, 2) for z in distances],
                    "elapsed_s": round(time.time() - t0, 2),
                    **({} if ok else {"error": "; ".join(f"{s}: {r['error']}" for s, r in results.items() if not r["ok"])})}), \
        (200 if ok else 502)


@bp.route("/api/stack")
def stack_info() -> Response:
    thumbs = request.args.get("thumbs", "1") != "0"
    with _STACK_LOCK:
        snap = {k: (list(v.frames), list(v.sharpness), list(v.z_mm)) for k, v in _STACKS.items()}
    stacks = {}
    for src, (frames, sharp, z) in snap.items():
        d: dict[str, Any] = {"count": len(frames), "sharpness": [round(s, 1) for s in sharp], "z_mm": z}
        if frames:
            d["width"], d["height"] = int(frames[0].shape[1]), int(frames[0].shape[0])
        if thumbs:
            d["thumbs"] = [_thumb(f) for f in frames]
        stacks[src] = d
    return jsonify({"ok": True, "max": _MAX_STACK, "stacks": stacks,
                    "count": sum(s["count"] for s in stacks.values())})


@bp.route("/api/stack/clear", methods=["POST"])
def stack_clear() -> Response:
    source = _json_body().get("source")
    with _STACK_LOCK:
        if source:
            _STACKS.pop(source, None)
        else:
            _STACKS.clear()
    return jsonify({"ok": True})


@bp.route("/api/stack/undo", methods=["POST"])
def stack_undo() -> Response:
    source = _json_body().get("source")
    with _STACK_LOCK:
        for key in ([source] if source else list(_STACKS)):
            st = _STACKS.get(key)
            if st and st.frames:
                st.frames.pop(); st.sharpness.pop(); st.z_mm.pop()
    return jsonify({"ok": True})


@bp.route("/api/release", methods=["POST"])
def release() -> Response:
    _camera.release()
    return jsonify({"ok": True})


def _new_run_dir(tag: str) -> Path:
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    old = sorted((p for p in _RUNS_DIR.iterdir() if p.is_dir()), key=lambda p: p.name)
    for p in old[: max(0, len(old) - (_KEEP_RUNS * _MAX_SOURCES - 1))]:
        shutil.rmtree(p, ignore_errors=True)
    safe = "".join(c if c.isalnum() else "_" for c in tag)[:40]
    run_dir = _RUNS_DIR / datetime.now().strftime(f"run_%Y%m%d_%H%M%S_%f_{safe}")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _run_one(source: str, frames: list[np.ndarray], z_mm: list[float | None],
             step_um: float, z0_um: float, px_um: float, align: bool) -> dict[str, Any]:
    import cv2

    from pyontrust.analysis.auto_depth import AutoDepthPipeline

    swept = all(z is not None for z in z_mm) and len(z_mm) >= 2
    if swept:                                     # metric planes from the focus sweep
        step_um = abs(z_mm[1] - z_mm[0]) * 1000.0
        z0_um = 0.0
    pipe = AutoDepthPipeline(n_frames=len(frames), step_um=step_um, z0_um=z0_um, px_um=px_um,
                             export=("png", "stl"), align=align)
    out_dir = _new_run_dir(source)
    rep = pipe.run(frames=frames, out_dir=out_dir)
    stacked_path = out_dir / "stacked.png"
    cv2.imwrite(str(stacked_path), rep.stacked_image)
    exports = {k: str(v) for k, v in (rep.exports or {}).items()}
    exports["stacked_png"] = str(stacked_path)
    if rep.report_path:
        exports["report_json"] = str(rep.report_path)
    hm = cv2.imread(exports.get("heightmap_png", "")) if exports.get("heightmap_png") else None
    stats = {**rep.stats, "source": source, "metric_from_focus": swept}
    return {"source": source, "stats": stats, "exports": exports,
            "stacked_png_b64": _b64_jpeg(_prepare(rep.stacked_image, 0, 1600), 85),
            "heightmap_png_b64": _b64_png(hm) if hm is not None else None}


@bp.route("/api/run", methods=["POST"])
def run_stack() -> Response:
    """Stack + depth for every selected source's captured stack."""
    body = _json_body()
    try:
        step_um = float(body.get("step_um", 2.0))
        z0_um = float(body.get("z0_um", 0.0))
        px_um = float(body.get("px_um", 1.0))
        align = bool(body.get("align", True))
    except (TypeError, ValueError) as exc:
        return _err(f"Invalid parameter: {exc}", 400)
    if step_um <= 0 or px_um <= 0:
        return _err("step_um and px_um must be > 0", 400)
    with _STACK_LOCK:
        wanted = body.get("sources") or list(_STACKS)
        jobs = {s: (list(_STACKS[s].frames), list(_STACKS[s].z_mm)) for s in wanted
                if s in _STACKS and len(_STACKS[s].frames) >= 2}
    if not jobs:
        return _err("Capture at least 2 planes (or run a focus sweep) first", 400)

    from pyontrust.gateway import context
    from pyontrust.gateway.blueprints.station import runs

    results: list[dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {s: ex.submit(_run_one, s, f, z, step_um, z0_um, px_um, align) for s, (f, z) in jobs.items()}
        for s, fut in futs.items():
            try:
                res = fut.result()
                runs().record("micro", f"stack:{s.split(':')[0]}", "done", context.actor(),
                              {k: res["stats"].get(k) for k in ("n_frames", "height_min_um", "height_max_um",
                                                                 "confidence_mean", "elapsed_s", "source",
                                                                 "metric_from_focus")},
                              list(res["exports"].values()))
                results.append({"ok": True, **res})
            except Exception as exc:
                logger.exception("microscopy run failed for %s", s)
                runs().record("micro", f"stack:{s.split(':')[0]}", "error", context.actor(), {"error": str(exc), "source": s})
                results.append({"ok": False, "source": s, "error": f"Pipeline failed: {exc}"})
    _LAST[:] = results
    for slot, r in enumerate(results):
        if r.get("ok"):
            r["export_urls"] = {k: f"/micro/api/export/{slot}/{k}" for k in r["exports"]}
    ok = any(r.get("ok") for r in results)
    return jsonify({"ok": ok, "results": results,
                    **({} if ok else {"error": results[0].get("error", "run failed")})}), (200 if ok else 500)


@bp.route("/api/export/<int:slot>/<key>")
def export(slot: int, key: str) -> Response:
    if not 0 <= slot < len(_LAST) or not _LAST[slot].get("ok"):
        return _err("No such result", 404)
    path = _LAST[slot]["exports"].get(key)
    if not path or not Path(path).is_file():
        return _err(f"No export {key!r} available", 404)
    return send_file(path, as_attachment=True, download_name=Path(path).name)
