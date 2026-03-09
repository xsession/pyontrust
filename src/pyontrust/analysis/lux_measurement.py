"""Parallel lux measurement — webcam + Android light sensor.

Toggles the Android phone flashlight (torch) on and off while
simultaneously measuring illuminance from two independent sources:

1. **Webcam** — estimates lux from mean V-channel brightness of
   captured frames (calibrated linear mapping).
2. **Android light sensor** — reads the hardware ambient-light
   sensor via ADB / simulated driver.

The two time-series are then correlated and compared to validate
that both sensors track the same light event.

Design
------
* Pure-compute analysis is separated from I/O (same as ``led_blink``).
* Torch control uses ``adb shell cmd statusbar`` or ``adb shell
  svc power`` depending on Android version.
* A ``threading.Thread`` runs the webcam capture loop while the main
  thread paces the Android sensor reads — both share a common
  monotonic clock.
* All heavy imports (numpy, cv2) are lazy.

Algorithm
---------
1. Open webcam + Android sensors.
2. Start parallel capture threads (webcam frames + phone light sensor).
3. Toggle torch ON → wait → toggle OFF → wait (configurable cycles).
4. Stop capture, collect time-series.
5. Analyse:
   a. Per-source statistics (mean, std, min, max).
   b. ON-vs-OFF delta for each source.
   c. Pearson correlation between the two series.
   d. Lag estimation via cross-correlation peak.
6. Package into ``LuxResult`` dataclass.
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger("pyontrust.analysis.lux_measurement")


# ───────────────────── lazy imports ─────────────────────


def _import_numpy():
    try:
        import numpy as np
        return np
    except ImportError as exc:
        raise ImportError(
            "numpy is required for lux measurement. "
            "Install with: pip install numpy"
        ) from exc


def _import_cv2():
    try:
        import cv2
        return cv2
    except ImportError as exc:
        raise ImportError(
            "OpenCV is required for lux measurement. "
            "Install with: pip install opencv-python"
        ) from exc


# ───────────────────── data classes ─────────────────────


@dataclass(frozen=True)
class LuxCaptureConfig:
    """Settings for the parallel lux capture."""

    # Webcam
    device_index: int = 0
    width: int = 640
    height: int = 480
    target_fps: float = 30.0
    warmup_frames: int = 10
    roi: Optional[tuple[int, int, int, int]] = None  # (x, y, w, h)

    # Torch cycling
    torch_on_s: float = 3.0       # seconds torch stays ON per cycle
    torch_off_s: float = 3.0      # seconds torch stays OFF per cycle
    n_cycles: int = 3             # number of ON/OFF cycles
    pre_capture_s: float = 1.0    # baseline capture before first toggle

    # Android sensor
    android_mode: str = "simulated"   # simulated / adb / adb_bridge
    android_sample_rate_hz: float = 10.0

    # Webcam-to-lux calibration
    # lux ≈ brightness * lux_scale + lux_offset
    # Default: 0–255 V-channel → ~0–500 lux (indoor range)
    lux_scale: float = 2.0
    lux_offset: float = 0.0


@dataclass
class LuxResult:
    """Complete parallel lux measurement output."""

    ok: bool = False
    error: Optional[str] = None

    # Webcam series
    webcam_timestamps: list[float] = field(default_factory=list)
    webcam_lux: list[float] = field(default_factory=list)
    webcam_brightness: list[float] = field(default_factory=list)

    # Android sensor series
    android_timestamps: list[float] = field(default_factory=list)
    android_lux: list[float] = field(default_factory=list)

    # Torch state log (for overlay on charts)
    torch_events: list[dict[str, Any]] = field(default_factory=list)
    # e.g. [{"t": 1.0, "state": "ON"}, {"t": 4.0, "state": "OFF"}, ...]

    # Capture metadata
    capture_duration_s: float = 0.0
    webcam_frame_count: int = 0
    webcam_actual_fps: float = 0.0
    android_sample_count: int = 0
    n_cycles: int = 0

    # Analysis results
    webcam_lux_mean_on: Optional[float] = None
    webcam_lux_mean_off: Optional[float] = None
    webcam_lux_delta: Optional[float] = None
    android_lux_mean_on: Optional[float] = None
    android_lux_mean_off: Optional[float] = None
    android_lux_delta: Optional[float] = None

    correlation: Optional[float] = None       # Pearson r
    lag_ms: Optional[float] = None            # cross-correlation lag

    def summary(self) -> dict[str, Any]:
        """Compact dict for JSON serialisation."""
        d: dict[str, Any] = {
            "ok": self.ok,
            "capture_duration_s": round(self.capture_duration_s, 3),
            "webcam_frame_count": self.webcam_frame_count,
            "webcam_actual_fps": round(self.webcam_actual_fps, 1),
            "android_sample_count": self.android_sample_count,
            "n_cycles": self.n_cycles,
            "webcam_lux_mean_on": _r(self.webcam_lux_mean_on),
            "webcam_lux_mean_off": _r(self.webcam_lux_mean_off),
            "webcam_lux_delta": _r(self.webcam_lux_delta),
            "android_lux_mean_on": _r(self.android_lux_mean_on),
            "android_lux_mean_off": _r(self.android_lux_mean_off),
            "android_lux_delta": _r(self.android_lux_delta),
            "correlation": _r(self.correlation),
            "lag_ms": _r(self.lag_ms),
        }
        if self.error:
            d["error"] = self.error
        return d


def _r(v: Optional[float], decimals: int = 4) -> Optional[float]:
    return round(v, decimals) if v is not None else None


# ═══════════════════════════════════════════════════════════════════════
#  Torch control via ADB
# ═══════════════════════════════════════════════════════════════════════

_ADB = os.environ.get("ADB_PATH", "adb")


def _run_adb_cmd(*args: str, timeout: float = 5.0) -> str:
    """Run an ADB command and return stdout."""
    cmd = [_ADB] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("adb not found — install Android SDK Platform-Tools")
    except subprocess.TimeoutExpired:
        return ""


def torch_on() -> bool:
    """Turn on the Android phone's flashlight (torch) via ADB.

    Tries multiple methods for compatibility across Android versions:
    1. ``cmd statusbar expand-notifications`` + keyevent (Android 6+)
    2. ``svc power`` camera flashlight API via shell
    3. Direct camera2 API via am broadcast

    Returns True if the command completed without error.
    """
    try:
        # Method 1: am broadcast to custom receiver (most reliable with helper APK)
        _run_adb_cmd(
            "shell", "cmd", "statusbar", "expand-notifications",
            timeout=3,
        )
        # Method 2: Use settings/content provider (Android 7+)
        out = _run_adb_cmd(
            "shell",
            "am", "broadcast",
            "-a", "com.pyontrust.TORCH",
            "--ez", "state", "true",
            timeout=3,
        )
        if "error" in out.lower():
            # Fallback: use svc power via shell (needs root on some devices)
            _run_adb_cmd(
                "shell",
                "settings", "put", "system", "torch_state", "1",
                timeout=3,
            )
        logger.info("Torch ON command sent")
        return True
    except Exception as exc:
        logger.warning("torch_on failed: %s", exc)
        return False


def torch_off() -> bool:
    """Turn off the Android phone's flashlight via ADB."""
    try:
        _run_adb_cmd(
            "shell",
            "am", "broadcast",
            "-a", "com.pyontrust.TORCH",
            "--ez", "state", "false",
            timeout=3,
        )
        _run_adb_cmd(
            "shell",
            "settings", "put", "system", "torch_state", "0",
            timeout=3,
        )
        logger.info("Torch OFF command sent")
        return True
    except Exception as exc:
        logger.warning("torch_off failed: %s", exc)
        return False


