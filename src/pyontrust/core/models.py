"""Domain value objects — stdlib only, no third-party dependencies.

This module defines all core data types used throughout pyontrust:
- Power measurement: PowerSample, PowerTrace, PowerSummary
- Test execution: TestStep, PowerTest, TestArtifacts, TestContext
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PowerSample:
    """A single power measurement sample."""

    t_s: float
    current_a: float
    voltage_v: float

    @property
    def power_w(self) -> float:
        return self.current_a * self.voltage_v


@dataclass(frozen=True)
class PowerSummary:
    """Aggregated statistics over a power trace."""

    duration_s: float
    samples: int
    avg_current_a: float
    max_current_a: float
    avg_voltage_v: float
    charge_c: float
    energy_j: float
    avg_power_w: float


@dataclass(frozen=True)
class PowerTrace:
    """An ordered sequence of power samples with summary computation."""

    samples: list[PowerSample]

    def summary(self) -> PowerSummary:
        if not self.samples:
            return PowerSummary(
                duration_s=0.0,
                samples=0,
                avg_current_a=0.0,
                max_current_a=0.0,
                avg_voltage_v=0.0,
                charge_c=0.0,
                energy_j=0.0,
                avg_power_w=0.0,
            )

        t0 = self.samples[0].t_s
        t1 = self.samples[-1].t_s
        duration_s = max(0.0, t1 - t0)

        currents = [s.current_a for s in self.samples]
        voltages = [s.voltage_v for s in self.samples]

        # Trapezoidal integration over time.
        charge_c = 0.0
        energy_j = 0.0
        for prev, nxt in zip(self.samples, self.samples[1:]):
            dt = max(0.0, nxt.t_s - prev.t_s)
            i_avg = 0.5 * (prev.current_a + nxt.current_a)
            p_avg = 0.5 * (prev.power_w + nxt.power_w)
            charge_c += i_avg * dt
            energy_j += p_avg * dt

        avg_current_a = (charge_c / duration_s) if duration_s > 0 else float(currents[0])
        avg_voltage_v = sum(voltages) / len(voltages)
        avg_power_w = (energy_j / duration_s) if duration_s > 0 else float(self.samples[0].power_w)

        return PowerSummary(
            duration_s=duration_s,
            samples=len(self.samples),
            avg_current_a=avg_current_a,
            max_current_a=max(currents),
            avg_voltage_v=avg_voltage_v,
            charge_c=charge_c,
            energy_j=energy_j,
            avg_power_w=avg_power_w,
        )


@dataclass
class TestArtifacts:
    """Filesystem paths for test run outputs."""

    root_dir: pathlib.Path
    meta_path: pathlib.Path
    markers_json_path: pathlib.Path
    recorders_dir: pathlib.Path
    trace_csv_path: pathlib.Path
    summary_json_path: pathlib.Path
    report_md_path: pathlib.Path


@dataclass
class TestContext:
    """Mutable context passed through a test run, carrying state and utilities."""

    artifacts: TestArtifacts
    instruments: dict[str, Any]
    start_time_s: float
    markers: list[dict[str, Any]]
    recorder_outputs: dict[str, Any]

    def now_s(self) -> float:
        """Monotonic seconds since test start."""
        return time.perf_counter() - self.start_time_s

    def mark(self, label: str, **fields: Any) -> None:
        """Record a timestamped marker event."""
        event = {"t_s": self.now_s(), "label": label}
        if fields:
            event.update(fields)
        self.markers.append(event)


@dataclass(frozen=True)
class TestStep:
    """A single step in a power test — name, duration, and action callable."""

    name: str
    duration_s: float
    action: Callable[[TestContext], None]


@dataclass(frozen=True)
class PowerTest:
    """Complete test definition: named steps and instrument requirements."""

    name: str
    description: str
    steps: list[TestStep]

    # Instrument names are just keys in ctx.instruments.
    power_meter_key: str = "power_meter"

    def required_instruments(self) -> set[str]:
        return {self.power_meter_key}
