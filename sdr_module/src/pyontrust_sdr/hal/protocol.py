from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ..models import DeviceInfo, RxConfig


@runtime_checkable
class SdrHal(Protocol):
    def discover(self) -> list[DeviceInfo]:
        ...

    def open(self, device_id: str) -> None:
        ...

    def close(self) -> None:
        ...

    def set_rx_config(self, cfg: RxConfig) -> None:
        ...

    def start_stream(self) -> None:
        ...

    def read_iq(self, num_samples: int, timeout_s: float) -> np.ndarray:
        """Return complex64 IQ with length == num_samples (best-effort)."""

    def stop_stream(self) -> None:
        ...