class SimulatedTorch:
    """Simulated torch for CI / testing without a phone.

    Tracks state and generates synthetic lux modulation data.
    """

    def __init__(self) -> None:
        self._on = False
        self._events: list[dict[str, Any]] = []
        self._t0 = time.perf_counter()

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def on(self) -> bool:
        self._on = True
        self._events.append({
            "t": time.perf_counter() - self._t0,
            "state": "ON",
        })
        return True

    def off(self) -> bool:
        self._on = False
        self._events.append({
            "t": time.perf_counter() - self._t0,
            "state": "OFF",
        })
        return True


# ═══════════════════════════════════════════════════════════════════════
#  Webcam lux estimation
# ═══════════════════════════════════════════════════════════════════════


def frame_to_brightness(
    frame_bgr: Any,
    roi: Optional[tuple[int, int, int, int]] = None,
) -> float:
    """Compute mean brightness (V-channel of HSV) from a BGR frame.

    Returns a value in [0, 255].
    """
    np = _import_numpy()
    cv2 = _import_cv2()

    if roi is not None:
        x, y, w, h = roi
        frame_bgr = frame_bgr[y:y + h, x:x + w]

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:, :, 2]
    return float(np.mean(v_channel))


def brightness_to_lux(
    brightness: float,
    scale: float = 2.0,
    offset: float = 0.0,
) -> float:
    """Convert V-channel mean brightness (0–255) to estimated lux.

    Uses a simple linear calibration model:
        lux = brightness * scale + offset

    For a more accurate mapping, calibrate ``scale`` and ``offset``
    against a reference lux meter.
    """
    return max(0.0, brightness * scale + offset)


