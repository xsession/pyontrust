from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Optional

try:
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "nicegui":
        raise

    msg = """
Missing dependency: nicegui

You likely ran this file with the wrong Python environment.

Recommended dev run (PowerShell):
  Set-Location C:\GIT\pyontrust
  python -m venv .venv-nicegui
  .\.venv-nicegui\Scripts\python -m pip install -U pip
  .\.venv-nicegui\Scripts\python -m pip install -r scripts\requirements.txt
  .\.venv-nicegui\Scripts\python -m pip install -e gui_app\nicegui_control
  .\.venv-nicegui\Scripts\python -m pyontrust_gui
""".strip()
    print(msg, file=sys.stderr)
    raise SystemExit(1)


# Make `pyontrust_packages/` importable when running from this app folder.
# For Briefcase builds, `pyontrust_packages` is included as an app source.
HERE = pathlib.Path(__file__).resolve()
REPO_ROOT = HERE.parents[4] if (HERE.parents[4] / "pyontrust_packages").exists() else None
if REPO_ROOT is not None:
    sys.path.append(str(REPO_ROOT / "pyontrust_packages"))
    sys.path.append(str(REPO_ROOT / "scripts"))

from power_test_framework.core import PowerTest, PowerTestRunner, TestStep  # noqa: E402
from power_test_framework.instruments.simulated import SimulatedPowerMeter  # noqa: E402
from power_test_framework.instruments.csv_power_meter import CsvFilePowerMeter, CsvProcessPowerMeter  # noqa: E402
from power_test_framework.instruments.ad3_dwf import Ad3DwfPowerMeter  # noqa: E402
from power_test_framework.recorders.process import ProcessRecorder  # noqa: E402
from power_test_framework.recorders.hackrf_iq import HackRfIqRecorder  # noqa: E402
from power_test_framework.recorders.ffmpeg_webcam import FfmpegWebcamRecorder  # noqa: E402
from power_test_framework.vision_change_logger import VisionChangeConfig, analyze_video_changes  # noqa: E402
from power_test_framework.vision_object_detector import ObjectDetectConfig, analyze_video_objects  # noqa: E402


