"""Microscopy GUI backend — focus stacking + depth-from-focus.

Wraps :class:`pyontrust.analysis.auto_depth.AutoDepthPipeline` (stack ->
metric height map -> exports) behind a small JSON API for the ``/micro`` web
page.  Two frame sources are supported:

* ``synthetic`` — a multi-depth PCB scene (``generate_synthetic_stack``), so
  the tool works without any hardware;
* ``captured``  — frames grabbed from a USB microscope / UVC camera (OpenCV).
  The user steps the focus knob between captures (one click per plane, or a
  timed burst while sweeping focus); frame *i* is assigned height
  ``z0 + i * step``.

Routes (under ``/micro``)
-------------------------
GET  /                       — page
GET  /api/cameras            — probe local video devices
GET  /api/preview?device=N   — one JPEG frame + focus sharpness score
POST /api/capture            — append one frame to the capture stack
GET  /api/stack              — capture-stack summary (count + thumbnails)
POST /api/stack/clear        — drop all captured frames
POST /api/stack/undo         — drop the last captured frame
POST /api/release            — release the camera device
POST /api/run                — run stack + depth (source synthetic|captured)
GET  /api/last               — summary of the most recent run
GET  /api/export/<key>       — download an export of the most recent run
"""
from __future__ import annotations

import base64
import logging
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory, stream_with_context

logger = logging.getLogger("pyontrust.gateway.microscopy")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "micro"
bp = Blueprint(
    "microscopy", __name__, static_folder=str(_WEB_DIR), static_url_path="/static",
)

_RUNS_DIR = Path(tempfile.gettempdir()) / "pyontrust_micro"
_KEEP_RUNS = 10
_MAX_STACK = 32

_LAST: dict[str, Any] = {}  # summary of the most recent run (in-process)
_STACK: list[np.ndarray] = []  # captured BGR frames, in focus order
_STACK_SHARPNESS: list[float] = []
_STACK_LOCK = threading.Lock()


