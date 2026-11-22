"""Camera sources shared by every imaging tool (Microscopy, 3D Scan, …).

A *source* is one real camera, named by a string:

* ``phone:<adb serial>:<camera id>`` — a camera of an Android phone running
  the pyontrust camera app (live MJPEG, full-res stills, manual focus);
* ``usb:<index>`` — a USB microscope / UVC camera (OpenCV).

One implementation of: listing sources, live frames, stills, rotation /
resizing, MJPEG streaming with live statistics.  No simulated sources.
"""
from __future__ import annotations

import concurrent.futures as cf
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from flask import Response, stream_with_context

logger = logging.getLogger("pyontrust.services.camera_sources")

MAX_SOURCES = 4
LIVE: dict[str, dict[str, Any]] = {}       # live-feed statistics per source


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


class _UsbCameras:
    """USB / UVC cameras held open between requests — one slot per device,
    so several cameras (e.g. a stereo pair) run at the same time.  Each slot
    has its own lock and is released after ``idle_s`` without use."""

    def __init__(self, idle_s: float = 30.0) -> None:
        self.idle_s = idle_s
        self._guard = threading.Lock()
        self._slots: dict[int, dict[str, Any]] = {}
        self._reaper: threading.Thread | None = None

    @property
    def held(self) -> set[int]:
        with self._guard:
            return {d for d, s in self._slots.items() if s["cap"] is not None}

    def _slot(self, device: int) -> dict[str, Any]:
        with self._guard:
            return self._slots.setdefault(device, {"lock": threading.Lock(), "cap": None, "used": 0.0})

    def grab(self, device: int, fresh: bool = True) -> np.ndarray:
        slot = self._slot(device)
        with slot["lock"]:
            if slot["cap"] is None:
                cap = _open_capture(device)
                if not cap.isOpened():
                    cap.release()
                    raise RuntimeError(f"Cannot open video device {device}")
                for _ in range(4):            # let auto-exposure settle
                    cap.read()
                slot["cap"] = cap
                self._ensure_reaper()
            slot["used"] = time.time()
            if fresh:
                slot["cap"].grab()            # drop one buffered frame → current image
            ok, frame = slot["cap"].read()
            if not ok or frame is None:
                slot["cap"].release()
                slot["cap"] = None
                raise RuntimeError(f"Video device {device} returned no frame")
            return frame

    def release(self, device: int | None = None) -> None:
        with self._guard:
            slots = [self._slots[device]] if device in self._slots else ([] if device is not None else list(self._slots.values()))
        for slot in slots:
            with slot["lock"]:
                if slot["cap"] is not None:
                    slot["cap"].release()
                    slot["cap"] = None

    def _ensure_reaper(self) -> None:
        if self._reaper is not None and self._reaper.is_alive():
            return

        def loop() -> None:
            while True:
                time.sleep(2.0)
                with self._guard:
                    slots = list(self._slots.items())
                active = 0
                for device, slot in slots:
                    with slot["lock"]:
                        if slot["cap"] is None:
                            continue
                        if time.time() - slot["used"] > self.idle_s:
                            logger.info("Releasing idle USB camera %s", device)
                            slot["cap"].release()
                            slot["cap"] = None
                        else:
                            active += 1
                if not active:
                    self._reaper = None
                    return

        self._reaper = threading.Thread(target=loop, name="usb-camera-reaper", daemon=True)
        self._reaper.start()


_camera = _UsbCameras()

_CAMERA_CACHE: dict[str, Any] = {"t": 0.0, "list": []}


def _probe_cameras() -> list[dict[str, Any]]:
    """List video devices that actually deliver frames (cached for 15 s)."""
    if time.time() - _CAMERA_CACHE["t"] < 15.0:
        return _CAMERA_CACHE["list"]

    found: list[dict[str, Any]] = []
    held = _camera.held
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
        if idx in held:
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





_CAMERA_CACHE: dict[str, Any] = {"t": 0.0, "list": []}




def _device_arg(value: Any) -> int:
    try:
        dev = int(value)
    except (TypeError, ValueError):
        raise ValueError("device must be an integer video index") from None
    if not 0 <= dev < 64:
        raise ValueError("device index out of range")
    return dev


def _source_arg(source: Any, device: Any = None) -> tuple:
    """``"usb:2"`` -> ("usb", 2); ``"phone:SERIAL:0"`` -> ("phone", SERIAL, "0")."""
    if source in (None, ""):
        if device is None:
            raise ValueError("source is required (usb:<n> or phone:<serial>:<camera>)")
        return ("usb", _device_arg(device))
    kind, _, rest = str(source).partition(":")
    if kind == "usb":
        return ("usb", _device_arg(rest))
    if kind == "phone":
        serial, _, cam = rest.rpartition(":")
        if not serial or not cam or not all(c.isalnum() or c in "._-" for c in serial) or not cam.isdigit():
            raise ValueError("phone source must be phone:<serial>:<camera id>")
        return ("phone", serial, cam)
    raise ValueError(f"Unknown source {source!r}")


