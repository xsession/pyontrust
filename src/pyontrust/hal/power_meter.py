"""Power measurement protocol definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from pyontrust.core.models import PowerSample


@runtime_checkable
class PowerMeter(Protocol):
    """Minimal power meter interface used by the framework.

    Implementations may talk to PPK2, AD3+DWF, a bench DMM, etc.
    """

    def open(self) -> None:  # pragma: no cover
        ...

    def close(self) -> None:  # pragma: no cover
        ...

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        """Capture for duration_s and yield samples with monotonic timestamps."""
        ...  # pragma: no cover


@runtime_checkable
class StreamingPowerMeter(PowerMeter, Protocol):
    """Extension for instruments that support continuous streaming."""

    def start_stream(self) -> None:  # pragma: no cover
        ...

    def read_samples(self, max_samples: int, timeout_s: float) -> list[PowerSample]:
        ...  # pragma: no cover

    def stop_stream(self) -> None:  # pragma: no cover
        ...


@dataclass(frozen=True)
class InstrumentInfo:
    """Metadata about a discovered instrument."""

    name: str
    model: str
    serial: str | None = None
