"""Thermal measurement — production-grade Seek Thermal measurement sessions.

Orchestrates multi-frame thermal capture sessions with:

- **Continuous monitoring** — capture N frames at a target rate, compute
  running statistics per zone.
- **Soak test** — hold DUT at operating state for a configurable duration,
  track temperature rise and settle.
- **Delta measurement** — capture baseline, apply stimulus, capture again,
  compute per-zone Δ T.
- **Gradient scan** — detect spatial temperature gradients across the board.
- **HTML report** — self-contained Catppuccin Mocha report with time-series
  charts, heatmap snapshots, zone tables, and pass/fail verdict.

The module uses the ``ThermalService`` (which wraps SeekThermalCamera /
SimulatedThermalCamera + ThermalAnalyzer) for frame acquisition and
analysis, so it works identically with real libseek USB hardware and
simulated cameras in CI.

Algorithm
---------
1. Open thermal camera (libseek / seekcamera / simulated).
2. Warm-up: discard first N frames for FFC stabilisation.
3. Run selected measurement mode (continuous / soak / delta / gradient).
4. Accumulate per-zone time-series + global statistics.
5. Evaluate pass/fail against user-defined thermal limits.
6. Generate ``ThermalMeasurementResult`` + HTML report.

Usage::

    from pyontrust.analysis.thermal.measurement import (
        ThermalMeasurementConfig, run_thermal_measurement,
    )

    cfg = ThermalMeasurementConfig(
        mode="continuous",
        duration_s=30.0,
        camera={"mode": "simulated", "base_temp_c": 35.0, "inject_hotspot": True},
        zones=[
            {"name": "MCU", "x": 40, "y": 30, "width": 30, "height": 30,
             "warn_temp_c": 60, "max_temp_c": 85},
        ],
    )
    result = run_thermal_measurement(cfg)
    print(result.summary())
    result.write_report("test_reports/thermal_meas.html")
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import os
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
    ThermalZone,
    ZoneReading,
)

logger = logging.getLogger("pyontrust.analysis.thermal.measurement")


# ═══════════════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ThermalMeasurementConfig:
    """Configuration for a thermal measurement session."""

    # ── Mode ─────────────────────────────────────────────────────────
    mode: str = "continuous"
    """Measurement mode:
    - "continuous"  — capture for duration_s, report statistics
    - "soak"        — monitor temperature rise until stable or timeout
    - "delta"       — baseline → stimulus → measure ΔT
    - "gradient"    — single-frame spatial gradient analysis
    """

    # ── Timing ───────────────────────────────────────────────────────
    duration_s: float = 30.0
    """Total capture duration (continuous & soak modes)."""

    capture_interval_s: float = 0.5
    """Seconds between frame captures."""

    warmup_frames: int = 5
    """Frames to discard for FFC / sensor warm-up."""

    # ── Soak mode ────────────────────────────────────────────────────
    soak_stable_window_s: float = 10.0
    """Window over which temperature must be stable."""

    soak_stable_threshold_c: float = 0.5
    """Max ΔT in the stable window to declare "settled"."""

    soak_timeout_s: float = 300.0
    """Abort soak if not settled within this time."""

    # ── Delta mode ───────────────────────────────────────────────────
    delta_baseline_frames: int = 10
    """Frames to capture for baseline average."""

    delta_stimulus_frames: int = 10
    """Frames to capture after stimulus."""

    delta_pause_s: float = 5.0
    """Pause between baseline and stimulus capture."""

    # ── Camera ───────────────────────────────────────────────────────
    camera: dict[str, Any] = field(default_factory=lambda: {"mode": "simulated"})
    """Camera config dict passed to seek_thermal.create()."""

    # ── Zones ────────────────────────────────────────────────────────
    zones: list[dict[str, Any]] = field(default_factory=list)
    """Zone definitions — each dict has name, x, y, width, height, etc."""

    # ── Limits ───────────────────────────────────────────────────────
    global_max_temp_c: float = 85.0
    """Fail if any frame exceeds this global max."""

    max_gradient_c_per_mm: float = 0.0
    """Fail if spatial gradient exceeds this (0 = disabled)."""

    pixel_pitch_mm: float = 0.17
    """Physical pixel pitch for gradient calculation."""

    # ── Output ───────────────────────────────────────────────────────
    board_id: str = ""
    """DUT board identifier for reports."""

    colormap: str = "inferno"
    """Heatmap colour palette."""

    report_dir: str = "test_reports"
    """Directory for HTML reports."""

    save_snapshots: bool = True
    """Include per-frame data in the result (memory-heavy)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "duration_s": self.duration_s,
            "capture_interval_s": self.capture_interval_s,
            "warmup_frames": self.warmup_frames,
            "soak_stable_window_s": self.soak_stable_window_s,
            "soak_stable_threshold_c": self.soak_stable_threshold_c,
            "soak_timeout_s": self.soak_timeout_s,
            "delta_baseline_frames": self.delta_baseline_frames,
            "delta_stimulus_frames": self.delta_stimulus_frames,
            "delta_pause_s": self.delta_pause_s,
            "camera": self.camera,
            "zones": self.zones,
            "global_max_temp_c": self.global_max_temp_c,
            "board_id": self.board_id,
            "colormap": self.colormap,
        }


