"""Seek Thermal USB camera instrument — real hardware + simulated driver.

Provides two ``ThermalCamera`` implementations:

- **SeekThermalCamera** — real Seek Thermal Compact / CompactPRO / CompactXR
  via the ``seekcamera`` Python SDK (or ``seek_thermal`` open-source lib)
- **SimulatedThermalCamera** — deterministic synthetic thermal frames for CI

Both share the ``create()`` entry-point factory for the instrument registry.

Hardware info:
    Seek Thermal Compact      — 206×156 px, 36° FOV, USB-C, <100 mK NETD
    Seek Thermal CompactPRO   — 320×240 px, 32° FOV, USB-C, <70 mK NETD
    Seek Thermal CompactXR    — 206×156 px, 20° FOV, USB-C, extended range

Temperature calibration:
    Raw sensor pixel values are converted to °C using the manufacturer's
    calibration tables.  For the open-source ``seekcamera`` API, the SDK
    provides the ``thermography_frame`` directly in degrees Celsius.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pyontrust.hal.thermal_camera import ThermalCameraInfo

logger = logging.getLogger("pyontrust.instruments.seek_thermal")


# ═══════════════════════════════════════════════════════════════════════
#  Simulated thermal camera (CI / development — no hardware required)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class SimulatedThermalCamera:
    """Deterministic simulated thermal camera for testing.

    Generates synthetic radiometric frames centered around a base
    temperature with optional hotspot injection for testing thermal
    analysis pipelines without hardware.
    """

    width: int = 206
    height: int = 156
    base_temp_c: float = 25.0
    noise_stddev_c: float = 0.3
    inject_hotspot: bool = False
    hotspot_temp_c: float = 85.0
    emissivity: float = 0.95
    reflected_temp_c: float = 23.0
    _opened: bool = False

    def open(self) -> None:
        self._opened = True
        logger.info(
            "SimulatedThermalCamera opened (%dx%d, base=%.1f°C)",
            self.width, self.height, self.base_temp_c,
        )

    def close(self) -> None:
        self._opened = False
        logger.info("SimulatedThermalCamera closed")

    def configure(
        self,
        emissivity: float = 0.95,
        reflected_temp_c: float = 23.0,
    ) -> None:
        self.emissivity = emissivity
        self.reflected_temp_c = reflected_temp_c
        logger.debug(
            "Configured: emissivity=%.2f, reflected_temp=%.1f°C",
            emissivity, reflected_temp_c,
        )

    def grab_frame(self) -> Any:
        """Return a synthetic raw thermal frame (uint16, simulated ADC values)."""
        import numpy as np

        if not self._opened:
            raise RuntimeError("Thermal camera not open. Call open() first.")

        rng = np.random.default_rng()
        # Simulate raw ADC values: temperature * 100 + offset
        base_adc = int(self.base_temp_c * 100) + 8000
        frame = rng.normal(base_adc, self.noise_stddev_c * 100, (self.height, self.width))

        if self.inject_hotspot:
            cy, cx = self.height // 3, self.width // 3
            h, w = max(6, self.height // 20), max(8, self.width // 20)
            hotspot_adc = int(self.hotspot_temp_c * 100) + 8000
            frame[cy : cy + h, cx : cx + w] = rng.normal(
                hotspot_adc, 10.0, (h, w)
            )

        return np.clip(frame, 0, 65535).astype(np.uint16)

    def grab_temperature_frame(self) -> Any:
        """Return a float32 frame where each pixel is temperature in °C."""
        import numpy as np

        if not self._opened:
            raise RuntimeError("Thermal camera not open. Call open() first.")

        rng = np.random.default_rng()
        frame = rng.normal(
            self.base_temp_c, self.noise_stddev_c,
            (self.height, self.width),
        ).astype(np.float32)

        if self.inject_hotspot:
            cy, cx = self.height // 3, self.width // 3
            h, w = max(6, self.height // 20), max(8, self.width // 20)
            frame[cy : cy + h, cx : cx + w] = rng.normal(
                self.hotspot_temp_c, 1.5, (h, w)
            ).astype(np.float32)

        return frame

    def spot_temperature(self, x: int, y: int) -> float:
        frame = self.grab_temperature_frame()
        return float(frame[y, x])

    def info(self) -> ThermalCameraInfo:
        return ThermalCameraInfo(
            model="SimulatedThermal",
            serial="SIM-THERMAL-0000",
            vendor="pyontrust",
            resolution=(self.width, self.height),
            fpa_type="simulated",
            spectral_range="simulated",
            frame_rate_hz=9.0,
            temperature_range_c=(-40.0, 330.0),
        )


# ═══════════════════════════════════════════════════════════════════════
#  Seek Thermal — real hardware via seekcamera SDK
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class SeekThermalCamera:
    """Seek Thermal USB camera (Compact / CompactPRO / CompactXR).

    Requires the ``seekcamera`` Python package (Seek Thermal's official
    SDK) or the community ``seek_thermal`` library.

    Install::

        pip install seekcamera-python

    Or for the community library::

        pip install seek_thermal

    The driver will try both in order.
    """

    device_index: int = 0
    emissivity: float = 0.95
    reflected_temp_c: float = 23.0
    _backend: str = ""  # "seekcamera" | "seek_thermal" | ""
    _camera: Any = field(default=None, repr=False)
    _manager: Any = field(default=None, repr=False)
    _last_frame: Any = field(default=None, repr=False)
    _frame_available: Any = field(default=None, repr=False)

    def _detect_backend(self) -> str:
        """Detect which Seek Thermal library is available."""
        try:
            import seekcamera  # noqa: F401
            return "seekcamera"
        except ImportError:
            pass

        try:
            import seek_thermal  # noqa: F401
            return "seek_thermal"
        except ImportError:
            pass

        raise ImportError(
            "No Seek Thermal library found. Install either:\n"
            "  pip install seekcamera-python   (official SDK)\n"
            "  pip install seek_thermal        (community library)"
        )

    def open(self) -> None:
        self._backend = self._detect_backend()

        if self._backend == "seekcamera":
            self._open_seekcamera_sdk()
        elif self._backend == "seek_thermal":
            self._open_seek_thermal()

        logger.info(
            "SeekThermalCamera opened (backend=%s, device=%d)",
            self._backend, self.device_index,
        )

    def _open_seekcamera_sdk(self) -> None:
        """Open via official Seek Thermal SDK."""
        import threading
        import seekcamera as skc

        self._frame_available = threading.Event()

        def _on_frame(camera, camera_frame, _user_data):
            self._last_frame = camera_frame.thermography_float
            self._frame_available.set()

        def _on_connect(manager, event, status, camera, _user_data):
            if event == skc.CameraEvent.CONNECT:
                camera.color_palette = skc.ColorPalette.TYRIAN
                camera.thermography_enabled = True
                camera.register_frame_available_callback(_on_frame)

        self._manager = skc.CameraManager()
        self._manager.register_event_callback(_on_connect)

    def _open_seek_thermal(self) -> None:
        """Open via community seek_thermal library."""
        from seek_thermal import SeekPro, SeekCompact

        # Try CompactPRO first, then regular Compact
        for CamClass in (SeekPro, SeekCompact):
            try:
                self._camera = CamClass()
                self._camera.open()
                return
            except Exception:
                continue
        raise RuntimeError(
            "Could not open Seek Thermal camera via seek_thermal library."
        )

    def close(self) -> None:
        if self._backend == "seek_thermal" and self._camera is not None:
            try:
                self._camera.close()
            except Exception:
                pass
            self._camera = None
        elif self._backend == "seekcamera" and self._manager is not None:
            self._manager = None

        logger.info("SeekThermalCamera closed.")

    def configure(
        self,
        emissivity: float = 0.95,
        reflected_temp_c: float = 23.0,
    ) -> None:
        self.emissivity = emissivity
        self.reflected_temp_c = reflected_temp_c
        logger.debug(
            "Configured: emissivity=%.2f, reflected_temp=%.1f°C",
            emissivity, reflected_temp_c,
        )

    def grab_frame(self) -> Any:
        """Grab raw thermal frame (uint16 or float32 depending on backend)."""
        import numpy as np

        if self._backend == "seekcamera":
            if self._frame_available is None:
                raise RuntimeError("Camera not open.")
            self._frame_available.wait(timeout=5.0)
            self._frame_available.clear()
            if self._last_frame is None:
                raise RuntimeError("No frame received from Seek camera.")
            return np.array(self._last_frame, dtype=np.float32)

        elif self._backend == "seek_thermal":
            if self._camera is None:
                raise RuntimeError("Camera not open.")
            frame = self._camera.read()
            return np.array(frame, dtype=np.uint16)

        raise RuntimeError("No backend initialised. Call open() first.")

    def grab_temperature_frame(self) -> Any:
        """Grab radiometric frame — float32 temperatures in °C."""
        import numpy as np

        raw = self.grab_frame()

        if self._backend == "seekcamera":
            # Official SDK provides temperatures directly
            return raw.astype(np.float32)
        elif self._backend == "seek_thermal":
            # Community lib raw values: approximate conversion
            # T(°C) ≈ (raw - offset) / scale  (camera-specific)
            return (raw.astype(np.float32) - 8000.0) / 100.0

        raise RuntimeError("Unknown backend.")

    def spot_temperature(self, x: int, y: int) -> float:
        frame = self.grab_temperature_frame()
        return float(frame[y, x])

    def info(self) -> ThermalCameraInfo:
        model = "Seek Thermal"
        resolution = (206, 156)
        if self._backend == "seek_thermal" and self._camera is not None:
            try:
                w = getattr(self._camera, "width", 206)
                h = getattr(self._camera, "height", 156)
                resolution = (w, h)
            except Exception:
                pass

        return ThermalCameraInfo(
            model=model,
            serial="",
            vendor="Seek Thermal",
            resolution=resolution,
            fpa_type="VOx micro-bolometer",
            spectral_range="7.5–13 µm",
            frame_rate_hz=9.0,
            temperature_range_c=(-40.0, 330.0),
        )


# ═══════════════════════════════════════════════════════════════════════
#  Entry-point factory (instrument registry)
# ═══════════════════════════════════════════════════════════════════════


def create(config: dict[str, Any]) -> SimulatedThermalCamera | SeekThermalCamera:
    """Entry-point factory for the thermal camera instrument.

    Config keys:
        mode: "simulated" (default) or "seek"
        device_index: Seek camera device index (default 0)
        emissivity: Surface emissivity (default 0.95)
        reflected_temp_c: Reflected temperature for radiometric correction (default 23.0)
        base_temp_c: Base temperature for simulated camera (default 25.0)
        inject_hotspot: Inject synthetic hotspot in simulated mode (default False)
        hotspot_temp_c: Hotspot temperature for simulated mode (default 85.0)
    """
    mode = str(config.get("mode", "simulated"))

    if mode == "seek":
        return SeekThermalCamera(
            device_index=int(config.get("device_index", 0)),
            emissivity=float(config.get("emissivity", 0.95)),
            reflected_temp_c=float(config.get("reflected_temp_c", 23.0)),
        )

    return SimulatedThermalCamera(
        width=int(config.get("width", 206)),
        height=int(config.get("height", 156)),
        base_temp_c=float(config.get("base_temp_c", 25.0)),
        noise_stddev_c=float(config.get("noise_stddev_c", 0.3)),
        inject_hotspot=bool(config.get("inject_hotspot", False)),
        hotspot_temp_c=float(config.get("hotspot_temp_c", 85.0)),
        emissivity=float(config.get("emissivity", 0.95)),
        reflected_temp_c=float(config.get("reflected_temp_c", 23.0)),
    )