def _sources_arg(body: dict[str, Any]) -> list[str]:
    raw = body.get("sources")
    if raw is None and body.get("source"):
        raw = [body["source"]]
    if not isinstance(raw, list) or not raw:
        raise ValueError("Select at least one camera")
    if len(raw) > MAX_SOURCES:
        raise ValueError(f"At most {MAX_SOURCES} cameras at once")
    out = []
    for s in raw:
        src = _source_arg(s)
        out.append(":".join(map(str, src)))
    return list(dict.fromkeys(out))


def _key(src: tuple) -> str:
    return ":".join(map(str, src))


def _live_frame(src: tuple) -> np.ndarray:
    """Newest live frame (fast)."""
    if src[0] == "usb":
        return _camera.grab(src[1], fresh=False)
    from pyontrust.instruments import phone_camera as pc
    return pc.stream(src[1], src[2]).latest_bgr()


def _still(src: tuple) -> np.ndarray:
    """Best-quality single image (phones: full-resolution still)."""
    if src[0] == "usb":
        return _camera.grab(src[1], fresh=True)
    from pyontrust.instruments import phone_camera as pc
    return pc.capture(src[1], src[2])


def _prepare(frame: np.ndarray, rotate: Any = 0, max_px: Any = 0) -> np.ndarray:
    """Rotate (0/90/180/270, clockwise) and cap the long edge at ``max_px`` (0 = full)."""
    import cv2

    try:
        rot = int(rotate) % 360
        cap = int(max_px or 0)
    except (TypeError, ValueError):
        raise ValueError("rotate / max_px must be integers") from None
    if rot == 90:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif rot == 180:
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    elif rot == 270:
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rot:
        raise ValueError("rotate must be 0, 90, 180 or 270")
    if cap > 0 and max(frame.shape[:2]) > cap:
        k = cap / max(frame.shape[:2])
        frame = cv2.resize(frame, (int(frame.shape[1] * k), int(frame.shape[0] * k)), interpolation=cv2.INTER_AREA)
    return frame


def _fov_deg(cam: dict[str, Any]) -> float | None:
    """Horizontal field of view from focal length and sensor width."""
    import math

    f, sw = cam.get("focal_mm") or 0, (cam.get("sensor_mm") or [0])[0] or 0
    return round(math.degrees(2 * math.atan(sw / (2 * f)))) if f and sw else None


