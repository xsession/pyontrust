from __future__ import annotations

import json
import os
import pathlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from .recorders.base import Recorder

from .reporting import write_power_trace_csv, write_report_md, write_summary_json
from .utils import utc_timestamp_id


@dataclass(frozen=True)
class PowerSample:
    t_s: float
    current_a: float
    voltage_v: float

    @property
    def power_w(self) -> float:
        return self.current_a * self.voltage_v


@dataclass(frozen=True)
class PowerSummary:
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
    root_dir: pathlib.Path
    meta_path: pathlib.Path
    markers_json_path: pathlib.Path
    recorders_dir: pathlib.Path
    trace_csv_path: pathlib.Path
    summary_json_path: pathlib.Path
    report_md_path: pathlib.Path


@dataclass
class TestContext:
    artifacts: TestArtifacts
    instruments: dict[str, Any]
    start_time_s: float
    markers: list[dict[str, Any]]
    recorder_outputs: dict[str, Any]

    def now_s(self) -> float:
        return time.perf_counter() - self.start_time_s

    def mark(self, label: str, **fields: Any) -> None:
        event = {"t_s": self.now_s(), "label": label}
        if fields:
            event.update(fields)
        self.markers.append(event)


@dataclass(frozen=True)
class TestStep:
    name: str
    duration_s: float
    action: Callable[[TestContext], None]


@dataclass(frozen=True)
class PowerTest:
    name: str
    description: str
    steps: list[TestStep]

    # Instrument names are just keys in ctx.instruments.
    power_meter_key: str = "power_meter"

    def required_instruments(self) -> set[str]:
        return {self.power_meter_key}


class PowerTestRunner:
    def __init__(
        self,
        artifacts_root: str | os.PathLike[str] = "artifacts",
    ) -> None:
        self._artifacts_root = pathlib.Path(artifacts_root)

    def run(
        self,
        test: PowerTest,
        instruments: dict[str, Any],
        recorders: Optional[list[Recorder]] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> TestArtifacts:
        self._artifacts_root.mkdir(parents=True, exist_ok=True)
        run_id = utc_timestamp_id()
        safe_test_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in test.name)
        root_dir = self._artifacts_root / f"{safe_test_name}_{run_id}"
        root_dir.mkdir(parents=True, exist_ok=False)

        artifacts = TestArtifacts(
            root_dir=root_dir,
            meta_path=root_dir / "meta.json",
            markers_json_path=root_dir / "markers.json",
            recorders_dir=root_dir / "recorders",
            trace_csv_path=root_dir / "power_trace.csv",
            summary_json_path=root_dir / "summary.json",
            report_md_path=root_dir / "report.md",
        )
        artifacts.recorders_dir.mkdir(parents=True, exist_ok=True)

        missing = test.required_instruments() - set(instruments.keys())
        if missing:
            raise KeyError(f"Missing required instruments: {sorted(missing)}")

        ctx = TestContext(
            artifacts=artifacts,
            instruments=instruments,
            start_time_s=time.perf_counter(),
            markers=[],
            recorder_outputs={},
        )

        # Open instruments if they support it.
        opened: list[Any] = []
        started_recorders: list[Recorder] = []
        trace: PowerTrace | None = None
        summary: PowerSummary | None = None
        run_error: str | None = None

        test_meta: dict[str, Any] = {
            "name": test.name,
            "description": test.description,
            "power_meter_key": test.power_meter_key,
            "steps": [{"name": s.name, "duration_s": s.duration_s} for s in test.steps],
        }

        try:
            for inst in instruments.values():
                if hasattr(inst, "open"):
                    inst.open()
                    opened.append(inst)

            for rec in recorders or []:
                rec.start(ctx)
                started_recorders.append(rec)
                ctx.mark("recorder_start", recorder=rec.name)

            trace = self._run_steps_with_power_capture(test=test, ctx=ctx)
            summary = trace.summary()
        except BaseException as exc:  # noqa: BLE001
            run_error = repr(exc)
            raise
        finally:
            # Stop recorders first so their outputs/exit codes land in meta.
            for rec in reversed(started_recorders):
                try:
                    rec.stop(ctx)
                    ctx.mark("recorder_stop", recorder=rec.name)
                except BaseException as exc:  # noqa: BLE001
                    ctx.recorder_outputs.setdefault(rec.name, {})
                    ctx.recorder_outputs[rec.name]["stop_error"] = repr(exc)

            for inst in reversed(opened):
                if hasattr(inst, "close"):
                    inst.close()

            # Write best-effort artifacts even on failure.
            meta_out: dict[str, Any] = {
                "test": test_meta,
                "markers": ctx.markers,
                "recorders": ctx.recorder_outputs,
            }
            if run_error:
                meta_out["error"] = run_error
            if meta:
                meta_out["meta"] = meta

            if summary is not None:
                meta_out["summary"] = summary.__dict__

            artifacts.meta_path.write_text(json.dumps(meta_out, indent=2), encoding="utf-8")
            artifacts.markers_json_path.write_text(json.dumps(ctx.markers, indent=2), encoding="utf-8")

            if trace is not None and summary is not None:
                write_power_trace_csv(artifacts.trace_csv_path, trace)
                write_summary_json(artifacts.summary_json_path, summary)
                write_report_md(artifacts.report_md_path, test=test, summary=summary, artifacts=artifacts)

        return artifacts


    def _run_steps_with_power_capture(self, test: PowerTest, ctx: TestContext) -> PowerTrace:
        meter = ctx.instruments[test.power_meter_key]
        all_samples: list[PowerSample] = []

        for step in test.steps:
            ctx.mark("step_start", step=step.name)
            # Run action in parallel with capture so DUT manipulation overlaps measurement.
            error: list[BaseException] = []

            def _action_wrapper() -> None:
                try:
                    step.action(ctx)
                except BaseException as exc:  # noqa: BLE001
                    error.append(exc)

            thread = threading.Thread(target=_action_wrapper, name=f"step:{step.name}")
            thread.start()
            samples: Iterable[PowerSample] = meter.capture(duration_s=step.duration_s)
            thread.join(timeout=step.duration_s + 30.0)

            all_samples.extend(list(samples))
            if error:
                raise error[0]

            ctx.mark("step_end", step=step.name)

        return PowerTrace(samples=all_samples)
