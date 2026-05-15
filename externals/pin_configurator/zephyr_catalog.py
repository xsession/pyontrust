"""Zephyr-backed catalog of supported MCU boards and sensor bindings."""

from __future__ import annotations

import os
import pathlib
from typing import Iterable

import yaml


_HERE = pathlib.Path(__file__).resolve().parent
_CATALOG_CACHE: dict[str, dict] = {}


def _valid_zephyr_root(path: pathlib.Path) -> bool:
    return (
        path.is_dir()
        and (path / "boards").is_dir()
        and (path / "dts" / "bindings").is_dir()
    )


def _candidate_roots(preferred: str | os.PathLike[str] | None = None) -> Iterable[pathlib.Path]:
    seen: set[str] = set()

    def emit(path: pathlib.Path | None):
        if path is None:
            return
        resolved = str(path.expanduser().resolve(strict=False))
        if resolved in seen:
            return
        seen.add(resolved)
        yield pathlib.Path(resolved)

    if preferred:
        yield from emit(pathlib.Path(preferred))

    env_root = os.environ.get("ZEPHYR_BASE")
    if env_root:
        yield from emit(pathlib.Path(env_root))

    for parent in [_HERE, *_HERE.parents]:
        for candidate in (
            parent / "zephyr",
            parent / "locator_base" / "zephyr",
            parent / "WORK" / "codelayer" / "locator_base" / "zephyr",
            parent / "codelayer" / "locator_base" / "zephyr",
        ):
            yield from emit(candidate)


def detect_zephyr_root(preferred: str | os.PathLike[str] | None = None) -> pathlib.Path:
    if preferred:
        preferred_path = pathlib.Path(preferred).expanduser().resolve(strict=False)
        if _valid_zephyr_root(preferred_path):
            return preferred_path
        raise FileNotFoundError(
            f"Unable to locate a Zephyr tree at {preferred_path}. Provide a valid zephyr_root or set ZEPHYR_BASE."
        )

    for candidate in _candidate_roots(preferred):
        if _valid_zephyr_root(candidate):
            return candidate
    raise FileNotFoundError(
        "Unable to locate a Zephyr tree. Provide zephyr_root explicitly or set ZEPHYR_BASE."
    )


