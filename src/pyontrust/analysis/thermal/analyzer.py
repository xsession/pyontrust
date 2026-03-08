"""Thermal frame analyzer — ROI temperature tracking and hotspot detection.

Processes radiometric frames from a thermal camera and produces
``ThermalSnapshot`` objects with per-zone temperature readings,
hotspot location, and verdict (NORMAL / WARM / HOT / RUNAWAY).

Requires numpy; OpenCV is optional (for colourised heatmap overlays).
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Optional

import numpy as np

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
    ThermalZone,
    ZoneReading,
)

logger = logging.getLogger("pyontrust.analysis.thermal.analyzer")


class ThermalAnalyzer:
    """Stateful thermal frame analyzer with zone tracking.

    Maintains history for rate-of-rise calculations and generates
    annotated thermal snapshots.

    Usage::

        zones = [
            ThermalZone("CPU", x=40, y=30, width=30, height=30, max_temp_c=85),
            ThermalZone("VREG", x=100, y=60, width=20, height=15, max_temp_c=105),
        ]
        analyzer = ThermalAnalyzer(zones=zones)
        snap = analyzer.analyse_frame(temp_frame, frame_index=0)
    """

    def __init__(
        self,
        zones: list[ThermalZone] | None = None,
        colormap: str = "inferno",
    ) -> None:
        self._zones = zones or []
        self._colormap = colormap
        self._prev_zone_temps: dict[str, float] = {}
        self._prev_time: float | None = None
        self._start_time: float | None = None
        self._timeline = ThermalTimeline(zones=self._zones)

    @property
    def timeline(self) -> ThermalTimeline:
        """Access the accumulated thermal timeline."""
        return self._timeline

    def reset(self) -> None:
        """Clear accumulated history."""
        self._prev_zone_temps.clear()
        self._prev_time = None
        self._start_time = None
        self._timeline = ThermalTimeline(zones=self._zones)

    def analyse_frame(
        self,
        temp_frame: np.ndarray,
        frame_index: int = 0,
        timestamp_s: float | None = None,
    ) -> ThermalSnapshot:
        """Analyse a single radiometric frame (float32, °C per pixel).

        Parameters
        ----------
        temp_frame : numpy.ndarray
            2D float32 array where each value is temperature in °C.
        frame_index : int
            Sequential frame number.
        timestamp_s : float, optional
            Monotonic timestamp. If None, uses time.perf_counter().

        Returns
        -------
        ThermalSnapshot
            Complete analysis of the frame including zone readings.
        """
        now = timestamp_s if timestamp_s is not None else time.perf_counter()
        if self._start_time is None:
            self._start_time = now

        t_rel = now - self._start_time
        dt = (now - self._prev_time) if self._prev_time is not None else 0.0

        # Global statistics
        global_min = float(np.min(temp_frame))
        global_max = float(np.max(temp_frame))
        global_mean = float(np.mean(temp_frame))

        # Hotspot location
        hotspot_idx = np.unravel_index(np.argmax(temp_frame), temp_frame.shape)
        hotspot_y, hotspot_x = int(hotspot_idx[0]), int(hotspot_idx[1])

        # Per-zone analysis
        zone_readings: list[ZoneReading] = []
        worst_verdict = ThermalVerdict.NORMAL

        for zone in self._zones:
            roi = temp_frame[
                zone.y : zone.y + zone.height,
                zone.x : zone.x + zone.width,
            ]
            if roi.size == 0:
                continue

            z_mean = float(np.mean(roi))
            z_max = float(np.max(roi))
            z_min = float(np.min(roi))
            z_std = float(np.std(roi))

            # Rate of rise
            rate = 0.0
            if dt > 0 and zone.name in self._prev_zone_temps:
                rate = (z_mean - self._prev_zone_temps[zone.name]) / dt
            self._prev_zone_temps[zone.name] = z_mean

            # Verdict
            if abs(rate) > zone.max_rate_c_per_s:
                verdict = ThermalVerdict.RUNAWAY
            elif z_max > zone.max_temp_c:
                verdict = ThermalVerdict.HOT
            elif z_max > zone.warn_temp_c:
                verdict = ThermalVerdict.WARM
            else:
                verdict = ThermalVerdict.NORMAL

            zone_readings.append(ZoneReading(
                zone_name=zone.name,
                mean_temp_c=z_mean,
                max_temp_c=z_max,
                min_temp_c=z_min,
                std_temp_c=z_std,
                verdict=verdict,
                rate_c_per_s=rate,
            ))

            _severity = {
                ThermalVerdict.NORMAL: 0,
                ThermalVerdict.WARM: 1,
                ThermalVerdict.HOT: 2,
                ThermalVerdict.RUNAWAY: 3,
            }
            if _severity.get(verdict, 0) > _severity.get(worst_verdict, 0):
                worst_verdict = verdict

        # Global verdict (no zones → check global max against 85°C default)
        if not self._zones:
            if global_max > 85.0:
                worst_verdict = ThermalVerdict.HOT
            elif global_max > 60.0:
                worst_verdict = ThermalVerdict.WARM

        self._prev_time = now

        snapshot = ThermalSnapshot(
            timestamp_s=t_rel,
            wall_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            frame_index=frame_index,
            global_min_c=global_min,
            global_max_c=global_max,
            global_mean_c=global_mean,
            zone_readings=zone_readings,
            verdict=worst_verdict,
            hotspot_x=hotspot_x,
            hotspot_y=hotspot_y,
        )

        self._timeline.snapshots.append(snapshot)
        return snapshot

    def colorise_frame(
        self,
        temp_frame: np.ndarray,
        vmin: float | None = None,
        vmax: float | None = None,
        draw_zones: bool = True,
        draw_hotspot: bool = True,
    ) -> Any:
        """Convert a temperature frame to a colourised BGR image.

        Requires OpenCV. Falls back to a simple intensity map if unavailable.
        """
        try:
            import cv2
        except ImportError:
            # Fallback: normalize to 0-255 greyscale
            vmin = vmin or float(np.min(temp_frame))
            vmax = vmax or float(np.max(temp_frame))
            rng = max(vmax - vmin, 1e-3)
            normalized = ((temp_frame - vmin) / rng * 255).clip(0, 255).astype(np.uint8)
            return np.stack([normalized] * 3, axis=-1)

        vmin = vmin or float(np.min(temp_frame))
        vmax = vmax or float(np.max(temp_frame))
        rng = max(vmax - vmin, 1e-3)
        normalized = ((temp_frame - vmin) / rng * 255).clip(0, 255).astype(np.uint8)

        colormaps = {
            "inferno": cv2.COLORMAP_INFERNO,
            "jet": cv2.COLORMAP_JET,
            "hot": cv2.COLORMAP_HOT,
            "rainbow": cv2.COLORMAP_RAINBOW,
            "turbo": cv2.COLORMAP_TURBO,
        }
        cm = colormaps.get(self._colormap, cv2.COLORMAP_INFERNO)
        colour = cv2.applyColorMap(normalized, cm)

        if draw_zones:
            for zone in self._zones:
                cv2.rectangle(
                    colour,
                    (zone.x, zone.y),
                    (zone.x + zone.width, zone.y + zone.height),
                    (0, 255, 0), 1,
                )
                cv2.putText(
                    colour, zone.name,
                    (zone.x, zone.y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1,
                )

        if draw_hotspot:
            hy = int(np.argmax(temp_frame) // temp_frame.shape[1])
            hx = int(np.argmax(temp_frame) % temp_frame.shape[1])
            cv2.drawMarker(
                colour, (hx, hy),
                (0, 0, 255), cv2.MARKER_CROSS, 8, 1,
            )

        return colour