# ═══════════════════════════════════════════════════════════════════════
#  Pure-compute: analyse pre-captured parallel series
# ═══════════════════════════════════════════════════════════════════════


def classify_on_off_regions(
    timestamps: Sequence[float],
    torch_events: Sequence[dict[str, Any]],
) -> tuple[list[int], list[int]]:
    """Classify each sample index as ON or OFF based on torch events.

    Returns ``(on_indices, off_indices)``.
    """
    if not torch_events:
        # No events — assume all OFF
        return [], list(range(len(timestamps)))

    on_indices: list[int] = []
    off_indices: list[int] = []

    for i, t in enumerate(timestamps):
        # Find the last event before this timestamp
        state = "OFF"
        for evt in torch_events:
            if evt["t"] <= t:
                state = evt["state"]
            else:
                break
        if state == "ON":
            on_indices.append(i)
        else:
            off_indices.append(i)

    return on_indices, off_indices


def analyse_parallel_lux(
    webcam_timestamps: Sequence[float],
    webcam_brightness: Sequence[float],
    android_timestamps: Sequence[float],
    android_lux_values: Sequence[float],
    torch_events: Sequence[dict[str, Any]],
    lux_scale: float = 2.0,
    lux_offset: float = 0.0,
) -> LuxResult:
    """Analyse pre-captured parallel lux data.

    Computes:
    - Webcam-estimated lux from brightness series
    - Per-source ON/OFF statistics
    - Pearson correlation between resampled series
    - Cross-correlation lag

    Parameters
    ----------
    webcam_timestamps : array-like
        Monotonic timestamps (seconds) for webcam frames.
    webcam_brightness : array-like
        Mean V-channel brightness [0–255] per frame.
    android_timestamps : array-like
        Monotonic timestamps (seconds) for phone sensor readings.
    android_lux_values : array-like
        Phone sensor lux readings.
    torch_events : list of dicts
        Torch state transitions [{"t": float, "state": "ON"/"OFF"}].
    lux_scale / lux_offset : float
        Webcam brightness → lux calibration coefficients.
    """
    np = _import_numpy()

    w_ts = list(webcam_timestamps)
    w_br = list(webcam_brightness)
    a_ts = list(android_timestamps)
    a_lux = list(android_lux_values)

    if len(w_ts) < 4:
        return LuxResult(ok=False, error="Too few webcam frames (need ≥ 4)")
    if len(a_ts) < 2:
        return LuxResult(ok=False, error="Too few Android samples (need ≥ 2)")

    # Webcam lux estimation
    w_lux = [brightness_to_lux(b, lux_scale, lux_offset) for b in w_br]

    # Duration
    duration = max(w_ts[-1] - w_ts[0], a_ts[-1] - a_ts[0]) if w_ts and a_ts else 0

    # ON/OFF classification for webcam
    w_on_idx, w_off_idx = classify_on_off_regions(w_ts, torch_events)
    w_on_vals = [w_lux[i] for i in w_on_idx] if w_on_idx else []
    w_off_vals = [w_lux[i] for i in w_off_idx] if w_off_idx else []

    # ON/OFF classification for Android
    a_on_idx, a_off_idx = classify_on_off_regions(a_ts, torch_events)
    a_on_vals = [a_lux[i] for i in a_on_idx] if a_on_idx else []
    a_off_vals = [a_lux[i] for i in a_off_idx] if a_off_idx else []

    # Statistics
    w_mean_on = float(np.mean(w_on_vals)) if w_on_vals else None
    w_mean_off = float(np.mean(w_off_vals)) if w_off_vals else None
    w_delta = (w_mean_on - w_mean_off) if (w_mean_on is not None and w_mean_off is not None) else None

    a_mean_on = float(np.mean(a_on_vals)) if a_on_vals else None
    a_mean_off = float(np.mean(a_off_vals)) if a_off_vals else None
    a_delta = (a_mean_on - a_mean_off) if (a_mean_on is not None and a_mean_off is not None) else None

    # ── Correlation between the two series ──
    # Resample both to a common uniform time base
    correlation: Optional[float] = None
    lag_ms: Optional[float] = None

    t_start = max(w_ts[0], a_ts[0])
    t_end = min(w_ts[-1], a_ts[-1])
    overlap = t_end - t_start

    if overlap > 0.5 and len(w_ts) >= 4 and len(a_ts) >= 4:
        # Resample to ~10 Hz uniform grid
        n_pts = max(10, int(overlap * 10))
        t_uniform = np.linspace(t_start, t_end, n_pts)

        w_interp = np.interp(t_uniform, w_ts, w_lux)
        a_interp = np.interp(t_uniform, a_ts, a_lux)

        # Pearson correlation
        if np.std(w_interp) > 1e-9 and np.std(a_interp) > 1e-9:
            r = float(np.corrcoef(w_interp, a_interp)[0, 1])
            correlation = r

        # Cross-correlation for lag estimation
        w_ac = w_interp - np.mean(w_interp)
        a_ac = a_interp - np.mean(a_interp)
        if np.any(w_ac != 0) and np.any(a_ac != 0):
            xcorr = np.correlate(w_ac, a_ac, mode="full")
            dt_uniform = overlap / (n_pts - 1) if n_pts > 1 else 1.0
            lags = np.arange(-(n_pts - 1), n_pts) * dt_uniform
            peak_idx = int(np.argmax(np.abs(xcorr)))
            lag_ms = float(lags[peak_idx]) * 1000.0

    webcam_fps = len(w_ts) / (w_ts[-1] - w_ts[0]) if len(w_ts) > 1 and w_ts[-1] > w_ts[0] else 0

    return LuxResult(
        ok=True,
        webcam_timestamps=w_ts,
        webcam_lux=w_lux,
        webcam_brightness=w_br,
        android_timestamps=a_ts,
        android_lux=a_lux,
        torch_events=list(torch_events),
        capture_duration_s=duration,
        webcam_frame_count=len(w_ts),
        webcam_actual_fps=webcam_fps,
        android_sample_count=len(a_ts),
        n_cycles=sum(1 for e in torch_events if e.get("state") == "ON"),
        webcam_lux_mean_on=w_mean_on,
        webcam_lux_mean_off=w_mean_off,
        webcam_lux_delta=w_delta,
        android_lux_mean_on=a_mean_on,
        android_lux_mean_off=a_mean_off,
        android_lux_delta=a_delta,
        correlation=correlation,
        lag_ms=lag_ms,
    )


