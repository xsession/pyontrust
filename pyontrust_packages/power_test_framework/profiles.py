from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

from .core import PowerTest, PowerTestRunner, TestContext, TestStep
from .instruments.csv_power_meter import CsvFilePowerMeter, CsvProcessPowerMeter
from .instruments.ad3_dwf import Ad3DwfPowerMeter
from .instruments.simulated import SimulatedPowerMeter
from .recorders.process import ProcessRecorder


@dataclass(frozen=True)
class Profile:
    raw: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw.get("name", "unnamed_profile"))


def load_profile(path: str | os.PathLike[str]) -> Profile:
    p = pathlib.Path(path)
    return Profile(raw=json.loads(p.read_text(encoding="utf-8")))


def run_profile(profile: Profile, repo_root: str | os.PathLike[str]) -> pathlib.Path:
    repo_root = pathlib.Path(repo_root)
    artifacts_root = profile.raw.get("artifacts_root") or str(repo_root / "artifacts")

    instruments = _build_instruments(profile.raw.get("instruments") or {})
    recorders = _build_recorders(profile.raw.get("recorders") or [])
    test = _build_test(profile.raw)

    runner = PowerTestRunner(artifacts_root=artifacts_root)
    artifacts = runner.run(test=test, instruments=instruments, recorders=recorders, meta=profile.raw.get("meta"))
    return artifacts.root_dir


def _build_instruments(cfg: dict[str, Any]) -> dict[str, Any]:
    power = cfg.get("power_meter") or {"type": "simulated"}
    p_type = power.get("type", "simulated")
    if p_type == "simulated":
        return {
            "power_meter": SimulatedPowerMeter(
                sample_rate_hz=float(power.get("sample_rate_hz", 500.0)),
                voltage_v=float(power.get("voltage_v", 3.0)),
                sleep_current_a=float(power.get("sleep_current_a", 5e-6)),
                active_current_a=float(power.get("active_current_a", 8e-3)),
            )
        }
    if p_type == "csv_file":
        return {
            "power_meter": CsvFilePowerMeter(
                csv_path=power["csv_path"],
                t_col=power.get("t_col", "t_s"),
                i_col=power.get("i_col", "current_a"),
                v_col=power.get("v_col", "voltage_v"),
            )
        }
    if p_type == "csv_process":
        return {
            "power_meter": CsvProcessPowerMeter(
                command=list(power["command"]),
                csv_path=power["csv_path"],
                t_col=power.get("t_col", "t_s"),
                i_col=power.get("i_col", "current_a"),
                v_col=power.get("v_col", "voltage_v"),
                cwd=power.get("cwd"),
            )
        }

    if p_type == "ad3_dwf":
        return {
            "power_meter": Ad3DwfPowerMeter(
                sample_rate_hz=float(power.get("sample_rate_hz", 1000.0)),
                device_index=int(power.get("device_index", -1)),
                current_channel=int(power.get("current_channel", 0)),
                voltage_channel=int(power.get("voltage_channel", 1)),
                current_range_v=float(power.get("current_range_v", 5.0)),
                voltage_range_v=float(power.get("voltage_range_v", 5.0)),
                current_a_per_v=float(power.get("current_a_per_v", 1.0)),
                voltage_v_per_v=float(power.get("voltage_v_per_v", 1.0)),
                current_offset_v=float(power.get("current_offset_v", 0.0)),
                voltage_offset_v=float(power.get("voltage_offset_v", 0.0)),
            )
        }

    raise ValueError(f"Unknown power_meter type: {p_type}")


def _build_recorders(items: list[dict[str, Any]]):
    recs = []
    for it in items:
        r_type = it.get("type", "process")
        if r_type == "process":
            recs.append(
                ProcessRecorder(
                    name=str(it["name"]),
                    command=list(it["command"]),
                    cwd=it.get("cwd"),
                    skip_if_missing=bool(it.get("skip_if_missing", True)),
                )
            )
            continue
        if r_type == "hackrf_iq":
            from .recorders.hackrf_iq import HackRfIqRecorder  # local import: optional tool

            recs.append(HackRfIqRecorder(**{k: v for k, v in it.items() if k != "type"}))
            continue
        if r_type == "ffmpeg_webcam":
            from .recorders.ffmpeg_webcam import FfmpegWebcamRecorder  # local import: optional tool

            recs.append(FfmpegWebcamRecorder(**{k: v for k, v in it.items() if k != "type"}))
            continue
        if r_type == "wireshark_tshark":
            # tshark -i <iface> -w <pcapng>
            iface = str(it.get("interface", "1"))
            out = str(it.get("out", "capture.pcapng"))
            recs.append(
                ProcessRecorder(
                    name=str(it.get("name", "tshark")),
                    command=["tshark", "-i", iface, "-w", out],
                    skip_if_missing=True,
                )
            )
            continue
        if r_type == "ghidra_headless":
            # analyzeHeadless <project_dir> <project_name> -import <file> -scriptPath <dir> -postScript <script>
            ghidra = it.get("analyze_headless", "analyzeHeadless")
            project_dir = str(it["project_dir"])
            project_name = str(it["project_name"])
            import_file = str(it["import_file"])
            script_path = it.get("script_path")
            post_script = it.get("post_script")
            cmd = [ghidra, project_dir, project_name, "-import", import_file]
            if script_path:
                cmd += ["-scriptPath", str(script_path)]
            if post_script:
                cmd += ["-postScript", str(post_script)]
            recs.append(ProcessRecorder(name=str(it.get("name", "ghidra")), command=cmd, skip_if_missing=True))
            continue
        if r_type == "pcan_can":
            from .recorders.pcan_can import PcanCanRecorder  # local import: optional deps

            recs.append(PcanCanRecorder(**{k: v for k, v in it.items() if k != "type"}))
            continue
        raise ValueError(f"Unknown recorder type: {r_type}")
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

    if a_type is None:
        # allow empty list
        return lambda ctx: None

    raise ValueError(f"Unknown action type: {a_type}")