def _safe_float(value: str, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass
class GuiModel:
    artifacts_root: str

    # power meter
    power_meter_type: str = "simulated"  # simulated | ad3_dwf | csv_file | csv_process

    # simulated
    sim_sample_rate_hz: str = "200"
    sim_voltage_v: str = "3.0"

    # ad3/dwf
    ad3_sample_rate_hz: str = "1000"
    ad3_device_index: str = "-1"
    ad3_current_channel: str = "0"
    ad3_voltage_channel: str = "1"
    ad3_current_a_per_v: str = "1.0"
    ad3_voltage_v_per_v: str = "1.0"
    ad3_current_offset_v: str = "0.0"
    ad3_voltage_offset_v: str = "0.0"

    # csv file
    csv_file_path: str = ""

    # csv process
    csv_process_command: str = ""
    csv_process_csv_path: str = ""

    # recorders
    enable_hackrf: bool = False
    hackrf_tool: str = "hackrf_transfer"
    hackrf_freq_hz: str = "2402000000"
    hackrf_sample_rate_hz: str = "10000000"
    hackrf_baseband_filter_hz: str = ""
    hackrf_lna_gain_db: str = ""
    hackrf_vga_gain_db: str = ""
    hackrf_amp_enable: bool = False
    hackrf_device_serial: str = ""

    enable_webcam: bool = False
    webcam_ffmpeg: str = "ffmpeg"
    webcam_input_device: str = ""

    enable_process: bool = False
    process_name: str = "process"
    process_command: str = ""

    # vision change logging
    enable_vision: bool = False
    vision_mode: str = "display_change"
    vision_fps: str = "2"
    vision_scale_width: str = "160"
    vision_blink_delta: str = "25"
    vision_display_delta: str = "12"

    # object detection
    enable_object_detect: bool = False
    object_bootstrap_ml: bool = True
    object_model: str = "yolov8n.pt"
    object_conf: str = "0.25"
    object_fps: str = "1"
    object_scale_width: str = "320"

    # profile runner
    profile_path: str = ""


def _default_repo_root() -> pathlib.Path:
    if REPO_ROOT is not None:
        return REPO_ROOT
    # Fallback: best-effort based on cwd.
    return pathlib.Path.cwd()


MODEL = GuiModel(artifacts_root=str(_default_repo_root() / "artifacts"))
MODEL.profile_path = str(_default_repo_root() / "scripts" / "power_tests" / "example_profile.json")


def _open_folder(path: str) -> None:
    p = pathlib.Path(path)
    if not p.exists():
        ui.notify(f"Path does not exist: {path}", type="warning")
        return
    try:
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception as exc:  # noqa: BLE001
        ui.notify(repr(exc), type="negative")


def _build_meter(m: GuiModel):
    t = m.power_meter_type
    if t == "simulated":
        return SimulatedPowerMeter(
            sample_rate_hz=_safe_float(m.sim_sample_rate_hz, 200.0),
            voltage_v=_safe_float(m.sim_voltage_v, 3.0),
        )

    if t == "ad3_dwf":
        return Ad3DwfPowerMeter(
            sample_rate_hz=_safe_float(m.ad3_sample_rate_hz, 1000.0),
            device_index=_safe_int(m.ad3_device_index, -1),
            current_channel=_safe_int(m.ad3_current_channel, 0),
            voltage_channel=_safe_int(m.ad3_voltage_channel, 1),
            current_a_per_v=_safe_float(m.ad3_current_a_per_v, 1.0),
            voltage_v_per_v=_safe_float(m.ad3_voltage_v_per_v, 1.0),
            current_offset_v=_safe_float(m.ad3_current_offset_v, 0.0),
            voltage_offset_v=_safe_float(m.ad3_voltage_offset_v, 0.0),
        )

    if t == "csv_file":
        if not m.csv_file_path.strip():
            raise ValueError("csv_file_path is required")
        return CsvFilePowerMeter(csv_path=m.csv_file_path.strip())

    if t == "csv_process":
        if not m.csv_process_command.strip():
            raise ValueError("csv_process_command is required")
        if not m.csv_process_csv_path.strip():
            raise ValueError("csv_process_csv_path is required")
        return CsvProcessPowerMeter(
            command=m.csv_process_command.strip().split(),
            csv_path=m.csv_process_csv_path.strip(),
        )

    raise ValueError(f"Unknown power_meter_type: {t}")


def _build_recorders(m: GuiModel):
    recs = []

    if m.enable_hackrf:
        baseband = m.hackrf_baseband_filter_hz.strip()
        lna = m.hackrf_lna_gain_db.strip()
        vga = m.hackrf_vga_gain_db.strip()
        recs.append(
            HackRfIqRecorder(
                name="hackrf",
                tool_path=m.hackrf_tool.strip() or "hackrf_transfer",
                freq_hz=_safe_int(m.hackrf_freq_hz, 2402000000),
                sample_rate_hz=_safe_int(m.hackrf_sample_rate_hz, 10000000),
                baseband_filter_hz=_safe_int(baseband, 0) if baseband else None,
                lna_gain_db=_safe_int(lna, 0) if lna else None,
                vga_gain_db=_safe_int(vga, 0) if vga else None,
                amp_enable=bool(m.hackrf_amp_enable),
                device_serial=m.hackrf_device_serial.strip() or None,
                skip_if_missing=True,
            )
        )

    if m.enable_webcam:
        recs.append(
            FfmpegWebcamRecorder(
                name="webcam",
                ffmpeg_path=m.webcam_ffmpeg.strip() or "ffmpeg",
                input_device=m.webcam_input_device.strip() or None,
                skip_if_missing=True,
            )
        )

    if m.enable_process:
        if not m.process_command.strip():
            raise ValueError("process_command is required when process recorder is enabled")
        recs.append(
            ProcessRecorder(
                name=m.process_name.strip() or "process",
                command=m.process_command.strip().split(),
                skip_if_missing=False,
            )
        )

    return recs


def _validate_tools(m: GuiModel) -> list[str]:
    missing = []
    if m.enable_hackrf and shutil.which(m.hackrf_tool.strip() or "hackrf_transfer") is None:
        missing.append("hackrf_transfer")
    if m.enable_webcam and shutil.which(m.webcam_ffmpeg.strip() or "ffmpeg") is None:
        missing.append("ffmpeg")
    return missing


def _run_quick_test(m: GuiModel, log: ui.log, set_artifacts_cb) -> None:
    missing = _validate_tools(m)
    if missing:
        ui.notify("Missing tools: " + ", ".join(missing), type="warning")

    meter = _build_meter(m)
    recorders = _build_recorders(m)

    def _noop(ctx):
        return

    test = PowerTest(
        name="gui_run",
        description="Run from NiceGUI control GUI",
        steps=[TestStep(name="capture", duration_s=0.5, action=_noop)],
    )

    def _post_run(ctx):
        if not m.enable_webcam:
            return

        rec = ctx.recorder_outputs.get("webcam")
        if not isinstance(rec, dict) or rec.get("skipped") is True:
            if m.enable_vision:
                ctx.mark("vision_skipped", reason="webcam_recorder_skipped")
            if m.enable_object_detect:
                ctx.mark("object_detect_skipped", reason="webcam_recorder_skipped")
            return

        video = rec.get("video")
        if not video:
            if m.enable_vision:
                ctx.mark("vision_skipped", reason="no_video_path")
            if m.enable_object_detect:
                ctx.mark("object_detect_skipped", reason="no_video_path")
            return

        if m.enable_vision:
            cfg = VisionChangeConfig(
                ffmpeg_path=m.webcam_ffmpeg.strip() or "ffmpeg",
                fps=_safe_float(m.vision_fps, 2.0),
                scale_width=_safe_int(m.vision_scale_width, 160),
                mode=m.vision_mode.strip() or "display_change",
                blink_brightness_delta=_safe_float(m.vision_blink_delta, 25.0),
                display_change_delta=_safe_float(m.vision_display_delta, 12.0),
            )
            summary = analyze_video_changes(artifacts_root=ctx.artifacts.root_dir, video_path=video, cfg=cfg, extra={"recorder": "webcam"})
            ctx.mark("vision_summary", **{k: v for k, v in summary.items() if k in {"mode", "events", "frames_analyzed"}})

        if m.enable_object_detect:
            cfg = ObjectDetectConfig(
                ffmpeg_path=m.webcam_ffmpeg.strip() or "ffmpeg",
                fps=_safe_float(m.object_fps, 1.0),
                scale_width=_safe_int(m.object_scale_width, 320),
                model=m.object_model.strip() or "yolov8n.pt",
                conf=_safe_float(m.object_conf, 0.25),
                bootstrap_ml=bool(m.object_bootstrap_ml),
            )
            summary = analyze_video_objects(artifacts_root=ctx.artifacts.root_dir, video_path=video, cfg=cfg, extra={"recorder": "webcam"})
            if summary.get("skipped"):
                ctx.mark("object_detect_skipped", reason=summary.get("reason"))
            else:
                ctx.mark(
                    "object_detect_summary",
                    frames_analyzed=summary.get("frames_analyzed"),
                    detections=summary.get("detections"),
                    top_labels=summary.get("top_labels"),
                )

    runner = PowerTestRunner(artifacts_root=m.artifacts_root.strip() or str(_default_repo_root() / "artifacts"))
    artifacts = runner.run(test=test, instruments={"power_meter": meter}, recorders=recorders, post_run=_post_run)

    cfg_out = {
        "power_meter_type": m.power_meter_type,
        "recorders": [r.__class__.__name__ for r in recorders],
        "vision": {"enable": m.enable_vision, "mode": m.vision_mode} if m.enable_webcam else {"enable": False},
        "object_detect": {"enable": m.enable_object_detect, "model": m.object_model} if m.enable_webcam else {"enable": False},
    }
    (pathlib.Path(artifacts.root_dir) / "gui_config.json").write_text(json.dumps(cfg_out, indent=2), encoding="utf-8")

    set_artifacts_cb(str(artifacts.root_dir))


def _run_profile(m: GuiModel, log: ui.log) -> None:
    profile = m.profile_path.strip()
    if not profile:
        raise ValueError("Profile path is empty")

    repo_root = _default_repo_root()

    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "power_tests" / "run_profile.py"),
        "run",
        profile,
        f"--repo-root={repo_root}",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        log.push(proc.stdout.rstrip())
    if proc.stderr:
        log.push(proc.stderr.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"FAILED rc={proc.returncode}")


