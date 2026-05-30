"""Shared helpers for importing Zephyr projects and exporting generated targets."""

from __future__ import annotations

from dataclasses import asdict
import pathlib
from typing import Iterable

from board_schema import board_to_frontend
from boards import BOARDS
from dts_generator import ExternalDeviceConfig, PinAssignment, PeripheralConfig, generate
from overlay_parser import ImportResult, import_result_to_json, parse_import


def get_board_definition(board_ref: str):
    if not board_ref:
        return None

    builder = BOARDS.get(board_ref)
    if builder is not None:
        return builder()

    for board_id, board_builder in BOARDS.items():
        board = board_builder()
        if board.board == board_ref or board_id == board_ref:
            return board

    return None


def scan_zephyr_project(project_path: str | pathlib.Path) -> list[dict]:
    project = pathlib.Path(project_path)
    if not project.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {project}")

    found: list[dict] = []
    search_dirs = [project]
    boards_dir = project / "boards"
    if boards_dir.is_dir():
        search_dirs.append(boards_dir)

    for directory in search_dirs:
      for file_path in sorted(directory.iterdir()):
          if file_path.is_file() and file_path.suffix in (".overlay", ".conf"):
              found.append({
                  "path": str(file_path),
                  "relative": str(file_path.relative_to(project)),
                  "name": file_path.name,
                  "type": file_path.suffix.lstrip("."),
                  "size": file_path.stat().st_size,
                  "content": file_path.read_text(encoding="utf-8", errors="replace"),
              })

    prj_conf = project / "prj.conf"
    if prj_conf.is_file() and not any(entry["path"] == str(prj_conf) for entry in found):
        found.append({
            "path": str(prj_conf),
            "relative": "prj.conf",
            "name": prj_conf.name,
            "type": "conf",
            "size": prj_conf.stat().st_size,
            "content": prj_conf.read_text(encoding="utf-8", errors="replace"),
        })

    return found


def choose_project_files(scanned_files: Iterable[dict], overlay_paths: Iterable[str] | None = None,
                         conf_paths: Iterable[str] | None = None) -> tuple[list[dict], list[dict]]:
    overlay_set = {str(path) for path in (overlay_paths or []) if str(path).strip()}
    conf_set = {str(path) for path in (conf_paths or []) if str(path).strip()}

    overlays: list[dict] = []
    confs: list[dict] = []
    for entry in scanned_files:
        entry_path = str(entry.get("path", ""))
        entry_type = str(entry.get("type", ""))
        if overlay_set or conf_set:
            if entry_type == "overlay" and entry_path in overlay_set:
                overlays.append(entry)
            if entry_type == "conf" and entry_path in conf_set:
                confs.append(entry)
            continue

        if entry_type == "overlay" and not overlays:
            overlays.append(entry)
        elif entry_type == "conf":
            if entry.get("name") != "prj.conf" and not confs:
                confs.append(entry)
            elif not confs:
                confs.append(entry)

    return overlays, confs


def import_zephyr_project(project_path: str | pathlib.Path, *, board_name: str = "",
                          overlay_paths: Iterable[str] | None = None,
                          conf_paths: Iterable[str] | None = None) -> dict:
    scanned_files = scan_zephyr_project(project_path)
    overlays, confs = choose_project_files(scanned_files, overlay_paths=overlay_paths, conf_paths=conf_paths)

    overlay_text = "\n".join(entry.get("content", "") for entry in overlays)
    conf_text = "\n".join(entry.get("content", "") for entry in confs)
    imported = parse_import(overlay_text=overlay_text, conf_text=conf_text, board_name=board_name)
    return {
        "files": scanned_files,
        "selected_overlay_paths": [entry.get("path", "") for entry in overlays],
        "selected_conf_paths": [entry.get("path", "") for entry in confs],
        "import": import_result_to_json(imported),
        "import_result": imported,
    }


