"""Thermal monitoring service — orchestrates thermal camera for the gateway and CLI.

Framework-agnostic façade that wraps the thermal camera instrument and
analyser for use from the gateway dashboard, CLI scripts, or test profiles.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
    ThermalZone,
)

logger = logging.getLogger("pyontrust.services.thermal_service")


class ThermalService:
    """Service layer for thermal monitoring.

    Manages the thermal camera + analyser lifecycle and exposes query
    methods for the gateway.

    Usage::

        svc = ThermalService(config_dict={
            "camera": {"mode": "simulated", "inject_hotspot": True},
            "zones": [{"name": "CPU", "x": 40, "y": 30, "width": 30, "height": 30}],
        })
        svc.open()
        snap = svc.capture()
        timeline = svc.get_timeline()
        svc.close()
    """

    def __init__(
        self,
        config_dict: dict[str, Any] | None = None,
    ) -> None:
        self._config = config_dict or {}
        self._camera: Any = None
        self._analyzer: Any = None
        self._ready = False

    def open(self) -> None:
        """Initialise camera and analyser."""
        from pyontrust.instruments.seek_thermal import create as create_thermal
        from pyontrust.analysis.thermal.analyzer import ThermalAnalyzer

        cam_cfg = self._config.get("camera", {"mode": "simulated"})
        self._camera = create_thermal(cam_cfg)
        self._camera.open()

        zones: list[ThermalZone] = []
        for zc in self._config.get("zones", []):
            zones.append(ThermalZone(
                name=str(zc.get("name", f"zone_{len(zones)}")),
                x=int(zc.get("x", 0)),
                y=int(zc.get("y", 0)),
                width=int(zc.get("width", 30)),
                height=int(zc.get("height", 30)),
                warn_temp_c=float(zc.get("warn_temp_c", 60.0)),
                max_temp_c=float(zc.get("max_temp_c", 85.0)),
                max_rate_c_per_s=float(zc.get("max_rate_c_per_s", 5.0)),
                description=str(zc.get("description", "")),
            ))

        self._analyzer = ThermalAnalyzer(
            zones=zones,
            colormap=str(self._config.get("colormap", "inferno")),
        )

        self._ready = True
        logger.info("Thermal service ready (zones=%d).", len(zones))

    def close(self) -> None:
        if self._camera:
            self._camera.close()
            self._camera = None
        self._analyzer = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def capture(self) -> ThermalSnapshot:
        """Grab one thermal frame and analyse it.

        Returns a ThermalSnapshot with per-zone readings.
        """
        if not self._ready:
            raise RuntimeError("Thermal service not initialised. Call open() first.")

        temp_frame = self._camera.grab_temperature_frame()
        frame_idx = len(self._analyzer.timeline.snapshots) + 1
        return self._analyzer.analyse_frame(temp_frame, frame_index=frame_idx)

    def capture_colorised(self) -> tuple[ThermalSnapshot, Any]:
        """Grab, analyse, and return (snapshot, colourised_BGR_image)."""
        if not self._ready:
            raise RuntimeError("Thermal service not initialised. Call open() first.")

        temp_frame = self._camera.grab_temperature_frame()
        frame_idx = len(self._analyzer.timeline.snapshots) + 1
        snap = self._analyzer.analyse_frame(temp_frame, frame_index=frame_idx)
        colour = self._analyzer.colorise_frame(temp_frame)
        return snap, colour

    def spot_temperature(self, x: int, y: int) -> float:
        """Read temperature at a single pixel."""
        if not self._ready:
            raise RuntimeError("Thermal service not initialised. Call open() first.")
        return self._camera.spot_temperature(x, y)

    def get_timeline(self) -> ThermalTimeline:
        """Return the accumulated thermal timeline."""
        if not self._analyzer:
            return ThermalTimeline()
        return self._analyzer.timeline

    def get_summary(self) -> dict[str, Any]:
        """Return a concise summary dict."""
        if not self._analyzer:
            return {"status": "not_initialised"}
        return self._analyzer.timeline.summary()

    def get_violations(self) -> list[dict[str, Any]]:
        """Return all temperature violations."""
        if not self._analyzer:
            return []
        return self._analyzer.timeline.violations()

    def get_zone_history(self, zone_name: str) -> list[dict[str, float]]:
        """Return temperature time-series for a specific zone."""
        if not self._analyzer:
            return []
        return self._analyzer.timeline.zone_history(zone_name)

    def get_camera_info(self) -> dict[str, Any]:
        """Return thermal camera metadata."""
        if not self._camera:
            return {}
        info = self._camera.info()
        return {
            "model": info.model,
            "serial": info.serial,
            "vendor": info.vendor,
            "resolution": list(info.resolution),
            "fpa_type": info.fpa_type,
            "spectral_range": info.spectral_range,
            "frame_rate_hz": info.frame_rate_hz,
            "temperature_range_c": list(info.temperature_range_c),
        }
