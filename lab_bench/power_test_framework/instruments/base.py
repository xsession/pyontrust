from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from ..core import PowerSample


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
        """Capture for `duration_s` and yield samples with monotonic timestamps (seconds)."""
        ...


@dataclass(frozen=True)
class InstrumentInfo:
    name: str
    model: str
    serial: str | None = None