def _match_pin_assignment(board_payload: dict, parsed_pin: dict) -> PinAssignment | None:
    board_pin = next((pin for pin in board_payload.get("pins", [])
                      if str(pin.get("name", "")).upper() == str(parsed_pin.get("pin_name", "")).upper()), None)
    if not board_pin:
        return None

    alt_function = next((entry for entry in board_pin.get("alt_functions", [])
                         if entry.get("pincm") == parsed_pin.get("pincm")
                         and entry.get("function_id") == parsed_pin.get("function_id")), None)
    if alt_function is None:
        alt_function = next((entry for entry in board_pin.get("alt_functions", [])
                             if entry.get("peripheral") == parsed_pin.get("peripheral")
                             and entry.get("signal") == parsed_pin.get("signal")), None)
    if not alt_function:
        return None

    return PinAssignment(
        pin_name=str(board_pin.get("name", parsed_pin.get("pin_name", ""))),
        pincm=int(alt_function.get("pincm", parsed_pin.get("pincm", 0)) or 0),
        function_id=int(alt_function.get("function_id", parsed_pin.get("function_id", 0)) or 0),
        af_name=str(alt_function.get("name", parsed_pin.get("function_macro", ""))),
        peripheral=str(alt_function.get("peripheral", parsed_pin.get("peripheral", ""))),
        signal=str(alt_function.get("signal", parsed_pin.get("signal", ""))),
        direction=str(alt_function.get("direction", "io") or "io"),
        zephyr_pinmux=str(alt_function.get("zephyr_pinmux", "") or ""),
        bias_pull_up=bool(parsed_pin.get("bias_pull_up")),
        bias_pull_down=bool(parsed_pin.get("bias_pull_down")),
        drive_open_drain=bool(parsed_pin.get("drive_open_drain")),
        input_enable=bool(parsed_pin.get("input_enable")),
    )


def _match_peripherals(board_payload: dict, parsed_result: dict) -> list[PeripheralConfig]:
    parsed_peripherals = {
        str(peripheral.get("name", "")): peripheral
        for peripheral in parsed_result.get("peripherals", [])
    }
    peripherals: list[PeripheralConfig] = []
    for peripheral in board_payload.get("peripherals", []):
        parsed = parsed_peripherals.get(str(peripheral.get("name", "")), {})
        peripherals.append(PeripheralConfig(
            name=str(peripheral.get("name", "")),
            dts_node=str(peripheral.get("dts_node", "")),
            compatible=str(peripheral.get("compatible", "")),
            enabled=bool(parsed.get("enabled", False)),
            core_id=str(peripheral.get("core_id", "") or ""),
        ))
    return peripherals


def generate_from_import(board_ref: str, imported_result: dict, *, targets: list[str] | None = None,
                         external_devices: Iterable[dict] | None = None):
    board = get_board_definition(board_ref)
    if board is None:
        raise KeyError(f"Unknown board: {board_ref}")

    board_payload = board_to_frontend(board)
    assignments = []
    for parsed_pin in imported_result.get("pins", []):
        assignment = _match_pin_assignment(board_payload, parsed_pin)
        if assignment is not None:
            assignments.append(assignment)

    peripherals = _match_peripherals(board_payload, imported_result)
    device_configs = [
        ExternalDeviceConfig(**{
            key: value for key, value in device.items()
            if key in {field.name for field in ExternalDeviceConfig.__dataclass_fields__.values()}
        })
        for device in (external_devices or [])
    ]

    generated = generate(
        assignments,
        peripherals,
        board_name=board.board,
        targets=targets,
        external_devices=device_configs,
    )
    return generated


def export_generated_target(target_dir: str | pathlib.Path, files: dict[str, str], *, sketch_name: str = "") -> dict:
    destination = pathlib.Path(target_dir)
    destination.mkdir(parents=True, exist_ok=True)

    normalized_name = sketch_name.strip() or destination.name.strip() or "sketch"
    written: dict[str, str] = {}
    for filename, content in files.items():
        output_name = filename
        if filename.lower().endswith(".ino"):
            output_name = f"{normalized_name}.ino"
        output_path = destination / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        written[output_name] = str(output_path)

    return written


def describe_generated_output(generated) -> dict:
    return {
        "overlay": generated.overlay,
        "prj_conf": generated.prj_conf,
        "targets": generated.targets,
    }
