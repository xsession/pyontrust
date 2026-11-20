"""Live thermal camera plumbing for the gateway.

One USB thermal camera, several would-be users (live video, zone readings,
calibration, flat-field, single capture, long-term tracking, measurement
runs).  This module keeps that in one place:

* :class:`LiveCamera`    — the camera held open between requests (opening a
  Seek runs a multi-second USB init), released when idle.
* :class:`CameraArbiter` — decides who may use the device right now:
  a running measurement owns it exclusively, a tracking session shares its
  camera, otherwise the live camera serves.
* :func:`render_frame`   — °C frame -> colour image + metadata (display only).
* :class:`LiveFeed`      — latest streamed frame + metadata (fps, errors).
* :func:`zone_stats`     — min / mean / max °C inside rectangles.
* :func:`mjpeg_part` / :func:`status_jpeg` — MJPEG streaming helpers.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import ExitStack, contextmanager
from typing import Any, Callable, Iterator

logger = logging.getLogger("pyontrust.services.thermal_live")

# Simulated camera: automated tests / headless CI only (never offered in the GUI).
SIM_CAMERA: dict[str, Any] = {"mode": "simulated", "inject_hotspot": True, "hotspot_temp_c": 62.0}

DISPLAY_MIN_SPAN_C = 3.0   # never stretch less than this over the colour map
DISPLAY_EDGE_C = 1.0       # bilateral range sigma: smooth < ~1 °C, keep edges


def camera_config(mode: str) -> dict[str, Any]:
    """Instrument config for a camera mode ("seek" or "simulated")."""
    return {"mode": "seek"} if mode == "seek" else dict(SIM_CAMERA)


class FrameError(Exception):
    """A frame could not be provided; carries the HTTP status to report."""

    def __init__(self, status: int, message: str, busy: bool = False) -> None:
        super().__init__(message)
        self.status, self.busy = status, busy


# ═══════════════════════════════════════════════════════════════════════
#  Held-open camera
# ═══════════════════════════════════════════════════════════════════════


class LiveCamera:
    """Camera kept open between requests, released after ``idle_s`` unused."""

    def __init__(self, idle_s: float = 20.0,
                 factory: Callable[[dict[str, Any]], Any] | None = None) -> None:
        self.idle_s = idle_s
        self._factory = factory
        self._lock = threading.RLock()
        self._cam: Any = None
        self._mode: str | None = None
        self._last_used = 0.0
        self._reaper: threading.Thread | None = None

    @property
    def is_open(self) -> bool:
        return self._cam is not None

    @contextmanager
    def exclusive(self, mode: str) -> Iterator[Any]:
        """Yield the open camera (opening it if needed) with exclusive access."""
        with self._lock:
            if self._cam is not None and self._mode != mode:
                self._close_locked()
            if self._cam is None:
                cam = self._create(camera_config(mode))
                cam.open()
                self._cam, self._mode = cam, mode
                self._ensure_reaper()
            self._last_used = time.time()
            try:
                yield self._cam
            except Exception:
                # A failed operation usually means the device went away —
                # drop it so the next request re-opens cleanly.
                self._close_locked()
                raise
            finally:
                self._last_used = time.time()

    def grab(self, mode: str) -> Any:
        """One temperature frame (°C) from the held-open camera."""
        with self.exclusive(mode) as cam:
            return cam.grab_temperature_frame()

    def release(self) -> None:
        with self._lock:
            self._close_locked()

    # ── internals ───────────────────────────────────────────────────────

    def _create(self, cfg: dict[str, Any]) -> Any:
        if self._factory is not None:
            return self._factory(cfg)
        from pyontrust.instruments.seek_thermal import create as create_thermal
        return create_thermal(cfg)

    def _close_locked(self) -> None:
        cam, self._cam, self._mode = self._cam, None, None
        if cam is not None:
            try:
                cam.close()
            except Exception:  # pragma: no cover - best effort
                logger.debug("live camera close failed", exc_info=True)

    def _ensure_reaper(self) -> None:
        if self._reaper is not None and self._reaper.is_alive():
            return

        def _loop() -> None:
            while True:
                time.sleep(2.0)
                with self._lock:
                    if self._cam is None:
                        self._reaper = None
                        return
                    if time.time() - self._last_used > self.idle_s:
                        logger.info("Releasing idle live thermal camera")
                        self._close_locked()
                        self._reaper = None
                        return

        self._reaper = threading.Thread(target=_loop, name="thermal-live-reaper", daemon=True)
        self._reaper.start()


# ═══════════════════════════════════════════════════════════════════════
#  Who owns the device
# ═══════════════════════════════════════════════════════════════════════


class CameraArbiter:
    """Single authority on camera ownership.

    * measurement running -> the measurement owns the device; everyone else
      gets a 409 "busy";
    * tracking running    -> its camera is shared (serialised with sampling);
    * otherwise           -> the held-open :class:`LiveCamera`.
    """

    def __init__(self, live: LiveCamera, tracking: Any,
                 measurement_running: Callable[[], bool]) -> None:
        self.live = live
        self.tracking = tracking
        self._measurement_running = measurement_running
        self._handover = threading.Event()

    @contextmanager
    def handover(self) -> Iterator[None]:
        """Hand the device from the live camera to another owner.

        Releases the live camera and refuses to re-open it until the block
        ends — otherwise a running live stream re-opens it in the gap and two
        USB opens race (the Seek then fails its init).
        """
        self._handover.set()
        try:
            self.live.release()
            yield
        finally:
            self._handover.clear()

    @contextmanager
    def exclusive(self, mode: str = "seek") -> Iterator[tuple[Any, str]]:
        """Yield ``(camera, source)`` with exclusive access.

        ``source`` is ``"tracking"`` when the tracking session's camera is
        lent out, else the live camera mode.  Raises :class:`FrameError`.
        """
        if self._measurement_running():
            raise FrameError(409, "Camera is in use by the running measurement", busy=True)
        if self._handover.is_set():
            raise FrameError(409, "Camera is switching to a new session", busy=True)
        # Only *acquiring* the camera is translated into FrameError; errors
        # raised by the caller's own code propagate unchanged.
        stack = ExitStack()
        try:
            if self.tracking.running:
                source = "tracking"
                try:
                    cam = stack.enter_context(self.tracking.exclusive_camera())
                except RuntimeError as exc:  # session ended between check and use
                    raise FrameError(409, str(exc), busy=True) from exc
            else:
                source = mode
                try:
                    cam = stack.enter_context(self.live.exclusive(mode))
                except Exception as exc:
                    raise FrameError(502, f"Camera not available (connected?): {exc}") from exc
        except BaseException:
            stack.close()
            raise
        with stack:
            yield cam, source

    def display_frame(self, mode: str = "seek") -> tuple[Any, str]:
        """One °C frame for display -> ``(frame, source)``."""
        with self.exclusive(mode) as (cam, source):
            try:
                return cam.grab_temperature_frame(), source
            except Exception as exc:
                raise FrameError(502, f"Cannot grab frame (camera connected?): {exc}") from exc

    def is_simulated(self, source: str) -> bool:
        if source == "simulated":
            return True
        if source == "tracking":
            from pyontrust.instruments.seek_thermal import SimulatedThermalCamera
            return isinstance(getattr(self.tracking, "camera", None), SimulatedThermalCamera)
        return False


# ═══════════════════════════════════════════════════════════════════════
#  Rendering (display only — measurements use the raw temperatures)
# ═══════════════════════════════════════════════════════════════════════


def render_frame(temp: Any, *, annotate: bool = False,
                 simulated: bool = False) -> tuple[Any, dict[str, Any]]:
    """Colour-map a °C frame, upscaled to ~640 px wide -> ``(BGR, meta)``.

    * edge-preserving smoothing hides sub-degree sensor speckle while keeping
      real edges (hand vs. wall, component outlines) sharp;
    * robust percentile stretch with a minimum span, so a flat scene isn't
      blown up into noise and a few extreme pixels can't wash it out.
    """
    import cv2
    import numpy as np

    temp = np.asarray(temp, dtype=np.float32)
    vmin, vmax = float(np.min(temp)), float(np.max(temp))

    disp = cv2.bilateralFilter(temp, 5, DISPLAY_EDGE_C, 2.0)
    lo, hi = (float(v) for v in np.percentile(disp, [1.0, 99.7]))
    if hi - lo < DISPLAY_MIN_SPAN_C:
        mid = (hi + lo) / 2
        lo, hi = mid - DISPLAY_MIN_SPAN_C / 2, mid + DISPLAY_MIN_SPAN_C / 2
    norm = ((disp - lo) / (hi - lo) * 255).clip(0, 255).astype(np.uint8)
    color = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)

    h, w = temp.shape[:2]
    scale = max(1, int(round(640 / w)))
    big = cv2.resize(color, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    my, mx = np.unravel_index(int(np.argmax(temp)), temp.shape)
    cy, cx = h // 2, w // 2
    center_c = float(temp[cy, cx])
    if annotate:
        # Hottest pixel marker + centre spot + min/max readout bar.
        px, py = int(mx * scale + scale // 2), int(my * scale + scale // 2)
        cv2.drawMarker(big, (px, py), (255, 255, 255), cv2.MARKER_CROSS, 22, 2)
        cv2.putText(big, f"{vmax:.1f}C", (px + 10, max(18, py - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.drawMarker(big, (int(cx * scale), int(cy * scale)), (0, 0, 0),
                       cv2.MARKER_TILTED_CROSS, 14, 1)
        bar_y = big.shape[0] - 26
        cv2.rectangle(big, (0, bar_y), (big.shape[1], big.shape[0]), (20, 20, 20), -1)
        cv2.putText(big, f"min {vmin:.1f}C   max {vmax:.1f}C   centre {center_c:.1f}C",
                    (10, big.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (230, 230, 230), 1, cv2.LINE_AA)
    if simulated:
        cv2.putText(big, "SIMULATED - not a camera image", (12, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

    meta = {
        "width": int(w), "height": int(h),          # native resolution (selection coords)
        "display_width": int(w * scale), "display_height": int(h * scale),
        "min_c": round(vmin, 2), "max_c": round(vmax, 2), "center_c": round(center_c, 2),
        "scale_lo_c": round(lo, 2), "scale_hi_c": round(hi, 2),
        "max_xy": [int(mx), int(my)],
    }
    return big, meta


def zone_stats(frame: Any, zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Min / mean / max °C inside each rectangle (clipped to the frame).

    Zones are ``{"name", "x", "y", "w"|"width", "h"|"height"}`` in native
    pixels; malformed entries are skipped, empty intersections report
    ``pixels: 0`` without temperatures.
    """
    import numpy as np

    frame = np.asarray(frame, dtype=np.float32)
    fh, fw = frame.shape[:2]
    out: list[dict[str, Any]] = []
    for z in zones or []:
        try:
            x, y = int(z.get("x", 0)), int(z.get("y", 0))
            w = int(z.get("w", z.get("width", 1)))
            h = int(z.get("h", z.get("height", 1)))
        except (TypeError, ValueError, AttributeError):
            continue
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(fw, x + max(1, w)), min(fh, y + max(1, h))
        region = frame[y0:y1, x0:x1] if (x1 > x0 and y1 > y0) else frame[0:0, 0:0]
        entry: dict[str, Any] = {"name": str(z.get("name", "")), "pixels": int(region.size)}
        if region.size:
            entry.update(min_c=round(float(region.min()), 2),
                         mean_c=round(float(region.mean()), 2),
                         max_c=round(float(region.max()), 2))
        out.append(entry)
    return out


