"""Bidirectional converter between FlowLab diagrams and HIL test profiles.

Provides two main functions:

- ``diagram_to_hil(diagram_json)`` — Convert a FlowLab diagram to a HIL
  profile JSON that can be run via ``/hil/api/start`` or saved as a
  ``.json`` profile file.
- ``hil_to_diagram(profile_json)`` — Convert a HIL test profile into a
  FlowLab diagram (blocks + wires) for visual editing.

The HIL profile format supports two variants:
1. **Flat actions** — ``{"name", "description", "instruments", "actions": [...]}``
2. **Nested steps** — ``{"name", "description", "steps": [{"name", "duration_s", "actions": [...]}]}``

Both are supported for import.  Export always produces the nested-steps
format so that ``profiles.py._build_test()`` can parse it directly.
"""
from __future__ import annotations

import json
import logging
import math
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger("pyontrust.gateway.hil_flowlab_converter")

# ═══════════════════════════════════════════════════════════════════
# Block-type ↔ HIL-action mapping tables
# ═══════════════════════════════════════════════════════════════════

# Map FlowLab block types → HIL action types
_BLOCK_TO_HIL: dict[str, str] = {
    # Direct mappings
    "sleep_test":      "sleep_test_block",
    "tx_burst_test":   "tx_burst_test_block",
    "delay":           "sleep",
    "shell_cmd":       "run",
    "gpio_toggle":     "gpio_toggle",
    "serial_send":     "serial_send",
    "http_request":    "http_request",
    # Instrument blocks → measurement steps
    "simulated_power": "measure",
    "ppk2_meter":      "measure",
    "ad3_dwf_meter":   "measure",
    "csv_file":        "csv_load",
    "csv_replay":      "csv_replay",
    "waveform_gen":    "waveform_gen",
    "random_data":     "random_data",
    # Vision → inspection
    "aoi_camera":      "snapshot",
    "seek_thermal":    "thermal_capture",
    "aoi_inspect":     "inspect",
    "thermal_analyze": "thermal_analyze",
    # Analysis blocks → analysis step
    "stats":           "analysis",
    "filter":          "analysis",
    "highpass_filter":  "analysis",
    "bandpass_filter":  "analysis",
    "fft_spectrum":    "analysis",
    "moving_average":  "analysis",
    "threshold":       "threshold_check",
    "assert_check":    "assert",
    # I/O blocks
    "display":         "display",
    "plot_trace":      "plot",
    "plot_xy":         "plot",
    "plot_histogram":  "plot",
    "plot_heatmap":    "plot",
    "save_file":       "save_artifact",
    "log_message":     "mark",
    # Actions
    "load_profile":    "load_profile",
    "benchmark_timer": "benchmark",
}

