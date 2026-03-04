from __future__ import annotations

from typing import Protocol

import numpy as np

from ..models import AwgConfig, Capabilities, ChannelConfig, DeviceInfo, ScopeConfig, TriggerConfig


class InstrumentHal(Protocol):
    def discover(self) -> list[DeviceInfo]:
        ...

    def open(self, device_id: str) -> None:
        ...

    def close(self) -> None:
        ...

    def capabilities(self) -> Capabilities:
        ...

    def configure_scope(self, cfg: ScopeConfig) -> None:
        ...

    def configure_trigger(self, cfg: TriggerConfig) -> None:
        ...

    def configure_channel(self, cfg: ChannelConfig) -> None:
        ...

    def configure_awg(self, cfg: AwgConfig) -> None:
        ...

    def start_streaming(self) -> None:
        ...

    def read_samples(self, max_n: int, timeout_s: float) -> dict[int, np.ndarray]:
        ...

    def stop_streaming(self) -> None:
        ...
