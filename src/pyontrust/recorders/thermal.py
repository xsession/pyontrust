"""Thermal recorder — background temperature logging during test profiles.

Captures thermal frames at a configurable interval during a test run,
analyses each frame for per-zone temperatures, and writes a thermal
timeline JSON summary.  Optionally saves colourised heatmap images.

Implements the ``Recorder`` protocol from ``pyontrust.hal.recorder``.
"""

from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyontrust.core.models import TestContext

logger = logging.getLogger("pyontrust.recorders.thermal")


@dataclass
class ThermalRecorder:
    """Background thermal capture + analysis during test runs.

    Grabs radiometric frames from a thermal camera at ``capture_interval_s``
    and runs the ``ThermalAnalyzer`` on each frame.  Results are accumulated
    into a ``ThermalTimeline`` and written to JSON when stopped.
    """

    name: str = "thermal"
    capture_interval_s: float = 1.0
    save_images: bool = True
    colormap: str = "inferno"
    camera_config: dict[str, Any] | None = None
    zones_config: list[dict[str, Any]] | None = None

    # Internals
    _thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None
    _out_dir: pathlib.Path | None = None
    _camera: Any = None
    _analyzer: Any = None
    _frame_count: int = 0

    def start(self, ctx: "TestContext") -> None:
        """Start background thermal capture."""
        from pyontrust.instruments.seek_thermal import create as create_thermal
        from pyontrust.analysis.thermal.analyzer import ThermalAnalyzer
        from pyontrust.analysis.thermal.models import ThermalZone

        self._out_dir = ctx.artifacts.recorders_dir / "thermal"
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._frame_count = 0

        # Create camera
        cam_cfg = self.camera_config or {"mode": "simulated"}
        self._camera = create_thermal(cam_cfg)
        self._camera.open()

        # Parse zones from config
        zones: list[ThermalZone] = []
        if self.zones_config:
            for zc in self.zones_config:
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

        self._analyzer = ThermalAnalyzer(zones=zones, colormap=self.colormap)

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="thermal-recorder",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Thermal recorder started (interval=%.1fs, zones=%d)",
            self.capture_interval_s, len(zones),
        )

    def stop(self, ctx: "TestContext") -> None:
        """Stop background capture and write summary."""
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10.0)
            self._thread = None

        if self._camera:
            self._camera.close()
            self._camera = None

        # Write thermal timeline JSON
        if self._out_dir and self._analyzer:
            timeline = self._analyzer.timeline
            summary_path = self._out_dir / "thermal_timeline.json"
            summary_path.write_text(
                json.dumps(timeline.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )

            # Also write a concise summary
            stats_path = self._out_dir / "thermal_summary.json"
            stats_path.write_text(
                json.dumps(timeline.summary(), indent=2, default=str),
                encoding="utf-8",
            )

        ctx.recorder_outputs[self.name] = {
            "frames_captured": self._frame_count,
            "output_dir": str(self._out_dir),
            "peak_temperature_c": (
                round(self._analyzer.timeline.peak_temperature_c, 2)
                if self._analyzer else 0.0
            ),
            "worst_verdict": (
                self._analyzer.timeline.worst_verdict.value
                if self._analyzer else "NORMAL"
            ),
        }
        logger.info(
            "Thermal recorder stopped (%d frames, peak=%.1f°C).",
            self._frame_count,
            self._analyzer.timeline.peak_temperature_c if self._analyzer else 0.0,
        )

    def _capture_loop(self) -> None:
        """Background thread: grab thermal frames at interval."""
        assert self._stop_event is not None
        assert self._out_dir is not None
        assert self._analyzer is not None

        while not self._stop_event.is_set():
            try:
                temp_frame = self._camera.grab_temperature_frame()
                self._frame_count += 1

                snapshot = self._analyzer.analyse_frame(
                    temp_frame, frame_index=self._frame_count,
                )

                # Save colourised heatmap image
                if self.save_images:
                    try:
                        import cv2
                        colour = self._analyzer.colorise_frame(temp_frame)
                        fname = self._out_dir / f"thermal_{self._frame_count:04d}.png"
                        cv2.imwrite(str(fname), colour)
                    except ImportError:
                        # Fallback: save raw numpy
                        fname = self._out_dir / f"thermal_{self._frame_count:04d}.npy"
                        np.save(str(fname), temp_frame)

                # Log any violations
                if snapshot.verdict != snapshot.verdict.NORMAL:
                    logger.warning(
                        "Thermal %s at frame %d: max=%.1f°C",
                        snapshot.verdict.value,
                        self._frame_count,
                        snapshot.global_max_c,
                    )

            except Exception as e:
                logger.warning("Thermal capture error: %s", e)

            self._stop_event.wait(self.capture_interval_s)


def create(config: dict[str, Any]) -> ThermalRecorder:
    """Entry-point factory for the thermal recorder.

    Config keys:
        name: Recorder name (default "thermal")
        capture_interval_s: Seconds between captures (default 1.0)
        save_images: Save colourised heatmap PNGs (default True)
        colormap: Colour palette — "inferno", "jet", "hot" (default "inferno")
        camera: Camera configuration dict (passed to seek_thermal.create)
        zones: List of zone dicts with name, x, y, width, height, temps
    """
    return ThermalRecorder(
        name=str(config.get("name", "thermal")),
        capture_interval_s=float(config.get("capture_interval_s", 1.0)),
        save_images=bool(config.get("save_images", True)),
        colormap=str(config.get("colormap", "inferno")),
        camera_config=config.get("camera"),
        zones_config=config.get("zones"),
    )
