"""Programmable power supply protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PowerSupply(Protocol):
    """Hardware abstraction for programmable power supplies."""

    def open(self) -> None:
        ...  # pragma: no cover

    def close(self) -> None:
        ...  # pragma: no cover

    def set_voltage(self, volts: float) -> None:
        ...  # pragma: no cover

    def set_current_limit(self, amps: float) -> None:
        ...  # pragma: no cover

    def enable_output(self, on: bool) -> None:
        ...  # pragma: no cover

    def measure(self) -> tuple[float, float]:
        """Measure actual output. Returns (voltage_v, current_a)."""
        ...  # pragma: no cover
