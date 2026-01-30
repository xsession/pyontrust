from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..models import DeviceInfo, RxConfig
from .protocol import SdrHal


@dataclass
class SimParams:
    mode: str = "tone"  # tone|noise|chirp
    tone_hz: float = 100e3
    snr_db: float = 30.0
    chirp_f0_hz: float = -200e3
    chirp_f1_hz: float = 200e3
    chirp_period_s: float = 1.0


class SimulatedHal(SdrHal):
    def __init__(self) -> None:
        self._cfg = RxConfig()
        self._t0 = 0.0
        self._phase = 0.0
        self._streaming = False
        self._params = SimParams()

    def discover(self) -> list[DeviceInfo]:
        return [DeviceInfo(device_id="sim0", driver="sim", display_name="Simulated IQ", meta={})]

    def open(self, device_id: str) -> None:
        self._t0 = time.time()
        self._phase = 0.0

    def close(self) -> None:
        self._streaming = False

    def set_rx_config(self, cfg: RxConfig) -> None:
        self._cfg = cfg

    def start_stream(self) -> None:
        self._streaming = True

    def read_iq(self, num_samples: int, timeout_s: float) -> np.ndarray:
        if not self._streaming:
            return np.empty((0,), dtype=np.complex64)

        sr = float(self._cfg.sample_rate_hz)
        t = (np.arange(num_samples, dtype=np.float32) / sr).astype(np.float32)

        if self._params.mode == "noise":
            sig = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)).astype(np.complex64)
            sig *= 0.2
        elif self._params.mode == "chirp":
            # linear chirp in baseband
            now = time.time() - self._t0
            tau = (now % self._params.chirp_period_s) / self._params.chirp_period_s
            f0 = self._params.chirp_f0_hz
            f1 = self._params.chirp_f1_hz
            # instantaneous freq across buffer (approx)
            fi = f0 + (f1 - f0) * tau
            dphi = 2.0 * math.pi * fi / sr
            phase = self._phase + dphi * np.arange(num_samples, dtype=np.float32)
            sig = np.exp(1j * phase).astype(np.complex64)
            self._phase = float(phase[-1] + dphi)
            sig *= 0.7
        else:
            # tone
            w = 2.0 * math.pi * float(self._params.tone_hz) / sr
            phase = self._phase + w * np.arange(num_samples, dtype=np.float32)
            sig = np.exp(1j * phase).astype(np.complex64)
            self._phase = float(phase[-1] + w)
            sig *= 0.7

        # add noise for SNR
        snr = 10 ** (float(self._params.snr_db) / 10.0)
        noise_pow = (np.mean(np.abs(sig) ** 2) / snr) if snr > 0 else 0.01
        n = (
            np.random.randn(num_samples).astype(np.float32)
            + 1j * np.random.randn(num_samples).astype(np.float32)
        ).astype(np.complex64)
        n *= math.sqrt(noise_pow / 2.0)
        return (sig + n).astype(np.complex64)

    def stop_stream(self) -> None:
        self._streaming = False