def _camera_roles(cams: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    """Order a phone's cameras main → other back cameras (widest first) → front, with a role name."""
    back = [c for c in cams if c.get("facing") in ("back", "external")]
    front = [c for c in cams if c.get("facing") == "front"]
    if not back:
        return [(c, "front" if i == 0 else f"front {c['id']}") for i, c in enumerate(front)]
    # main = first camera the phone lists itself (what its own camera app opens)
    main = next((c for c in back if c.get("listed", True) and not c.get("physical_of")), back[0])
    others = sorted((c for c in back if c is not main), key=lambda c: -(_fov_deg(c) or 0))
    main_fov = _fov_deg(main) or 0
    out = [(main, "main")]
    for c in others:
        fov = _fov_deg(c) or 0
        role = "mono" if c.get("mono") else ("wide" if fov > main_fov + 8 else "tele" if fov and fov < main_fov - 8 else "back")
        out.append((c, f"{role} {c['id']}" if role == "back" else role))
    out += [(c, "front" if i == 0 else f"front {c['id']}") for i, c in enumerate(front)]
    return out


def _probe_phones() -> list[dict[str, Any]]:
    """Every camera of every phone (main, other back cameras, front); unusable phones get a hint."""
    from pyontrust.instruments import phone_camera as pc

    out: list[dict[str, Any]] = []
    for ph in pc.list_phones():
        if not ph.ready:
            out.append({"source": None, "kind": "phone", "label": f"📱 {ph.label} — {ph.hint}", "hint": ph.hint})
            continue
        try:
            cams = pc.cameras(ph.serial)
        except Exception as exc:
            out.append({"source": None, "kind": "phone", "label": f"📱 {ph.label} — {exc}", "hint": str(exc)})
            continue
        for c, role in _camera_roles(cams):
            size = "×".join(str(v) for v in c.get("max_size") or [] if v)
            fov = _fov_deg(c)
            old_api = c.get("api") == "camera1"
            manual = bool(c.get("min_focus_diopters")) and not old_api
            detail = " · ".join(x for x in (f"{c['focal_mm']:.1f} mm" if c.get("focal_mm") else "",
                                            f"{fov}°" if fov else "", size) if x)
            out.append({"source": f"phone:{ph.serial}:{c['id']}", "kind": "phone", "serial": ph.serial,
                        "phone": ph.label, "camera_id": str(c["id"]), "role": role,
                        "facing": c.get("facing", "back"), "fov_deg": fov, "hidden": not c.get("listed", True),
                        "label": f"📱 {ph.label} · {role} camera" + (f" ({detail})" if detail else ""),
                        "short": f"{role} · {detail}" if detail else role,
                        "manual_focus": manual,
                        "min_focus_mm": round(1000 / c["min_focus_diopters"]) if manual else None})
    return out


def _error_jpeg(text: str, w: int = 640, h: int = 480) -> bytes:
    import cv2

    img = np.full((h, w, 3), 30, np.uint8)
    y = h // 2 - 20
    for line in text.split("\n"):
        cv2.putText(img, line[:60], (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 255), 1, cv2.LINE_AA)
        y += 28
    return cv2.imencode(".jpg", img)[1].tobytes()


def _mjpeg_part(jpeg: bytes) -> bytes:
    return (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")



def mjpeg_stream(source: str, rotate: int = 0) -> Response:
    """Live MJPEG of one source.  Phone frames are relayed without re-encoding
    (unless rotated); focus sharpness is computed on every 3rd frame."""
    import cv2

    src = _source_arg(source)
    _prepare(np.zeros((2, 2, 3), np.uint8), rotate)       # validates rotate
    key = _key(src)

    def stats(frame: np.ndarray, fps: float) -> None:
        h, w = frame.shape[:2]
        LIVE[key] = {"t": time.time(), "error": None, "width": int(w), "height": int(h),
                      "fps": fps, "sharpness": round(_sharpness(frame), 1)}

    def gen_phone():
        from pyontrust.instruments import phone_camera as pc

        st = pc.stream(src[1], src[2])
        seq, n = 0, 0
        while True:
            got = st.wait(seq, timeout=5.0)
            if not got:
                LIVE[key] = {"t": time.time(), "error": st.error or "no frames from the phone"}
                yield _mjpeg_part(_error_jpeg(f"{src[1]} camera {src[2]}:\n{(st.error or 'waiting for frames')[:60]}\nretrying..."))
                continue
            seq, jpeg = got
            n += 1
            if rotate or n % 3 == 1:
                frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                if rotate:
                    frame = _prepare(frame, rotate)
                    jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])[1].tobytes()
                if n % 3 == 1:
                    stats(frame, st.fps)
            yield _mjpeg_part(jpeg)

    def gen_usb():
        n, t_fps, fps = 0, time.time(), 0.0
        while True:
            t0 = time.time()
            try:
                frame = _prepare(_camera.grab(src[1], fresh=False), rotate)
            except Exception as exc:
                LIVE[key] = {"t": time.time(), "error": str(exc)}
                yield _mjpeg_part(_error_jpeg(f"camera #{src[1]} unavailable:\n{str(exc)[:60]}\nretrying..."))
                time.sleep(1.0)
                continue
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                continue
            n += 1
            if time.time() - t_fps >= 1.0:
                fps, n, t_fps = round(n / (time.time() - t_fps), 1), 0, time.time()
            stats(frame, fps)
            yield _mjpeg_part(buf.tobytes())
            time.sleep(max(0.0, 1 / 15 - (time.time() - t0)))

    gen = gen_phone if src[0] == "phone" else gen_usb
    return Response(stream_with_context(gen()), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})




def live_stats(source: str) -> dict[str, Any]:
    d = dict(LIVE.get(source, {"t": 0.0}))
    d["ok"] = True
    d["active"] = time.time() - d.get("t", 0.0) < 3.0
    return d


def list_sources(refresh: bool = False) -> list[dict[str, Any]]:
    """Phones' back cameras first, then USB cameras."""
    if refresh:
        _CAMERA_CACHE["t"] = 0.0
        from pyontrust.instruments import phone_camera as pc
        pc._CAMERA_CACHE.clear()
    out = _probe_phones()
    out += [{"source": f"usb:{c['index']}", "kind": "usb", "name": c["name"],
             "label": f"🔌 #{c['index']} {c['name']}" + (f" ({c['resolution']})" if c.get("resolution") else "")}
            for c in _probe_cameras()]
    return out


def grab_simultaneous(sources: list[str], still: bool = False) -> dict[str, Any]:
    """One frame from every source at the same moment (one thread each)."""
    fn = _still if still else _live_frame
    out: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=max(1, len(sources))) as ex:
        futs = {s: ex.submit(fn, _source_arg(s)) for s in sources}
        for s, fut in futs.items():
            out[s] = fut.result()
    return out