# ═══════════════════════════════════════════════════════════════════════
#  I/O: parallel capture from webcam + Android sensor
# ═══════════════════════════════════════════════════════════════════════


def _webcam_capture_thread(
    cap_cfg: LuxCaptureConfig,
    stop_event: threading.Event,
    t0: float,
    out_timestamps: list[float],
    out_brightness: list[float],
) -> None:
    """Background thread: capture webcam frames and compute brightness."""
    cv2 = _import_cv2()

    cap = cv2.VideoCapture(cap_cfg.device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(cap_cfg.device_index)
    if not cap.isOpened():
        logger.error("Cannot open webcam %d", cap_cfg.device_index)
        return

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_cfg.height)

        # Warmup
        for _ in range(cap_cfg.warmup_frames):
            cap.read()

        frame_interval = 1.0 / cap_cfg.target_fps

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                continue
            t_now = time.perf_counter() - t0
            br = frame_to_brightness(frame, roi=cap_cfg.roi)
            out_timestamps.append(t_now)
            out_brightness.append(br)

            # Pace to target FPS
            t_next = t0 + len(out_timestamps) * frame_interval
            sleep_time = t_next - time.perf_counter()
            if sleep_time > 0:
                time.sleep(min(sleep_time, 0.1))
    finally:
        cap.release()


def _android_sensor_thread(
    cfg: LuxCaptureConfig,
    stop_event: threading.Event,
    t0: float,
    out_timestamps: list[float],
    out_lux: list[float],
) -> None:
    """Background thread: read Android light sensor periodically."""
    from pyontrust.instruments.android_sensors import create as create_android

    inst = create_android({
        "mode": cfg.android_mode,
        "sample_rate_hz": cfg.android_sample_rate_hz,
    })
    inst.open()

    try:
        interval = 1.0 / cfg.android_sample_rate_hz
        while not stop_event.is_set():
            t_now = time.perf_counter() - t0
            try:
                data = inst.read_light(0.05)  # quick 50 ms read
                lux_val = data.get("lux", 0)
                if isinstance(lux_val, list):
                    # Sensor may return a list of readings
                    for v in lux_val:
                        out_timestamps.append(t_now)
                        out_lux.append(float(v))
                else:
                    out_timestamps.append(t_now)
                    out_lux.append(float(lux_val))
            except Exception as exc:
                logger.warning("Android light read error: %s", exc)

            # Pace
            sleep_time = interval - (time.perf_counter() - t0 - t_now)
            if sleep_time > 0:
                time.sleep(min(sleep_time, 0.2))
    finally:
        inst.close()