# Map HIL action types → FlowLab block type + default params
_HIL_TO_BLOCK: dict[str, dict[str, Any]] = {
    "mark": {
        "type": "log_message",
        "params_map": {"label": "prefix"},
    },
    "run": {
        "type": "shell_cmd",
        "params_map": {"command": "command", "timeout_s": "timeout_s"},
        "fallback_params": {"command": "echo step"},
    },
    "sleep": {
        "type": "delay",
        "params_map": {"seconds": "seconds"},
    },
    "measure": {
        "type": "simulated_power",
        "params_map": {
            "duration_s": "duration_s",
            "sample_rate_hz": "sample_rate_hz",
        },
    },
    "flash": {
        "type": "shell_cmd",
        "params_map": {"firmware": "command"},
        "transform": lambda p: {"command": f"nrfjprog --program {p.get('firmware', '')} --chiperase --verify --reset"},
    },
    "reset_target": {
        "type": "shell_cmd",
        "params_map": {},
        "transform": lambda p: {"command": "nrfjprog --reset"},
    },
    "set_voltage": {
        "type": "constant",
        "params_map": {"voltage_v": "value"},
        "transform": lambda p: {"value": str(p.get("voltage_v", 3.3)), "dtype": "float"},
    },
    "enable_output": {
        "type": "constant",
        "params_map": {"on": "value"},
        "transform": lambda p: {"value": str(p.get("on", True)), "dtype": "bool"},
    },
    "snapshot": {
        "type": "aoi_camera",
        "params_map": {"instrument": "mode"},
    },
    "inspect": {
        "type": "aoi_inspect",
        "params_map": {"board_id": "reference", "tolerance": "tolerance"},
    },
    "thermal_capture": {
        "type": "seek_thermal",
        "params_map": {"zones": "zones"},
    },
    "rf_sweep": {
        "type": "http_request",
        "params_map": {},
        "transform": lambda p: {
            "url": "http://localhost:5200/api/rf_sweep",
            "method": "POST",
        },
    },
    "set_power_mode": {
        "type": "constant",
        "params_map": {"mode": "value"},
        "transform": lambda p: {"value": str(p.get("mode", "source")), "dtype": "str"},
    },
    # Compound test blocks (flat profile actions using "run" with duration_s)
    "sleep_test_block": {
        "type": "sleep_test",
        "params_map": {"duration_s": "duration_s", "max_avg_ua": "max_avg_ua"},
    },
    "tx_burst_test_block": {
        "type": "tx_burst_test",
        "params_map": {"duration_s": "duration_s", "interval_ms": "interval_ms"},
    },
}


# ═══════════════════════════════════════════════════════════════════
# FlowLab diagram → HIL profile
# ═══════════════════════════════════════════════════════════════════

def diagram_to_hil(diagram: dict[str, Any]) -> dict[str, Any]:
    """Convert a FlowLab diagram to a HIL test profile JSON.

    The resulting profile uses the nested ``steps`` format compatible
    with ``profiles.py._build_test()``.

    Parameters
    ----------
    diagram : dict
        FlowLab diagram with ``blocks`` and ``wires`` arrays.

    Returns
    -------
    dict
        HIL profile JSON with ``name``, ``description``, ``instruments``,
        ``recorders``, and ``steps`` fields.
    """
    blocks_raw = diagram.get("blocks", [])
    wires_raw = diagram.get("wires", [])

    if not blocks_raw:
        return _empty_profile("empty_flowlab_export")

    # Build execution order via topological sort
    block_map = {b["id"]: b for b in blocks_raw}
    order = _topo_sort(blocks_raw, wires_raw)

    # Detect instruments from block types
    instruments = _detect_instruments(blocks_raw)

    # Convert each block to a HIL step
    steps: list[dict[str, Any]] = []
    step_idx = 0

    for bid in order:
        bdef = block_map.get(bid)
        if not bdef:
            continue

        btype = bdef.get("type", "")
        params = bdef.get("params", {})

        # Skip pure data-routing blocks that don't map to physical actions
        if btype in ("constant", "expression", "merge", "gate", "null_check",
                      "try_catch", "sequence", "dict_get", "dict_set",
                      "dict_build", "list_build", "json_parse", "format_string",
                      "type_cast", "pick_field", "repeat", "map_range",
                      "multiply", "add", "subtract", "divide", "abs_val",
                      "power", "log_math", "trig", "clamp", "compare",
                      "unit_convert"):
            continue

        step_idx += 1
        step = _block_to_step(btype, params, step_idx, bid)
        if step:
            steps.append(step)

    # Extract a name from diagram metadata or generate one
    name = diagram.get("name", "flowlab_export")
    desc = diagram.get("description", f"HIL test exported from FlowLab ({len(steps)} steps)")

    return {
        "name": name,
        "description": desc,
        "instruments": instruments,
        "recorders": [],
        "steps": steps,
        "meta": {
            "source": "flowlab",
            "diagram_version": diagram.get("version", 1),
            "block_count": len(blocks_raw),
            "wire_count": len(wires_raw),
        },
    }


