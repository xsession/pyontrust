from __future__ import annotations

import json
import pathlib
import shutil
import sys
from dataclasses import dataclass
from typing import Optional

import reflex as rx

# Make `pyontrust_packages/` importable when running from this app folder.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

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
class RunResult:
    ok: bool
    artifacts_dir: Optional[str] = None
    error: Optional[str] = None


class AppState(rx.State):
    # Common
    artifacts_root: str = str(REPO_ROOT / "artifacts")

    # Power meter selection
    power_meter_type: str = "simulated"  # simulated | ad3_dwf | csv_file | csv_process

    # Simulated
    sim_sample_rate_hz: str = "200"
    sim_voltage_v: str = "3.0"

    # AD3/DWF
    ad3_sample_rate_hz: str = "1000"
    ad3_device_index: str = "-1"
    ad3_current_channel: str = "0"
    ad3_voltage_channel: str = "1"
    ad3_current_a_per_v: str = "1.0"
    ad3_voltage_v_per_v: str = "1.0"
    ad3_current_offset_v: str = "0.0"
    ad3_voltage_offset_v: str = "0.0"

    # CSV file
    csv_file_path: str = ""

    # CSV process
    csv_process_command: str = ""  # space-separated
    csv_process_csv_path: str = ""

    # Optional recorders
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
    webcam_input_device: str = ""  # Windows: dshow name; Linux: /dev/video0

    # Optional vision analysis (webcam)
    enable_vision: bool = False
    vision_mode: str = "display_change"  # display_change | blink
    vision_fps: str = "2"
    vision_scale_width: str = "160"
    vision_blink_delta: str = "25"
    vision_display_delta: str = "12"

    # Optional object detection (webcam)
    enable_object_detect: bool = False
    object_bootstrap_ml: bool = True
    object_model: str = "yolov8n.pt"
    object_conf: str = "0.25"
    object_fps: str = "1"
    object_scale_width: str = "320"

    enable_process: bool = False
    process_name: str = "process"
    process_command: str = ""  # space-separated

    # Output
    last_run_ok: bool = False
    last_artifacts_dir: str = ""
    last_error: str = ""

    def _build_meter(self):
        t = self.power_meter_type
        if t == "simulated":
            return SimulatedPowerMeter(
                sample_rate_hz=_safe_float(self.sim_sample_rate_hz, 200.0),
                voltage_v=_safe_float(self.sim_voltage_v, 3.0),
            )

        if t == "ad3_dwf":
            return Ad3DwfPowerMeter(
                sample_rate_hz=_safe_float(self.ad3_sample_rate_hz, 1000.0),
                device_index=_safe_int(self.ad3_device_index, -1),
                current_channel=_safe_int(self.ad3_current_channel, 0),
                voltage_channel=_safe_int(self.ad3_voltage_channel, 1),
                current_a_per_v=_safe_float(self.ad3_current_a_per_v, 1.0),
                voltage_v_per_v=_safe_float(self.ad3_voltage_v_per_v, 1.0),
                current_offset_v=_safe_float(self.ad3_current_offset_v, 0.0),
                voltage_offset_v=_safe_float(self.ad3_voltage_offset_v, 0.0),
            )

        if t == "csv_file":
            if not self.csv_file_path.strip():
                raise ValueError("csv_file_path is required")
            return CsvFilePowerMeter(csv_path=self.csv_file_path.strip())

        if t == "csv_process":
            if not self.csv_process_command.strip():
                raise ValueError("csv_process_command is required")
            if not self.csv_process_csv_path.strip():
                raise ValueError("csv_process_csv_path is required")
            return CsvProcessPowerMeter(
                command=self.csv_process_command.strip().split(),
                csv_path=self.csv_process_csv_path.strip(),
            )

        raise ValueError(f"Unknown power_meter_type: {t}")

    def _build_recorders(self):
        recs = []

        if self.enable_hackrf:
            baseband = self.hackrf_baseband_filter_hz.strip()
            lna = self.hackrf_lna_gain_db.strip()
            vga = self.hackrf_vga_gain_db.strip()
            recs.append(
                HackRfIqRecorder(
                    name="hackrf",
                    tool_path=self.hackrf_tool.strip() or "hackrf_transfer",
                    freq_hz=_safe_int(self.hackrf_freq_hz, 2402000000),
                    sample_rate_hz=_safe_int(self.hackrf_sample_rate_hz, 10000000),
                    baseband_filter_hz=_safe_int(baseband, 0) if baseband else None,
                    lna_gain_db=_safe_int(lna, 0) if lna else None,
                    vga_gain_db=_safe_int(vga, 0) if vga else None,
                    amp_enable=bool(self.hackrf_amp_enable),
                    device_serial=self.hackrf_device_serial.strip() or None,
                    skip_if_missing=True,
                )
            )

        if self.enable_webcam:
            recs.append(
                FfmpegWebcamRecorder(
                    name="webcam",
                    ffmpeg_path=self.webcam_ffmpeg.strip() or "ffmpeg",
                    input_device=self.webcam_input_device.strip() or None,
                    skip_if_missing=True,
                )
            )

        if self.enable_process:
            if not self.process_command.strip():
                raise ValueError("process_command is required when process recorder is enabled")
            recs.append(
                ProcessRecorder(
                    name=self.process_name.strip() or "process",
                    command=self.process_command.strip().split(),
                    skip_if_missing=False,
                )
            )

        return recs

    def validate_tools(self):
        missing = []
        if self.enable_hackrf and shutil.which(self.hackrf_tool.strip() or "hackrf_transfer") is None:
            missing.append("hackrf_transfer")
        if self.enable_webcam and shutil.which(self.webcam_ffmpeg.strip() or "ffmpeg") is None:
            missing.append("ffmpeg")
        if missing:
            self.last_run_ok = False
            self.last_error = "Missing tools: " + ", ".join(missing)
        else:
            self.last_error = ""

    def run_quick_test(self):
        self.last_error = ""
        self.last_artifacts_dir = ""
        self.last_run_ok = False

        try:
            meter = self._build_meter()
            recorders = self._build_recorders()

            # Minimal, deterministic-ish test.
            def _noop(ctx):
                return

            test = PowerTest(
                name="gui_run",
                description="Run from Reflex control GUI",
                steps=[TestStep(name="capture", duration_s=0.5, action=_noop)],
            )

            def _post_run(ctx):
                if not self.enable_webcam:
                    return

                # Webcam recorder name is fixed to "webcam" in this GUI.
                rec = ctx.recorder_outputs.get("webcam")
                if not isinstance(rec, dict) or rec.get("skipped") is True:
                    if self.enable_vision:
                        ctx.mark("vision_skipped", reason="webcam_recorder_skipped")
                    if self.enable_object_detect:
                        ctx.mark("object_detect_skipped", reason="webcam_recorder_skipped")
                    return
                video = rec.get("video")
                if not video:
                    if self.enable_vision:
                        ctx.mark("vision_skipped", reason="no_video_path")
                    if self.enable_object_detect:
                        ctx.mark("object_detect_skipped", reason="no_video_path")
                    return

                if self.enable_vision:
                    cfg = VisionChangeConfig(
                        ffmpeg_path=self.webcam_ffmpeg.strip() or "ffmpeg",
                        fps=_safe_float(self.vision_fps, 2.0),
                        scale_width=_safe_int(self.vision_scale_width, 160),
                        mode=self.vision_mode.strip() or "display_change",
                        blink_brightness_delta=_safe_float(self.vision_blink_delta, 25.0),
                        display_change_delta=_safe_float(self.vision_display_delta, 12.0),
                    )

                    summary = analyze_video_changes(
                        artifacts_root=ctx.artifacts.root_dir,
                        video_path=video,
                        cfg=cfg,
                        extra={"recorder": "webcam"},
                    )
                    ctx.mark(
                        "vision_summary",
                        **{k: v for k, v in summary.items() if k in {"mode", "events", "frames_analyzed"}},
                    )

                if self.enable_object_detect:
                    cfg = ObjectDetectConfig(
                        ffmpeg_path=self.webcam_ffmpeg.strip() or "ffmpeg",
                        fps=_safe_float(self.object_fps, 1.0),
                        scale_width=_safe_int(self.object_scale_width, 320),
                        model=self.object_model.strip() or "yolov8n.pt",
                        conf=_safe_float(self.object_conf, 0.25),
                        bootstrap_ml=bool(self.object_bootstrap_ml),
                    )

                    summary = analyze_video_objects(
                        artifacts_root=ctx.artifacts.root_dir,
                        video_path=video,
                        cfg=cfg,
                        extra={"recorder": "webcam"},
                    )

                    if summary.get("skipped"):
                        ctx.mark("object_detect_skipped", reason=summary.get("reason"))
                    else:
                        top = summary.get("top_labels")
                        ctx.mark(
                            "object_detect_summary",
                            frames_analyzed=summary.get("frames_analyzed"),
                            detections=summary.get("detections"),
                            top_labels=top,
                        )

            runner = PowerTestRunner(artifacts_root=self.artifacts_root.strip() or str(REPO_ROOT / "artifacts"))
            artifacts = runner.run(test=test, instruments={"power_meter": meter}, recorders=recorders, post_run=_post_run)

            self.last_run_ok = True
            self.last_artifacts_dir = str(artifacts.root_dir)

            # Drop a small JSON next to artifacts with the GUI configuration.
            cfg = {
                "power_meter_type": self.power_meter_type,
                "recorders": [r.__class__.__name__ for r in recorders],
            }
            (pathlib.Path(artifacts.root_dir) / "gui_config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.last_run_ok = False
            self.last_error = repr(exc)


def _field(label: str, value: str, on_change):
    return rx.vstack(
        rx.text(label, size="2"),
        rx.input(value=value, on_change=on_change, width="100%"),
        spacing="1",
        width="100%",
    )


def _panel(title: str, body: rx.Component) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(title, size="4"),
                rx.spacer(),
                align="center",
                width="100%",
            ),
            rx.divider(),
            body,
            spacing="3",
            width="100%",
        ),
        border="1px solid var(--gray-a6)",
        border_radius="12px",
        padding="16px",
        width="100%",
    )


