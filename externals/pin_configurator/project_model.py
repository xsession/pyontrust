"""Canonical project document helpers for the Pin Configurator."""

from __future__ import annotations

from copy import deepcopy


PROJECT_FILE_VERSION = 1


_RENODE_DEFAULTS = {
    "lp_mspm0g3507": {
        "platform": "platforms/boards/ti/lp_mspm0g3507.repl",
        "uart": "sysbus.uart0",
    },
    "rpi_pico": {
        "platform": "platforms/cpus/raspberrypi/rp2040.repl",
        "uart": "sysbus.uart0",
    },
}


def default_renode_profile(board_id: str | None) -> dict:
    board_key = str(board_id or "").strip()
    defaults = _RENODE_DEFAULTS.get(board_key, {})
    return {
        "enabled": bool(defaults),
        "platform": defaults.get("platform", ""),
        "resc": "",
        "robot": "",
        "uart": defaults.get("uart", "sysbus.uart0"),
        "boot_line": "Pin Configurator demo boot",
        "appbench_target": "appbench",
        "robot_target": "robotbench",
    }


def build_project_document(body: dict | None) -> dict:
    payload = body or {}
    board_id = payload.get("board_id", "")
    renode = default_renode_profile(board_id)
    renode.update(deepcopy(payload.get("renode") or {}))

    return {
        "version": PROJECT_FILE_VERSION,
        "board_id": board_id,
        "pin_states": deepcopy(payload.get("pin_states") or {}),
        "periph_states": deepcopy(payload.get("periph_states") or {}),
        "periph_core_states": deepcopy(payload.get("periph_core_states") or {}),
        "external_device_states": deepcopy(payload.get("external_device_states") or {}),
        "protocol_editor": deepcopy(payload.get("protocol_editor") or {}),
        "lvgl_layout": deepcopy(payload.get("lvgl_layout") or {}),
        "generated_overlay": str(payload.get("generated_overlay") or ""),
        "generated_conf": str(payload.get("generated_conf") or ""),
        "generated_fragments": deepcopy(payload.get("generated_fragments") or {}),
        "sensor_jobs": deepcopy(payload.get("sensor_jobs") or []),
        "sensor_selected": payload.get("sensor_selected", ""),
        "mcu_jobs": deepcopy(payload.get("mcu_jobs") or []),
        "mcu_selected": payload.get("mcu_selected", ""),
        "arduino_workspace": deepcopy(payload.get("arduino_workspace") or {}),
        "renode": renode,
        "tabs": deepcopy(payload.get("tabs") or {}),
    }


def normalize_project_document(document: dict | None) -> dict:
    source = document or {}
    normalized = build_project_document(source)
    normalized["version"] = int(source.get("version") or PROJECT_FILE_VERSION)
    return normalized