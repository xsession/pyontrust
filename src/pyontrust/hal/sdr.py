"""SDR (Software-Defined Radio) protocol definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class DeviceInfo:
    """Discovered SDR device metadata."""

    device_id: str
    label: str
    driver: str
    serial: str | None = None
    hardware: str | None = None


@dataclass(frozen=True)
class RxConfig:
    """Receiver configuration."""

    center_freq_hz: float
    sample_rate_hz: float
    bandwidth_hz: float | None = None
    gain_db: float | None = None
    antenna: str | None = None


@runtime_checkable
class SdrHal(Protocol):
    """Hardware abstraction for SDR receivers."""

    def discover(self) -> list[DeviceInfo]:
        """List available SDR devices."""
        ...  # pragma: no cover

    def open(self, device_id: str) -> None:
        ...  # pragma: no cover

    def close(self) -> None:
        ...  # pragma: no cover

    def set_rx_config(self, cfg: RxConfig) -> None:
        ...  # pragma: no cover

    def start_stream(self) -> None:
        ...  # pragma: no cover

    def read_iq(self, num_samples: int, timeout_s: float) -> Any:
        """Read IQ samples. Returns numpy complex64 ndarray."""
        ...  # pragma: no cover

    def stop_stream(self) -> None:
        ...  # pragma: no cover