def index() -> rx.Component:
    power_meter_panel = _panel(
        "Power Meter",
        rx.vstack(
            rx.select(
                ["simulated", "ad3_dwf", "csv_file", "csv_process"],
                value=AppState.power_meter_type,
                on_change=AppState.set_power_meter_type,
                width="100%",
            ),
            rx.cond(
                AppState.power_meter_type == "simulated",
                rx.vstack(
                    _field("Sample rate (Hz)", AppState.sim_sample_rate_hz, AppState.set_sim_sample_rate_hz),
                    _field("Voltage (V)", AppState.sim_voltage_v, AppState.set_sim_voltage_v),
                    spacing="3",
                    width="100%",
                ),
                rx.box(),
            ),
            rx.cond(
                AppState.power_meter_type == "ad3_dwf",
                rx.vstack(
                    _field("Sample rate (Hz)", AppState.ad3_sample_rate_hz, AppState.set_ad3_sample_rate_hz),
                    _field("Device index", AppState.ad3_device_index, AppState.set_ad3_device_index),
                    rx.hstack(
                        rx.box(
                            _field("Current channel", AppState.ad3_current_channel, AppState.set_ad3_current_channel),
                            width="100%",
                        ),
                        rx.box(
                            _field("Voltage channel", AppState.ad3_voltage_channel, AppState.set_ad3_voltage_channel),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.box(_field("Current A/V", AppState.ad3_current_a_per_v, AppState.set_ad3_current_a_per_v), width="100%"),
                        rx.box(_field("Voltage V/V", AppState.ad3_voltage_v_per_v, AppState.set_ad3_voltage_v_per_v), width="100%"),
                        spacing="3",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.box(
                            _field("Current offset (V)", AppState.ad3_current_offset_v, AppState.set_ad3_current_offset_v),
                            width="100%",
                        ),
                        rx.box(
                            _field("Voltage offset (V)", AppState.ad3_voltage_offset_v, AppState.set_ad3_voltage_offset_v),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.box(),
            ),
            rx.cond(
                AppState.power_meter_type == "csv_file",
                rx.vstack(
                    _field("CSV path", AppState.csv_file_path, AppState.set_csv_file_path),
                    spacing="3",
                    width="100%",
                ),
                rx.box(),
            ),
            rx.cond(
                AppState.power_meter_type == "csv_process",
                rx.vstack(
                    _field("Command", AppState.csv_process_command, AppState.set_csv_process_command),
                    _field("CSV output path", AppState.csv_process_csv_path, AppState.set_csv_process_csv_path),
                    spacing="3",
                    width="100%",
                ),
                rx.box(),
            ),
            spacing="3",
            width="100%",
        ),
    )

    recorders_panel = _panel(
        "Recorders",
        rx.vstack(
            rx.vstack(
                rx.checkbox("HackRF IQ", is_checked=AppState.enable_hackrf, on_change=AppState.set_enable_hackrf),
                rx.cond(
                    AppState.enable_hackrf,
                    rx.vstack(
                        _field("Tool", AppState.hackrf_tool, AppState.set_hackrf_tool),
                        _field("Freq (Hz)", AppState.hackrf_freq_hz, AppState.set_hackrf_freq_hz),
                        _field("Sample rate (Hz)", AppState.hackrf_sample_rate_hz, AppState.set_hackrf_sample_rate_hz),
                        rx.hstack(
                            rx.box(
                                _field(
                                    "Baseband filter (Hz)",
                                    AppState.hackrf_baseband_filter_hz,
                                    AppState.set_hackrf_baseband_filter_hz,
                                ),
                                width="100%",
                            ),
                            rx.box(
                                _field("LNA gain (dB)", AppState.hackrf_lna_gain_db, AppState.set_hackrf_lna_gain_db),
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.box(
                                _field("VGA gain (dB)", AppState.hackrf_vga_gain_db, AppState.set_hackrf_vga_gain_db),
                                width="100%",
                            ),
                            rx.box(
                                _field(
                                    "Device serial (opt)",
                                    AppState.hackrf_device_serial,
                                    AppState.set_hackrf_device_serial,
                                ),
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        rx.checkbox(
                            "AMP enable",
                            is_checked=AppState.hackrf_amp_enable,
                            on_change=AppState.set_hackrf_amp_enable,
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.box(),
                ),
                spacing="2",
                width="100%",
            ),
            rx.divider(),
            rx.vstack(
                rx.checkbox("Webcam (ffmpeg)", is_checked=AppState.enable_webcam, on_change=AppState.set_enable_webcam),
                rx.cond(
                    AppState.enable_webcam,
                    rx.vstack(
                        _field("ffmpeg", AppState.webcam_ffmpeg, AppState.set_webcam_ffmpeg),
                        _field("Input device", AppState.webcam_input_device, AppState.set_webcam_input_device),
                        rx.text("Windows: DirectShow camera name. Linux: /dev/video0", size="2"),
                        rx.divider(),
                        rx.checkbox(
                            "Enable vision change logging",
                            is_checked=AppState.enable_vision,
                            on_change=AppState.set_enable_vision,
                        ),
                        rx.cond(
                            AppState.enable_vision,
                            rx.vstack(
                                rx.select(
                                    ["display_change", "blink"],
                                    value=AppState.vision_mode,
                                    on_change=AppState.set_vision_mode,
                                    width="100%",
                                ),
                                rx.hstack(
                                    rx.box(_field("Analyze FPS", AppState.vision_fps, AppState.set_vision_fps), width="100%"),
                                    rx.box(
                                        _field("Scale width", AppState.vision_scale_width, AppState.set_vision_scale_width),
                                        width="100%",
                                    ),
                                    spacing="3",
                                    width="100%",
                                ),
                                rx.cond(
                                    AppState.vision_mode == "blink",
                                    _field(
                                        "Blink delta threshold",
                                        AppState.vision_blink_delta,
                                        AppState.set_vision_blink_delta,
                                    ),
                                    _field(
                                        "Change delta threshold",
                                        AppState.vision_display_delta,
                                        AppState.set_vision_display_delta,
                                    ),
                                ),
                                rx.text(
                                    "Writes vision_events.jsonl and vision_summary.json into the run artifacts.",
                                    size="2",
                                ),
                                spacing="3",
                                width="100%",
                            ),
                            rx.box(),
                        ),
                        rx.divider(),
                        rx.checkbox(
                            "Enable object detection (labels)",
                            is_checked=AppState.enable_object_detect,
                            on_change=AppState.set_enable_object_detect,
                        ),
                        rx.cond(
                            AppState.enable_object_detect,
                            rx.vstack(
                                _field("Model", AppState.object_model, AppState.set_object_model),
                                rx.hstack(
                                    rx.box(_field("Confidence", AppState.object_conf, AppState.set_object_conf), width="100%"),
                                    rx.box(_field("Analyze FPS", AppState.object_fps, AppState.set_object_fps), width="100%"),
                                    spacing="3",
                                    width="100%",
                                ),
                                _field("Scale width", AppState.object_scale_width, AppState.set_object_scale_width),
                                rx.checkbox(
                                    "Bootstrap ML deps if missing (venv only)",
                                    is_checked=AppState.object_bootstrap_ml,
                                    on_change=AppState.set_object_bootstrap_ml,
                                ),
                                rx.text(
                                    "Writes object_events.jsonl and object_summary.json into the run artifacts.",
                                    size="2",
                                ),
                                spacing="3",
                                width="100%",
                            ),
                            rx.box(),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.box(),
                ),
                spacing="2",
                width="100%",
            ),
            rx.divider(),
            rx.vstack(
                rx.checkbox("Process", is_checked=AppState.enable_process, on_change=AppState.set_enable_process),
                rx.cond(
                    AppState.enable_process,
                    rx.vstack(
                        _field("Name", AppState.process_name, AppState.set_process_name),
                        _field("Command", AppState.process_command, AppState.set_process_command),
                        spacing="3",
                        width="100%",
                    ),
                    rx.box(),
                ),
                spacing="2",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
    )

    run_panel = _panel(
        "Run Settings",
        rx.vstack(
            _field("Artifacts root", AppState.artifacts_root, AppState.set_artifacts_root),
            rx.text(f"Repo: {REPO_ROOT}", size="2"),
            spacing="2",
            width="100%",
        ),
    )

    status_panel = _panel(
        "Output",
        rx.vstack(
            rx.cond(
                AppState.last_error != "",
                rx.callout(AppState.last_error, icon="triangle_alert", color_scheme="red"),
                rx.box(),
            ),
            rx.cond(
                AppState.last_run_ok,
                rx.callout(
                    rx.vstack(
                        rx.text("Run completed"),
                        rx.text(AppState.last_artifacts_dir, size="2"),
                        spacing="1",
                    ),
                    icon="check",
                    color_scheme="green",
                ),
                rx.box(),
            ),
            rx.box(
                rx.vstack(
                    rx.text("Last artifacts directory", size="2"),
                    rx.text(rx.cond(AppState.last_artifacts_dir != "", AppState.last_artifacts_dir, "(none)"), size="3"),
                    spacing="1",
                ),
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
    )

    top_bar = rx.box(
        rx.hstack(
            rx.vstack(
                rx.heading("Instrument Control", size="6"),
                rx.text("Configure instruments and run a quick capture.", size="2"),
                spacing="1",
            ),
            rx.spacer(),
            rx.hstack(
                rx.button("Validate tools", on_click=AppState.validate_tools),
                rx.button("Run quick test", on_click=AppState.run_quick_test),
                spacing="3",
            ),
            align="center",
            width="100%",
        ),
        border_bottom="1px solid var(--gray-a6)",
        padding="16px",
        width="100%",
    )

    sidebar = rx.vstack(
        power_meter_panel,
        recorders_panel,
        run_panel,
        spacing="3",
        width="420px",
        min_width="360px",
    )

    main = rx.vstack(
        status_panel,
        spacing="3",
        width="100%",
    )

    return rx.box(
        rx.vstack(
            top_bar,
            rx.hstack(
                sidebar,
                main,
                spacing="3",
                align="start",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        padding="20px",
        width="100%",
        max_width="1200px",
        margin_x="auto",
    )


app = rx.App()
app.add_page(index, route="/")
