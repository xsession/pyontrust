from __future__ import annotations

import math
from typing import Dict

import numpy as np

from .base import Block
from ..dsp_core.fir import design_lowpass, fir_filter
from ..runtime.pubsub import PubSub


class DcBlocker(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._alpha = float(self._params.get("alpha", 0.995))
        self._y1 = np.complex64(0)
        self._x1 = np.complex64(0)

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        x = x.astype(np.complex64, copy=False)
        y = np.empty_like(x)
        a = np.float32(self._alpha)
        y1 = self._y1
        x1 = self._x1
        for i in range(len(x)):
            y1 = a * (y1 + x[i] - x1)
            y[i] = y1
            x1 = x[i]
        self._y1 = np.complex64(y1)
        self._x1 = np.complex64(x1)
        return {"iq": y}


class Agc(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._target = float(self._params.get("target", 0.5))
        self._rate = float(self._params.get("rate", 1e-3))
        self._gain = float(self._params.get("gain", 1.0))

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        x = x.astype(np.complex64, copy=False)
        mag = np.abs(x).astype(np.float32)
        rms = float(np.sqrt(np.mean(mag**2) + 1e-12))
        err = (self._target / max(1e-9, rms))
        self._gain = (1.0 - self._rate) * self._gain + self._rate * err
        y = (x * np.complex64(self._gain)).astype(np.complex64)
        return {"iq": y}


class FrequencyTranslate(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._shift_hz = float(self._params.get("shift_hz", 0.0))
        self._phase = 0.0

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        x = x.astype(np.complex64, copy=False)
        w = 2.0 * math.pi * self._shift_hz / float(sample_rate_hz)
        ph = self._phase + w * np.arange(len(x), dtype=np.float32)
        lo = np.exp(1j * ph).astype(np.complex64)
        self._phase = float(ph[-1] + w)
        return {"iq": (x * lo).astype(np.complex64)}


class FirLowpass(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._cutoff_hz = float(self._params.get("cutoff_hz", 100e3))
        self._taps = int(self._params.get("taps", 101))
        self._h = None
        self._zi = None
        self._sr_last = None

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        if self._h is None or self._sr_last != sample_rate_hz:
            self._h = design_lowpass(cutoff_hz=self._cutoff_hz, sample_rate_hz=sample_rate_hz, taps=self._taps)
            self._zi = None
            self._sr_last = sample_rate_hz
        y, zf = fir_filter(x, self._h, zi=self._zi)
        self._zi = zf
        return {"iq": y}


class Decimator(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._q = int(self._params.get("q", 2))

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        q = max(1, int(self._q))
        return {"iq": x[::q].astype(np.complex64, copy=False)}


class AmDemod(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"audio": "float32"}

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        a = np.abs(x).astype(np.float32)
        a -= float(np.mean(a))
        return {"audio": a.astype(np.float32)}


class FmDemod(Block):
    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def output_ports(self) -> Dict[str, str]:
        return {"audio": "float32"}

    def output_ports(self) -> Dict[str, str]:
        return {"audio": "float32"}

    def configure(self, params: dict) -> None:
        super().configure(params)
        self._prev = np.complex64(1.0 + 0.0j)

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        x = inputs.get("iq")
        if x is None:
            return {}
        x = x.astype(np.complex64, copy=False)
        y = x * np.conj(np.concatenate([[self._prev], x[:-1]]))
        self._prev = np.complex64(x[-1])
        audio = np.angle(y).astype(np.float32)
        return {"audio": audio}
