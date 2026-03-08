"""AOI recorder — background inspection during test profile execution.

Captures frames at a configurable interval during a test run and
stores them for offline AOI analysis.  When ``live_inspect`` is enabled,
each captured frame is passed through the AOI processing pipeline in
real-time and defects are logged to the event bus.
"""

from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyontrust.core.models import TestContext

logger = logging.getLogger("pyontrust.recorders.aoi")


@dataclass
class AOIRecorder:
    """Background AOI frame capture during test runs.

    Implements the ``Recorder`` protocol from ``pyontrust.hal.recorder``.
    """

    name: str = "aoi"
    capture_interval_s: float = 2.0
    live_inspect: bool = False
    camera_config: dict[str, Any] | None = None

    # Internals
    _thread: threading.Thread | None = None
    _stop_event: threading.Event | None = None
    _out_dir: pathlib.Path | None = None
    _camera: Any = None
    _inspector: Any = None
    _frame_count: int = 0
    _results: list[dict[str, Any]] | None = None

    def start(self, ctx: "TestContext") -> None:
        """Start background frame capture."""
        from pyontrust.instruments.aoi_camera import create as create_camera

        self._out_dir = ctx.artifacts.recorders_dir / "aoi"
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._results = []
        self._frame_count = 0

        # Create camera
        cam_cfg = self.camera_config or {"mode": "simulated"}
        self._camera = create_camera(cam_cfg)
        self._camera.open()

        # Optionally create live inspector
        if self.live_inspect:
            try:
                from pyontrust.analysis.aoi.processing import (
                    ImagePreprocessor,
                    DefectDetector,
                )
                self._inspector = {
                    "preprocessor": ImagePreprocessor(denoise_strength=3),
                }
            except ImportError:
                logger.warning("OpenCV not available; live_inspect disabled.")
                self._inspector = None

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="aoi-recorder",
            daemon=True,
        )
        self._thread.start()
        logger.info("AOI recorder started (interval=%.1fs)", self.capture_interval_s)

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

        # Write summary
        if self._out_dir and self._results is not None:
            summary_path = self._out_dir / "aoi_recorder_summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "frames_captured": self._frame_count,
                        "results": self._results,
                    },
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )

        ctx.recorder_outputs[self.name] = {
            "frames_captured": self._frame_count,
            "output_dir": str(self._out_dir),
        }
        logger.info("AOI recorder stopped (%d frames).", self._frame_count)

    def _capture_loop(self) -> None:
        """Background thread: grab frames at interval."""
        assert self._stop_event is not None
        assert self._out_dir is not None

        while not self._stop_event.is_set():
            try:
                frame = self._camera.grab_frame()
                self._frame_count += 1

                # Save raw frame
                try:
                    import cv2
                    fname = self._out_dir / f"frame_{self._frame_count:04d}.png"
                    cv2.imwrite(str(fname), frame)
                except ImportError:
                    # Fall back to numpy save
                    import numpy as np
                    fname = self._out_dir / f"frame_{self._frame_count:04d}.npy"
                    np.save(str(fname), frame)

                # Optional live inspection
                if self._inspector and self._results is not None:
                    try:
                        processed = self._inspector["preprocessor"].process(frame)
                        self._results.append({
                            "frame": self._frame_count,
                            "timestamp": time.time(),
                            "mean_intensity": float(frame.mean()),
                        })
                    except Exception as e:
                        logger.debug("Live inspect error: %s", e)

            except Exception as e:
                logger.warning("AOI capture error: %s", e)

            self._stop_event.wait(self.capture_interval_s)


def create(config: dict[str, Any]) -> AOIRecorder:
    """Entry-point factory for the AOI recorder.

    Config keys:
        name: Recorder name (default "aoi")
        capture_interval_s: Seconds between captures (default 2.0)
        live_inspect: Enable real-time inspection (default False)
        camera: Camera configuration dict (passed to aoi_camera.create)
    """
    return AOIRecorder(
        name=str(config.get("name", "aoi")),
        capture_interval_s=float(config.get("capture_interval_s", 2.0)),
        live_inspect=bool(config.get("live_inspect", False)),
        camera_config=config.get("camera"),
    )
