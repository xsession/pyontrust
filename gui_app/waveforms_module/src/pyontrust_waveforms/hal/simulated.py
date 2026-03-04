from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from ..models import AwgConfig, Capabilities, ChannelConfig, DeviceInfo, ScopeConfig, TriggerConfig
from .registry import register_hal


class SimulatedHal:
    def __init__(self, config: dict[str, Any]):
        self._cfg = config
        self._opened = False
        self._scope = ScopeConfig(sample_rate_hz=1_000_000.0, record_length=4096, mode="realtime")
        self._t = 0.0

    def discover(self) -> list[DeviceInfo]:
        return [DeviceInfo(device_id="sim0", display_name="Simulated Instrument", transport="unknown", vendor="pyontrust", product="sim")]

    def open(self, device_id: str) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def capabilities(self) -> Capabilities:
        return Capabilities(analog_in_channels=2, analog_out_channels=2, max_sample_rate_hz=50_000_000.0, has_hw_trigger=False, has_awg=True)

    def configure_scope(self, cfg: ScopeConfig) -> None:
        self._scope = cfg

    def configure_trigger(self, cfg: TriggerConfig) -> None:
        pass

    def configure_channel(self, cfg: ChannelConfig) -> None:
        pass

    def configure_awg(self, cfg: AwgConfig) -> None:
        pass

    def start_streaming(self) -> None:
        pass

    def stop_streaming(self) -> None:
        pass

    def read_samples(self, max_n: int, timeout_s: float) -> dict[int, np.ndarray]:
        n = int(max_n)
        sr = float(self._scope.sample_rate_hz)
        t = (np.arange(n, dtype=np.float32) + self._t) / sr
        self._t += n
        y0 = 0.8 * np.sin(2 * np.pi * 10_000.0 * t) + 0.05 * np.random.randn(n).astype(np.float32)
        return {0: y0.astype(np.float32)}


register_hal("simulated", lambda cfg: SimulatedHal(cfg))
