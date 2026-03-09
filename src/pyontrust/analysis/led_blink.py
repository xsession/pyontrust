"""LED blink periodicity measurement from webcam frames.

Captures a time-series of frames from an OpenCV webcam, isolates
the red LED region via HSV colour masking, tracks brightness over
time, and computes blink frequency using FFT and zero-crossing.

Design
------
* Uses ``OpenCVWebcam`` (IndustrialCamera) from ``aoi_camera`` for
  frame acquisition — follows project lazy-import convention.
* Pure-compute analysis separated from I/O so the algorithm can be
  unit-tested with synthetic frames.
* Real hardware test at the bottom of the companion test file.

Algorithm
---------
1. Convert each BGR frame to HSV.
2. Apply two-range red mask (H 0-10 and 170-180) with S/V thresholds.
3. Compute mean brightness of the masked region per frame.
4. Build a brightness time-series ``(t[], b[])``.
5. Estimate blink frequency via:
   a. FFT of AC-coupled brightness signal.
   b. Zero-crossing fallback.
   c. Peak-to-peak interval measurement for validation.
6. Report ``BlinkResult`` with frequency, period, duty-cycle, and
   the raw time-series for plotting.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger("pyontrust.analysis.led_blink")


# ───────────────────── lazy imports ─────────────────────


def _import_numpy():
    try:
        import numpy as np
        return np
    except ImportError as exc:
        raise ImportError(
            "numpy is required for LED blink analysis. "
            "Install with: pip install numpy"
        ) from exc


def _import_cv2():
    try:
        import cv2
        return cv2
    except ImportError as exc:
        raise ImportError(
            "OpenCV is required for LED blink analysis. "
            "Install with: pip install opencv-python"
        ) from exc


# ───────────────────── data classes ─────────────────────


@dataclass(frozen=True)
class RedLEDMaskConfig:
    """HSV thresholds for isolating a red LED.

    Red wraps around in HSV so we use two ranges:
      Range 1: H ∈ [low_h1, high_h1]  (near 0°)
      Range 2: H ∈ [low_h2, high_h2]  (near 180°)
    """
    low_h1: int = 0
    high_h1: int = 10
    low_h2: int = 160
    high_h2: int = 180
    low_s: int = 80
    high_s: int = 255
    low_v: int = 80
    high_v: int = 255
    min_pixel_count: int = 5  # ignore mask if fewer red pixels


@dataclass(frozen=True)
class CaptureConfig:
    """Settings for the frame-capture loop."""
    device_index: int = 0
    width: int = 640
    height: int = 480
    capture_duration_s: float = 5.0
    target_fps: float = 30.0
    warmup_frames: int = 10  # discard first N frames (auto-exposure)
    roi: Optional[tuple[int, int, int, int]] = None  # (x, y, w, h) or None=full


@dataclass
class BlinkResult:
    """Complete blink measurement output."""
    ok: bool = False
    frequency_hz: Optional[float] = None
    period_s: Optional[float] = None
    duty_cycle: Optional[float] = None  # 0.0–1.0
    method: str = ""  # "fft", "zero_crossing", "peak_interval"
    blink_count: int = 0
    capture_duration_s: float = 0.0
    frame_count: int = 0
    actual_fps: float = 0.0
    timestamps: list[float] = field(default_factory=list)
    brightness: list[float] = field(default_factory=list)
    red_pixel_counts: list[int] = field(default_factory=list)
    error: Optional[str] = None

    def summary(self) -> dict[str, Any]:
        """Compact dict for JSON serialisation."""
        d: dict[str, Any] = {
            "ok": self.ok,
            "frequency_hz": round(self.frequency_hz, 4) if self.frequency_hz else None,
            "period_s": round(self.period_s, 4) if self.period_s else None,
            "duty_cycle": round(self.duty_cycle, 3) if self.duty_cycle is not None else None,
            "method": self.method,
            "blink_count": self.blink_count,
            "capture_duration_s": round(self.capture_duration_s, 3),
            "frame_count": self.frame_count,
            "actual_fps": round(self.actual_fps, 1),
        }
        if self.error:
            d["error"] = self.error
        return d


# ═══════════════════════════════════════════════════════════════════════
#  Pure-compute: analyse a pre-captured frame sequence
# ═══════════════════════════════════════════════════════════════════════


def extract_red_brightness(
    frame_bgr: Any,
    mask_cfg: RedLEDMaskConfig = RedLEDMaskConfig(),
    roi: Optional[tuple[int, int, int, int]] = None,
) -> tuple[float, int]:
    """Extract mean red-LED brightness from a single BGR frame.

    Returns ``(mean_brightness, pixel_count)`` where *mean_brightness*
    is the average V-channel value within the red mask, and
    *pixel_count* is how many pixels passed the mask.  If fewer than
    ``mask_cfg.min_pixel_count`` pixels are red, returns ``(0.0, 0)``.
    """
    np = _import_numpy()
    cv2 = _import_cv2()

    # Crop ROI
    if roi is not None:
        x, y, w, h = roi
        frame_bgr = frame_bgr[y:y + h, x:x + w]

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

    # Two-range red mask
    lo1 = np.array([mask_cfg.low_h1, mask_cfg.low_s, mask_cfg.low_v], dtype=np.uint8)
    hi1 = np.array([mask_cfg.high_h1, mask_cfg.high_s, mask_cfg.high_v], dtype=np.uint8)
    lo2 = np.array([mask_cfg.low_h2, mask_cfg.low_s, mask_cfg.low_v], dtype=np.uint8)
    hi2 = np.array([mask_cfg.high_h2, mask_cfg.high_s, mask_cfg.high_v], dtype=np.uint8)

    mask = cv2.inRange(hsv, lo1, hi1) | cv2.inRange(hsv, lo2, hi2)
    count = int(cv2.countNonZero(mask))

    if count < mask_cfg.min_pixel_count:
        return 0.0, 0

    v_channel = hsv[:, :, 2]
    mean_val = float(cv2.mean(v_channel, mask=mask)[0])
    return mean_val, count


def analyse_brightness_series(
    timestamps: Sequence[float],
    brightness: Sequence[float],
    min_blink_hz: float = 0.2,
    max_blink_hz: float = 50.0,
) -> BlinkResult:
    """Compute blink frequency from a brightness time-series.

    Uses three methods in priority order:
    1. FFT — most robust for periodic signals.
    2. Zero-crossing — fallback for noisy / non-sinusoidal signals.
    3. Peak-interval — direct measurement of ON→OFF transitions.

    Parameters
    ----------
    timestamps : array-like of float
        Monotonic wall-clock timestamps (seconds).
    brightness : array-like of float
        Mean red-LED brightness at each timestamp.
    min_blink_hz / max_blink_hz
        Plausible blink frequency range (rejects out-of-band noise).
    """
    np = _import_numpy()

    ts = np.asarray(timestamps, dtype=np.float64)
    br = np.asarray(brightness, dtype=np.float64)

    if len(ts) < 8:
        return BlinkResult(
            ok=False, error="Not enough frames for frequency estimation",
            timestamps=list(timestamps), brightness=list(brightness),
            frame_count=len(ts),
        )

    duration = float(ts[-1] - ts[0])
    if duration <= 0:
        return BlinkResult(
            ok=False, error="Zero capture duration",
            timestamps=list(timestamps), brightness=list(brightness),
            frame_count=len(ts),
        )

    actual_fps = len(ts) / duration

    # ---------- 1. FFT ----------
    freq_fft, period_fft = _fft_frequency(ts, br, min_blink_hz, max_blink_hz)

    # ---------- 2. Zero-crossing ----------
    freq_zc, period_zc = _zero_crossing_frequency(ts, br, min_blink_hz, max_blink_hz)

    # ---------- 3. Peak-interval ----------
    freq_pk, period_pk, n_blinks, duty = _peak_interval_frequency(
        ts, br, min_blink_hz, max_blink_hz,
    )

    # Pick best
    freq: Optional[float] = None
    period: Optional[float] = None
    method = ""

    if freq_fft is not None:
        freq, period, method = freq_fft, period_fft, "fft"
    elif freq_pk is not None:
        freq, period, method = freq_pk, period_pk, "peak_interval"
    elif freq_zc is not None:
        freq, period, method = freq_zc, period_zc, "zero_crossing"

    if freq is None:
        return BlinkResult(
            ok=False, error="Could not determine blink frequency",
            capture_duration_s=duration, frame_count=len(ts),
            actual_fps=actual_fps,
            timestamps=list(timestamps), brightness=list(brightness),
        )

    return BlinkResult(
        ok=True,
        frequency_hz=freq,
        period_s=period,
        duty_cycle=duty,
        method=method,
        blink_count=n_blinks if n_blinks else int(round(freq * duration)),
        capture_duration_s=duration,
        frame_count=len(ts),
        actual_fps=actual_fps,
        timestamps=list(timestamps),
        brightness=list(brightness),
    )


# ──────────── frequency estimation helpers ────────────


def _fft_frequency(
    ts: Any, br: Any,
    min_hz: float, max_hz: float,
) -> tuple[Optional[float], Optional[float]]:
    """Dominant frequency via FFT."""
    np = _import_numpy()

    duration = float(ts[-1] - ts[0])
    n = len(ts)
    dt = duration / (n - 1)

    # Uniform re-sampling
    t_uniform = np.linspace(float(ts[0]), float(ts[-1]), n)
    y_uniform = np.interp(t_uniform, ts, br)
    y_ac = y_uniform - np.mean(y_uniform)

    # Hann window to reduce spectral leakage
    window = np.hanning(len(y_ac))
    y_windowed = y_ac * window

    yf = np.fft.rfft(y_windowed)
    freqs = np.fft.rfftfreq(len(y_windowed), d=dt)

    if len(freqs) < 2:
        return None, None

    mag = np.abs(yf)
    mag[0] = 0.0  # ignore DC

    # Restrict to plausible range
    valid = (freqs >= min_hz) & (freqs <= max_hz)
    if not np.any(valid):
        return None, None

    mag_valid = np.where(valid, mag, 0.0)
    k = int(np.argmax(mag_valid))
    peak_mag = float(mag_valid[k])

    # SNR check: peak should be ≥ 3× the mean of valid bins
    mean_mag = float(np.mean(mag_valid[valid]))
    if mean_mag <= 0 or peak_mag < 3.0 * mean_mag:
        return None, None

    f = float(freqs[k])
    if f <= 0:
        return None, None
    return f, 1.0 / f


def _zero_crossing_frequency(
    ts: Any, br: Any,
    min_hz: float, max_hz: float,
) -> tuple[Optional[float], Optional[float]]:
    """Frequency via zero-crossing of AC-coupled brightness."""
    np = _import_numpy()

    y_ac = br - np.mean(br)
    signs = (y_ac >= 0).astype(np.int8)
    crossings = int(np.sum(signs[1:] != signs[:-1]))
    duration = float(ts[-1] - ts[0])

    if crossings < 2 or duration <= 0:
        return None, None

    f = (crossings / 2.0) / duration
    if f < min_hz or f > max_hz:
        return None, None
    return f, 1.0 / f


def _peak_interval_frequency(
    ts: Any, br: Any,
    min_hz: float, max_hz: float,
) -> tuple[Optional[float], Optional[float], int, Optional[float]]:
    """Frequency via measuring intervals between brightness peaks.

    Also estimates duty cycle (fraction of time LED is ON).
    Returns ``(freq, period, blink_count, duty_cycle)``.
    """
    np = _import_numpy()

    # Simple threshold at the midpoint
    threshold = float((np.max(br) + np.min(br)) / 2.0)
    amplitude = float(np.max(br) - np.min(br))
    if amplitude < 5.0:
        # No meaningful on/off transitions
        return None, None, 0, None

    above = br >= threshold

    # Find rising edges (OFF→ON transitions)
    edges = np.diff(above.astype(np.int8))
    rising = np.where(edges == 1)[0]
    falling = np.where(edges == -1)[0]

    if len(rising) < 2:
        return None, None, 0, None

    # Period = mean interval between consecutive rising edges
    intervals = np.diff(ts[rising])
    mean_period = float(np.mean(intervals))
    if mean_period <= 0:
        return None, None, 0, None

    freq = 1.0 / mean_period
    if freq < min_hz or freq > max_hz:
        return None, None, 0, None

    # Duty cycle: fraction of samples above threshold
    duty = float(np.sum(above)) / float(len(above))

    return freq, mean_period, len(rising), duty


# ═══════════════════════════════════════════════════════════════════════
#  I/O: capture frames from a live webcam
# ═══════════════════════════════════════════════════════════════════════


def capture_led_frames(
    cap_cfg: CaptureConfig = CaptureConfig(),
    mask_cfg: RedLEDMaskConfig = RedLEDMaskConfig(),
) -> tuple[list[float], list[float], list[int], int]:
    """Open the webcam, capture frames, and return brightness series.

    Returns ``(timestamps, brightness, red_pixel_counts, total_frames)``.
    """
    cv2 = _import_cv2()

    cap = cv2.VideoCapture(cap_cfg.device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        # Fallback without DSHOW
        cap = cv2.VideoCapture(cap_cfg.device_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open webcam at index {cap_cfg.device_index}. "
            "Check device connection."
        )

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_cfg.height)

        # Warmup: let auto-exposure settle
        for _ in range(cap_cfg.warmup_frames):
            cap.read()

        timestamps: list[float] = []
        brightness_vals: list[float] = []
        red_counts: list[int] = []
        frame_interval = 1.0 / cap_cfg.target_fps
        t_start = time.perf_counter()

        while True:
            t_now = time.perf_counter()
            elapsed = t_now - t_start
            if elapsed >= cap_cfg.capture_duration_s:
                break

            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame grab failed at t=%.3f", elapsed)
                continue

            mean_b, px_count = extract_red_brightness(
                frame, mask_cfg, roi=cap_cfg.roi,
            )
            timestamps.append(elapsed)
            brightness_vals.append(mean_b)
            red_counts.append(px_count)

            # Pace to target FPS
            t_next = t_start + len(timestamps) * frame_interval
            sleep_time = t_next - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        cap.release()

    return timestamps, brightness_vals, red_counts, len(timestamps)


# ═══════════════════════════════════════════════════════════════════════
#  Top-level convenience: capture + analyse in one call
# ═══════════════════════════════════════════════════════════════════════


def measure_led_blink_rate(
    cap_cfg: CaptureConfig = CaptureConfig(),
    mask_cfg: RedLEDMaskConfig = RedLEDMaskConfig(),
    min_blink_hz: float = 0.2,
    max_blink_hz: float = 50.0,
) -> BlinkResult:
    """End-to-end: open webcam → capture → analyse → return BlinkResult.

    This is the main entry point for the diagnostic page and CLI usage.
    """
    try:
        timestamps, brightness, red_counts, n_frames = capture_led_frames(
            cap_cfg, mask_cfg,
        )
    except Exception as exc:
        return BlinkResult(ok=False, error=str(exc))

    if n_frames < 8:
        return BlinkResult(
            ok=False, error=f"Only {n_frames} frames captured — need ≥ 8",
            frame_count=n_frames,
            timestamps=timestamps,
            brightness=brightness,
            red_pixel_counts=red_counts,
        )

    result = analyse_brightness_series(
        timestamps, brightness,
        min_blink_hz=min_blink_hz,
        max_blink_hz=max_blink_hz,
    )
    result.red_pixel_counts = red_counts
    return result
