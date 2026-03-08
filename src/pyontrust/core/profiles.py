"""Profile loading, instrument factory, and test building.

Handles JSON profile parsing, instrument instantiation via the plugin
registry, recorder building, and test step composition.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyontrust.core.models import PowerTest, TestContext, TestStep
from pyontrust.core.runner import PowerTestRunner
from pyontrust.instruments import create_instrument
from pyontrust.instruments.simulated import SimulatedPowerMeter
from pyontrust.recorders import create_recorder


@dataclass(frozen=True)
class Profile:
    """Loaded test profile wrapping raw JSON config."""

    raw: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw.get("name", "unnamed_profile"))


def load_profile(path: str | os.PathLike[str]) -> Profile:
    """Load a profile from a JSON file."""
    p = pathlib.Path(path)
    return Profile(raw=json.loads(p.read_text(encoding="utf-8")))


def run_profile(
    profile: Profile,
    repo_root: str | os.PathLike[str],
    *,
    lab_bench_path: Optional[str | os.PathLike[str]] = None,
) -> pathlib.Path:
    """Execute a test profile and return the artifacts directory."""
    repo_root = pathlib.Path(repo_root)
    artifacts_root = profile.raw.get("artifacts_root") or str(repo_root / "artifacts")

    # Merge lab bench + profile instruments
    bench_instruments: dict[str, Any] = {}
    if lab_bench_path is not None:
        from pyontrust.core.lab_bench import LabBench

        bench = LabBench.load(lab_bench_path)
        bench_instruments = {
            name: cfg.params | {"type": cfg.type}
            for name, cfg in bench.enabled_instruments().items()
        }

    # Profile-level instruments override bench defaults
    raw_instruments = {**bench_instruments, **(profile.raw.get("instruments") or {})}

    instruments = _build_instruments(raw_instruments)
    recorders = _build_recorders(profile.raw.get("recorders") or [])
    test = _build_test(profile.raw)

    runner = PowerTestRunner(artifacts_root=artifacts_root)
    artifacts = runner.run(test=test, instruments=instruments, recorders=recorders, meta=profile.raw.get("meta"))
    return artifacts.root_dir


def _build_instruments(cfg: dict[str, Any]) -> dict[str, Any]:
    """Build instrument instances from config dict using the plugin registry."""
    instruments: dict[str, Any] = {}

    for name, inst_cfg in cfg.items():
        if not isinstance(inst_cfg, dict):
            continue
        p_type = inst_cfg.get("type", "simulated")
        params = {k: v for k, v in inst_cfg.items() if k != "type"}
        instruments[name] = create_instrument(p_type, params)

    # Legacy fallback
    if "power_meter" not in instruments and not cfg:
        instruments["power_meter"] = SimulatedPowerMeter()

    return instruments


def _build_recorders(items: list[dict[str, Any]]) -> list[Any]:
    """Build recorder instances from config list using the plugin registry."""
    recs = []
    for it in items:
        r_type = it.get("type", "process")
        params = {k: v for k, v in it.items() if k != "type"}
        recs.append(create_recorder(r_type, params))
    return recs


def _build_test(raw: dict[str, Any]) -> PowerTest:
    name = str(raw.get("name", "profile_test"))
    desc = str(raw.get("description", ""))
    steps_cfg = raw.get("steps") or []

    steps: list[TestStep] = []
    for step_cfg in steps_cfg:
        step_name = str(step_cfg.get("name", "step"))
        duration_s = float(step_cfg.get("duration_s", 1.0))
        actions_cfg = step_cfg.get("actions") or []

        action = _compose_actions(step_name, actions_cfg)
        steps.append(TestStep(name=step_name, duration_s=duration_s, action=action))

    return PowerTest(name=name, description=desc, steps=steps)


def _compose_actions(step_name: str, actions_cfg: list[dict[str, Any]]) -> Callable[[TestContext], None]:
    actions = [_make_action(step_name, a) for a in actions_cfg]

    def _run(ctx: TestContext) -> None:
        for fn in actions:
            fn(ctx)

    return _run


def _make_action(step_name: str, cfg: dict[str, Any]) -> Callable[[TestContext], None]:
    a_type = cfg.get("type")
    if a_type == "mark":
        label = str(cfg.get("label", step_name))

        def _mark(ctx: TestContext) -> None:
            ctx.mark(label, step=step_name)

        return _mark

    if a_type == "set_power_mode":
        mode = str(cfg["mode"])

        def _set(ctx: TestContext) -> None:
            meter = ctx.instruments.get("power_meter")
            if meter is None or not hasattr(meter, "set_mode"):
                raise RuntimeError("power_meter does not support set_mode")
            meter.set_mode(mode)
            ctx.mark("power_mode", mode=mode, step=step_name)

        return _set

    if a_type == "flash":
        firmware = str(cfg["firmware"])
        target = str(cfg.get("instrument", "jlink"))

        def _flash(ctx: TestContext) -> None:
            jlink = ctx.instruments.get(target)
            if jlink is None or not hasattr(jlink, "flash"):
                raise RuntimeError(f"Instrument '{target}' does not support flash()")
            jlink.flash(firmware, erase=cfg.get("erase", True), reset=cfg.get("reset", True))
            ctx.mark("flash", firmware=firmware, step=step_name)

        return _flash

    if a_type == "reset_target":
        target = str(cfg.get("instrument", "jlink"))
        halt = bool(cfg.get("halt", False))

        def _reset(ctx: TestContext) -> None:
            jlink = ctx.instruments.get(target)
            if jlink is None or not hasattr(jlink, "reset"):
                raise RuntimeError(f"Instrument '{target}' does not support reset()")
            jlink.reset(halt=halt)
            ctx.mark("reset_target", step=step_name)

        return _reset

    if a_type == "set_voltage":
        target = str(cfg.get("instrument", "psu"))
        voltage_v = float(cfg["voltage_v"])

        def _set_voltage(ctx: TestContext) -> None:
            psu = ctx.instruments.get(target)
            if psu is None or not hasattr(psu, "set_voltage"):
                raise RuntimeError(f"Instrument '{target}' does not support set_voltage()")
            psu.set_voltage(voltage_v)
            ctx.mark("set_voltage", voltage_v=voltage_v, step=step_name)

        return _set_voltage

    if a_type == "enable_output":
        target = str(cfg.get("instrument", "psu"))
        on = bool(cfg.get("on", True))

        def _enable_output(ctx: TestContext) -> None:
            psu = ctx.instruments.get(target)
            if psu is None or not hasattr(psu, "enable_output"):
                raise RuntimeError(f"Instrument '{target}' does not support enable_output()")
            psu.enable_output(on)
            ctx.mark("enable_output", on=on, step=step_name)

        return _enable_output

    if a_type == "snapshot":
        target = str(cfg.get("instrument", "webcam"))
        filename = str(cfg.get("filename", f"snapshot_{step_name}.jpg"))

        def _snapshot(ctx: TestContext) -> None:
            cam = ctx.instruments.get(target)
            if cam is None or not hasattr(cam, "snapshot"):
                raise RuntimeError(f"Instrument '{target}' does not support snapshot()")
            out = ctx.artifacts.recorders_dir / filename
            cam.snapshot(out)
            ctx.mark("snapshot", path=str(out), step=step_name)

        return _snapshot

    if a_type == "rf_sweep":
        target = str(cfg.get("instrument", "hackrf"))

        def _sweep(ctx: TestContext) -> None:
            rf = ctx.instruments.get(target)
            if rf is None or not hasattr(rf, "sweep"):
                raise RuntimeError(f"Instrument '{target}' does not support sweep()")
            out = ctx.artifacts.recorders_dir / f"sweep_{step_name}.csv"
            rf.sweep(
                out,
                freq_start_mhz=int(cfg.get("freq_start_mhz", 700)),
                freq_stop_mhz=int(cfg.get("freq_stop_mhz", 6000)),
            )
            ctx.mark("rf_sweep", path=str(out), step=step_name)

        return _sweep

    if a_type == "sleep":
        delay_s = float(cfg.get("seconds", 1.0))

        def _sleep(ctx: TestContext) -> None:
            time.sleep(delay_s)
            ctx.mark("sleep", seconds=delay_s, step=step_name)

        return _sleep

    if a_type == "run":
        command = list(cfg["command"])
        timeout_s = cfg.get("timeout_s")

        def _run_cmd(ctx: TestContext) -> None:
            out_dir = ctx.artifacts.recorders_dir / "actions"
            out_dir.mkdir(parents=True, exist_ok=True)
            log_path = out_dir / f"{step_name}_{int(time.time())}.log"
            with log_path.open("w", encoding="utf-8", newline="") as f:
                proc = subprocess.run(
                    command,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout_s,
                )
            if proc.returncode != 0:
                raise RuntimeError(f"Action command failed rc={proc.returncode}. See {log_path}")
            ctx.mark("action_run", step=step_name, log=str(log_path))

        return _run_cmd

    if a_type == "inspect":
        target = str(cfg.get("instrument", "aoi_camera"))
        board_id_tpl = str(cfg.get("board_id", f"board_{step_name}"))

        def _inspect(ctx: TestContext) -> None:
            cam = ctx.instruments.get(target)
            if cam is None or not hasattr(cam, "grab_frame"):
                raise RuntimeError(f"Instrument '{target}' does not support grab_frame()")
            frame = cam.grab_frame()
            out_dir = ctx.artifacts.recorders_dir / "aoi"
            out_dir.mkdir(parents=True, exist_ok=True)
            # Try full AOI pipeline; fall back to saving raw frame
            try:
                from pyontrust.analysis.aoi.inspector import AOIInspector
                from pyontrust.analysis.aoi.processing import ImagePreprocessor
                inspector = AOIInspector(
                    grabber=cam,
                    preprocessor=ImagePreprocessor(denoise_strength=3),
                    aligner=None,
                    detector=None,
                    db_path=out_dir / "aoi_results.db",
                    image_archive=out_dir,
                )
                inspector._init_database()
                result = inspector.inspect_frame(frame, board_id_tpl)
                ctx.mark("aoi_inspect", board_id=board_id_tpl,
                         verdict=result.verdict.value,
                         defects=result.total_defect_count, step=step_name)
            except ImportError:
                # Minimal: just save the frame
                try:
                    import cv2
                    cv2.imwrite(str(out_dir / f"{board_id_tpl}.png"), frame)
                except ImportError:
                    import numpy as np
                    np.save(str(out_dir / f"{board_id_tpl}.npy"), frame)
                ctx.mark("aoi_snapshot", board_id=board_id_tpl, step=step_name)

        return _inspect

    if a_type == "thermal_capture":
        target = str(cfg.get("instrument", "seek_thermal"))
        zone_cfgs = cfg.get("zones", [])

        def _thermal_capture(ctx: TestContext) -> None:
            cam = ctx.instruments.get(target)
            if cam is None or not hasattr(cam, "grab_temperature_frame"):
                raise RuntimeError(
                    f"Instrument '{target}' does not support grab_temperature_frame()"
                )
            out_dir = ctx.artifacts.recorders_dir / "thermal"
            out_dir.mkdir(parents=True, exist_ok=True)

            temp_frame = cam.grab_temperature_frame()
            try:
                from pyontrust.analysis.thermal.analyzer import ThermalAnalyzer
                from pyontrust.analysis.thermal.models import ThermalZone

                zones = [
                    ThermalZone(
                        name=str(zc.get("name", f"zone_{i}")),
                        x=int(zc.get("x", 0)),
                        y=int(zc.get("y", 0)),
                        width=int(zc.get("width", 30)),
                        height=int(zc.get("height", 30)),
                        warn_temp_c=float(zc.get("warn_temp_c", 60.0)),
                        max_temp_c=float(zc.get("max_temp_c", 85.0)),
                    )
                    for i, zc in enumerate(zone_cfgs)
                ]

                analyzer = ThermalAnalyzer(zones=zones)
                snap = analyzer.analyse_frame(temp_frame, frame_index=0)

                # Save colourised image
                try:
                    import cv2
                    colour = analyzer.colorise_frame(temp_frame)
                    cv2.imwrite(
                        str(out_dir / f"thermal_{step_name}.png"), colour,
                    )
                except ImportError:
                    import numpy as np
                    np.save(str(out_dir / f"thermal_{step_name}.npy"), temp_frame)

                ctx.mark(
                    "thermal_capture",
                    step=step_name,
                    verdict=snap.verdict.value,
                    global_max_c=round(snap.global_max_c, 2),
                    global_mean_c=round(snap.global_mean_c, 2),
                )
            except ImportError:
                # Minimal: save raw frame
                import numpy as np
                np.save(str(out_dir / f"thermal_{step_name}.npy"), temp_frame)
                ctx.mark("thermal_raw", step=step_name)

        return _thermal_capture

    if a_type is None:
        return lambda ctx: None

    raise ValueError(f"Unknown action type: {a_type}")