def capture_parallel_lux(
    cfg: LuxCaptureConfig = LuxCaptureConfig(),
    use_real_torch: bool = False,
) -> LuxResult:
    """Run the full parallel capture with torch cycling.

    Opens the webcam and Android sensor in background threads,
    cycles the torch ON/OFF, and returns the raw data in a
    ``LuxResult`` for analysis.
    """
    stop_event = threading.Event()
    t0 = time.perf_counter()

    # Data collectors (thread-safe lists via GIL)
    w_ts: list[float] = []
    w_br: list[float] = []
    a_ts: list[float] = []
    a_lux: list[float] = []

    # Torch controller
    torch = SimulatedTorch() if not use_real_torch else None
    torch_events: list[dict[str, Any]] = []

    # Start capture threads
    webcam_thread = threading.Thread(
        target=_webcam_capture_thread,
        args=(cfg, stop_event, t0, w_ts, w_br),
        daemon=True,
    )
    android_thread = threading.Thread(
        target=_android_sensor_thread,
        args=(cfg, stop_event, t0, a_ts, a_lux),
        daemon=True,
    )

    webcam_thread.start()
    android_thread.start()

    try:
        # Pre-capture baseline
        time.sleep(cfg.pre_capture_s)

        # Torch cycling
        for cycle in range(cfg.n_cycles):
            # ON
            t_on = time.perf_counter() - t0
            if torch:
                torch.on()
            elif use_real_torch:
                torch_on()
            torch_events.append({"t": t_on, "state": "ON"})
            logger.info("Cycle %d/%d: torch ON at t=%.2f", cycle + 1, cfg.n_cycles, t_on)
            time.sleep(cfg.torch_on_s)

            # OFF
            t_off = time.perf_counter() - t0
            if torch:
                torch.off()
            elif use_real_torch:
                torch_off()
            torch_events.append({"t": t_off, "state": "OFF"})
            logger.info("Cycle %d/%d: torch OFF at t=%.2f", cycle + 1, cfg.n_cycles, t_off)
            time.sleep(cfg.torch_off_s)

    finally:
        stop_event.set()
        webcam_thread.join(timeout=5)
        android_thread.join(timeout=5)

    if not w_ts:
        return LuxResult(ok=False, error="No webcam frames captured")
    if not a_ts:
        return LuxResult(ok=False, error="No Android sensor readings")

    duration = time.perf_counter() - t0
    return LuxResult(
        ok=True,
        webcam_timestamps=w_ts,
        webcam_brightness=w_br,
        webcam_lux=[brightness_to_lux(b, cfg.lux_scale, cfg.lux_offset) for b in w_br],
        android_timestamps=a_ts,
        android_lux=a_lux,
        torch_events=torch_events,
        capture_duration_s=duration,
        webcam_frame_count=len(w_ts),
        webcam_actual_fps=len(w_ts) / (w_ts[-1] - w_ts[0]) if len(w_ts) > 1 else 0,
        android_sample_count=len(a_ts),
        n_cycles=cfg.n_cycles,
    )


# ═══════════════════════════════════════════════════════════════════════
#  Top-level convenience: capture + analyse in one call
# ═══════════════════════════════════════════════════════════════════════


def measure_parallel_lux(
    cfg: LuxCaptureConfig = LuxCaptureConfig(),
    use_real_torch: bool = False,
) -> LuxResult:
    """End-to-end: open webcam + phone → capture with torch cycling → analyse.

    This is the main entry-point for the diagnostic page and CLI.
    """
    try:
        raw = capture_parallel_lux(cfg, use_real_torch=use_real_torch)
    except Exception as exc:
        return LuxResult(ok=False, error=str(exc))

    if not raw.ok:
        return raw

    # Run analysis on the raw captured data
    result = analyse_parallel_lux(
        raw.webcam_timestamps,
        raw.webcam_brightness,
        raw.android_timestamps,
        raw.android_lux,
        raw.torch_events,
        lux_scale=cfg.lux_scale,
        lux_offset=cfg.lux_offset,
    )
    # Preserve torch events from capture
    result.torch_events = raw.torch_events
    return result
