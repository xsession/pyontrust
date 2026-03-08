"""Thermal camera protocol — USB thermal imaging abstraction.

Extends the basic Camera protocol with features required for thermal
monitoring: radiometric frame access, temperature range queries,
emissivity control, and spot / ROI temperature readout.

Designed around consumer-grade USB thermal cameras (Seek Thermal,
FLIR Lepton, InfiRay, etc.) that provide radiometric data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ThermalCameraInfo:
    """Metadata about a thermal camera."""

    model: str
    serial: str
    vendor: str
    resolution: tuple[int, int]  # (width, height)
    fpa_type: str  # "micro-bolometer", "InSb", etc.
    spectral_range: str  # e.g. "7.5–13 µm"
    frame_rate_hz: float = 0.0
    temperature_range_c: tuple[float, float] = (-40.0, 330.0)


@runtime_checkable
class ThermalCamera(Protocol):
    """Hardware abstraction for USB thermal imaging cameras.

    Implementations provide both radiometric (°C) and visual frames.
    The ``grab_frame()`` method returns the raw sensor output as a
    numpy array, while ``grab_temperature_frame()`` returns a float32
    array where each pixel is a temperature in °C.
    """

    def open(self) -> None:
        """Initialise USB connection and start thermal sensor."""
        ...  # pragma: no cover

    def close(self) -> None:
        """Release camera resources."""
        ...  # pragma: no cover

    def configure(
        self,
        emissivity: float = 0.95,
        reflected_temp_c: float = 23.0,
    ) -> None:
        """Set emissivity and reflected temperature for radiometric accuracy."""
        ...  # pragma: no cover

    def grab_frame(self) -> Any:
        """Grab a raw thermal frame as numpy.ndarray (uint16 or float32).

        Return type is ``Any`` to avoid hard numpy dependency in HAL.
        Implementations MUST return ``numpy.ndarray``.
        """
        ...  # pragma: no cover

    def grab_temperature_frame(self) -> Any:
        """Grab a radiometric frame — float32 array of temperatures in °C.

        Each pixel value is the estimated surface temperature.
        """
        ...  # pragma: no cover

    def spot_temperature(self, x: int, y: int) -> float:
        """Read temperature (°C) at a single pixel coordinate."""
        ...  # pragma: no cover

    def info(self) -> ThermalCameraInfo:
        """Return camera metadata."""
        ...  # pragma: no cover
