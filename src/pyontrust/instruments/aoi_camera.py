"""AOI camera instrument — Harvesters GenICam, OpenCV webcam & simulated.

Provides three ``IndustrialCamera`` implementations:

- **HarvestersCamera** — real GenICam camera via Harvesters + GenTL Producer
- **OpenCVWebcam** — ordinary USB webcam via OpenCV ``VideoCapture``
- **SimulatedAOICamera** — deterministic test camera for CI (no hardware)

All share the same ``create()`` entry-point factory so the instrument
registry can dispatch on ``{"type": "aoi_camera"}``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pyontrust.hal.industrial_camera import CameraInfo

logger = logging.getLogger("pyontrust.instruments.aoi_camera")


# ═══════════════════════════════════════════════════════════════════════
#  Simulated AOI camera (CI / development — no hardware required)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class SimulatedAOICamera:
    """Deterministic simulated industrial camera for testing.

    Generates synthetic grayscale frames with optional injected defects
    so the full processing pipeline can be exercised without hardware.
    """

    width: int = 640
    height: int = 480
    channels: int = 1  # 1=mono, 3=colour
    exposure_us: float = 5000.0
    gain_db: float = 0.0
    noise_stddev: float = 5.0
    inject_defect: bool = False
    _opened: bool = False

    def open(self) -> None:
        self._opened = True
        logger.info("SimulatedAOICamera opened (%dx%d)", self.width, self.height)

    def close(self) -> None:
        self._opened = False
        logger.info("SimulatedAOICamera closed")

    def configure(self, exposure_us: float, gain_db: float) -> None:
        self.exposure_us = exposure_us
        self.gain_db = gain_db
        logger.debug("Configured: exposure=%.1f µs, gain=%.1f dB", exposure_us, gain_db)

    def grab_frame(self) -> Any:
        """Return a synthetic numpy frame."""
        import numpy as np

        if not self._opened:
            raise RuntimeError("Camera not open. Call open() first.")

        rng = np.random.default_rng()

        if self.channels == 1:
            # Grayscale gradient with noise
            base = np.linspace(100, 180, self.width, dtype=np.float64)
            frame = np.tile(base, (self.height, 1))
        else:
            frame = np.full(
                (self.height, self.width, self.channels), 140.0, dtype=np.float64
            )

        # Add Gaussian noise
        noise = rng.normal(0, self.noise_stddev, frame.shape)
        frame = frame + noise

        # Optionally inject a synthetic defect (bright rectangle)
        if self.inject_defect:
            cy, cx = self.height // 3, self.width // 3
            h, w = 30, 60
            if self.channels == 1:
                frame[cy : cy + h, cx : cx + w] += 80
            else:
                frame[cy : cy + h, cx : cx + w, :] += 80

        return np.clip(frame, 0, 255).astype(np.uint8)

    def grab_sequence(self, count: int, interval_ms: float = 0) -> list[Any]:
        frames = []
        for i in range(count):
            frames.append(self.grab_frame())
            if interval_ms > 0 and i < count - 1:
                time.sleep(interval_ms / 1000.0)
        return frames

    def info(self) -> CameraInfo:
        return CameraInfo(
            model="SimulatedAOI",
            serial="SIM-0000",
            vendor="pyontrust",
            transport="Simulated",
        )


# ═══════════════════════════════════════════════════════════════════════
#  OpenCV USB webcam (ordinary webcam for AOI — no GenICam required)
# ═══════════════════════════════════════════════════════════════════════


def _import_cv2():
    """Lazy-import OpenCV with a clear error message."""
    try:
        import cv2
        return cv2
    except ImportError as exc:
        raise ImportError(
            "OpenCV required for webcam AOI mode. "
            "Install with: pip install opencv-python"
        ) from exc


@dataclass
class OpenCVWebcam:
    """USB webcam wrapped as IndustrialCamera via OpenCV VideoCapture.

    Allows any standard USB webcam (or built-in laptop camera) to be
    used for AOI inspection — no GenICam / GenTL required.

    Config example::

        {
            "type": "aoi_camera",
            "mode": "webcam",
            "device_index": 0,
            "width": 1280,
            "height": 720
        }
    """

    device_index: int = 0
    width: int = 1280
    height: int = 720
    exposure_us: float = 0.0  # 0 = auto
    gain_db: float = 0.0
    _cap: Any = None

    def open(self) -> None:
        cv2 = _import_cv2()
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Cannot open webcam at index {self.device_index}. "
                "Check device connection and permissions."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if self.exposure_us > 0:
            self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # manual
            self._cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure_us / 1e6)
        logger.info(
            "OpenCVWebcam opened (device=%d, %dx%d)",
            self.device_index, self.width, self.height,
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("OpenCVWebcam closed.")

    def configure(self, exposure_us: float, gain_db: float) -> None:
        self.exposure_us = exposure_us
        self.gain_db = gain_db
        if self._cap is not None:
            cv2 = _import_cv2()
            if exposure_us > 0:
                self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self._cap.set(cv2.CAP_PROP_EXPOSURE, exposure_us / 1e6)
            if gain_db > 0:
                self._cap.set(cv2.CAP_PROP_GAIN, gain_db)

    def grab_frame(self) -> Any:
        import numpy as np

        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("Webcam not open. Call open() first.")
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to grab frame from webcam.")
        return frame  # BGR numpy array H×W×3

    def grab_sequence(self, count: int, interval_ms: float = 0) -> list[Any]:
        frames = []
        for i in range(count):
            frames.append(self.grab_frame())
            if interval_ms > 0 and i < count - 1:
                time.sleep(interval_ms / 1000.0)
        return frames

    def info(self) -> CameraInfo:
        return CameraInfo(
            model=f"USB Webcam #{self.device_index}",
            serial="",
            vendor="",
            transport="USB/UVC",
        )


# ═══════════════════════════════════════════════════════════════════════
#  Harvesters GenICam camera (real hardware)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class HarvestersCamera:
    """GenICam-compliant industrial camera using the Harvesters library.

    Works with any camera that provides a GenTL Producer (.cti file):
    Basler, FLIR, Baumer, IDS, or the open-source Aravis library.
    """

    cti_path: str = ""
    camera_index: int = 0
    pixel_format: str = "Mono8"
    exposure_us: float = 5000.0
    gain_db: float = 0.0
    _harvester: Any = field(default=None, repr=False)
    _acquirer: Any = field(default=None, repr=False)

    def _resolve_cti(self) -> str:
        """Resolve GenTL Producer path from config or environment."""
        if self.cti_path and Path(self.cti_path).exists():
            return self.cti_path

        env_vars = [
            "GENTL_PRODUCER_PATH",
            "PYLON_GENICAM_GENTL64_CTI",
            "FLIR_GENTL64_CTI",
            "GENICAM_GENTL64_PATH",
        ]
        for var in env_vars:
            path = os.environ.get(var)
            if path and Path(path).exists():
                logger.info("Found GenTL producer via %s: %s", var, path)
                return path

        # Aravis open-source fallback (Linux)
        for candidate in [
            "/usr/lib/x86_64-linux-gnu/libaravis-0.8.so",
            "/usr/lib64/libaravis-0.8.so",
        ]:
            if Path(candidate).exists():
                return candidate

        raise FileNotFoundError(
            "No GenTL Producer (.cti) found. Set GENTL_PRODUCER_PATH "
            "environment variable or pass cti_path in config."
        )

    def open(self) -> None:
        try:
            from harvesters.core import Harvester
        except ImportError as exc:
            raise ImportError(
                "Harvesters library required for GenICam cameras. "
                "Install with: pip install harvesters"
            ) from exc

        cti = self._resolve_cti()
        self._harvester = Harvester()
        self._harvester.add_file(cti)
        self._harvester.update()

        devices = self._harvester.device_info_list
        if not devices:
            raise RuntimeError(
                "No GenICam cameras discovered. Check cables, power, "
                "and GenTL Producer path."
            )

        logger.info(
            "Discovered %d camera(s): %s",
            len(devices),
            [d.model for d in devices],
        )

        self._acquirer = self._harvester.create(self.camera_index)

        # Configure pixel format
        node_map = self._acquirer.remote_device.node_map
        if hasattr(node_map, "PixelFormat"):
            node_map.PixelFormat.value = self.pixel_format

        # Apply initial exposure/gain
        self.configure(self.exposure_us, self.gain_db)
        self._acquirer.start()

        model = devices[self.camera_index].model
        logger.info("Camera opened: %s (index=%d)", model, self.camera_index)

    def close(self) -> None:
        if self._acquirer:
            self._acquirer.stop()
            self._acquirer.destroy()
            self._acquirer = None
        if self._harvester:
            self._harvester.reset()
            self._harvester = None
        logger.info("HarvestersCamera closed.")

    def configure(self, exposure_us: float, gain_db: float) -> None:
        if not self._acquirer:
            # Store for when open() is called
            self.exposure_us = exposure_us
            self.gain_db = gain_db
            return

        node_map = self._acquirer.remote_device.node_map

        if hasattr(node_map, "ExposureTime"):
            node_map.ExposureTime.value = exposure_us
            logger.debug("ExposureTime set to %.1f µs", exposure_us)

        if hasattr(node_map, "Gain"):
            node_map.Gain.value = gain_db
            logger.debug("Gain set to %.1f dB", gain_db)

        self.exposure_us = exposure_us
        self.gain_db = gain_db

    def grab_frame(self) -> Any:
        import numpy as np

        if not self._acquirer:
            raise RuntimeError("Camera not open. Call open() first.")

        with self._acquirer.fetch() as buffer:
            component = buffer.payload.components[0]
            frame = component.data.reshape(
                component.height, component.width, -1
            ).squeeze()
            return frame.copy()

    def grab_sequence(self, count: int, interval_ms: float = 0) -> list[Any]:
        frames = []
        for i in range(count):
            frames.append(self.grab_frame())
            if interval_ms > 0 and i < count - 1:
                time.sleep(interval_ms / 1000.0)
        return frames

    def info(self) -> CameraInfo:
        if self._harvester and self._harvester.device_info_list:
            d = self._harvester.device_info_list[self.camera_index]
            return CameraInfo(
                model=d.model,
                serial=getattr(d, "serial_number", ""),
                vendor=getattr(d, "vendor", ""),
                transport=getattr(d, "tl_type", "GenTL"),
            )
        return CameraInfo(
            model="HarvestersCamera",
            serial="",
            vendor="",
            transport="GenTL",
        )


# ═══════════════════════════════════════════════════════════════════════
#  Entry-point factory (instrument registry)
# ═══════════════════════════════════════════════════════════════════════


def create(config: dict[str, Any]) -> SimulatedAOICamera | OpenCVWebcam | HarvestersCamera:
    """Entry-point factory for the AOI camera instrument.

    Config keys:
        mode: "simulated" (default), "webcam", or "harvesters"
        --- webcam mode ---
        device_index: OpenCV VideoCapture device index (default 0)
        --- harvesters mode ---
        cti_path: Path to GenTL Producer .cti file
        camera_index: Camera index (default 0)
        pixel_format: GenICam pixel format (default "Mono8")
        --- common ---
        exposure_us: Exposure time in microseconds (default 5000)
        gain_db: Analog gain in dB (default 0)
        width: Frame width (default 640 simulated, 1280 webcam)
        height: Frame height (default 480 simulated, 720 webcam)
        channels: Number of channels for simulated camera (default 1)
        inject_defect: Inject synthetic defect in simulated mode (default False)
    """
    mode = str(config.get("mode", "simulated"))

    if mode == "webcam":
        return OpenCVWebcam(
            device_index=int(config.get("device_index", 0)),
            width=int(config.get("width", 1280)),
            height=int(config.get("height", 720)),
            exposure_us=float(config.get("exposure_us", 0.0)),
            gain_db=float(config.get("gain_db", 0.0)),
        )

    if mode == "harvesters":
        return HarvestersCamera(
            cti_path=str(config.get("cti_path", "")),
            camera_index=int(config.get("camera_index", 0)),
            pixel_format=str(config.get("pixel_format", "Mono8")),
            exposure_us=float(config.get("exposure_us", 5000.0)),
            gain_db=float(config.get("gain_db", 0.0)),
        )

    return SimulatedAOICamera(
        width=int(config.get("width", 640)),
        height=int(config.get("height", 480)),
        channels=int(config.get("channels", 1)),
        exposure_us=float(config.get("exposure_us", 5000.0)),
        gain_db=float(config.get("gain_db", 0.0)),
        noise_stddev=float(config.get("noise_stddev", 5.0)),
        inject_defect=bool(config.get("inject_defect", False)),
    )
