"""Simulated power meter — for CI / development without hardware."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Iterable

from pyontrust.core.models import PowerSample


@dataclass
class SimulatedPowerMeter:
    """Deterministic-ish simulated power meter.

    Useful for CI and for developing test logic without lab hardware.
    """

    sample_rate_hz: float = 1000.0
    voltage_v: float = 3.0
    sleep_current_a: float = 5e-6
    active_current_a: float = 8e-3
    noise_a_rms: float = 2e-6

    _mode: str = "sleep"
    _t0: float | None = None

    def open(self) -> None:
        self._t0 = time.perf_counter()

    def close(self) -> None:
        self._t0 = None

    def set_mode(self, mode: str) -> None:
        if mode not in {"sleep", "active"}:
            raise ValueError("mode must be 'sleep' or 'active'")
        self._mode = mode

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        if self._t0 is None:
            self.open()
        assert self._t0 is not None

        dt = 1.0 / float(self.sample_rate_hz)
        start = time.perf_counter()
        t = start
        while (t - start) < duration_s:
            base = self.sleep_current_a if self._mode == "sleep" else self.active_current_a
            noise = random.gauss(0.0, self.noise_a_rms)
            now = time.perf_counter()
            yield PowerSample(t_s=(now - self._t0), current_a=max(0.0, base + noise), voltage_v=self.voltage_v)
            time.sleep(max(0.0, dt))
            t = time.perf_counter()


def create(config: dict[str, Any]) -> SimulatedPowerMeter:
    """Entry-point factory for the simulated power meter."""
    return SimulatedPowerMeter(
        sample_rate_hz=float(config.get("sample_rate_hz", 1000.0)),
        voltage_v=float(config.get("voltage_v", 3.0)),
        sleep_current_a=float(config.get("sleep_current_a", 5e-6)),
        active_current_a=float(config.get("active_current_a", 8e-3)),
        noise_a_rms=float(config.get("noise_a_rms", 2e-6)),
    )