def _block_to_step(
    btype: str,
    params: dict[str, Any],
    idx: int,
    block_id: str,
) -> dict[str, Any] | None:
    """Convert a single FlowLab block to a HIL test step."""
    hil_action_type = _BLOCK_TO_HIL.get(btype, btype)

    # Build step actions list
    actions: list[dict[str, Any]] = []

    # Leading marker
    actions.append({"type": "mark", "label": f"step_{idx}_start_{btype}"})

    # Main action based on block type
    if btype == "sleep_test":
        actions.append({
            "type": "mark", "label": "sleep_test_start",
        })
        dur = float(params.get("duration_s", 5))
        # The sleep test is a measurement step
        return {
            "name": f"step_{idx}_sleep_test",
            "duration_s": dur,
            "description": f"Sleep current test ({dur}s)",
            "actions": actions,
        }

    if btype == "tx_burst_test":
        dur = float(params.get("duration_s", 3))
        actions.append({
            "type": "mark", "label": "tx_burst_start",
        })
        return {
            "name": f"step_{idx}_tx_burst",
            "duration_s": dur,
            "description": f"TX burst profile test ({dur}s)",
            "actions": actions,
        }

    if btype == "delay":
        secs = float(params.get("seconds", 1))
        actions.append({"type": "sleep", "seconds": secs})
        return {
            "name": f"step_{idx}_delay",
            "duration_s": secs,
            "description": f"Delay {secs}s",
            "actions": actions,
        }

    if btype == "shell_cmd":
        cmd = str(params.get("command", "echo hello"))
        timeout = float(params.get("timeout_s", 30))
        actions.append({
            "type": "run",
            "command": [cmd] if " " not in cmd else ["bash", "-c", cmd],
            "timeout_s": timeout,
        })
        return {
            "name": f"step_{idx}_shell",
            "duration_s": timeout,
            "description": f"Shell: {cmd[:60]}",
            "actions": actions,
        }

    if btype in ("simulated_power", "ppk2_meter", "ad3_dwf_meter"):
        dur = float(params.get("duration_s", 2))
        rate = float(params.get("sample_rate_hz", 1000))
        actions.append({"type": "mark", "label": f"measure_start_{btype}"})
        return {
            "name": f"step_{idx}_measure",
            "duration_s": dur,
            "description": f"Power measurement ({btype}, {dur}s @ {rate}Hz)",
            "actions": actions,
        }

    if btype == "gpio_toggle":
        pin = str(params.get("pin", "P0.13"))
        action = str(params.get("action", "toggle"))
        actions.append({
            "type": "mark", "label": f"gpio_{action}_{pin}",
        })
        return {
            "name": f"step_{idx}_gpio",
            "duration_s": 0.1,
            "description": f"GPIO {action}: {pin}",
            "actions": actions,
        }

    if btype == "serial_send":
        port = str(params.get("port", "COM3"))
        cmd = str(params.get("command", "AT\\r\\n"))
        actions.append({
            "type": "mark", "label": f"serial_{port}",
        })
        return {
            "name": f"step_{idx}_serial",
            "duration_s": float(params.get("timeout_s", 2)),
            "description": f"Serial: {port} → {cmd[:40]}",
            "actions": actions,
        }

    if btype == "http_request":
        url = str(params.get("url", ""))
        method = str(params.get("method", "GET"))
        actions.append({"type": "mark", "label": f"http_{method}"})
        return {
            "name": f"step_{idx}_http",
            "duration_s": 30,
            "description": f"{method} {url[:60]}",
            "actions": actions,
        }

    if btype in ("aoi_camera", "aoi_inspect"):
        actions.append({
            "type": "inspect",
            "instrument": "aoi_camera",
            "board_id": str(params.get("reference", f"board_step_{idx}")),
        })
        return {
            "name": f"step_{idx}_inspect",
            "duration_s": 5,
            "description": "AOI inspection",
            "actions": actions,
        }

    if btype in ("seek_thermal", "thermal_analyze"):
        actions.append({
            "type": "thermal_capture",
            "instrument": "seek_thermal",
        })
        return {
            "name": f"step_{idx}_thermal",
            "duration_s": 5,
            "description": "Thermal capture & analysis",
            "actions": actions,
        }

    if btype in ("stats", "filter", "highpass_filter", "bandpass_filter",
                 "fft_spectrum", "moving_average", "derivative", "integral",
                 "edge_detect", "histogram", "correlate", "window_slice",
                 "resample"):
        actions.append({"type": "mark", "label": f"analysis_{btype}"})
        return {
            "name": f"step_{idx}_analysis_{btype}",
            "duration_s": 1,
            "description": f"Analysis: {btype}",
            "actions": actions,
        }

    if btype == "threshold":
        metric = str(params.get("metric", "avg_current_a"))
        max_val = float(params.get("max_val", 0.01))
        min_val = float(params.get("min_val", 0))
        actions.append({
            "type": "mark",
            "label": f"threshold_{metric}_min{min_val}_max{max_val}",
        })
        return {
            "name": f"step_{idx}_threshold",
            "duration_s": 0.1,
            "description": f"Threshold: {metric} [{min_val}, {max_val}]",
            "actions": actions,
        }

    if btype == "assert_check":
        msg = str(params.get("message", "Assertion"))
        actions.append({"type": "mark", "label": f"assert_{msg[:30]}"})
        return {
            "name": f"step_{idx}_assert",
            "duration_s": 0.1,
            "description": f"Assert: {msg[:60]}",
            "actions": actions,
        }

    if btype in ("display", "plot_trace", "plot_xy", "plot_histogram",
                 "plot_heatmap", "gauge_display", "table_display"):
        actions.append({"type": "mark", "label": f"display_{btype}"})
        return {
            "name": f"step_{idx}_display",
            "duration_s": 0.1,
            "description": f"Display: {btype}",
            "actions": actions,
        }

    if btype == "save_file":
        path = str(params.get("path", "output.json"))
        actions.append({"type": "mark", "label": f"save_{path}"})
        return {
            "name": f"step_{idx}_save",
            "duration_s": 1,
            "description": f"Save: {path}",
            "actions": actions,
        }

    if btype == "log_message":
        prefix = str(params.get("prefix", "LOG"))
        actions.append({"type": "mark", "label": prefix})
        return {
            "name": f"step_{idx}_log",
            "duration_s": 0.1,
            "description": f"Log: {prefix}",
            "actions": actions,
        }

    if btype == "load_profile":
        path = str(params.get("path", ""))
        actions.append({"type": "mark", "label": f"load_profile_{path}"})
        return {
            "name": f"step_{idx}_load_profile",
            "duration_s": 0.1,
            "description": f"Load profile: {path}",
            "actions": actions,
        }

    if btype == "benchmark_timer":
        label = str(params.get("label", "timer"))
        actions.append({"type": "mark", "label": f"timer_{label}"})
        return {
            "name": f"step_{idx}_timer",
            "duration_s": 0.1,
            "description": f"Timer: {label}",
            "actions": actions,
        }

    # Catch-all: create a marker step
    if btype in ("csv_file", "csv_replay", "waveform_gen", "random_data"):
        dur = float(params.get("duration_s", 1))
        actions.append({"type": "mark", "label": f"source_{btype}"})
        return {
            "name": f"step_{idx}_{btype}",
            "duration_s": dur,
            "description": f"Data source: {btype}",
            "actions": actions,
        }

    # Generic fallback
    actions.append({"type": "mark", "label": f"block_{btype}"})
    return {
        "name": f"step_{idx}_{btype}",
        "duration_s": 1,
        "description": f"Block: {btype} (id={block_id})",
        "actions": actions,
    }


