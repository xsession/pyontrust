from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

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


def run_profile(
    profile: Profile,
    repo_root: str | os.PathLike[str],
    *,
    lab_bench_path: Optional[str | os.PathLike[str]] = None,
) -> pathlib.Path:
    """Execute a test profile.

    Parameters
    ----------
    profile : Profile
        Loaded profile definition.
    repo_root : path
        Repository root (used for default artifacts path).
    lab_bench_path : path, optional
        Path to a ``lab_bench.json``.  When provided, instrument configs
        from the bench file are merged with (and overridden by) profile-level
        instrument configs, allowing a single bench definition to feed many
        profiles.
    """
    repo_root = pathlib.Path(repo_root)
    artifacts_root = profile.raw.get("artifacts_root") or str(repo_root / "artifacts")

    # Merge lab bench + profile instruments
    bench_instruments: dict[str, Any] = {}
    if lab_bench_path is not None:
        from .lab_bench import LabBench

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
    """Build instrument instances from config dict.

    Supports both the legacy ``{"power_meter": {...}}`` format and the new
    multi-instrument format where every key is an instrument name::

        {
          "power_meter": {"type": "ppk2", ...},
          "psu": {"type": "sk120", ...},
          "jlink": {"type": "jlink", ...},
          "hackrf": {"type": "hackrf", ...},
          "webcam": {"type": "webcam", ...}
        }
    """
    instruments: dict[str, Any] = {}

    for name, inst_cfg in cfg.items():
        if not isinstance(inst_cfg, dict):
            continue
        p_type = inst_cfg.get("type", "simulated")
        params = {k: v for k, v in inst_cfg.items() if k != "type"}

        instruments[name] = _create_instrument(p_type, params)

    # Legacy fallback: if no "power_meter" key, use default simulated
    if "power_meter" not in instruments and not cfg:
        instruments["power_meter"] = SimulatedPowerMeter()

    return instruments


def _create_instrument(p_type: str, params: dict[str, Any]) -> Any:
    """Factory: instantiate a single instrument by type string."""

    if p_type == "simulated":
        return SimulatedPowerMeter(
            sample_rate_hz=float(params.get("sample_rate_hz", 500.0)),
            voltage_v=float(params.get("voltage_v", 3.0)),
            sleep_current_a=float(params.get("sleep_current_a", 5e-6)),
            active_current_a=float(params.get("active_current_a", 8e-3)),
        )

    if p_type == "csv_file":
        return CsvFilePowerMeter(
            csv_path=params["csv_path"],
            t_col=params.get("t_col", "t_s"),
            i_col=params.get("i_col", "current_a"),
            v_col=params.get("v_col", "voltage_v"),
        )

    if p_type == "csv_process":
        return CsvProcessPowerMeter(
            command=list(params["command"]),
            csv_path=params["csv_path"],
            t_col=params.get("t_col", "t_s"),
            i_col=params.get("i_col", "current_a"),
            v_col=params.get("v_col", "voltage_v"),
            cwd=params.get("cwd"),
        )

    if p_type == "ad3_dwf":
        return Ad3DwfPowerMeter(
            sample_rate_hz=float(params.get("sample_rate_hz", 1000.0)),
            device_index=int(params.get("device_index", -1)),
            current_channel=int(params.get("current_channel", 0)),
            voltage_channel=int(params.get("voltage_channel", 1)),
            current_range_v=float(params.get("current_range_v", 5.0)),
            voltage_range_v=float(params.get("voltage_range_v", 5.0)),
            current_a_per_v=float(params.get("current_a_per_v", 1.0)),
            voltage_v_per_v=float(params.get("voltage_v_per_v", 1.0)),
            current_offset_v=float(params.get("current_offset_v", 0.0)),
            voltage_offset_v=float(params.get("voltage_offset_v", 0.0)),
        )

    if p_type == "ad3_cluster":
        from .instruments.ad3_cluster import Ad3ClusterPowerMeter, Ad3DeviceConfig

        devices = [Ad3DeviceConfig.from_dict(d) for d in params.get("devices", [])]
        return Ad3ClusterPowerMeter(
            devices=devices,
            buffer_size=int(params.get("buffer_size", 8192)),
            trigger_source=params.get("trigger_source", "none"),
        )

    if p_type == "ppk2":
        from .instruments.ppk2 import Ppk2PowerMeter

        return Ppk2PowerMeter(
            serial_port=params.get("serial_port", params.get("port", "auto")),
            sample_rate_hz=float(params.get("sample_rate_hz", 100_000)),
            mode=params.get("mode", "ampere"),
            source_voltage_mv=int(params.get("source_voltage_mv", 3300)),
        )

    if p_type == "sk120":
        from .instruments.sk120_psu import Sk120PowerSupply

        return Sk120PowerSupply(
            port=params.get("port", ""),
            baud=int(params.get("baud", 9600)),
            voltage_v=float(params.get("voltage_v", 3.3)),
            current_limit_a=float(params.get("current_limit_a", 0.5)),
            channel=int(params.get("channel", 1)),
            output_on=bool(params.get("output_on", True)),
        )

    if p_type == "jlink":
        from .instruments.jlink_ctrl import JLinkController

        return JLinkController(
            device=params.get("device", ""),
            interface=params.get("interface", "swd"),
            speed_khz=int(params.get("speed_khz", 4000)),
            serial=params.get("serial", "auto"),
            jlink_path=params.get("jlink_path", "auto"),
        )

    if p_type == "hackrf":
        from .instruments.hackrf_instrument import HackRfInstrument

        return HackRfInstrument(
            freq_hz=int(params.get("freq_hz", 2_402_000_000)),
            sample_rate_hz=int(params.get("sample_rate_hz", 10_000_000)),
            lna_gain_db=int(params.get("lna_gain_db", 16)),
            vga_gain_db=int(params.get("vga_gain_db", 20)),
            amp_enable=bool(params.get("amp_enable", False)),
            device_serial=params.get("device_serial", "auto"),
        )

    if p_type == "webcam":
        from .instruments.webcam_instrument import WebcamInstrument

        return WebcamInstrument(
            input_device=params.get("input_device", ""),
            ffmpeg_path=params.get("ffmpeg_path", "ffmpeg"),
            framerate=int(params.get("framerate", 30)),
            video_size=params.get("video_size", "1280x720"),
        )

    raise ValueError(f"Unknown instrument type: {p_type}")


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
        if r_type == "nrf52840_dongle":
            from .recorders.nrf52840_dongle import Nrf52840DongleRecorder  # optional deps

            recs.append(Nrf52840DongleRecorder(**{k: v for k, v in it.items() if k != "type"}))
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

    if a_type is None:
        # allow empty list
        return lambda ctx: None

    raise ValueError(f"Unknown action type: {a_type}")