def _json_body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


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
    scale = width / max(w, 1)
    small = cv2.resize(arr, (width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    return _b64_jpeg(small, quality=70)


def _sharpness(arr: np.ndarray) -> float:
    """Variance of the Laplacian — standard focus measure (higher = sharper)."""
    import cv2

    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.ndim == 3 else arr
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


# ═══════════════════════════════════════════════════════════════════════
#  Camera (USB microscope / UVC) — held open between preview polls
# ═══════════════════════════════════════════════════════════════════════


def _open_capture(device: int) -> Any:
    import cv2

    backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
    cap = cv2.VideoCapture(device, backend)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(device)
    return cap


class _MicroCamera:
    """One OpenCV capture device, opened lazily and released when idle."""

    def __init__(self, idle_s: float = 30.0) -> None:
        self.idle_s = idle_s
        self._lock = threading.Lock()
        self._cap: Any = None
        self._device: int | None = None
        self._last_used = 0.0
        self._reaper: threading.Thread | None = None

    @property
    def device(self) -> int | None:
        return self._device

    def grab(self, device: int, fresh: bool = True) -> np.ndarray:
        with self._lock:
            if self._cap is not None and self._device != device:
                self._close_locked()
            if self._cap is None:
                cap = _open_capture(device)
                if not cap.isOpened():
                    cap.release()
                    raise RuntimeError(f"Cannot open video device {device}")
                self._cap, self._device = cap, device
                # Drain a few frames: UVC cameras deliver dark / unexposed
                # frames right after opening while auto-exposure settles.
                for _ in range(4):
                    cap.read()
                self._ensure_reaper()
            self._last_used = time.time()
            # Drop one buffered frame so the returned image is current, not
            # whatever sat in the driver queue since the last poll.  The live
            # stream reads continuously, so its frames are already current.
            if fresh:
                self._cap.grab()
            ok, frame = self._cap.read()
            if not ok or frame is None:
                self._close_locked()
                raise RuntimeError(f"Video device {device} returned no frame")
            return frame

    def release(self) -> None:
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        cap, self._cap, self._device = self._cap, None, None
        if cap is not None:
            try:
                cap.release()
            except Exception:  # pragma: no cover - best effort
                pass

    def _ensure_reaper(self) -> None:
        if self._reaper is not None and self._reaper.is_alive():
            return

        def _loop() -> None:
            while True:
                time.sleep(2.0)
                with self._lock:
                    if self._cap is None:
                        self._reaper = None
                        return
                    if time.time() - self._last_used > self.idle_s:
                        logger.info("Releasing idle microscopy camera %s", self._device)
                        self._close_locked()
                        self._reaper = None
                        return

        self._reaper = threading.Thread(target=_loop, name="micro-cam-reaper", daemon=True)
        self._reaper.start()


_camera = _MicroCamera()
_CAMERA_CACHE: dict[str, Any] = {"t": 0.0, "list": []}


def _device_arg(value: Any) -> int:
    try:
        dev = int(value)
    except (TypeError, ValueError):
        raise ValueError("device must be an integer video index") from None
    if not 0 <= dev < 64:
        raise ValueError("device index out of range")
    return dev


def _probe_cameras() -> list[dict[str, Any]]:
    """List video devices that actually deliver frames (cached for 15 s)."""
    if time.time() - _CAMERA_CACHE["t"] < 15.0:
        return _CAMERA_CACHE["list"]

    found: list[dict[str, Any]] = []
    held = _camera.device
    if sys.platform.startswith("linux"):
        candidates = sorted(int(p.name[5:]) for p in Path("/dev").glob("video*")
                            if p.name[5:].isdigit())
    else:
        candidates = list(range(6))

    for idx in candidates:
        name = ""
        sysfs = Path(f"/sys/class/video4linux/video{idx}/name")
        if sysfs.is_file():
            try:
                name = sysfs.read_text().strip()
            except OSError:
                pass
        if idx == held:
            found.append({"index": idx, "name": name or f"Camera {idx}", "in_use": True})
            continue
        cap = _open_capture(idx)
        try:
            ok = cap.isOpened() and cap.read()[0]
            if ok:
                w = int(cap.get(3))  # CAP_PROP_FRAME_WIDTH
                h = int(cap.get(4))  # CAP_PROP_FRAME_HEIGHT
                found.append({"index": idx, "name": name or f"Camera {idx}",
                              "resolution": f"{w}x{h}"})
        finally:
            cap.release()

    _CAMERA_CACHE.update(t=time.time(), list=found)
    return found


# ═══════════════════════════════════════════════════════════════════════
#  Routes
# ═══════════════════════════════════════════════════════════════════════


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/cameras")
def cameras() -> Response:
    if request.args.get("refresh"):
        _CAMERA_CACHE["t"] = 0.0
    try:
        cams = _probe_cameras()
    except ImportError:
        return jsonify({"ok": False, "error": "OpenCV (cv2) is not installed", "cameras": []}), 500
    return jsonify({"ok": True, "cameras": cams})


@bp.route("/api/preview")
def preview() -> Response:
    try:
        dev = _device_arg(request.args.get("device", 0))
        frame = _camera.grab(dev)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    h, w = frame.shape[:2]
    return jsonify({
        "ok": True,
        "image_b64": _b64_jpeg(frame),
        "width": int(w), "height": int(h),
        "sharpness": round(_sharpness(frame), 1),
    })


# Latest live-stream statistics (sharpness meter etc.), updated per frame.
_LIVE: dict[str, Any] = {"t": 0.0}


def _error_jpeg(text: str, w: int = 640, h: int = 480) -> bytes:
    import cv2

    img = np.full((h, w, 3), 30, np.uint8)
    y = h // 2 - 20
    for line in text.split("\n"):
        cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 255), 1, cv2.LINE_AA)
        y += 28
    return cv2.imencode(".jpg", img)[1].tobytes()


