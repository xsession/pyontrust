"""Seek Thermal USB camera instrument — real hardware + simulated driver.

Provides two ``ThermalCamera`` implementations:

- **SeekThermalCamera** — real Seek Thermal Compact / CompactPRO / CompactXR
  via multiple backends (in priority order):
    1. **libseek** — pure-Python pyusb driver ported from OpenThermal/libseek-thermal
    2. **seekcamera** — official Seek Thermal SDK (seekcamera-python + native DLL)
    3. **seek_thermal** — community pip library
- **SimulatedThermalCamera** — deterministic synthetic thermal frames for CI

Both share the ``create()`` entry-point factory for the instrument registry.

Hardware info:
    Seek Thermal Compact      — 207×154 px, 36° FOV, USB-C, <100 mK NETD
    Seek Thermal CompactPRO   — 320×240 px, 32° FOV, USB-C, <70 mK NETD
    Seek Thermal CompactXR    — 207×154 px, 20° FOV, USB-C, extended range

Temperature calibration:
    The libseek backend provides raw 14-bit data with an approximate
    linear °C mapping.  For the ``seekcamera`` SDK, the thermography
    frame is already in degrees Celsius.

References:
    - https://github.com/OpenThermal/libseek-thermal
    - https://developer.thermal.com
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

    Supports three backends (tried in priority order):

    1. **libseek** (recommended) — pure-Python driver using ``pyusb``,
       ported from the OpenThermal/libseek-thermal C++ library::

           pip install pyusb

       On Windows, use Zadig to set the Seek Thermal USB interface
       driver to *libusb-win32* or *WinUSB*.

    2. **seekcamera** — official Seek Thermal SDK::

           pip install seekcamera-python
           # + install native seekcamera.dll from developer.thermal.com

    3. **seek_thermal** — community pip library::

           pip install seek_thermal
    """

    device_index: int = 0
    camera_type: str = "compact"  # "compact" or "pro"
    ffc_file: str | None = None
    emissivity: float = 0.95
    reflected_temp_c: float = 23.0
    _backend: str = ""  # "libseek" | "seekcamera" | "seek_thermal" | ""
    _camera: Any = field(default=None, repr=False)
    _manager: Any = field(default=None, repr=False)
    _last_frame: Any = field(default=None, repr=False)
    _frame_available: Any = field(default=None, repr=False)
    _libseek_cam: Any = field(default=None, repr=False)

    def _detect_backend(self) -> str:
        """Detect which Seek Thermal library is available **and functional**."""
        # ── libseek: pure-Python pyusb driver (preferred) ────────────
        try:
            from pyontrust.instruments.libseek_driver import (
                LibSeekCamera, detect_camera,
            )
            import usb.core  # noqa: F401
            detected = detect_camera()
            if detected is not None:
                logger.info("libseek backend: detected %s camera via USB", detected)
                return "libseek"
            # pyusb available but no camera plugged in — fall through
            logger.debug("libseek: pyusb available but no camera detected on USB")
        except ImportError:
            logger.debug("libseek backend not available (pyusb not installed)")

        # ── Official SDK: seekcamera-python ──────────────────────────
        try:
            import seekcamera as _skc  # noqa: F401
            from seekcamera._clib import configure_dll, _cdll
            if _cdll is None:
                try:
                    configure_dll()
                except (RuntimeError, OSError, FileNotFoundError) as exc:
                    logger.warning(
                        "seekcamera Python package found but native SDK "
                        "runtime missing: %s", exc,
                    )
                    raise ImportError(str(exc))
            return "seekcamera"
        except ImportError:
            pass

        # ── Community library: seek_thermal ─────────────────────────
        try:
            import seek_thermal  # noqa: F401
            return "seek_thermal"
        except ImportError:
            pass

        raise ImportError(
            "No Seek Thermal library found. Install ONE of:\n"
            "\n"
            "  Option A — libseek (recommended, no native SDK needed):\n"
            "    pip install pyusb\n"
            "    (Windows: use Zadig to set Seek USB driver to libusb-win32)\n"
            "\n"
            "  Option B — Official SDK:\n"
            "    1. pip install seekcamera-python\n"
            "    2. Install the native Seek Thermal SDK runtime from\n"
            "       https://developer.thermal.com  (seekcamera.dll / libseekcamera.so)\n"
            "\n"
            "  Option C — Community library:\n"
            "    pip install seek_thermal\n"
        )

    def open(self) -> None:
        self._backend = self._detect_backend()

        if self._backend == "libseek":
            self._open_libseek()
        elif self._backend == "seekcamera":
            self._open_seekcamera_sdk()
        elif self._backend == "seek_thermal":
            self._open_seek_thermal()

        logger.info(
            "SeekThermalCamera opened (backend=%s, device=%d)",
            self._backend, self.device_index,
        )

    def _open_libseek(self) -> None:
        """Open via pure-Python libseek driver (pyusb)."""
        from pyontrust.instruments.libseek_driver import LibSeekCamera, detect_camera

        cam_type = self.camera_type
        if cam_type not in ("compact", "pro"):
            # Auto-detect
            detected = detect_camera()
            cam_type = detected or "compact"

        self._libseek_cam = LibSeekCamera(
            camera_type=cam_type,
            ffc_file=self.ffc_file,
        )
        self._libseek_cam.open()
        self._camera = self._libseek_cam

    def _open_seekcamera_sdk(self) -> None:
        """Open via official Seek Thermal SDK (seekcamera-python ≥ 1.1)."""
        import threading
        import seekcamera as skc

        self._frame_available = threading.Event()

        def _on_frame(camera, camera_frame, _user_data):
            # Request the thermography float frame (°C per pixel)
            thermo = camera_frame.data
            if thermo is not None:
                import numpy as np
                self._last_frame = np.array(thermo, dtype=np.float32)
            self._frame_available.set()

        def _on_event(manager, event, status, camera, _user_data):
            if event == skc.SeekCameraManagerEvent.CONNECT:
                camera.color_palette = skc.SeekCameraColorPalette.TYRIAN
                camera.temperature_unit = skc.SeekCameraTemperatureUnit.CELSIUS
                camera.scene_emissivity = self.emissivity
                camera.register_frame_available_callback(
                    _on_frame, None,
                )
                camera.capture_session_start(
                    skc.SeekCameraFrameFormat.THERMOGRAPHY_FLOAT,
                )
                self._camera = camera
                logger.info(
                    "Seek camera connected: SN=%s",
                    camera.serial_number,
                )
            elif event == skc.SeekCameraManagerEvent.DISCONNECT:
                logger.warning("Seek camera disconnected")
                self._camera = None

        self._manager = skc.SeekCameraManager(
            skc.SeekCameraIOType.USB,
        )
        self._manager.register_event_callback(_on_event, None)

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
        if self._backend == "libseek":
            if self._libseek_cam is not None:
                try:
                    self._libseek_cam.close()
                except Exception:
                    pass
                self._libseek_cam = None
                self._camera = None
        elif self._backend == "seek_thermal" and self._camera is not None:
            try:
                self._camera.close()
            except Exception:
                pass
            self._camera = None
        elif self._backend == "seekcamera":
            if self._camera is not None:
                try:
                    self._camera.capture_session_stop()
                except Exception:
                    pass
                self._camera = None
            if self._manager is not None:
                try:
                    self._manager.destroy()
                except Exception:
                    pass
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

        if self._backend == "libseek":
            if self._libseek_cam is None:
                raise RuntimeError("Camera not open.")
            return self._libseek_cam.grab()

        if self._backend == "seekcamera":
            if self._frame_available is None:
                raise RuntimeError("Camera not open.")
            self._frame_available.clear()
            if not self._frame_available.wait(timeout=5.0):
                raise RuntimeError("Timeout waiting for Seek Thermal frame (5s).")
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

        if self._backend == "libseek":
            if self._libseek_cam is None:
                raise RuntimeError("Camera not open.")
            return self._libseek_cam.grab_temperature_frame()

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
        serial = ""
        resolution = (207, 154)

        if self._backend == "libseek" and self._libseek_cam is not None:
            w, h = self._libseek_cam.resolution
            resolution = (w, h)
            cam_type = self._libseek_cam.camera_type
            if cam_type in ("pro", "compactpro", "compact_pro"):
                model = "Seek Thermal CompactPRO (libseek)"
            else:
                model = "Seek Thermal Compact (libseek)"
            serial = "libseek-usb"
        elif self._backend == "seekcamera" and self._camera is not None:
            try:
                serial = str(self._camera.serial_number)
                cpn = str(self._camera.core_part_number)
                if cpn:
                    model = f"Seek Thermal ({cpn})"
            except Exception:
                pass
        elif self._backend == "seek_thermal" and self._camera is not None:
            try:
                w = getattr(self._camera, "width", 206)
                h = getattr(self._camera, "height", 156)
                resolution = (w, h)
            except Exception:
                pass

        return ThermalCameraInfo(
            model=model,
            serial=serial,
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
        camera_type: "compact" (default) or "pro"
        ffc_file: Path to flat-field calibration PNG (default None)
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
            camera_type=str(config.get("camera_type", "compact")),
            ffc_file=config.get("ffc_file"),
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
