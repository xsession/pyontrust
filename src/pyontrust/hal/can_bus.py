"""CAN bus interface protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CanFrame:
    """A single CAN bus frame."""

    arbitration_id: int
    data: bytes
    is_extended: bool = False
    timestamp: float = 0.0


@runtime_checkable
class CanBusInterface(Protocol):
    """Hardware abstraction for CAN bus adapters."""

    def open(self) -> None:
        ...  # pragma: no cover

    def close(self) -> None:
        ...  # pragma: no cover

    def send(self, arbitration_id: int, data: bytes) -> None:
        ...  # pragma: no cover

    def recv(self, timeout_s: float) -> CanFrame | None:
        ...  # pragma: no cover