def _mjpeg_part(jpeg: bytes) -> bytes:
    return (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")


@bp.route("/api/stream")
def stream() -> Response:
    """Live MJPEG video from a USB microscope / camera (use as <img src>)."""
    import cv2

    try:
        dev = _device_arg(request.args.get("device", 0))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    max_fps = max(1.0, min(30.0, float(request.args.get("fps", 15))))

    def gen():
        period = 1.0 / max_fps
        n, t_fps = 0, time.time()
        while True:
            t0 = time.time()
            try:
                frame = _camera.grab(dev, fresh=False)
            except Exception as exc:
                _LIVE.update(t=time.time(), error=str(exc))
                yield _mjpeg_part(_error_jpeg(f"Camera #{dev} unavailable:\n{exc}\nretrying..."))
                time.sleep(1.0)
                continue
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                continue
            n += 1
            now = time.time()
            if now - t_fps >= 1.0:
                _LIVE["fps"] = round(n / (now - t_fps), 1)
                n, t_fps = 0, now
            h, w = frame.shape[:2]
            _LIVE.update(t=now, error=None, device=dev, width=int(w), height=int(h),
                         sharpness=round(_sharpness(frame), 1))
            yield _mjpeg_part(buf.tobytes())
            time.sleep(max(0.0, period - (time.time() - t0)))

    return Response(stream_with_context(gen()),
                    mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})


@bp.route("/api/live_stats")
def live_stats() -> Response:
    """Stats of the most recent live-stream frame (for the focus meter)."""
    d = dict(_LIVE)
    d["ok"] = True
    d["active"] = time.time() - d.get("t", 0.0) < 3.0
    return jsonify(d)


def _stack_summary(with_thumbs: bool = True) -> dict[str, Any]:
    with _STACK_LOCK:
        frames = list(_STACK)
        sharp = list(_STACK_SHARPNESS)
    out: dict[str, Any] = {"ok": True, "count": len(frames), "max": _MAX_STACK,
                           "sharpness": [round(s, 1) for s in sharp]}
    if frames:
        h, w = frames[0].shape[:2]
        out["width"], out["height"] = int(w), int(h)
    if with_thumbs:
        out["thumbs"] = [_thumb(f) for f in frames]
    return out


@bp.route("/api/capture", methods=["POST"])
def capture() -> Response:
    body = _json_body()
    try:
        dev = _device_arg(body.get("device", 0))
        frame = _camera.grab(dev)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    with _STACK_LOCK:
        if _STACK and _STACK[0].shape != frame.shape:
            return jsonify({"ok": False, "error": (
                f"Frame size {frame.shape[1]}x{frame.shape[0]} differs from the stack "
                f"({_STACK[0].shape[1]}x{_STACK[0].shape[0]}) — clear the stack first")}), 409
        if len(_STACK) >= _MAX_STACK:
            return jsonify({"ok": False, "error": f"Stack is full ({_MAX_STACK} frames)"}), 409
        _STACK.append(frame)
        _STACK_SHARPNESS.append(_sharpness(frame))
        count = len(_STACK)

    return jsonify({"ok": True, "count": count, "thumb": _thumb(frame),
                    "sharpness": round(_STACK_SHARPNESS[-1], 1)})


@bp.route("/api/stack")
def stack_info() -> Response:
    return jsonify(_stack_summary(with_thumbs=request.args.get("thumbs", "1") != "0"))


@bp.route("/api/stack/clear", methods=["POST"])
def stack_clear() -> Response:
    with _STACK_LOCK:
        _STACK.clear()
        _STACK_SHARPNESS.clear()
    return jsonify({"ok": True, "count": 0})


@bp.route("/api/stack/undo", methods=["POST"])
def stack_undo() -> Response:
    with _STACK_LOCK:
        if _STACK:
            _STACK.pop()
            _STACK_SHARPNESS.pop()
        count = len(_STACK)
    return jsonify({"ok": True, "count": count})


@bp.route("/api/release", methods=["POST"])
def release() -> Response:
    _camera.release()
    return jsonify({"ok": True})


def _new_run_dir() -> Path:
    """Fresh output dir per run; keep only the newest ``_KEEP_RUNS``."""
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    old = sorted((p for p in _RUNS_DIR.iterdir() if p.is_dir()), key=lambda p: p.name)
    for p in old[: max(0, len(old) - (_KEEP_RUNS - 1))]:
        shutil.rmtree(p, ignore_errors=True)
    run_dir = _RUNS_DIR / datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


