"""Lab-bench orchestrator / logger GUI.

A NiceGUI-based dashboard for:
- Editing and managing lab bench configurations
- Building and running test profiles
- Live log output with colour-coded verdicts
- Reviewing past test artifacts and pass/fail results

The module exposes a single ``mount(container)`` function so it can be
embedded into the main Pyontrust GUI as a tab panel *or* run standalone.
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import logging
import os
import pathlib
import sys
import textwrap
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from nicegui import ui

# ---------------------------------------------------------------------------
# Path bootstrap – make pyontrust_packages importable regardless of
# installation mode (editable install *or* raw sys.path).
# ---------------------------------------------------------------------------

_HERE = pathlib.Path(__file__).resolve().parent

def _find_repo_root() -> pathlib.Path:
    """Walk upward until we find the ``pyontrust_packages`` directory."""
    for parent in (_HERE, *_HERE.parents):
        if (parent / "pyontrust_packages").is_dir():
            return parent
    return _HERE.parents[4]  # fallback matching existing app.py

REPO_ROOT = _find_repo_root()

_pkg_root = str(REPO_ROOT / "pyontrust_packages")
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from power_test_framework import (  # noqa: E402
    CalibrationData,
    InstrumentConfig,
    LabBench,
    Limit,
    LimitResult,
    PowerTest,
    PowerTestRunner,
    TestArtifacts,
    TestSpec,
    TestVerdict,
    Verdict,
    evaluate,
)
from power_test_framework.profiles import load_profile, run_profile  # noqa: E402

logger = logging.getLogger("pyontrust.orchestrator")

# ── Instrument type metadata ──────────────────────────────────────────────

INSTRUMENT_TYPES: dict[str, dict[str, Any]] = {
    "simulated": {
        "label": "Simulated Power Meter",
        "icon": "science",
        "colour": "blue-grey",
        "params": {
            "sample_rate_hz": {"type": "number", "default": 1000, "unit": "Hz"},
            "voltage_v": {"type": "number", "default": 3.3, "unit": "V"},
        },
    },
    "ad3_dwf": {
        "label": "Analog Discovery 3 (single)",
        "icon": "memory",
        "colour": "deep-purple",
        "params": {
            "sample_rate_hz": {"type": "number", "default": 100000, "unit": "Hz"},
            "device_index": {"type": "number", "default": 0},
            "current_channel": {"type": "number", "default": 0},
            "voltage_channel": {"type": "number", "default": 1},
            "current_a_per_v": {"type": "number", "default": 1.0, "unit": "A/V"},
            "voltage_v_per_v": {"type": "number", "default": 1.0, "unit": "V/V"},
        },
    },
    "ad3_cluster": {
        "label": "AD3 Cluster",
        "icon": "hub",
        "colour": "purple",
        "params": {
            "devices": {"type": "json", "default": "[]"},
            "buffer_size": {"type": "number", "default": 8192},
            "trigger_source": {"type": "text", "default": "none"},
        },
    },
    "ppk2": {
        "label": "Nordic PPK2",
        "icon": "battery_charging_full",
        "colour": "blue",
        "params": {
            "serial_port": {"type": "text", "default": "auto"},
            "mode": {"type": "select", "default": "source", "options": ["source", "ampere"]},
            "source_voltage_mv": {"type": "number", "default": 3300, "unit": "mV"},
            "sample_rate_hz": {"type": "number", "default": 100000, "unit": "Hz"},
        },
    },
    "sk120": {
        "label": "SK120 PSU",
        "icon": "power",
        "colour": "orange",
        "params": {
            "port": {"type": "text", "default": "COM5"},
            "baud": {"type": "number", "default": 9600},
            "voltage_v": {"type": "number", "default": 3.3, "unit": "V"},
            "current_limit_a": {"type": "number", "default": 0.5, "unit": "A"},
            "channel": {"type": "number", "default": 1},
            "output_on": {"type": "bool", "default": True},
        },
    },
    "jlink": {
        "label": "J-Link",
        "icon": "bug_report",
        "colour": "green",
        "params": {
            "device": {"type": "text", "default": "nRF9160_xxAA"},
            "interface": {"type": "select", "default": "swd", "options": ["swd", "jtag"]},
            "speed_khz": {"type": "number", "default": 4000, "unit": "kHz"},
            "serial": {"type": "text", "default": "auto"},
            "jlink_path": {"type": "text", "default": "auto"},
        },
    },
    "hackrf": {
        "label": "HackRF One",
        "icon": "cell_tower",
        "colour": "red",
        "params": {
            "freq_hz": {"type": "number", "default": 2402000000, "unit": "Hz"},
            "sample_rate_hz": {"type": "number", "default": 10000000, "unit": "Hz"},
            "lna_gain_db": {"type": "number", "default": 16, "unit": "dB"},
            "vga_gain_db": {"type": "number", "default": 20, "unit": "dB"},
            "amp_enable": {"type": "bool", "default": False},
            "device_serial": {"type": "text", "default": "auto"},
        },
    },
    "webcam": {
        "label": "Webcam",
        "icon": "videocam",
        "colour": "teal",
        "params": {
            "input_device": {"type": "text", "default": "HD USB Camera"},
            "ffmpeg_path": {"type": "text", "default": "ffmpeg"},
            "framerate": {"type": "number", "default": 30, "unit": "fps"},
            "video_size": {"type": "text", "default": "1280x720"},
        },
    },
    "pcan": {
        "label": "PEAK-CAN",
        "icon": "settings_input_composite",
        "colour": "amber",
        "params": {
            "channel": {"type": "text", "default": "PCAN_USBBUS1"},
            "bitrate": {"type": "number", "default": 500000, "unit": "bps"},
        },
    },
}

ACTION_TYPES = [
    "mark", "set_power_mode", "flash", "reset_target",
    "set_voltage", "enable_output", "snapshot", "rf_sweep", "sleep", "run",
]

# ── Helpers ───────────────────────────────────────────────────────────────

def _safe_float(v: str, fallback: float = 0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return fallback


def _safe_int(v: str, fallback: int = 0) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return fallback


def _ts() -> str:
    return _dt.datetime.now().strftime("%H:%M:%S")


def _default_bench_path() -> pathlib.Path:
    return REPO_ROOT / "scripts" / "power_tests" / "lab_bench.json"


def _default_profile_path() -> pathlib.Path:
    return REPO_ROOT / "scripts" / "power_tests" / "example_full_bench.json"


def _artifacts_root() -> pathlib.Path:
    return REPO_ROOT / "test_artifacts"


def _open_folder(path: str | pathlib.Path | None) -> None:
    if path is None:
        return
    p = pathlib.Path(path)
    if not p.exists():
        ui.notify(f"Path does not exist: {p}", type="warning")
        return
    if sys.platform == "win32":
        os.startfile(str(p))  # noqa: S606
    elif sys.platform == "darwin":
        os.system(f'open "{p}"')  # noqa: S605
    else:
        os.system(f'xdg-open "{p}"')  # noqa: S605


def _verdict_colour(v: Verdict | str) -> str:
    s = v.value if isinstance(v, Verdict) else str(v)
    return {
        "PASS": "positive",
        "FAIL": "negative",
        "WARN": "warning",
        "SKIP": "info",
        "ERROR": "negative",
    }.get(s, "info")


def _verdict_icon(v: Verdict | str) -> str:
    s = v.value if isinstance(v, Verdict) else str(v)
    return {
        "PASS": "check_circle",
        "FAIL": "cancel",
        "WARN": "warning",
        "SKIP": "skip_next",
        "ERROR": "error",
    }.get(s, "help")


# ── Orchestrator state ────────────────────────────────────────────────────

@dataclass
class OrchestratorState:
    """Mutable state shared across orchestrator UI components."""

    # Bench
    bench_path: str = ""
    bench: LabBench | None = None
    bench_dirty: bool = False

    # Profile
    profile_path: str = ""
    profile_raw: dict[str, Any] | None = None

    # Execution
    running: bool = False
    last_artifacts_path: str = ""
    last_verdict: TestVerdict | None = None

    # Log buffer (list of (timestamp, level, message) tuples)
    log_lines: list[tuple[str, str, str]] = field(default_factory=list)


STATE = OrchestratorState()


# ── Bench editor helpers ──────────────────────────────────────────────────

def _load_bench(path: str) -> LabBench | None:
    """Attempt to load a LabBench from *path*; return ``None`` on failure."""
    try:
        bench = LabBench.load(path)
        ui.notify(f"Loaded bench: {bench.name} ({len(bench.instruments)} instruments)", type="positive")
        return bench
    except Exception as exc:
        ui.notify(f"Failed to load bench: {exc}", type="negative")
        return None


def _save_bench(bench: LabBench, path: str) -> bool:
    try:
        bench.save(path)
        ui.notify(f"Saved bench to {path}", type="positive")
        return True
    except Exception as exc:
        ui.notify(f"Failed to save bench: {exc}", type="negative")
        return False


# ── Widget factories ──────────────────────────────────────────────────────

def _param_input(
    label: str,
    value: Any,
    on_change: Callable,
    param_meta: dict[str, Any] | None = None,
) -> None:
    """Render a single parameter input based on its type metadata."""
    pm = param_meta or {}
    ptype = pm.get("type", "text")
    unit = pm.get("unit", "")
    suffix = f" ({unit})" if unit else ""

    if ptype == "bool":
        ui.checkbox(label, value=bool(value), on_change=on_change)
    elif ptype == "select":
        ui.select(pm.get("options", []), value=value, label=label, on_change=on_change).classes("w-full")
    elif ptype == "json":
        ui.textarea(label + suffix, value=str(value), on_change=on_change).classes("w-full").props("rows=3")
    elif ptype == "number":
        ui.number(label + suffix, value=_safe_float(str(value)), on_change=on_change, format="%.6g").classes("w-full")
    else:
        ui.input(label + suffix, value=str(value), on_change=on_change).classes("w-full")


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API: mount the orchestrator into a NiceGUI container
# ══════════════════════════════════════════════════════════════════════════

def mount(container) -> None:
    """Mount the full orchestrator/logger GUI into *container*.

    ``container`` must be a NiceGUI layout element such as ``ui.column()``.
    """
    with container:
        _build_ui()


def _build_ui() -> None:
    """Assemble the complete orchestrator UI."""

    # ── Top toolbar ──────────────────────────────────────────────────
    with ui.row().classes("w-full items-center gap-2 q-pa-sm bg-blue-grey-1 rounded"):
        ui.icon("hub", size="sm").classes("text-primary")
        ui.label("Lab Bench Orchestrator").classes("text-h6 text-weight-bold q-mr-md")

        bench_path_input = ui.input(
            "Bench JSON",
            value=STATE.bench_path or str(_default_bench_path()),
            on_change=lambda e: setattr(STATE, "bench_path", e.value),
        ).classes("w-64").props("dense outlined")

        def _on_load_bench():
            path = STATE.bench_path or str(_default_bench_path())
            bench = _load_bench(path)
            if bench is not None:
                STATE.bench = bench
                STATE.bench_path = path
                STATE.bench_dirty = False
                bench_panel.refresh()
                dashboard_panel.refresh()

        ui.button("Load", icon="folder_open", on_click=_on_load_bench).props("flat dense")

        def _on_save_bench():
            if STATE.bench is None:
                ui.notify("No bench loaded", type="warning")
                return
            path = STATE.bench_path or str(_default_bench_path())
            if _save_bench(STATE.bench, path):
                STATE.bench_dirty = False

        ui.button("Save", icon="save", on_click=_on_save_bench).props("flat dense")

        def _on_new_bench():
            STATE.bench = LabBench(name="new_bench")
            STATE.bench_dirty = True
            bench_panel.refresh()
            dashboard_panel.refresh()
            ui.notify("Created new empty bench", type="info")

        ui.button("New", icon="add_circle", on_click=_on_new_bench).props("flat dense")
        ui.space()

        # Status badge
        status_badge = ui.badge("IDLE", color="blue-grey").props("outline")

    # ── Tabs ─────────────────────────────────────────────────────────
    with ui.tabs().classes("w-full") as tabs:
        ui.tab("dashboard", label="Dashboard", icon="dashboard")
        ui.tab("bench", label="Bench Editor", icon="build")
        ui.tab("profile", label="Profile Runner", icon="play_circle")
        ui.tab("log", label="Live Log", icon="terminal")
        ui.tab("results", label="Results", icon="assessment")

    # ── Tab panels ───────────────────────────────────────────────────
    with ui.tab_panels(tabs, value="dashboard").classes("w-full"):

        # ── DASHBOARD TAB ────────────────────────────────────────────
        with ui.tab_panel("dashboard"):
            @ui.refreshable
            def dashboard_panel():
                bench = STATE.bench
                if bench is None:
                    with ui.card().classes("w-full q-pa-lg"):
                        ui.icon("info", size="xl", color="blue-grey")
                        ui.label("No bench loaded.").classes("text-h6 text-grey")
                        ui.label("Load a bench JSON or create a new one using the toolbar above.")
                        ui.button("Load default bench", icon="folder_open", on_click=_on_load_bench).props("color=primary")
                    return

                # ── Bench overview card ──
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("hub", size="md", color="primary")
                        ui.label(bench.name).classes("text-h6 text-weight-bold")
                        ui.badge(f"{len(bench.instruments)} instruments").props("color=primary outline")
                        enabled_count = len(bench.enabled_instruments())
                        if enabled_count < len(bench.instruments):
                            ui.badge(f"{enabled_count} enabled").props("color=green outline")

                # ── Wiring info ──
                if bench.wiring:
                    with ui.card().classes("w-full"):
                        ui.label("Wiring Notes").classes("text-subtitle1 text-weight-bold")
                        for key, val in bench.wiring.items():
                            with ui.row().classes("items-baseline gap-1"):
                                ui.label(f"{key}:").classes("text-weight-medium text-grey-8")
                                ui.label(str(val)).classes("text-body2")

                # ── Instrument cards ──
                ui.label("Instruments").classes("text-h6 q-mt-md")
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    for inst_name, inst in bench.instruments.items():
                        meta = INSTRUMENT_TYPES.get(inst.type, {})
                        icon = meta.get("icon", "settings")
                        colour = meta.get("colour", "grey")
                        type_label = meta.get("label", inst.type)

                        with ui.card().classes("w-72"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon(icon, size="sm", color=colour)
                                ui.label(inst_name).classes("text-subtitle1 text-weight-bold")
                                if inst.enabled:
                                    ui.badge("ON", color="green").props("dense")
                                else:
                                    ui.badge("OFF", color="grey").props("dense")
                            ui.label(type_label).classes("text-caption text-grey-7")

                            # Key params
                            if inst.params:
                                ui.separator()
                                with ui.column().classes("gap-0"):
                                    shown = 0
                                    for k, v in inst.params.items():
                                        if shown >= 4:
                                            ui.label(f"… +{len(inst.params) - 4} more").classes("text-caption text-grey-5")
                                            break
                                        display_v = str(v) if not isinstance(v, (list, dict)) else json.dumps(v)[:60]
                                        ui.label(f"{k}: {display_v}").classes("text-caption")
                                        shown += 1

                            # Calibration
                            if inst.calibration and inst.calibration.last_cal_date:
                                ui.separator()
                                ui.label(f"Calibrated: {inst.calibration.last_cal_date}").classes("text-caption text-blue-8")

                # ── Last verdict ──
                if STATE.last_verdict is not None:
                    ui.separator()
                    v = STATE.last_verdict
                    with ui.card().classes("w-full"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(_verdict_icon(v.overall), size="md", color=_verdict_colour(v.overall))
                            ui.label(f"Last Result: {v.overall.value}").classes("text-h6 text-weight-bold")
                        ui.label(v.summary).classes("text-body2 text-grey-8")

            dashboard_panel()

        # ── BENCH EDITOR TAB ─────────────────────────────────────────
        with ui.tab_panel("bench"):
            @ui.refreshable
            def bench_panel():
                bench = STATE.bench
                if bench is None:
                    ui.label("No bench loaded. Load or create one via the toolbar.").classes("text-grey")
                    return

                with ui.card().classes("w-full"):
                    ui.label("Bench Properties").classes("text-subtitle1 text-weight-bold")
                    ui.input("Bench name", value=bench.name, on_change=lambda e: _set_bench_name(e.value)).classes("w-80")

                    def _set_bench_name(val):
                        bench.name = val
                        STATE.bench_dirty = True

                ui.separator()
                ui.label("Instruments").classes("text-h6")

                for inst_name in list(bench.instruments.keys()):
                    inst = bench.instruments[inst_name]
                    meta = INSTRUMENT_TYPES.get(inst.type, {})
                    icon = meta.get("icon", "settings")
                    colour = meta.get("colour", "grey")

                    with ui.expansion(
                        text=f"{inst_name}  —  {meta.get('label', inst.type)}",
                        icon=icon,
                    ).classes("w-full").props(f"header-class=bg-{colour}-1"):

                        with ui.row().classes("items-center gap-2 q-mb-sm"):
                            ui.checkbox(
                                "Enabled",
                                value=inst.enabled,
                                on_change=lambda e, n=inst_name: _toggle_instrument(n, e.value),
                            )

                            def _make_delete(n=inst_name):
                                def _del():
                                    del bench.instruments[n]
                                    STATE.bench_dirty = True
                                    bench_panel.refresh()
                                    dashboard_panel.refresh()
                                    ui.notify(f"Removed {n}", type="info")
                                return _del

                            ui.button("Remove", icon="delete", on_click=_make_delete(inst_name)).props("flat dense color=negative")

                        # Type selector
                        ui.select(
                            list(INSTRUMENT_TYPES.keys()),
                            value=inst.type,
                            label="Type",
                            on_change=lambda e, n=inst_name: _change_instrument_type(n, e.value),
                        ).classes("w-60")

                        # Params
                        param_defs = meta.get("params", {})
                        ui.label("Parameters").classes("text-subtitle2 q-mt-sm")
                        with ui.column().classes("gap-1"):
                            for pkey in list(inst.params.keys()):
                                pmeta = param_defs.get(pkey)
                                _param_input(
                                    pkey,
                                    inst.params[pkey],
                                    on_change=lambda e, n=inst_name, k=pkey: _set_param(n, k, e.value),
                                    param_meta=pmeta,
                                )

                            # Show missing defaults
                            for pkey, pmeta in param_defs.items():
                                if pkey not in inst.params:
                                    _param_input(
                                        f"(+) {pkey}",
                                        pmeta.get("default", ""),
                                        on_change=lambda e, n=inst_name, k=pkey: _set_param(n, k, e.value),
                                        param_meta=pmeta,
                                    )

                        # Calibration
                        ui.separator()
                        ui.label("Calibration").classes("text-subtitle2")
                        cal = inst.calibration
                        with ui.row().classes("gap-2 flex-wrap"):
                            ui.number("Current offset (A)", value=cal.current_offset_a, format="%.6g",
                                      on_change=lambda e, n=inst_name: _set_cal(n, "current_offset_a", e.value)).classes("w-40")
                            ui.number("Voltage offset (V)", value=cal.voltage_offset_v, format="%.6g",
                                      on_change=lambda e, n=inst_name: _set_cal(n, "voltage_offset_v", e.value)).classes("w-40")
                            ui.number("Gain correction", value=cal.gain_correction, format="%.6g",
                                      on_change=lambda e, n=inst_name: _set_cal(n, "gain_correction", e.value)).classes("w-40")
                            ui.input("Cal date", value=cal.last_cal_date or "",
                                     on_change=lambda e, n=inst_name: _set_cal(n, "last_cal_date", e.value or None)).classes("w-40")

                # ── Add instrument ──
                ui.separator()
                with ui.card().classes("w-full bg-blue-grey-1"):
                    ui.label("Add Instrument").classes("text-subtitle2")
                    with ui.row().classes("items-end gap-2"):
                        new_name = ui.input("Name", value="new_instrument").classes("w-40")
                        new_type = ui.select(list(INSTRUMENT_TYPES.keys()), value="simulated", label="Type").classes("w-40")

                        def _add_instrument():
                            name = new_name.value.strip()
                            if not name:
                                ui.notify("Name required", type="warning")
                                return
                            if name in bench.instruments:
                                ui.notify(f"'{name}' already exists", type="warning")
                                return
                            itype = new_type.value
                            defaults = {}
                            for pk, pm in INSTRUMENT_TYPES.get(itype, {}).get("params", {}).items():
                                defaults[pk] = pm.get("default", "")
                            bench.instruments[name] = InstrumentConfig(
                                name=name, type=itype, params=defaults, enabled=True,
                            )
                            STATE.bench_dirty = True
                            bench_panel.refresh()
                            dashboard_panel.refresh()
                            ui.notify(f"Added {name} ({itype})", type="positive")

                        ui.button("Add", icon="add", on_click=_add_instrument).props("color=primary")

                # ── Wiring notes ──
                ui.separator()
                with ui.card().classes("w-full"):
                    ui.label("Wiring Notes").classes("text-subtitle1 text-weight-bold")
                    ui.textarea(
                        "Wiring (JSON or free text)",
                        value=json.dumps(bench.wiring, indent=2) if bench.wiring else "",
                        on_change=lambda e: _set_wiring(e.value),
                    ).classes("w-full").props("rows=4")

                # ── Raw JSON preview ──
                ui.separator()
                with ui.expansion("Raw JSON preview", icon="code").classes("w-full"):
                    ui.code(json.dumps(bench.to_dict(), indent=2), language="json").classes("w-full")

                def _toggle_instrument(name, val):
                    bench.instruments[name].enabled = bool(val)
                    STATE.bench_dirty = True

                def _change_instrument_type(name, val):
                    bench.instruments[name].type = val
                    STATE.bench_dirty = True
                    bench_panel.refresh()

                def _set_param(name, key, val):
                    bench.instruments[name].params[key] = val
                    STATE.bench_dirty = True

                def _set_cal(name, attr, val):
                    setattr(bench.instruments[name].calibration, attr, val)
                    STATE.bench_dirty = True

                def _set_wiring(val):
                    try:
                        bench.wiring = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        bench.wiring = {"notes": val}
                    STATE.bench_dirty = True

            bench_panel()

        # ── PROFILE RUNNER TAB ───────────────────────────────────────
        with ui.tab_panel("profile"):
            with ui.card().classes("w-full"):
                ui.label("Profile Runner").classes("text-h6 text-weight-bold")
                ui.label(
                    "Load a test profile JSON and execute it against the loaded bench. "
                    "Results stream to the Live Log tab."
                ).classes("text-body2 text-grey-7 q-mb-sm")

                profile_input = ui.input(
                    "Profile JSON path",
                    value=STATE.profile_path or str(_default_profile_path()),
                    on_change=lambda e: setattr(STATE, "profile_path", e.value),
                ).classes("w-full")

                # ── Profile preview ──
                @ui.refreshable
                def profile_preview():
                    raw = STATE.profile_raw
                    if raw is None:
                        ui.label("No profile loaded.").classes("text-grey")
                        return

                    with ui.card().classes("w-full bg-grey-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("description", color="primary")
                            ui.label(raw.get("name", "unnamed")).classes("text-subtitle1 text-weight-bold")

                        desc = raw.get("description", "")
                        if desc:
                            ui.label(desc).classes("text-body2 text-grey-8")

                        # Steps summary
                        steps = raw.get("steps", [])
                        if steps:
                            ui.separator()
                            ui.label(f"{len(steps)} steps").classes("text-subtitle2")
                            with ui.column().classes("gap-0"):
                                for i, step in enumerate(steps):
                                    sname = step.get("name", f"step_{i}")
                                    sdur = step.get("duration_s", "?")
                                    actions = step.get("actions", [])
                                    action_types = [a.get("type", "?") for a in actions]
                                    ui.label(
                                        f"  {i+1}. {sname}  ({sdur}s)  → {', '.join(action_types)}"
                                    ).classes("text-caption font-mono")

                        # Limits summary
                        limits = raw.get("limits", {})
                        if limits:
                            ui.separator()
                            step_limits = limits.get("steps", {})
                            ui.label(f"Limits defined for {len(step_limits)} steps").classes("text-subtitle2")
                            for sname, slims in step_limits.items():
                                metrics = list(slims.keys())
                                ui.label(f"  {sname}: {', '.join(metrics)}").classes("text-caption font-mono")

                        # Instruments
                        insts = raw.get("instruments", {})
                        if insts:
                            ui.separator()
                            ui.label(f"{len(insts)} profile instruments").classes("text-subtitle2")
                            for iname, icfg in insts.items():
                                itype = icfg.get("type", "?") if isinstance(icfg, dict) else "?"
                                ui.label(f"  {iname}: {itype}").classes("text-caption font-mono")

                with ui.row().classes("gap-2 q-mt-sm"):
                    def _load_profile_clicked():
                        path = STATE.profile_path or str(_default_profile_path())
                        try:
                            p = pathlib.Path(path)
                            raw = json.loads(p.read_text(encoding="utf-8"))
                            STATE.profile_raw = raw
                            STATE.profile_path = path
                            profile_preview.refresh()
                            ui.notify(f"Loaded profile: {raw.get('name', 'unnamed')}", type="positive")
                        except Exception as exc:
                            ui.notify(f"Failed: {exc}", type="negative")

                    ui.button("Load Profile", icon="file_open", on_click=_load_profile_clicked).props("color=primary")

                    def _run_profile_clicked():
                        if STATE.running:
                            ui.notify("A test is already running", type="warning")
                            return
                        path = STATE.profile_path or str(_default_profile_path())
                        _execute_profile(path, status_badge, dashboard_panel, results_panel, log_view)

                    run_profile_btn = ui.button("Run Profile", icon="play_arrow", on_click=_run_profile_clicked).props("color=green")

                    def _stop_clicked():
                        STATE.running = False
                        status_badge.set_text("STOPPED")
                        status_badge.update()
                        ui.notify("Stop requested", type="warning")

                    ui.button("Stop", icon="stop", on_click=_stop_clicked).props("color=negative outline")

                profile_preview()

                # ── Bench merge info ──
                ui.separator()
                with ui.card().classes("w-full bg-amber-1"):
                    ui.icon("info", color="amber-8")
                    ui.label(
                        "When running a profile, the currently loaded bench configuration "
                        "will be merged with the profile's instrument definitions. "
                        "Bench instruments override profile defaults."
                    ).classes("text-body2 text-amber-10")

        # ── LIVE LOG TAB ─────────────────────────────────────────────
        with ui.tab_panel("log"):
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("Live Execution Log").classes("text-h6 text-weight-bold")
                    ui.space()

                    def _clear_log():
                        STATE.log_lines.clear()
                        log_view.refresh()

                    ui.button("Clear", icon="delete_sweep", on_click=_clear_log).props("flat dense")

                    def _export_log():
                        if not STATE.log_lines:
                            ui.notify("Log is empty", type="info")
                            return
                        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                        log_path = _artifacts_root() / f"log_{ts}.txt"
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(log_path, "w", encoding="utf-8") as f:
                            for t, lvl, msg in STATE.log_lines:
                                f.write(f"[{t}] [{lvl}] {msg}\n")
                        ui.notify(f"Exported to {log_path}", type="positive")

                    ui.button("Export", icon="download", on_click=_export_log).props("flat dense")

                @ui.refreshable
                def log_view():
                    lines = STATE.log_lines
                    if not lines:
                        ui.label("No log entries yet. Run a profile to see output here.").classes("text-grey")
                        return

                    with ui.scroll_area().classes("w-full").style("height: 600px; background: #1e1e1e; border-radius: 8px; padding: 8px;"):
                        for ts, level, msg in lines[-500:]:  # cap display
                            color_map = {
                                "INFO": "#8be9fd",
                                "WARN": "#f1fa8c",
                                "ERROR": "#ff5555",
                                "PASS": "#50fa7b",
                                "FAIL": "#ff5555",
                                "STEP": "#bd93f9",
                                "ACTION": "#ff79c6",
                            }
                            c = color_map.get(level, "#f8f8f2")
                            ui.html(
                                f'<span style="font-family: monospace; font-size: 13px; color: #6272a4;">[{ts}]</span> '
                                f'<span style="font-family: monospace; font-size: 13px; color: {c}; font-weight: bold;">[{level}]</span> '
                                f'<span style="font-family: monospace; font-size: 13px; color: #f8f8f2;">{msg}</span>'
                            )

                log_view()

        # ── RESULTS TAB ──────────────────────────────────────────────
        with ui.tab_panel("results"):
            @ui.refreshable
            def results_panel():
                verdict = STATE.last_verdict
                artifacts_path = STATE.last_artifacts_path

                if verdict is None and not artifacts_path:
                    with ui.card().classes("w-full q-pa-lg"):
                        ui.icon("hourglass_empty", size="xl", color="blue-grey")
                        ui.label("No results yet.").classes("text-h6 text-grey")
                        ui.label("Run a test profile to see pass/fail verdicts here.")
                    return

                # ── Verdict banner ──
                if verdict is not None:
                    vc = _verdict_colour(verdict.overall)
                    with ui.card().classes("w-full").style(
                        f"border-left: 6px solid var(--q-{vc})"
                    ):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon(
                                _verdict_icon(verdict.overall),
                                size="lg",
                                color=vc,
                            )
                            ui.label(verdict.overall.value).classes("text-h4 text-weight-bold")
                        ui.label(verdict.summary).classes("text-body1 text-grey-8 q-mt-sm")

                    # ── Per-result table ──
                    if verdict.results:
                        ui.label("Detailed Results").classes("text-h6 q-mt-md")
                        columns = [
                            {"name": "step", "label": "Step", "field": "step", "align": "left"},
                            {"name": "metric", "label": "Metric", "field": "metric", "align": "left"},
                            {"name": "value", "label": "Value", "field": "value", "align": "right"},
                            {"name": "limit", "label": "Limit", "field": "limit", "align": "left"},
                            {"name": "verdict", "label": "Verdict", "field": "verdict", "align": "center"},
                        ]
                        rows = []
                        for r in verdict.results:
                            lim_desc = r.limit.describe() if hasattr(r.limit, "describe") else str(r.limit)
                            rows.append({
                                "step": r.step_name or "",
                                "metric": r.metric,
                                "value": f"{r.value:.6g}" if isinstance(r.value, float) else str(r.value),
                                "limit": lim_desc,
                                "verdict": r.verdict.value if isinstance(r.verdict, Verdict) else str(r.verdict),
                            })
                        ui.table(columns=columns, rows=rows, row_key="metric").classes("w-full")

                # ── Artifacts ──
                if artifacts_path:
                    ui.separator()
                    with ui.card().classes("w-full"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("folder", color="amber")
                            ui.label("Artifacts").classes("text-subtitle1 text-weight-bold")
                            ui.button(
                                "Open folder", icon="open_in_new",
                                on_click=lambda: _open_folder(artifacts_path),
                            ).props("flat dense")

                        # List artifact files
                        art_dir = pathlib.Path(artifacts_path)
                        if art_dir.exists():
                            with ui.column().classes("gap-0"):
                                for f in sorted(art_dir.rglob("*")):
                                    if f.is_file():
                                        rel = f.relative_to(art_dir)
                                        size_kb = f.stat().st_size / 1024
                                        ui.label(f"  📄 {rel}  ({size_kb:.1f} KB)").classes("text-caption font-mono")
                        else:
                            ui.label(f"Directory not found: {art_dir}").classes("text-caption text-grey")

                # ── Verdict JSON ──
                if verdict is not None:
                    ui.separator()
                    with ui.expansion("Verdict JSON", icon="code").classes("w-full"):
                        ui.code(json.dumps(verdict.to_dict(), indent=2), language="json").classes("w-full")

            results_panel()


# ── Profile execution engine ──────────────────────────────────────────────

def _log(level: str, msg: str) -> None:
    """Append a log line and refresh the log view."""
    STATE.log_lines.append((_ts(), level, msg))


def _execute_profile(
    path: str,
    status_badge,
    dashboard_panel,
    results_panel,
    log_view,
) -> None:
    """Run a profile in a background thread, streaming log updates."""

    STATE.running = True
    STATE.last_verdict = None
    STATE.last_artifacts_path = ""
    status_badge.set_text("RUNNING")
    status_badge.update()

    _log("INFO", f"Starting profile: {path}")
    if STATE.bench:
        _log("INFO", f"Bench: {STATE.bench.name} ({len(STATE.bench.enabled_instruments())} enabled instruments)")

    def _worker():
        try:
            profile_path = pathlib.Path(path)
            if not profile_path.exists():
                _log("ERROR", f"Profile not found: {path}")
                ui.notify(f"Profile not found: {path}", type="negative")
                return

            _log("INFO", "Loading profile...")
            profile = load_profile(str(profile_path))
            _log("INFO", f"Profile: {profile.get('name', 'unnamed')} — {len(profile.get('steps', []))} steps")

            # Log step plan
            for i, step in enumerate(profile.get("steps", [])):
                sname = step.get("name", f"step_{i}")
                sdur = step.get("duration_s", "?")
                actions = step.get("actions", [])
                _log("STEP", f"  [{i+1}] {sname} ({sdur}s) — {len(actions)} actions")

            bench_path_arg = STATE.bench_path if STATE.bench else None

            _log("INFO", "Building instruments...")

            # Run the profile
            _log("INFO", "Executing test...")
            log_view.refresh()

            result = run_profile(
                profile,
                str(REPO_ROOT),
                lab_bench_path=bench_path_arg if bench_path_arg else None,
            )

            _log("INFO", "Test execution completed.")

            # Check for TestArtifacts
            if isinstance(result, TestArtifacts):
                STATE.last_artifacts_path = str(result.root_dir)
                _log("INFO", f"Artifacts saved to: {result.root_dir}")

                # Try to read summary
                summary_path = result.summary_json_path
                if pathlib.Path(summary_path).exists():
                    _log("INFO", "Reading summary...")
                    summary = json.loads(pathlib.Path(summary_path).read_text(encoding="utf-8"))

                    # Try to evaluate limits
                    profile_raw = json.loads(profile_path.read_text(encoding="utf-8"))
                    limits_raw = profile_raw.get("limits")
                    if limits_raw:
                        _log("INFO", "Evaluating limits...")
                        spec = TestSpec.from_dict(limits_raw)
                        verdict = evaluate(spec, summary)
                        STATE.last_verdict = verdict
                        _log(verdict.overall.value, f"Overall verdict: {verdict.overall.value}")
                        _log("INFO", verdict.summary)

                        for r in verdict.results:
                            _log(r.verdict.value if isinstance(r.verdict, Verdict) else "INFO", str(r))
                    else:
                        _log("INFO", "No limits defined in profile — skipping verdict evaluation.")
            else:
                _log("INFO", f"Profile returned: {type(result).__name__}")

            _log("PASS" if (STATE.last_verdict and STATE.last_verdict.passed) else "INFO", "Profile run complete.")

        except Exception as exc:
            _log("ERROR", f"Profile execution failed: {exc}")
            _log("ERROR", traceback.format_exc())
            ui.notify(f"Error: {exc}", type="negative")
        finally:
            STATE.running = False
            status_badge.set_text("IDLE")
            status_badge.update()
            log_view.refresh()
            results_panel.refresh()
            dashboard_panel.refresh()

    threading.Thread(target=_worker, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Run the orchestrator as a standalone NiceGUI app."""
    port = int(os.environ.get("PYONTRUST_PORT", "8082"))

    @ui.page("/")
    def _root():
        ui.page_title("Pyontrust Lab Bench Orchestrator")
        with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-md"):
            mount(ui.column().classes("w-full"))

    ui.run(title="Lab Bench Orchestrator", reload=False, port=port)


if __name__ == "__main__":
    main()