# ═══════════════════════════════════════════════════════════════════════
#  Result
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ZoneStatistics:
    """Aggregated statistics for one zone across the measurement."""

    zone_name: str
    mean_temp_c: float = 0.0
    max_temp_c: float = 0.0
    min_temp_c: float = 0.0
    std_temp_c: float = 0.0
    peak_rate_c_per_s: float = 0.0
    temp_rise_c: float = 0.0      # Last mean − first mean
    worst_verdict: str = "NORMAL"

    # Delta mode
    baseline_mean_c: float = 0.0
    stimulus_mean_c: float = 0.0
    delta_c: float = 0.0

    # Time-series
    timestamps: list[float] = field(default_factory=list)
    temperatures: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "zone_name": self.zone_name,
            "mean_temp_c": round(self.mean_temp_c, 2),
            "max_temp_c": round(self.max_temp_c, 2),
            "min_temp_c": round(self.min_temp_c, 2),
            "std_temp_c": round(self.std_temp_c, 3),
            "peak_rate_c_per_s": round(self.peak_rate_c_per_s, 3),
            "temp_rise_c": round(self.temp_rise_c, 2),
            "worst_verdict": self.worst_verdict,
        }
        if self.delta_c != 0.0:
            d["baseline_mean_c"] = round(self.baseline_mean_c, 2)
            d["stimulus_mean_c"] = round(self.stimulus_mean_c, 2)
            d["delta_c"] = round(self.delta_c, 2)
        return d


@dataclass
class GradientResult:
    """Spatial temperature gradient analysis."""

    max_gradient_c_per_px: float = 0.0
    max_gradient_c_per_mm: float = 0.0
    gradient_location: tuple[int, int] = (0, 0)
    direction_deg: float = 0.0
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_gradient_c_per_px": round(self.max_gradient_c_per_px, 4),
            "max_gradient_c_per_mm": round(self.max_gradient_c_per_mm, 4),
            "gradient_location": list(self.gradient_location),
            "direction_deg": round(self.direction_deg, 1),
            "passed": self.passed,
        }


@dataclass
class ThermalMeasurementResult:
    """Complete result of a thermal measurement session."""

    mode: str = "continuous"
    passed: bool = True
    fail_reasons: list[str] = field(default_factory=list)
    board_id: str = ""

    # Timing
    start_time: str = ""
    duration_s: float = 0.0
    total_frames: int = 0

    # Global stats
    global_min_c: float = 0.0
    global_max_c: float = 0.0
    global_mean_c: float = 0.0

    # Per-zone
    zone_stats: list[ZoneStatistics] = field(default_factory=list)

    # Gradient (gradient mode)
    gradient: GradientResult | None = None

    # Soak specific
    soak_settled: bool = False
    soak_settle_time_s: float = 0.0

    # Camera info
    camera_info: dict[str, Any] = field(default_factory=dict)

    # Configuration used
    config: dict[str, Any] = field(default_factory=dict)

    # Global time-series
    timestamps: list[float] = field(default_factory=list)
    global_temps: list[float] = field(default_factory=list)

    # Snapshots (optional, memory-heavy)
    snapshots: list[dict[str, Any]] = field(default_factory=list)

    # Hotspot tracking
    hotspot_history: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "passed": self.passed,
            "fail_reasons": self.fail_reasons,
            "board_id": self.board_id,
            "start_time": self.start_time,
            "duration_s": round(self.duration_s, 2),
            "total_frames": self.total_frames,
            "global_min_c": round(self.global_min_c, 2),
            "global_max_c": round(self.global_max_c, 2),
            "global_mean_c": round(self.global_mean_c, 2),
            "zone_stats": [z.to_dict() for z in self.zone_stats],
            "camera_info": self.camera_info,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.summary()
        d["config"] = self.config
        d["timestamps"] = [round(t, 4) for t in self.timestamps]
        d["global_temps"] = [round(t, 2) for t in self.global_temps]
        d["hotspot_history"] = self.hotspot_history
        if self.gradient:
            d["gradient"] = self.gradient.to_dict()
        if self.soak_settled:
            d["soak_settle_time_s"] = round(self.soak_settle_time_s, 2)
        return d

    def write_json(self, path: str | pathlib.Path) -> pathlib.Path:
        """Write result to a JSON file."""
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Thermal measurement JSON → %s", p)
        return p

    def write_report(self, path: str | pathlib.Path | None = None) -> pathlib.Path:
        """Generate a self-contained HTML report."""
        return generate_thermal_report(self, path)


# ═══════════════════════════════════════════════════════════════════════
#  Measurement engine
# ═══════════════════════════════════════════════════════════════════════


def run_thermal_measurement(
    config: ThermalMeasurementConfig | dict[str, Any],
    *,
    progress_cb: Any = None,
) -> ThermalMeasurementResult:
    """Execute a thermal measurement session.

    Parameters
    ----------
    config : ThermalMeasurementConfig | dict
        Measurement configuration. If a dict is given it is converted.
    progress_cb : callable, optional
        Called with (frame_index, total_expected, snapshot_dict) per frame.

    Returns
    -------
    ThermalMeasurementResult
    """
    if isinstance(config, dict):
        config = _dict_to_config(config)

    mode = config.mode.lower().strip()
    logger.info("Starting thermal measurement: mode=%s, duration=%.1fs", mode, config.duration_s)

    # Open camera + analyser via ThermalService
    from pyontrust.services.thermal_service import ThermalService

    svc = ThermalService(config_dict={
        "camera": config.camera,
        "zones": config.zones,
        "colormap": config.colormap,
    })
    svc.open()

    try:
        # Warm-up
        for i in range(config.warmup_frames):
            svc.capture()
            logger.debug("Warm-up frame %d/%d", i + 1, config.warmup_frames)
        # Reset timeline after warm-up
        svc._analyzer.reset()  # type: ignore[union-attr]

        if mode == "continuous":
            result = _run_continuous(config, svc, progress_cb)
        elif mode == "soak":
            result = _run_soak(config, svc, progress_cb)
        elif mode == "delta":
            result = _run_delta(config, svc, progress_cb)
        elif mode == "gradient":
            result = _run_gradient(config, svc, progress_cb)
        else:
            raise ValueError(f"Unknown measurement mode: {mode!r}")

        # Populate common fields
        result.camera_info = svc.get_camera_info()
        result.config = config.to_dict()

        # Evaluate global limits
        if result.global_max_c > config.global_max_temp_c:
            result.passed = False
            result.fail_reasons.append(
                f"Global max {result.global_max_c:.1f}°C exceeds limit {config.global_max_temp_c:.1f}°C"
            )

        # Check zone verdicts
        for zs in result.zone_stats:
            if zs.worst_verdict in ("HOT", "RUNAWAY"):
                result.passed = False
                result.fail_reasons.append(
                    f"Zone '{zs.zone_name}' verdict: {zs.worst_verdict} "
                    f"(max={zs.max_temp_c:.1f}°C)"
                )

        logger.info(
            "Thermal measurement complete: %s, frames=%d, peak=%.1f°C",
            "PASS" if result.passed else "FAIL",
            result.total_frames,
            result.global_max_c,
        )
        return result

    finally:
        svc.close()