@bp.route("/api/run", methods=["POST"])
def run_stack() -> Response:
    """Run the full focus-stacking + depth pipeline and return images + stats."""
    body = _json_body()
    try:
        source = str(body.get("source", "synthetic"))
        n_frames = max(2, min(_MAX_STACK, int(body.get("n_frames", 8))))
        step_um = float(body.get("step_um", 2.0))
        z0_um = float(body.get("z0_um", 0.0))
        px_um = float(body.get("px_um", 1.0))
        width = max(64, min(1920, int(body.get("width", 480))))
        height = max(64, min(1920, int(body.get("height", 360))))
        seed = int(body.get("seed", 7))
        align = bool(body.get("align", True))
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"Invalid parameter: {exc}"}), 400
    if step_um <= 0 or px_um <= 0:
        return jsonify({"ok": False, "error": "step_um and px_um must be > 0"}), 400

    from pyontrust.analysis.auto_depth import AutoDepthPipeline

    if source == "captured":
        with _STACK_LOCK:
            frames = list(_STACK)
        if len(frames) < 2:
            return jsonify({"ok": False, "error": (
                "Capture at least 2 frames at different focus positions first")}), 400
    elif source == "synthetic":
        from pyontrust.analysis.focus_stacking import generate_synthetic_stack

        # size is (h, w) in the generator's signature
        frames, _meta = generate_synthetic_stack(n_frames=n_frames, size=(height, width), seed=seed)
    else:
        return jsonify({"ok": False, "error": f"Unknown source {source!r}"}), 400

    pipe = AutoDepthPipeline(
        n_frames=len(frames), step_um=step_um, z0_um=z0_um, px_um=px_um,
        export=("png", "stl"), align=align,
    )
    out_dir = _new_run_dir()
    try:
        rep = pipe.run(frames=frames, out_dir=out_dir)
    except Exception as exc:
        logger.exception("microscopy run failed")
        return jsonify({"ok": False, "error": f"Pipeline failed: {exc}"}), 500

    import cv2

    # The stacked composite is useful on its own (sharp all-in-focus image).
    stacked_path = out_dir / "stacked.png"
    cv2.imwrite(str(stacked_path), rep.stacked_image)
    exports = {k: str(v) for k, v in (rep.exports or {}).items()}
    exports["stacked_png"] = str(stacked_path)
    if rep.report_path:
        exports["report_json"] = str(rep.report_path)

    heightmap_png_b64: str | None = None
    hm_path = Path(exports.get("heightmap_png", ""))
    if hm_path.is_file():
        img = cv2.imread(str(hm_path))
        if img is not None:
            heightmap_png_b64 = _b64_png(img)

    logger.info(
        "microscopy run (%s): %d frames, %.1f um range in %.3fs",
        source, len(frames),
        rep.stats.get("height_max_um", 0.0) - rep.stats.get("height_min_um", 0.0),
        rep.stats.get("elapsed_s", 0.0),
    )

    stats = {**rep.stats, "source": source}
    _LAST.clear()
    _LAST.update(stats=stats, exports=exports,
                 report_path=str(rep.report_path) if rep.report_path else None)

    return jsonify({
        "ok": True,
        "stats": stats,
        "stacked_png_b64": _b64_png(rep.stacked_image),
        "heightmap_png_b64": heightmap_png_b64,
        "exports": exports,
        "export_urls": {k: f"/micro/api/export/{k}" for k in exports},
        "report_path": str(rep.report_path) if rep.report_path else None,
    })


@bp.route("/api/last")
def last_run() -> Response:
    """Summary of the most recent run (kept in-process)."""
    return jsonify({"ok": True, "stats": _LAST.get("stats"), "report_path": _LAST.get("report_path"),
                    "exports": _LAST.get("exports", {})})


@bp.route("/api/export/<key>")
def export(key: str) -> Response:
    """Download one export (heightmap_png, mesh_stl, stacked_png, report_json)."""
    path = (_LAST.get("exports") or {}).get(key)
    if not path or not Path(path).is_file():
        return jsonify({"ok": False, "error": f"No export {key!r} available"}), 404
    return send_file(path, as_attachment=True, download_name=Path(path).name)
