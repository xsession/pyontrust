"""Debug probe protocol — J-Link, OpenOCD, etc."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DebugProbe(Protocol):
    """Hardware abstraction for debug probes."""

    def open(self) -> None:
        ...  # pragma: no cover

    def close(self) -> None:
        ...  # pragma: no cover

    def reset(self, halt: bool = False) -> None:
        ...  # pragma: no cover

    def read_rtt(self, timeout_s: float) -> str:
        """Read RTT output from target."""
        ...  # pragma: no cover


@runtime_checkable
class FlashableProbe(DebugProbe, Protocol):
    """Extension for probes that support firmware flashing."""

    def flash(self, firmware_path: str, erase: bool = True, reset: bool = True) -> None:
        ...  # pragma: no cover