# ═══════════════════════════════════════════════════════════════════════
#  Latest streamed frame
# ═══════════════════════════════════════════════════════════════════════


class LiveFeed:
    """Thread-safe record of the most recent live-stream frame."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._meta: dict[str, Any] = {"t": 0.0}
        self._frame: Any = None
        self._n = 0
        self._t_fps = time.time()

    def update(self, frame: Any, meta: dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            self._n += 1
            if now - self._t_fps >= 1.0:
                self._meta["fps"] = round(self._n / (now - self._t_fps), 1)
                self._n, self._t_fps = 0, now
            self._meta.update(meta, t=now, error=None)
            self._frame = frame

    def set_error(self, message: str) -> None:
        with self._lock:
            self._meta.update(t=time.time(), error=message, fps=0.0)

    def meta(self, max_age_s: float = 4.0) -> dict[str, Any]:
        with self._lock:
            d = dict(self._meta)
        d["active"] = time.time() - d.get("t", 0.0) < max_age_s
        d["ok"] = d["active"] and not d.get("error")
        return d

    def frame(self, max_age_s: float = 5.0) -> Any:
        """Latest frame, or None when the stream has been idle too long."""
        with self._lock:
            if self._frame is None or time.time() - self._meta.get("t", 0.0) > max_age_s:
                return None
            return self._frame


# ═══════════════════════════════════════════════════════════════════════
#  MJPEG helpers
# ═══════════════════════════════════════════════════════════════════════


def mjpeg_part(jpeg: bytes) -> bytes:
    return (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")


def status_jpeg(text: str, w: int = 640, h: int = 480) -> bytes:
    """A dark frame with a short multi-line message (shown in place of video)."""
    import cv2
    import numpy as np

    img = np.full((h, w, 3), 30, np.uint8)
    y = h // 2 - 30
    for line in text.split("\n"):
        cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 255), 1, cv2.LINE_AA)
        y += 28
    return cv2.imencode(".jpg", img)[1].tobytes()