def _load_yaml(path: pathlib.Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _slug(value: str, fallback: str) -> str:
    raw = (value or "").strip().lower() or fallback
    cleaned = [char if char.isalnum() else "_" for char in raw]
    collapsed = "".join(cleaned).strip("_") or fallback
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed


def _flatten_soc_variants(entries: list[dict], prefix: str = "") -> list[str]:
    flattened = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        full_name = f"{prefix}/{name}" if prefix and name else (name or prefix)
        if full_name:
            flattened.append(full_name)
        flattened.extend(_flatten_soc_variants(entry.get("variants") or [], full_name))
    return flattened


def _binding_buses(data: dict, path: pathlib.Path) -> list[str]:
    buses = set()

    def walk_include(value):
        if isinstance(value, str):
            token = value.lower()
            if "i2c" in token:
                buses.add("i2c")
            if "spi" in token:
                buses.add("spi")
            if "uart" in token:
                buses.add("uart")
            if "can" in token:
                buses.add("can")
            if "gpio" in token:
                buses.add("gpio")
        elif isinstance(value, list):
            for item in value:
                walk_include(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk_include(item)

    walk_include(data.get("include"))

    file_name = path.name.lower()
    for bus in ("i2c", "spi", "uart", "can", "gpio"):
        if f"-{bus}" in file_name or f"_{bus}" in file_name:
            buses.add(bus)
    return sorted(buses)


def _binding_properties(data: dict) -> list[dict]:
    props = []
    properties = data.get("properties") if isinstance(data.get("properties"), dict) else {}
    for key, meta in properties.items():
        if not isinstance(meta, dict):
            continue
        props.append({
            "name": str(key),
            "type": str(meta.get("type") or meta.get("specifier-space") or "mixed"),
            "required": bool(meta.get("required", False)),
            "default": meta.get("default"),
            "enum": meta.get("enum") if isinstance(meta.get("enum"), list) else [],
            "description": str(meta.get("description") or "").strip(),
        })
    return sorted(props, key=lambda item: item["name"])


def build_mcu_catalog(zephyr_root: pathlib.Path) -> list[dict]:
    boards_root = zephyr_root / "boards"
    items = []
    for board_file in boards_root.rglob("board.yml"):
        data = _load_yaml(board_file)
        board = data.get("board") if isinstance(data.get("board"), dict) else {}
        name = str(board.get("name") or "").strip()
        if not name:
            continue
        items.append({
            "key": f"mcu:{name}",
            "kind": "mcu",
            "name": name,
            "label": str(board.get("full_name") or name),
            "vendor": str(board.get("vendor") or ""),
            "socs": _flatten_soc_variants(board.get("socs") or []),
            "board_path": str(board_file.relative_to(zephyr_root).as_posix()),
            "directory": str(board_file.parent.relative_to(zephyr_root).as_posix()),
            "parameters": {
                "vendor": str(board.get("vendor") or ""),
                "full_name": str(board.get("full_name") or name),
                "socs": _flatten_soc_variants(board.get("socs") or []),
            },
        })
    return sorted(items, key=lambda item: (item["vendor"], item["label"], item["name"]))


def build_sensor_catalog(zephyr_root: pathlib.Path) -> list[dict]:
    sensors_root = zephyr_root / "dts" / "bindings" / "sensor"
    merged: dict[str, dict] = {}

    for binding_file in sensors_root.rglob("*.yaml"):
        data = _load_yaml(binding_file)
        compatible = str(data.get("compatible") or "").strip()
        if not compatible:
            continue

        item = merged.setdefault(compatible, {
            "key": f"sensor:{compatible}",
            "kind": "sensor",
            "name": compatible.split(",", 1)[-1].upper(),
            "label": str(data.get("title") or compatible),
            "vendor": compatible.split(",", 1)[0],
            "compatible": compatible,
            "buses": [],
            "properties": [],
            "binding_paths": [],
            "description": "",
            "parameters": {},
        })

        for bus in _binding_buses(data, binding_file):
            if bus not in item["buses"]:
                item["buses"].append(bus)

        existing_props = {entry["name"]: entry for entry in item["properties"]}
        for prop in _binding_properties(data):
            existing_props.setdefault(prop["name"], prop)
        item["properties"] = sorted(existing_props.values(), key=lambda entry: entry["name"])

        rel_path = str(binding_file.relative_to(zephyr_root).as_posix())
        if rel_path not in item["binding_paths"]:
            item["binding_paths"].append(rel_path)

        if not item["description"]:
            item["description"] = str(data.get("description") or "").strip()

        item["parameters"] = {
            "compatible": compatible,
            "buses": sorted(item["buses"]),
            "properties": item["properties"],
        }

    return sorted(merged.values(), key=lambda item: (item["vendor"], item["label"], item["compatible"]))


def load_zephyr_catalog(preferred_root: str | os.PathLike[str] | None = None, refresh: bool = False) -> dict:
    zephyr_root = detect_zephyr_root(preferred_root)
    cache_key = str(zephyr_root)
    if not refresh and cache_key in _CATALOG_CACHE:
        return _CATALOG_CACHE[cache_key]

    mcus = build_mcu_catalog(zephyr_root)
    sensors = build_sensor_catalog(zephyr_root)
    catalog = {
        "root": cache_key,
        "summary": {
            "mcu_count": len(mcus),
            "sensor_count": len(sensors),
        },
        "mcus": mcus,
        "sensors": sensors,
    }
    _CATALOG_CACHE[cache_key] = catalog
    return catalog