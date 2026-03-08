"""Industrial camera protocol — GenICam-style frame grabber abstraction.

Extends the basic Camera protocol with features required for AOI:
frame-level NumPy access, exposure/gain control, and multi-frame sequences.

This protocol is designed around GenICam SFNC naming conventions so that
any compliant camera (GigE Vision, USB3 Vision, CoaXPress) can plug in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class CameraInfo:
    """Metadata about a discovered industrial camera."""

    model: str
    serial: str
    vendor: str
    transport: str  # "GigE", "USB3", "CXP", "Simulated"
    firmware_version: str = ""


@runtime_checkable
class IndustrialCamera(Protocol):
    """Hardware abstraction for GenICam-compliant industrial cameras.

    Provides NumPy-array frame access needed by AOI image processing.
    """

    def open(self) -> None:
        """Initialise transport and connect to camera."""
        ...  # pragma: no cover

    def close(self) -> None:
        """Release camera resources."""
        ...  # pragma: no cover

    def configure(self, exposure_us: float, gain_db: float) -> None:
        """Set exposure time (µs) and gain (dB) via GenApi nodes."""
        ...  # pragma: no cover

    def grab_frame(self) -> Any:
        """Grab a single frame and return as numpy.ndarray (H×W or H×W×C).

        The return type is ``Any`` to avoid a hard numpy dependency in
        the HAL layer.  Implementations MUST return ``numpy.ndarray``.
        """
        ...  # pragma: no cover

    def grab_sequence(self, count: int, interval_ms: float = 0) -> list[Any]:
        """Grab *count* frames with optional inter-frame delay."""
        ...  # pragma: no cover

    def info(self) -> CameraInfo:
        """Return camera metadata."""
        ...  # pragma: no cover
