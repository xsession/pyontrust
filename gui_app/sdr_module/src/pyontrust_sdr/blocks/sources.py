from __future__ import annotations

import os
import math
import time
from typing import Dict

import numpy as np

from .base import Block
from ..runtime.pubsub import PubSub


class SdrSource(Block):
    """v0.1 compatibility block.

    This is *not* a real source in v0.2: it simply forwards IQ from its input
    to its output. Use `sim_iq_source`, `file_iq_source`, or `hal_rx_source`.
    """

    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        iq = inputs.get("iq")
        if iq is None:
            return {}
        return {"iq": iq.astype(np.complex64, copy=False)}


class HalRxSource(Block):
    """Graph-native HAL source.

    Reads IQ from the HAL device currently connected to the runtime.
    """

    is_source = True
    requires_hal = True

    def __init__(self) -> None:
        self._hal = None

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def bind_hal(self, hal) -> None:
        self._hal = hal

    def produce(self, *, chunk_size: int, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        if self._hal is None:
            return {}
        iq = self._hal.read_iq(int(chunk_size), timeout_s=0.25)
        if iq.size == 0:
            return {}
        if iq.dtype != np.complex64:
            iq = iq.astype(np.complex64)
        return {"iq": iq}


class SimIqSource(Block):
    """Graph-native simulated IQ source."""

    is_source = True

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def produce(self, *, chunk_size: int, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        n = int(chunk_size)
        tone_hz = float(self._params.get("tone_hz", 100e3))
        amp = float(self._params.get("amp", 0.7))
        noise = float(self._params.get("noise", 0.02))

        w = 2.0 * math.pi * tone_hz / float(sample_rate_hz)
        phase0 = float(self._params.get("phase", 0.0))
        phase = phase0 + w * np.arange(n, dtype=np.float32)
        self._params["phase"] = float(phase[-1] + w)

        iq = (amp * np.exp(1j * phase)).astype(np.complex64)
        if noise > 0:
            iq = iq + (noise * (np.random.randn(n) + 1j * np.random.randn(n))).astype(np.complex64)
        return {"iq": iq}


class SignalGeneratorSource(Block):
    """Standalone generator (not wired to HAL in v0.1 runtime)."""

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        n = int(self._params.get("n", 4096))
        tone_hz = float(self._params.get("tone_hz", 100e3))
        amp = float(self._params.get("amp", 0.7))
        w = 2.0 * math.pi * tone_hz / float(sample_rate_hz)
        phase0 = float(self._params.get("phase", 0.0))
        phase = phase0 + w * np.arange(n, dtype=np.float32)
        self._params["phase"] = float(phase[-1] + w)
        return {"iq": (amp * np.exp(1j * phase)).astype(np.complex64)}


class FileIqSource(Block):
    """Graph-native file replay IQ source.

    Params:
    - path: raw complex64 IQ file
    - loop: bool (default False)
    - pace: bool (default True) to approximate real-time
    """

    is_source = True

    def __init__(self) -> None:
        self._fh = None
        self._t_last = None

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def start(self, *, sample_rate_hz: float, pubsub: PubSub) -> None:
        path = str(self._params.get("path", "")).strip()
        if not path:
            raise ValueError("file_iq_source requires params.path")
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        self._fh = open(path, "rb")
        self._t_last = time.perf_counter()

    def stop(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
        self._fh = None
        self._t_last = None

    def produce(self, *, chunk_size: int, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        if self._fh is None:
            # runtime calls start(); if not, behave as no data
            return {}

        n = int(chunk_size)
        need_bytes = n * np.dtype(np.complex64).itemsize
        buf = self._fh.read(need_bytes)

        if len(buf) < need_bytes:
            if bool(self._params.get("loop", False)):
                self._fh.seek(0)
                rest = self._fh.read(need_bytes - len(buf))
                buf = buf + rest
            else:
                raise EOFError("End of IQ file")

        iq = np.frombuffer(buf, dtype=np.complex64, count=n)

        if bool(self._params.get("pace", True)):
            now = time.perf_counter()
            if self._t_last is not None:
                target = float(n) / float(sample_rate_hz)
                dt = now - float(self._t_last)
                if dt < target:
                    time.sleep(max(0.0, target - dt))
            self._t_last = time.perf_counter()

        return {"iq": iq}
