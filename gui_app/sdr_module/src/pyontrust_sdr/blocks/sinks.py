from __future__ import annotations

from typing import Dict

import numpy as np

from .base import Block
from ..dsp_core.fft import rfft_power_db
from ..runtime.pubsub import PubSub


class FftSink(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._bins = int(self._params.get("bins", 1024))

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        f_norm, p_db = rfft_power_db(x, bins=self._bins)
        # send only display payload (floats)
        pubsub.publish(
            "fft",
            {
                "freq_hz": (f_norm * float(sample_rate_hz)).astype(np.float32),
                "power_db": p_db.astype(np.float32),
            },
        )
        return {}


class WaterfallSink(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._bins = int(self._params.get("bins", 256))
        self._rows = int(self._params.get("rows", 200))
        self._buf = np.zeros((self._rows, self._bins), dtype=np.float32)

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        _, p_db = rfft_power_db(x, bins=self._bins)
        self._buf[:-1] = self._buf[1:]
        self._buf[-1] = p_db
        pubsub.publish(
            "waterfall",
            {
                "power_db": self._buf.copy(),  # 2D, small (rows*bins)
            },
        )
        return {}


class IqScopeSink(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._max_points = int(self._params.get("max_points", 1024))

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        x = x.astype(np.complex64, copy=False)
        if len(x) > self._max_points:
            step = max(1, len(x) // self._max_points)
            x = x[::step]
        pubsub.publish(
            "iq_scope",
            {
                "i": np.real(x).astype(np.float32),
                "q": np.imag(x).astype(np.float32),
            },
        )
        return {}