# ─── Continuous mode ─────────────────────────────────────────────────


def _run_continuous(
    cfg: ThermalMeasurementConfig,
    svc: Any,
    progress_cb: Any,
) -> ThermalMeasurementResult:
    """Capture frames for duration_s, accumulate statistics."""
    result = ThermalMeasurementResult(
        mode="continuous",
        board_id=cfg.board_id,
        start_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    t0 = time.perf_counter()
    total_expected = max(1, int(cfg.duration_s / cfg.capture_interval_s))
    frame_idx = 0

    all_maxs: list[float] = []
    all_mins: list[float] = []
    all_means: list[float] = []
    zone_series: dict[str, list[tuple[float, float, float]]] = {}  # name → [(t, mean, rate)]

    while time.perf_counter() - t0 < cfg.duration_s:
        snap = svc.capture()
        elapsed = time.perf_counter() - t0
        frame_idx += 1

        all_maxs.append(snap.global_max_c)
        all_mins.append(snap.global_min_c)
        all_means.append(snap.global_mean_c)
        result.timestamps.append(elapsed)
        result.global_temps.append(snap.global_mean_c)
        result.hotspot_history.append({
            "t_s": round(elapsed, 4),
            "x": snap.hotspot_x,
            "y": snap.hotspot_y,
            "temp_c": round(snap.global_max_c, 2),
        })

        for zr in snap.zone_readings:
            if zr.zone_name not in zone_series:
                zone_series[zr.zone_name] = []
            zone_series[zr.zone_name].append((elapsed, zr.mean_temp_c, zr.rate_c_per_s))

        if cfg.save_snapshots:
            result.snapshots.append(snap.to_dict())

        if progress_cb:
            try:
                progress_cb(frame_idx, total_expected, snap.to_dict())
            except Exception:
                pass

        # Pace capture
        next_t = t0 + frame_idx * cfg.capture_interval_s
        wait = next_t - time.perf_counter()
        if wait > 0:
            time.sleep(wait)

    result.total_frames = frame_idx
    result.duration_s = time.perf_counter() - t0
    result.global_max_c = max(all_maxs) if all_maxs else 0.0
    result.global_min_c = min(all_mins) if all_mins else 0.0
    result.global_mean_c = float(np.mean(all_means)) if all_means else 0.0

    # Per-zone statistics
    result.zone_stats = _compute_zone_stats(zone_series)

    return result


# ─── Soak mode ───────────────────────────────────────────────────────


def _run_soak(
    cfg: ThermalMeasurementConfig,
    svc: Any,
    progress_cb: Any,
) -> ThermalMeasurementResult:
    """Monitor temperature until it stabilises or times out."""
    result = ThermalMeasurementResult(
        mode="soak",
        board_id=cfg.board_id,
        start_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    t0 = time.perf_counter()
    timeout = min(cfg.soak_timeout_s, cfg.duration_s) if cfg.duration_s > 0 else cfg.soak_timeout_s
    frame_idx = 0
    settled = False
    settle_time = 0.0

    all_maxs: list[float] = []
    all_mins: list[float] = []
    all_means: list[float] = []
    zone_series: dict[str, list[tuple[float, float, float]]] = {}

    while time.perf_counter() - t0 < timeout:
        snap = svc.capture()
        elapsed = time.perf_counter() - t0
        frame_idx += 1

        all_maxs.append(snap.global_max_c)
        all_mins.append(snap.global_min_c)
        all_means.append(snap.global_mean_c)
        result.timestamps.append(elapsed)
        result.global_temps.append(snap.global_mean_c)
        result.hotspot_history.append({
            "t_s": round(elapsed, 4),
            "x": snap.hotspot_x,
            "y": snap.hotspot_y,
            "temp_c": round(snap.global_max_c, 2),
        })

        for zr in snap.zone_readings:
            if zr.zone_name not in zone_series:
                zone_series[zr.zone_name] = []
            zone_series[zr.zone_name].append((elapsed, zr.mean_temp_c, zr.rate_c_per_s))

        if cfg.save_snapshots:
            result.snapshots.append(snap.to_dict())

        if progress_cb:
            try:
                progress_cb(frame_idx, 0, snap.to_dict())
            except Exception:
                pass

        # Check stability: if the range of global_mean over the last
        # soak_stable_window_s is < soak_stable_threshold_c → settled
        if not settled and elapsed >= cfg.soak_stable_window_s:
            window_start = elapsed - cfg.soak_stable_window_s
            window_temps = [
                t for ts, t in zip(result.timestamps, result.global_temps)
                if ts >= window_start
            ]
            if window_temps:
                temp_range = max(window_temps) - min(window_temps)
                if temp_range < cfg.soak_stable_threshold_c:
                    settled = True
                    settle_time = elapsed
                    logger.info(
                        "Temperature settled at %.1f°C (range=%.2f°C in %.0fs window)",
                        snap.global_mean_c, temp_range, cfg.soak_stable_window_s,
                    )
                    break

        # Pace capture
        next_t = t0 + frame_idx * cfg.capture_interval_s
        wait = next_t - time.perf_counter()
        if wait > 0:
            time.sleep(wait)

    result.total_frames = frame_idx
    result.duration_s = time.perf_counter() - t0
    result.global_max_c = max(all_maxs) if all_maxs else 0.0
    result.global_min_c = min(all_mins) if all_mins else 0.0
    result.global_mean_c = float(np.mean(all_means)) if all_means else 0.0
    result.soak_settled = settled
    result.soak_settle_time_s = settle_time
    result.zone_stats = _compute_zone_stats(zone_series)

    if not settled:
        result.passed = False
        result.fail_reasons.append(
            f"Temperature did not settle within {timeout:.0f}s "
            f"(threshold={cfg.soak_stable_threshold_c:.1f}°C over {cfg.soak_stable_window_s:.0f}s window)"
        )

    return result


# ─── Delta mode ──────────────────────────────────────────────────────


def _run_delta(
    cfg: ThermalMeasurementConfig,
    svc: Any,
    progress_cb: Any,
) -> ThermalMeasurementResult:
    """Capture baseline → pause → capture stimulus → compute ΔT."""
    result = ThermalMeasurementResult(
        mode="delta",
        board_id=cfg.board_id,
        start_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    t0 = time.perf_counter()

    # ── Baseline ─────────────────────────────────────────────────────
    baseline_snaps: list[ThermalSnapshot] = []
    for i in range(cfg.delta_baseline_frames):
        snap = svc.capture()
        baseline_snaps.append(snap)
        elapsed = time.perf_counter() - t0
        result.timestamps.append(elapsed)
        result.global_temps.append(snap.global_mean_c)
        if cfg.save_snapshots:
            result.snapshots.append(snap.to_dict())
        if progress_cb:
            try:
                progress_cb(i + 1, cfg.delta_baseline_frames + cfg.delta_stimulus_frames, snap.to_dict())
            except Exception:
                pass
        time.sleep(cfg.capture_interval_s)

    # Reset analyser to separate baseline from stimulus
    svc._analyzer.reset()  # type: ignore[union-attr]

    # ── Pause (apply stimulus externally) ────────────────────────────
    logger.info("Delta mode: pausing %.1fs for stimulus application", cfg.delta_pause_s)
    time.sleep(cfg.delta_pause_s)

    # ── Stimulus ─────────────────────────────────────────────────────
    stimulus_snaps: list[ThermalSnapshot] = []
    for i in range(cfg.delta_stimulus_frames):
        snap = svc.capture()
        stimulus_snaps.append(snap)
        elapsed = time.perf_counter() - t0
        result.timestamps.append(elapsed)
        result.global_temps.append(snap.global_mean_c)
        if cfg.save_snapshots:
            result.snapshots.append(snap.to_dict())
        if progress_cb:
            try:
                progress_cb(
                    cfg.delta_baseline_frames + i + 1,
                    cfg.delta_baseline_frames + cfg.delta_stimulus_frames,
                    snap.to_dict(),
                )
            except Exception:
                pass
        time.sleep(cfg.capture_interval_s)

    result.total_frames = len(baseline_snaps) + len(stimulus_snaps)
    result.duration_s = time.perf_counter() - t0

    # ── Compute deltas ───────────────────────────────────────────────
    bl_means = [s.global_mean_c for s in baseline_snaps]
    st_means = [s.global_mean_c for s in stimulus_snaps]
    bl_maxs = [s.global_max_c for s in baseline_snaps]
    st_maxs = [s.global_max_c for s in stimulus_snaps]

    result.global_mean_c = float(np.mean(st_means)) if st_means else 0.0
    result.global_max_c = max(st_maxs) if st_maxs else 0.0
    result.global_min_c = min(bl_means) if bl_means else 0.0

    # Per-zone delta
    zone_baselines: dict[str, list[float]] = {}
    zone_stimuli: dict[str, list[float]] = {}

    for snap in baseline_snaps:
        for zr in snap.zone_readings:
            zone_baselines.setdefault(zr.zone_name, []).append(zr.mean_temp_c)

    for snap in stimulus_snaps:
        for zr in snap.zone_readings:
            zone_stimuli.setdefault(zr.zone_name, []).append(zr.mean_temp_c)

    for zone_name in zone_baselines:
        bl = zone_baselines[zone_name]
        st = zone_stimuli.get(zone_name, bl)
        bl_avg = float(np.mean(bl))
        st_avg = float(np.mean(st))
        all_temps = bl + st

        zs = ZoneStatistics(
            zone_name=zone_name,
            mean_temp_c=st_avg,
            max_temp_c=max(st) if st else 0.0,
            min_temp_c=min(bl) if bl else 0.0,
            std_temp_c=float(np.std(st)) if st else 0.0,
            temp_rise_c=st_avg - bl_avg,
            baseline_mean_c=bl_avg,
            stimulus_mean_c=st_avg,
            delta_c=st_avg - bl_avg,
        )
        result.zone_stats.append(zs)

    return result


# ─── Gradient mode ───────────────────────────────────────────────────


def _run_gradient(
    cfg: ThermalMeasurementConfig,
    svc: Any,
    progress_cb: Any,
) -> ThermalMeasurementResult:
    """Single-frame spatial gradient analysis."""
    result = ThermalMeasurementResult(
        mode="gradient",
        board_id=cfg.board_id,
        start_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    t0 = time.perf_counter()

    # Average several frames for noise reduction
    n_avg = max(cfg.delta_baseline_frames, 3)
    frames: list[np.ndarray] = []
    for i in range(n_avg):
        snap = svc.capture()
        # We need the raw temperature frame from the camera
        temp_frame = svc._camera.grab_temperature_frame()  # type: ignore[union-attr]
        frames.append(temp_frame)
        if progress_cb:
            try:
                progress_cb(i + 1, n_avg, snap.to_dict())
            except Exception:
                pass
        time.sleep(cfg.capture_interval_s)

    avg_frame = np.mean(np.stack(frames), axis=0).astype(np.float32)

    result.total_frames = n_avg
    result.duration_s = time.perf_counter() - t0
    result.global_max_c = float(np.max(avg_frame))
    result.global_min_c = float(np.min(avg_frame))
    result.global_mean_c = float(np.mean(avg_frame))

    # Compute gradient using Sobel-like finite differences
    gradient = _compute_gradient(avg_frame, cfg.pixel_pitch_mm)
    result.gradient = gradient

    if cfg.max_gradient_c_per_mm > 0 and gradient.max_gradient_c_per_mm > cfg.max_gradient_c_per_mm:
        gradient.passed = False
        result.passed = False
        result.fail_reasons.append(
            f"Spatial gradient {gradient.max_gradient_c_per_mm:.2f} °C/mm "
            f"exceeds limit {cfg.max_gradient_c_per_mm:.2f} °C/mm"
        )

    return result


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _dict_to_config(d: dict[str, Any]) -> ThermalMeasurementConfig:
    """Convert a plain dict to ThermalMeasurementConfig."""
    return ThermalMeasurementConfig(
        mode=str(d.get("mode", "continuous")),
        duration_s=float(d.get("duration_s", 30.0)),
        capture_interval_s=float(d.get("capture_interval_s", 0.5)),
        warmup_frames=int(d.get("warmup_frames", 5)),
        soak_stable_window_s=float(d.get("soak_stable_window_s", 10.0)),
        soak_stable_threshold_c=float(d.get("soak_stable_threshold_c", 0.5)),
        soak_timeout_s=float(d.get("soak_timeout_s", 300.0)),
        delta_baseline_frames=int(d.get("delta_baseline_frames", 10)),
        delta_stimulus_frames=int(d.get("delta_stimulus_frames", 10)),
        delta_pause_s=float(d.get("delta_pause_s", 5.0)),
        camera=d.get("camera", {"mode": "simulated"}),
        zones=d.get("zones", []),
        global_max_temp_c=float(d.get("global_max_temp_c", 85.0)),
        max_gradient_c_per_mm=float(d.get("max_gradient_c_per_mm", 0.0)),
        pixel_pitch_mm=float(d.get("pixel_pitch_mm", 0.17)),
        board_id=str(d.get("board_id", "")),
        colormap=str(d.get("colormap", "inferno")),
        report_dir=str(d.get("report_dir", "test_reports")),
        save_snapshots=bool(d.get("save_snapshots", True)),
    )


def _compute_zone_stats(
    zone_series: dict[str, list[tuple[float, float, float]]],
) -> list[ZoneStatistics]:
    """Aggregate per-zone time-series into ZoneStatistics."""
    stats: list[ZoneStatistics] = []
    for zone_name, series in zone_series.items():
        if not series:
            continue
        ts = [s[0] for s in series]
        temps = [s[1] for s in series]
        rates = [s[2] for s in series]

        # Worst verdict
        worst = "NORMAL"
        max_t = max(temps) if temps else 0.0
        if max_t > 85.0:
            worst = "HOT"
        elif max_t > 60.0:
            worst = "WARM"
        if any(abs(r) > 5.0 for r in rates):
            worst = "RUNAWAY"

        zs = ZoneStatistics(
            zone_name=zone_name,
            mean_temp_c=float(np.mean(temps)),
            max_temp_c=max(temps),
            min_temp_c=min(temps),
            std_temp_c=float(np.std(temps)),
            peak_rate_c_per_s=max(abs(r) for r in rates) if rates else 0.0,
            temp_rise_c=temps[-1] - temps[0] if len(temps) > 1 else 0.0,
            worst_verdict=worst,
            timestamps=ts,
            temperatures=temps,
        )
        stats.append(zs)
    return stats


def _compute_gradient(
    frame: np.ndarray,
    pixel_pitch_mm: float,
) -> GradientResult:
    """Compute spatial temperature gradient from a 2D temperature frame."""
    if frame.ndim != 2 or frame.size == 0:
        return GradientResult()

    # Finite differences (Sobel-like)
    gy, gx = np.gradient(frame.astype(np.float64))
    magnitude = np.sqrt(gx**2 + gy**2)

    max_idx = np.unravel_index(np.argmax(magnitude), magnitude.shape)
    max_grad_per_px = float(magnitude[max_idx])
    max_grad_per_mm = max_grad_per_px / pixel_pitch_mm if pixel_pitch_mm > 0 else 0.0

    direction = math.degrees(math.atan2(float(gy[max_idx]), float(gx[max_idx])))

    return GradientResult(
        max_gradient_c_per_px=max_grad_per_px,
        max_gradient_c_per_mm=max_grad_per_mm,
        gradient_location=(int(max_idx[1]), int(max_idx[0])),
        direction_deg=direction,
        passed=True,
    )


# ═══════════════════════════════════════════════════════════════════════
#  HTML report generation
# ═══════════════════════════════════════════════════════════════════════

_CSS = """\
:root {
  --bg: #1e1e2e; --bg2: #252538; --bg3: #2d2d44; --bg4: #353550;
  --fg: #cdd6f4; --fg-dim: #6c7086;
  --accent: #89b4fa; --green: #a6e3a1; --red: #f38ba8;
  --yellow: #f9e2af; --peach: #fab387; --mauve: #cba6f7;
  --teal: #94e2d5; --border: #45475a; --radius: 6px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--fg); line-height: 1.6;
  padding: 0; margin: 0;
}
.report { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
.report-header {
  border-bottom: 2px solid var(--accent); padding-bottom: 20px; margin-bottom: 28px;
}
.report-header h1 { color: var(--accent); font-size: 26px; margin-bottom: 4px; }
.report-header .subtitle { color: var(--fg-dim); font-size: 13px; }
.report-meta {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px 24px; margin-top: 14px; font-size: 12px;
}
.report-meta .key { color: var(--fg-dim); font-weight: 600; }
.report-meta .val { color: var(--fg); font-family: monospace; font-size: 11px; }
.verdict {
  padding: 16px 24px; border-radius: var(--radius); margin-bottom: 28px;
  display: flex; align-items: center; gap: 14px; font-size: 15px; font-weight: 700;
}
.verdict.pass { background: rgba(166,227,161,.12); color: var(--green); border: 1px solid var(--green); }
.verdict.fail { background: rgba(243,139,168,.12); color: var(--red); border: 1px solid var(--red); }
.section { margin-bottom: 28px; }
.section h2 {
  color: var(--mauve); font-size: 18px; margin-bottom: 12px;
  padding-bottom: 6px; border-bottom: 1px solid var(--border);
}
.section h3 { color: var(--teal); font-size: 14px; margin: 10px 0 6px; }
.kv-grid {
  display: grid; grid-template-columns: 180px 1fr;
  gap: 4px 16px; font-size: 13px;
}
.kv-grid .kv-key { color: var(--fg-dim); font-weight: 600; }
.kv-grid .kv-val { font-family: monospace; font-size: 12px; }
table {
  width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px;
}
th { background: var(--bg3); color: var(--accent); padding: 8px 12px; text-align: left; font-weight: 600; }
td { padding: 6px 12px; border-bottom: 1px solid var(--border); }
tr:hover td { background: var(--bg2); }
.verdict-badge {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700;
}
.verdict-badge.NORMAL { background: rgba(166,227,161,.15); color: var(--green); }
.verdict-badge.WARM   { background: rgba(249,226,175,.15); color: var(--yellow); }
.verdict-badge.HOT    { background: rgba(243,139,168,.15); color: var(--red); }
.verdict-badge.RUNAWAY { background: rgba(243,139,168,.25); color: var(--red); }
.chart-container {
  background: var(--bg2); border-radius: var(--radius);
  padding: 16px; margin: 12px 0; border: 1px solid var(--border);
}
svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
.fail-reasons { margin-top: 8px; }
.fail-reasons li {
  color: var(--red); font-size: 13px; margin: 4px 0;
  list-style: none; padding-left: 16px; position: relative;
}
.fail-reasons li::before { content: "✕ "; position: absolute; left: 0; }
.stat-cards {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px; margin: 12px 0;
}
.stat-card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 14px 16px; text-align: center;
}
.stat-card .stat-val { font-size: 24px; font-weight: 700; color: var(--accent); font-family: monospace; }
.stat-card .stat-lbl { font-size: 11px; color: var(--fg-dim); margin-top: 2px; }
"""


def _svg_line_chart(
    title: str,
    xs: Sequence[float],
    ys_dict: dict[str, Sequence[float]],
    x_label: str = "Time (s)",
    y_label: str = "Temperature (°C)",
    width: int = 920,
    height: int = 300,
) -> str:
    """Render an SVG line chart with multiple series."""
    if not xs or not ys_dict:
        return f'<div class="chart-container"><p style="color:var(--fg-dim)">No data for chart: {title}</p></div>'

    margin = {"top": 40, "right": 20, "bottom": 40, "left": 60}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]

    x_min = min(xs)
    x_max = max(xs)
    x_range = max(x_max - x_min, 1e-6)

    all_ys: list[float] = []
    for ys in ys_dict.values():
        all_ys.extend(float(y) for y in ys)
    y_min = min(all_ys) if all_ys else 0.0
    y_max = max(all_ys) if all_ys else 1.0
    y_pad = max((y_max - y_min) * 0.1, 0.5)
    y_min -= y_pad
    y_max += y_pad
    y_range = max(y_max - y_min, 1e-6)

    colours = ["#89b4fa", "#a6e3a1", "#f38ba8", "#f9e2af", "#cba6f7", "#94e2d5", "#fab387"]

    parts = [
        f'<div class="chart-container">',
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="{width // 2}" y="18" text-anchor="middle" fill="#cdd6f4" font-size="14" font-weight="600">{_esc(title)}</text>',
        # Grid lines
        f'<g transform="translate({margin["left"]},{margin["top"]})">',
    ]

    # Y-axis ticks
    n_yticks = 5
    for i in range(n_yticks + 1):
        y_val = y_min + i * y_range / n_yticks
        y_pos = plot_h - (i * plot_h / n_yticks)
        parts.append(f'<line x1="0" y1="{y_pos:.1f}" x2="{plot_w}" y2="{y_pos:.1f}" stroke="#45475a" stroke-dasharray="3,3"/>')
        parts.append(f'<text x="-8" y="{y_pos + 4:.1f}" text-anchor="end" fill="#6c7086" font-size="10">{y_val:.1f}</text>')

    # X-axis ticks
    n_xticks = min(8, len(xs))
    for i in range(n_xticks + 1):
        x_val = x_min + i * x_range / n_xticks
        x_pos = i * plot_w / n_xticks
        parts.append(f'<text x="{x_pos:.1f}" y="{plot_h + 18}" text-anchor="middle" fill="#6c7086" font-size="10">{x_val:.1f}</text>')

    # Axis labels
    parts.append(f'<text x="{plot_w // 2}" y="{plot_h + 34}" text-anchor="middle" fill="#6c7086" font-size="11">{_esc(x_label)}</text>')
    parts.append(f'<text x="-40" y="{plot_h // 2}" text-anchor="middle" fill="#6c7086" font-size="11" transform="rotate(-90,-40,{plot_h // 2})">{_esc(y_label)}</text>')

    # Plot series
    for idx, (label, ys) in enumerate(ys_dict.items()):
        colour = colours[idx % len(colours)]
        points = []
        for xi, yi in zip(xs, ys):
            px = (float(xi) - x_min) / x_range * plot_w
            py = plot_h - (float(yi) - y_min) / y_range * plot_h
            points.append(f"{px:.1f},{py:.1f}")
        if points:
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colour}" stroke-width="1.5"/>')

    parts.append('</g>')

    # Legend
    legend_y = height - 6
    legend_x = margin["left"]
    for idx, label in enumerate(ys_dict.keys()):
        colour = colours[idx % len(colours)]
        parts.append(f'<rect x="{legend_x}" y="{legend_y - 8}" width="12" height="4" fill="{colour}" rx="2"/>')
        parts.append(f'<text x="{legend_x + 16}" y="{legend_y - 3}" fill="#cdd6f4" font-size="10">{_esc(label)}</text>')
        legend_x += len(label) * 7 + 30

    parts.append('</svg></div>')
    return "\n".join(parts)


def _esc(s: str) -> str:
    """HTML-escape a string."""
    import html as html_mod
    return html_mod.escape(str(s))


def generate_thermal_report(
    result: ThermalMeasurementResult,
    path: str | pathlib.Path | None = None,
) -> pathlib.Path:
    """Generate a self-contained HTML report for a thermal measurement."""
    if path is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = pathlib.Path(result.config.get("report_dir", "test_reports")) / f"thermal_measurement_{ts}.html"
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    mode_labels = {
        "continuous": "Continuous Monitoring",
        "soak": "Thermal Soak Test",
        "delta": "Delta ΔT Measurement",
        "gradient": "Spatial Gradient Analysis",
    }

    parts: list[str] = []
    parts.append("<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>")
    parts.append(f"<title>Thermal Measurement — {_esc(result.board_id or 'DUT')}</title>")
    parts.append(f"<style>{_CSS}</style></head><body><div class='report'>")

    # Header
    parts.append("<div class='report-header'>")
    parts.append(f"<h1>🌡️ {_esc(mode_labels.get(result.mode, result.mode))}</h1>")
    parts.append(f"<div class='subtitle'>Seek Thermal Camera Measurement Report — pyontrust</div>")
    parts.append("<div class='report-meta'>")
    parts.append(f"<div><span class='key'>Board ID:</span> <span class='val'>{_esc(result.board_id or '—')}</span></div>")
    parts.append(f"<div><span class='key'>Start Time:</span> <span class='val'>{_esc(result.start_time)}</span></div>")
    parts.append(f"<div><span class='key'>Duration:</span> <span class='val'>{result.duration_s:.2f} s</span></div>")
    parts.append(f"<div><span class='key'>Frames:</span> <span class='val'>{result.total_frames}</span></div>")
    cam_model = result.camera_info.get("model", "—")
    parts.append(f"<div><span class='key'>Camera:</span> <span class='val'>{_esc(cam_model)}</span></div>")
    cam_res = result.camera_info.get("resolution", [])
    if cam_res:
        parts.append(f"<div><span class='key'>Resolution:</span> <span class='val'>{cam_res[0]}×{cam_res[1]} px</span></div>")
    parts.append("</div></div>")

    # Verdict
    vclass = "pass" if result.passed else "fail"
    vicon = "✓ PASS" if result.passed else "✕ FAIL"
    parts.append(f"<div class='verdict {vclass}'>{vicon}")
    if result.fail_reasons:
        parts.append("<ul class='fail-reasons'>")
        for reason in result.fail_reasons:
            parts.append(f"<li>{_esc(reason)}</li>")
        parts.append("</ul>")
    else:
        parts.append(f"<span>All thermal limits satisfied</span>")
    parts.append("</div>")

    # Global stats cards
    parts.append("<div class='section'><h2>📊 Global Statistics</h2>")
    parts.append("<div class='stat-cards'>")
    parts.append(f"<div class='stat-card'><div class='stat-val'>{result.global_min_c:.1f}°C</div><div class='stat-lbl'>Minimum</div></div>")
    parts.append(f"<div class='stat-card'><div class='stat-val'>{result.global_mean_c:.1f}°C</div><div class='stat-lbl'>Mean</div></div>")
    parts.append(f"<div class='stat-card'><div class='stat-val'>{result.global_max_c:.1f}°C</div><div class='stat-lbl'>Maximum</div></div>")
    parts.append(f"<div class='stat-card'><div class='stat-val'>{result.total_frames}</div><div class='stat-lbl'>Frames</div></div>")
    parts.append(f"<div class='stat-card'><div class='stat-val'>{result.duration_s:.1f}s</div><div class='stat-lbl'>Duration</div></div>")
    if result.mode == "soak":
        status_text = f"{result.soak_settle_time_s:.1f}s" if result.soak_settled else "NOT SETTLED"
        parts.append(f"<div class='stat-card'><div class='stat-val'>{status_text}</div><div class='stat-lbl'>Settle Time</div></div>")
    parts.append("</div></div>")

    # Temperature time-series chart
    if result.timestamps and result.global_temps:
        ys_dict: dict[str, Sequence[float]] = {"Global Mean": result.global_temps}
        for zs in result.zone_stats:
            if zs.timestamps and zs.temperatures:
                ys_dict[zs.zone_name] = zs.temperatures

        parts.append("<div class='section'><h2>📈 Temperature Time-Series</h2>")
        parts.append(_svg_line_chart(
            "Temperature vs Time",
            result.timestamps,
            ys_dict,
        ))
        parts.append("</div>")

    # Zone statistics table
    if result.zone_stats:
        parts.append("<div class='section'><h2>🎯 Zone Analysis</h2>")
        parts.append("<table><thead><tr>")
        headers = ["Zone", "Mean (°C)", "Max (°C)", "Min (°C)", "σ (°C)", "Rise (°C)", "Peak Rate (°C/s)", "Verdict"]
        if result.mode == "delta":
            headers = ["Zone", "Baseline (°C)", "Stimulus (°C)", "ΔT (°C)", "Max (°C)", "σ (°C)", "Verdict"]
        for h in headers:
            parts.append(f"<th>{h}</th>")
        parts.append("</tr></thead><tbody>")

        for zs in result.zone_stats:
            parts.append("<tr>")
            if result.mode == "delta":
                parts.append(f"<td><strong>{_esc(zs.zone_name)}</strong></td>")
                parts.append(f"<td>{zs.baseline_mean_c:.2f}</td>")
                parts.append(f"<td>{zs.stimulus_mean_c:.2f}</td>")
                parts.append(f"<td><strong>{zs.delta_c:+.2f}</strong></td>")
                parts.append(f"<td>{zs.max_temp_c:.2f}</td>")
                parts.append(f"<td>{zs.std_temp_c:.3f}</td>")
            else:
                parts.append(f"<td><strong>{_esc(zs.zone_name)}</strong></td>")
                parts.append(f"<td>{zs.mean_temp_c:.2f}</td>")
                parts.append(f"<td>{zs.max_temp_c:.2f}</td>")
                parts.append(f"<td>{zs.min_temp_c:.2f}</td>")
                parts.append(f"<td>{zs.std_temp_c:.3f}</td>")
                parts.append(f"<td>{zs.temp_rise_c:+.2f}</td>")
                parts.append(f"<td>{zs.peak_rate_c_per_s:.3f}</td>")
            parts.append(f"<td><span class='verdict-badge {zs.worst_verdict}'>{zs.worst_verdict}</span></td>")
            parts.append("</tr>")

        parts.append("</tbody></table></div>")

    # Gradient section
    if result.gradient:
        g = result.gradient
        parts.append("<div class='section'><h2>🌊 Spatial Gradient</h2>")
        parts.append("<div class='kv-grid'>")
        parts.append(f"<span class='kv-key'>Max Gradient:</span><span class='kv-val'>{g.max_gradient_c_per_px:.4f} °C/px = {g.max_gradient_c_per_mm:.2f} °C/mm</span>")
        parts.append(f"<span class='kv-key'>Location:</span><span class='kv-val'>({g.gradient_location[0]}, {g.gradient_location[1]})</span>")
        parts.append(f"<span class='kv-key'>Direction:</span><span class='kv-val'>{g.direction_deg:.1f}°</span>")
        passed_text = "PASS" if g.passed else "FAIL"
        parts.append(f"<span class='kv-key'>Verdict:</span><span class='kv-val'>{passed_text}</span>")
        parts.append("</div></div>")

    # Hotspot tracking
    if result.hotspot_history and len(result.hotspot_history) > 1:
        parts.append("<div class='section'><h2>🎯 Hotspot Tracking</h2>")
        hs_temps = [h["temp_c"] for h in result.hotspot_history]
        hs_xs_raw = [h["x"] for h in result.hotspot_history]
        hs_ys_raw = [h["y"] for h in result.hotspot_history]
        hs_ts = [h["t_s"] for h in result.hotspot_history]
        parts.append(_svg_line_chart(
            "Hotspot Temperature",
            hs_ts,
            {"Hotspot Peak": hs_temps},
            y_label="Peak Temp (°C)",
        ))
        parts.append("</div>")

    # Camera info
    if result.camera_info:
        parts.append("<div class='section'><h2>📷 Camera Info</h2>")
        parts.append("<div class='kv-grid'>")
        for k, v in result.camera_info.items():
            parts.append(f"<span class='kv-key'>{_esc(k.replace('_', ' ').title())}:</span><span class='kv-val'>{_esc(str(v))}</span>")
        parts.append("</div></div>")

    # Footer
    parts.append(f"<div style='margin-top:40px;padding-top:16px;border-top:1px solid var(--border);color:var(--fg-dim);font-size:11px;'>")
    parts.append(f"Generated by pyontrust thermal measurement · {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    parts.append("</div></div></body></html>")

    html_content = "\n".join(parts)
    p.write_text(html_content, encoding="utf-8")
    logger.info("Thermal measurement report → %s (%d bytes)", p, len(html_content))
    return p
