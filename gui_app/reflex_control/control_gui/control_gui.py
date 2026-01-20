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

    enable_webcam: bool = False
    webcam_ffmpeg: str = "ffmpeg"
    webcam_input_device: str = ""  # Windows: dshow name; Linux: /dev/video0

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
            recs.append(
                HackRfIqRecorder(
                    name="hackrf",
                    tool_path=self.hackrf_tool.strip() or "hackrf_transfer",
                    freq_hz=_safe_int(self.hackrf_freq_hz, 2402000000),
                    sample_rate_hz=_safe_int(self.hackrf_sample_rate_hz, 10000000),
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

            runner = PowerTestRunner(artifacts_root=self.artifacts_root.strip() or str(REPO_ROOT / "artifacts"))
            artifacts = runner.run(test=test, instruments={"power_meter": meter}, recorders=recorders)

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
        padding="14px",
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
        padding="14px",
        width="100%",
    )

    sidebar = rx.vstack(
        power_meter_panel,
        recorders_panel,
        run_panel,
        spacing="3",
        width="380px",
        min_width="320px",
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
        padding="16px",
        width="100%",
        max_width="1200px",
        margin_x="auto",
    )


app = rx.App()
app.add_page(index, route="/")