def _detect_instruments(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect required instruments from block types."""
    instruments: dict[str, Any] = {}
    for b in blocks:
        btype = b.get("type", "")
        params = b.get("params", {})

        if btype == "simulated_power":
            instruments["power_meter"] = {"type": "simulated", "params": {}}
        elif btype == "ppk2_meter":
            instruments["power_meter"] = {
                "type": "ppk2",
                "params": {
                    "serial_port": params.get("serial_port", ""),
                    "vdd_mv": params.get("vdd_mv", 3300),
                },
            }
        elif btype == "ad3_dwf_meter":
            instruments["power_meter"] = {
                "type": "ad3_dwf",
                "params": {
                    "device_index": params.get("device_index", 0),
                    "channel": params.get("channel", 0),
                    "shunt_ohm": params.get("shunt_ohm", 1.0),
                },
            }
        elif btype in ("aoi_camera", "aoi_inspect"):
            instruments["aoi_camera"] = {
                "type": params.get("mode", "simulated"),
                "params": {},
            }
        elif btype in ("seek_thermal", "thermal_analyze"):
            instruments["seek_thermal"] = {
                "type": params.get("mode", "simulated"),
                "params": {},
            }
        elif btype in ("sleep_test", "tx_burst_test"):
            instruments.setdefault("power_meter", {"type": "simulated", "params": {}})

    # Always ensure at least a simulated power meter
    if not instruments:
        instruments["power_meter"] = {"type": "simulated", "params": {}}

    return instruments


# ═══════════════════════════════════════════════════════════════════
# HIL profile → FlowLab diagram
# ═══════════════════════════════════════════════════════════════════

def hil_to_diagram(profile: dict[str, Any]) -> dict[str, Any]:
    """Convert a HIL test profile JSON into a FlowLab diagram.

    Handles both flat-actions format (``actions`` key) and nested-steps
    format (``steps`` key with per-step ``actions``).

    Parameters
    ----------
    profile : dict
        HIL profile JSON.

    Returns
    -------
    dict
        FlowLab diagram with ``version``, ``blocks``, and ``wires``.
    """
    # Normalise to a flat action list
    actions = _flatten_profile(profile)
    instruments = profile.get("instruments", {})

    blocks: list[dict[str, Any]] = []
    wires_list: list[dict[str, Any]] = []
    block_id_counter = 1

    # Layout configuration
    X_START = 80
    Y_START = 80
    X_STEP = 240
    Y_STEP = 140

    # First: add instrument source blocks based on profile instruments
    instrument_block_ids: dict[str, str] = {}
    inst_y = Y_START

    for inst_name, inst_cfg in instruments.items():
        inst_type = inst_cfg.get("type", "simulated") if isinstance(inst_cfg, dict) else "simulated"
        inst_params = inst_cfg.get("params", {}) if isinstance(inst_cfg, dict) else {}

        block_type = _instrument_to_block(inst_name, inst_type)
        bid = f"b{block_id_counter}"
        block_id_counter += 1

        params = _merge_instrument_params(inst_name, inst_type, inst_params)

        blocks.append({
            "id": bid,
            "type": block_type,
            "x": X_START,
            "y": inst_y,
            "params": params,
        })
        instrument_block_ids[inst_name] = bid
        inst_y += Y_STEP

    # Second: convert each action to a block
    prev_block_id: str | None = None
    prev_output_port: str | None = None
    action_x = X_START + X_STEP
    action_y = Y_START

    for i, action in enumerate(actions):
        a_type = action.get("type", "")
        bid = f"b{block_id_counter}"
        block_id_counter += 1

        block_info = _action_to_block(a_type, action, i)
        if block_info is None:
            continue

        btype, params, input_port, output_port = block_info

        blocks.append({
            "id": bid,
            "type": btype,
            "x": action_x,
            "y": action_y,
            "params": params,
        })

        # Wire from instrument if this is a measurement-type block
        if btype in ("simulated_power", "ppk2_meter", "ad3_dwf_meter",
                      "sleep_test", "tx_burst_test"):
            # This block IS the source — no wiring from instrument needed
            pass
        elif input_port and prev_block_id and prev_output_port:
            wid = f"b{block_id_counter}"
            block_id_counter += 1
            wires_list.append({
                "id": wid,
                "from": {"block": prev_block_id, "port": prev_output_port},
                "to": {"block": bid, "port": input_port},
            })

        prev_block_id = bid
        prev_output_port = output_port

        action_y += Y_STEP
        # Wrap to next column after 5 blocks
        if (i + 1) % 5 == 0:
            action_x += X_STEP
            action_y = Y_START

    return {
        "version": 1,
        "name": profile.get("name", "imported_profile"),
        "description": profile.get("description", ""),
        "blocks": blocks,
        "wires": wires_list,
    }


def _flatten_profile(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a profile into a sequential list of actions.

    Handles both:
    - Flat format: ``{"actions": [...]}``
    - Nested format: ``{"steps": [{"name", "duration_s", "actions": [...]}]}``
    """
    # Nested steps format
    steps = profile.get("steps")
    if steps and isinstance(steps, list):
        actions = []
        for step in steps:
            step_name = step.get("name", "step")
            duration_s = step.get("duration_s", 1.0)
            step_actions = step.get("actions", [])

            if step_actions:
                for a in step_actions:
                    actions.append({**a, "_step_name": step_name, "_duration_s": duration_s})
            else:
                # Step with no sub-actions → generate a run/measure action
                actions.append({
                    "type": "run",
                    "name": step_name,
                    "duration_s": duration_s,
                    "description": step.get("description", ""),
                    "_step_name": step_name,
                    "_duration_s": duration_s,
                })
        return actions

    # Flat actions format
    raw_actions = profile.get("actions", [])
    return list(raw_actions)


def _instrument_to_block(name: str, inst_type: str) -> str:
    """Map an instrument name/type to a FlowLab block type."""
    if "ppk2" in inst_type.lower():
        return "ppk2_meter"
    if "ad3" in inst_type.lower() or "dwf" in inst_type.lower():
        return "ad3_dwf_meter"
    if "webcam" in name or "aoi" in name or "camera" in name:
        return "aoi_camera"
    if "thermal" in name or "seek" in name:
        return "seek_thermal"
    # Default: simulated power meter
    return "simulated_power"


def _merge_instrument_params(name: str, inst_type: str, params: dict) -> dict[str, Any]:
    """Build FlowLab block params from instrument config."""
    result: dict[str, Any] = {}
    if "ppk2" in inst_type.lower():
        result["serial_port"] = params.get("serial_port", "")
        result["vdd_mv"] = params.get("vdd_mv", 3300)
    elif "ad3" in inst_type.lower() or "dwf" in inst_type.lower():
        result["device_index"] = params.get("device_index", 0)
        result["channel"] = params.get("channel", 0)
        result["shunt_ohm"] = params.get("shunt_ohm", 1.0)
    else:
        result["sample_rate_hz"] = params.get("sample_rate_hz", 1000)
        result["duration_s"] = params.get("duration_s", 2)
    return result


def _action_to_block(
    a_type: str,
    action: dict[str, Any],
    index: int,
) -> tuple[str, dict[str, Any], str | None, str | None] | None:
    """Convert a HIL action dict to (block_type, params, input_port, output_port).

    Returns None for actions that should be skipped.
    """
    if a_type == "mark":
        label = action.get("label", f"mark_{index}")
        return ("log_message", {"prefix": label, "level": "info"}, "data", "data")

    if a_type == "sleep":
        secs = float(action.get("seconds", 1.0))
        return ("delay", {"seconds": secs}, "trigger", "trigger")

    if a_type == "run":
        # Could be shell command or measurement step
        if "command" in action:
            cmd = action["command"]
            if isinstance(cmd, list):
                cmd = " ".join(cmd)
            return ("shell_cmd", {
                "command": cmd,
                "timeout_s": action.get("timeout_s", 30),
            }, "trigger", "stdout")
        elif "duration_s" in action:
            # Measurement / run step from flat format
            dur = float(action.get("duration_s", 1))
            name = action.get("name", "run_step")
            desc = action.get("description", "")

            # Try to detect test type from name/description
            lower_name = (name + " " + desc).lower()
            if "sleep" in lower_name or "idle" in lower_name:
                return ("sleep_test", {
                    "duration_s": dur,
                    "settle_s": 1,
                    "max_avg_ua": 10,
                }, None, "trace")
            elif "tx" in lower_name or "burst" in lower_name or "transmit" in lower_name:
                return ("tx_burst_test", {
                    "duration_s": dur,
                    "interval_ms": 100,
                    "max_peak_ma": 50,
                    "max_avg_ma": 5,
                }, None, "trace")
            else:
                # Generic measurement block
                return ("simulated_power", {
                    "duration_s": dur,
                    "sample_rate_hz": 1000,
                }, None, "trace")
        else:
            return ("shell_cmd", {"command": "echo step", "timeout_s": 30}, "trigger", "stdout")

    if a_type == "flash":
        fw = action.get("firmware", "")
        return ("shell_cmd", {
            "command": f"nrfjprog --program {fw} --chiperase --verify --reset",
            "timeout_s": 60,
        }, "trigger", "stdout")

    if a_type == "reset_target":
        return ("shell_cmd", {
            "command": "nrfjprog --reset",
            "timeout_s": 10,
        }, "trigger", "stdout")

    if a_type == "set_voltage":
        v = action.get("voltage_v", 3.3)
        return ("constant", {"value": str(v), "dtype": "float"}, None, "value")

    if a_type == "enable_output":
        on = action.get("on", True)
        return ("constant", {"value": str(on), "dtype": "bool"}, None, "value")

    if a_type == "snapshot":
        return ("aoi_camera", {
            "mode": "simulated",
            "width": 640,
            "height": 480,
        }, None, "frame")

    if a_type == "inspect":
        ref = action.get("board_id", "")
        return ("aoi_inspect", {
            "reference": ref,
            "tolerance": action.get("tolerance", 30),
        }, "frame", "result")

    if a_type == "thermal_capture":
        return ("seek_thermal", {
            "mode": "simulated",
            "base_temp_c": 25,
        }, None, "thermal")

    if a_type == "rf_sweep":
        return ("http_request", {
            "url": "http://localhost:5200/api/rf_sweep",
            "method": "POST",
        }, "body", "response")

    if a_type == "set_power_mode":
        mode = action.get("mode", "source")
        return ("constant", {"value": mode, "dtype": "str"}, None, "value")

    # Default: mark
    return ("log_message", {
        "prefix": f"{a_type}_{index}",
        "level": "info",
    }, "data", "data")


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _topo_sort(blocks_raw: list[dict], wires_raw: list[dict]) -> list[str]:
    """Topological sort using Kahn's algorithm (same as FlowLab engine)."""
    block_map = {b["id"]: b for b in blocks_raw}
    in_edges: dict[str, set[str]] = defaultdict(set)

    for w in wires_raw:
        src_blk = w["from"]["block"]
        dst_blk = w["to"]["block"]
        in_edges[dst_blk].add(src_blk)

    in_degree = {bid: 0 for bid in block_map}
    for bid, deps in in_edges.items():
        if bid in in_degree:
            in_degree[bid] = len(deps)

    queue: deque[str] = deque()
    for bid, deg in in_degree.items():
        if deg == 0:
            queue.append(bid)

    order: list[str] = []
    while queue:
        bid = queue.popleft()
        order.append(bid)
        for w in wires_raw:
            if w["from"]["block"] == bid:
                dst = w["to"]["block"]
                in_degree[dst] -= 1
                if in_degree[dst] == 0:
                    queue.append(dst)

    # Add any unreachable blocks at the end
    for bid in block_map:
        if bid not in order:
            order.append(bid)

    return order


def _empty_profile(name: str = "empty") -> dict[str, Any]:
    """Return a minimal valid HIL profile."""
    return {
        "name": name,
        "description": "Empty profile",
        "instruments": {"power_meter": {"type": "simulated", "params": {}}},
        "recorders": [],
        "steps": [],
    }