def _comfortable_input(label: str, value: str, on_change) -> ui.input:
    with ui.column().classes("w-full gap-1"):
        ui.label(label).classes("text-sm text-gray-600")
        return ui.input(value=value, on_change=on_change).classes("w-full")


def _comfortable_checkbox(label: str, value: bool, on_change) -> ui.checkbox:
    return ui.checkbox(label, value=value, on_change=on_change).props("dense")


def main() -> None:
    port = _safe_int(os.environ.get("PYONTRUST_GUI_PORT", "8080"), 8080)

    def _root() -> None:
        ui.page_title("Pyontrust GUI")

        last_artifacts = {"path": ""}

        def set_last_artifacts(path: str) -> None:
            last_artifacts["path"] = path
            artifacts_label.set_text(path)

        with ui.header().classes("items-center justify-between"):
            ui.label("Pyontrust GUI").classes("text-h6")
            with ui.row().classes("gap-2"):
                ui.button("Validate tools", on_click=lambda: ui.notify(", ".join(_validate_tools(MODEL)) or "OK")).props("outline")

                def _run_quick_clicked() -> None:
                    run_button.disable()
                    log.push("Starting quick test...")

                    def _worker() -> None:
                        try:
                            _run_quick_test(MODEL, log, set_last_artifacts)
                            ui.notify("Run completed", type="positive")
                            log.push("OK")
                        except Exception as exc:  # noqa: BLE001
                            ui.notify(repr(exc), type="negative")
                            log.push(repr(exc))
                        finally:
                            run_button.enable()

                    threading.Thread(target=_worker, daemon=True).start()

                run_button = ui.button("Run quick test", on_click=_run_quick_clicked).props("color=primary")

        with ui.left_drawer().props("width=420").classes("p-4"):
            with ui.column().classes("w-full gap-4"):
                ui.label("Artifacts").classes("text-subtitle2")
                _comfortable_input("Artifacts root", MODEL.artifacts_root, lambda e: setattr(MODEL, "artifacts_root", e.value))

                ui.separator()
                ui.label("Power Meter").classes("text-subtitle2")

                def _set_meter_type(e):
                    MODEL.power_meter_type = e.value
                    meter_panel.refresh()

                ui.select(["simulated", "ad3_dwf", "csv_file", "csv_process"], value=MODEL.power_meter_type, on_change=_set_meter_type).classes("w-full")

                @ui.refreshable
                def meter_panel() -> None:
                    t = MODEL.power_meter_type
                    if t == "simulated":
                        _comfortable_input("Sample rate (Hz)", MODEL.sim_sample_rate_hz, lambda e: setattr(MODEL, "sim_sample_rate_hz", e.value))
                        _comfortable_input("Voltage (V)", MODEL.sim_voltage_v, lambda e: setattr(MODEL, "sim_voltage_v", e.value))
                    elif t == "ad3_dwf":
                        _comfortable_input("Sample rate (Hz)", MODEL.ad3_sample_rate_hz, lambda e: setattr(MODEL, "ad3_sample_rate_hz", e.value))
                        _comfortable_input("Device index", MODEL.ad3_device_index, lambda e: setattr(MODEL, "ad3_device_index", e.value))
                        _comfortable_input("Current channel", MODEL.ad3_current_channel, lambda e: setattr(MODEL, "ad3_current_channel", e.value))
                        _comfortable_input("Voltage channel", MODEL.ad3_voltage_channel, lambda e: setattr(MODEL, "ad3_voltage_channel", e.value))
                        _comfortable_input("Current A/V", MODEL.ad3_current_a_per_v, lambda e: setattr(MODEL, "ad3_current_a_per_v", e.value))
                        _comfortable_input("Voltage V/V", MODEL.ad3_voltage_v_per_v, lambda e: setattr(MODEL, "ad3_voltage_v_per_v", e.value))
                        _comfortable_input("Current offset (V)", MODEL.ad3_current_offset_v, lambda e: setattr(MODEL, "ad3_current_offset_v", e.value))
                        _comfortable_input("Voltage offset (V)", MODEL.ad3_voltage_offset_v, lambda e: setattr(MODEL, "ad3_voltage_offset_v", e.value))
                    elif t == "csv_file":
                        _comfortable_input("CSV path", MODEL.csv_file_path, lambda e: setattr(MODEL, "csv_file_path", e.value))
                    else:
                        _comfortable_input("Command", MODEL.csv_process_command, lambda e: setattr(MODEL, "csv_process_command", e.value))
                        _comfortable_input("CSV output path", MODEL.csv_process_csv_path, lambda e: setattr(MODEL, "csv_process_csv_path", e.value))

                meter_panel()

                ui.separator()
                ui.label("Recorders").classes("text-subtitle2")

                def _set_enable_hackrf(e):
                    MODEL.enable_hackrf = bool(e.value)
                    recorder_panel.refresh()

                def _set_enable_webcam(e):
                    MODEL.enable_webcam = bool(e.value)
                    recorder_panel.refresh()

                def _set_enable_process(e):
                    MODEL.enable_process = bool(e.value)
                    recorder_panel.refresh()

                _comfortable_checkbox("HackRF IQ", MODEL.enable_hackrf, _set_enable_hackrf)
                _comfortable_checkbox("Webcam (ffmpeg)", MODEL.enable_webcam, _set_enable_webcam)
                _comfortable_checkbox("Process", MODEL.enable_process, _set_enable_process)

                @ui.refreshable
                def recorder_panel() -> None:
                    if MODEL.enable_hackrf:
                        _comfortable_input("Tool", MODEL.hackrf_tool, lambda e: setattr(MODEL, "hackrf_tool", e.value))
                        _comfortable_input("Freq (Hz)", MODEL.hackrf_freq_hz, lambda e: setattr(MODEL, "hackrf_freq_hz", e.value))
                        _comfortable_input("Sample rate (Hz)", MODEL.hackrf_sample_rate_hz, lambda e: setattr(MODEL, "hackrf_sample_rate_hz", e.value))
                        _comfortable_input("Baseband filter (Hz)", MODEL.hackrf_baseband_filter_hz, lambda e: setattr(MODEL, "hackrf_baseband_filter_hz", e.value))
                        _comfortable_input("LNA gain (dB)", MODEL.hackrf_lna_gain_db, lambda e: setattr(MODEL, "hackrf_lna_gain_db", e.value))
                        _comfortable_input("VGA gain (dB)", MODEL.hackrf_vga_gain_db, lambda e: setattr(MODEL, "hackrf_vga_gain_db", e.value))
                        _comfortable_checkbox("AMP enable", MODEL.hackrf_amp_enable, lambda e: setattr(MODEL, "hackrf_amp_enable", bool(e.value)))
                        _comfortable_input("Device serial (opt)", MODEL.hackrf_device_serial, lambda e: setattr(MODEL, "hackrf_device_serial", e.value))
                        ui.separator()

                    if MODEL.enable_webcam:
                        _comfortable_input("ffmpeg", MODEL.webcam_ffmpeg, lambda e: setattr(MODEL, "webcam_ffmpeg", e.value))
                        _comfortable_input("Input device", MODEL.webcam_input_device, lambda e: setattr(MODEL, "webcam_input_device", e.value))
                        ui.label("Windows: DirectShow camera name. Linux: /dev/video0").classes("text-xs text-gray-500")

                        ui.separator()
                        _comfortable_checkbox("Enable change logging", MODEL.enable_vision, lambda e: setattr(MODEL, "enable_vision", bool(e.value)))
                        if MODEL.enable_vision:
                            ui.select(["display_change", "blink"], value=MODEL.vision_mode, on_change=lambda e: setattr(MODEL, "vision_mode", e.value)).classes("w-full")
                            _comfortable_input("Analyze FPS", MODEL.vision_fps, lambda e: setattr(MODEL, "vision_fps", e.value))
                            _comfortable_input("Scale width", MODEL.vision_scale_width, lambda e: setattr(MODEL, "vision_scale_width", e.value))
                            if MODEL.vision_mode == "blink":
                                _comfortable_input("Blink delta threshold", MODEL.vision_blink_delta, lambda e: setattr(MODEL, "vision_blink_delta", e.value))
                            else:
                                _comfortable_input("Change delta threshold", MODEL.vision_display_delta, lambda e: setattr(MODEL, "vision_display_delta", e.value))

                        ui.separator()
                        _comfortable_checkbox("Enable object detection", MODEL.enable_object_detect, lambda e: setattr(MODEL, "enable_object_detect", bool(e.value)))
                        if MODEL.enable_object_detect:
                            _comfortable_input("Model", MODEL.object_model, lambda e: setattr(MODEL, "object_model", e.value))
                            _comfortable_input("Confidence", MODEL.object_conf, lambda e: setattr(MODEL, "object_conf", e.value))
                            _comfortable_input("Analyze FPS", MODEL.object_fps, lambda e: setattr(MODEL, "object_fps", e.value))
                            _comfortable_input("Scale width", MODEL.object_scale_width, lambda e: setattr(MODEL, "object_scale_width", e.value))
                            _comfortable_checkbox("Bootstrap ML deps (venv only)", MODEL.object_bootstrap_ml, lambda e: setattr(MODEL, "object_bootstrap_ml", bool(e.value)))

                        ui.separator()

                    if MODEL.enable_process:
                        _comfortable_input("Name", MODEL.process_name, lambda e: setattr(MODEL, "process_name", e.value))
                        _comfortable_input("Command", MODEL.process_command, lambda e: setattr(MODEL, "process_command", e.value))

                recorder_panel()

        with ui.column().classes("p-4 gap-4"):
            with ui.tabs().classes("w-full") as tabs:
                ui.tab("Instrument Control")
                ui.tab("Profile Runner")
                ui.tab("Orchestrator")
                ui.tab("SDR")
                ui.tab("GNU Radio")
                ui.tab("Waveforms")
                ui.tab("CSV Plotter")

            with ui.tab_panels(tabs, value="Instrument Control").classes("w-full"):
                with ui.tab_panel("Instrument Control"):
                    with ui.card().classes("w-full"):
                        ui.label("Output").classes("text-subtitle2")
                        log = ui.log(max_lines=500).classes("w-full")
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Last artifacts:").classes("text-sm text-gray-600")
                            artifacts_label = ui.label("(none)").classes("text-sm")
                            ui.button("Open", on_click=lambda: _open_folder(last_artifacts["path"]) if last_artifacts["path"] else None).props("outline")

                with ui.tab_panel("Profile Runner"):
                    with ui.card().classes("w-full"):
                        ui.label("Run a profile JSON").classes("text-subtitle2")
                        _comfortable_input("Profile JSON path", MODEL.profile_path, lambda e: setattr(MODEL, "profile_path", e.value))

                        def _profile_clicked() -> None:
                            profile_button.disable()
                            log.push("Running profile...")

                            def _worker() -> None:
                                try:
                                    _run_profile(MODEL, log)
                                    ui.notify("Profile run OK", type="positive")
                                    log.push("OK")
                                except Exception as exc:  # noqa: BLE001
                                    ui.notify(repr(exc), type="negative")
                                    log.push(repr(exc))
                                finally:
                                    profile_button.enable()

                            threading.Thread(target=_worker, daemon=True).start()

                        profile_button = ui.button("Run profile", on_click=_profile_clicked).props("color=primary")
                        ui.button("Clear log", on_click=lambda: log.clear()).props("outline")

                with ui.tab_panel("Orchestrator"):
                    try:
                        from pyontrust_gui.orchestrator import mount as _mount_orchestrator
                        _mount_orchestrator(ui.column().classes("w-full"))
                    except Exception as exc:  # noqa: BLE001
                        ui.label("Lab Bench Orchestrator").classes("text-subtitle2")
                        ui.label("Failed to load orchestrator module").classes("text-sm text-gray-600")
                        ui.label(repr(exc)).classes("text-xs text-gray-500")

                with ui.tab_panel("SDR"):
                    with ui.card().classes("w-full"):
                        ui.label("SDR Flowgraph").classes("text-subtitle2")

                        try:
                            from pyontrust_sdr import SdrModule  # type: ignore

                            SdrModule.mount(ui.column().classes("w-full"), config=None)
                        except Exception as exc:  # noqa: BLE001
                            ui.label("Optional module not installed: pyontrust_sdr").classes("text-sm text-gray-600")
                            ui.label(repr(exc)).classes("text-xs text-gray-500")
                            ui.label("Install (dev):").classes("text-sm")
                            ui.code(
                                "Set-Location C:\\GIT\\pyontrust\n"
                                "# Use the Python you run pyontrust_gui with:\n"
                                "python -m pip install -e sdr_module\n"
                                "\n"
                                "# Or create a dedicated venv:\n"
                                "python -m venv .venv-nicegui\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -U pip\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -r scripts\\requirements.txt\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -e sdr_module\n"
                            ).classes("w-full")

                with ui.tab_panel("GNU Radio"):
                    with ui.card().classes("w-full"):
                        ui.label("GNU Radio").classes("text-subtitle2")

                        try:
                            from pyontrust_gnuradio import GnuradioModule  # type: ignore

                            GnuradioModule.mount(ui.column().classes("w-full"), config=None)
                        except Exception as exc:  # noqa: BLE001
                            ui.label("Optional module not installed: pyontrust_gnuradio").classes("text-sm text-gray-600")
                            ui.label(repr(exc)).classes("text-xs text-gray-500")

                            ui.label("Install (dev):").classes("text-sm")
                            ui.code(
                                "Set-Location C:\\GIT\\pyontrust\n"
                                "# Use the Python you run pyontrust_gui with:\n"
                                "python -m pip install -e gnuradio_module\n"
                                "\n"
                                "# Or create a dedicated venv:\n"
                                "python -m venv .venv-nicegui\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -U pip\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -r scripts\\requirements.txt\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -e gnuradio_module\n"
                            ).classes("w-full")

                            ui.separator()
                            ui.label("Windows recommendation: install GNU Radio via Conda/Mamba (not pip).").classes(
                                "text-sm"
                            )
                            ui.label("Example (PowerShell):").classes("text-sm")
                            ui.code(
                                "# 1) Install Miniforge/Mambaforge first\n"
                                "# 2) Create an env with GNU Radio\n"
                                "conda create -n gnuradio -c conda-forge python=3.11 gnuradio\n"
                                "conda activate gnuradio\n"
                                "python -c \"from gnuradio import gr; print('GNU Radio OK')\"\n"
                            ).classes("w-full")

                with ui.tab_panel("Waveforms"):
                    with ui.card().classes("w-full"):
                        ui.label("Waveforms Module").classes("text-subtitle2")

                        try:
                            from pyontrust_waveforms import WaveformsConfig, WaveformsModule  # type: ignore

                            WaveformsModule.mount(ui.column().classes("w-full"), config=WaveformsConfig())
                        except Exception as exc:  # noqa: BLE001
                            ui.label("Optional module not installed: pyontrust_waveforms").classes("text-sm text-gray-600")
                            ui.label(repr(exc)).classes("text-xs text-gray-500")
                            ui.label("Install (dev):").classes("text-sm")
                            ui.code(
                                "Set-Location C:\\GIT\\pyontrust\n"
                                "# Use the Python you run pyontrust_gui with:\n"
                                "python -m pip install -e waveforms_module\n"
                                "\n"
                                "# Or create a dedicated venv:\n"
                                "python -m venv .venv-nicegui\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -U pip\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -r scripts\\requirements.txt\n"
                                ".\\.venv-nicegui\\Scripts\\python -m pip install -e waveforms_module\n"
                            ).classes("w-full")

                with ui.tab_panel("CSV Plotter"):
                    with ui.card().classes("w-full"):
                        ui.label("CSV Plotter").classes("text-subtitle2")

                        # Embed the CSV plotter without installing it as a package.
                        try:
                            repo_root = _default_repo_root()
                            csv_root = repo_root / "gui_app" / "csv_plotter"
                            if not csv_root.exists():
                                raise FileNotFoundError(str(csv_root))

                            # Temporarily expose csv_plotter's internal package name `app`.
                            sys.path.insert(0, str(csv_root))
                            try:
                                from app.embed import mount as _mount_csv  # type: ignore
                            finally:
                                # avoid repeated duplicates; keep import cache loaded
                                if str(csv_root) in sys.path:
                                    sys.path.remove(str(csv_root))

                            _mount_csv(ui.column().classes("w-full"))
                        except Exception as exc:  # noqa: BLE001
                            ui.label("CSV Plotter embed failed").classes("text-sm text-gray-600")
                            ui.label(repr(exc)).classes("text-xs text-gray-500")
                            ui.label("Standalone run:").classes("text-sm")
                            ui.code(
                                "Set-Location C:\\GIT\\pyontrust\n"
                                ".\\.venv-nicegui\\Scripts\\python gui_app\\csv_plotter\\nicegui_csv_plotter.py\n"
                            ).classes("w-full")

    ui.run(title="Pyontrust GUI", native=True, reload=False, port=port, root=_root)


if __name__ == "__main__":
    main()
