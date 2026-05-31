"""Helpers for generating Package Manager artifact bundles."""

from __future__ import annotations

import math
import re
import textwrap
from typing import Optional

from dts_generator import ExternalDeviceConfig, PeripheralConfig, PinAssignment, generate as generate_targets
from pdf_parser import DatasheetInfo, PackageInfo
from sensor_parser import SensorDatasheetInfo, generate_sensor_driver_package


_MCU_COMPAT_MAP = {
    "gpio": "ti,mspm0-gpio",
    "uart": "ti,mspm0-uart",
    "spi": "ti,mspm0-spi",
    "i2c": "ti,mspm0-i2c",
    "can": "ti,mspm0-can",
    "tima": "ti,mspm0-timer-pwm",
    "timg": "ti,mspm0-timer",
    "adc": "ti,mspm0-adc",
    "dac": "ti,mspm0-dac",
    "comp": "ti,mspm0-comp",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_") or "package"


def _positive_number(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _package_type(name: str, fallback: str = "") -> str:
    source = str(fallback or name or "").upper()
    for token in ("LQFP", "QFP", "TQFP", "QFN", "UFQFPN", "VFQFPN", "DFN", "LGA", "BGA", "UFBGA", "TFBGA", "WLCSP", "CSP", "SOIC", "SSOP", "TSSOP"):
        if token in source:
            return token
    return fallback.upper() if fallback else "QFN"


def _default_geometry(package_type: str, pin_count: int) -> tuple[float, float, float, float]:
    package_type = package_type.upper()
    if package_type in {"LQFP", "QFP", "TQFP"}:
        if pin_count <= 32:
            return 7.0, 7.0, 0.8, 1.4
        if pin_count <= 48:
            return 7.0, 7.0, 0.5, 1.4
        if pin_count <= 64:
            return 10.0, 10.0, 0.5, 1.4
        if pin_count <= 100:
            return 14.0, 14.0, 0.5, 1.4
        if pin_count <= 144:
            return 20.0, 20.0, 0.5, 1.4
        return 28.0, 28.0, 0.5, 1.4
    if package_type in {"QFN", "UFQFPN", "VFQFPN", "DFN", "LGA"}:
        if pin_count <= 8:
            return 3.0, 3.0, 0.5, 0.9
        if pin_count <= 16:
            return 4.0, 4.0, 0.5, 0.9
        if pin_count <= 32:
            return 5.0, 5.0, 0.5, 0.9
        return 7.0, 7.0, 0.5, 0.9
    if package_type in {"WLCSP", "BGA", "UFBGA", "TFBGA", "CSP"}:
        grid = max(2, math.ceil(math.sqrt(max(pin_count, 1))))
        pitch = 0.4 if package_type == "WLCSP" else 0.8
        size = round((grid - 1) * pitch + 1.2, 2)
        return size, size, pitch, 1.0
    if package_type in {"SOIC", "SSOP", "TSSOP"}:
        width = 3.9 if pin_count <= 8 else 4.4 if pin_count <= 16 else 6.1
        height = max(4.9, (pin_count / 2) * 0.65 + 1.5)
        pitch = 1.27 if package_type == "SOIC" else 0.65
        return width, round(height, 2), pitch, 1.5
    return 5.0, 5.0, 0.5, 1.0


def package_info_from_mcu(package: PackageInfo) -> dict:
    return {
        "name": package.name,
        "pin_count": package.pin_count,
        "pins": [
            {
                "number": pin.number,
                "name": pin.name,
                "kind": pin.kind,
            }
            for pin in package.pins
        ],
    }


def normalize_package(package: dict, overrides: Optional[dict] = None) -> dict:
    overrides = overrides or {}
    pins = list(package.get("pins") or [])
    pin_count = int(overrides.get("pin_count") or package.get("pin_count") or len(pins) or 0)
    package_type = _package_type(str(overrides.get("package_type") or package.get("package_type") or package.get("name") or ""))
    width_default, height_default, pitch_default, thickness_default = _default_geometry(package_type, pin_count)
    width_mm = _positive_number(overrides.get("width_mm")) or _positive_number(package.get("width_mm")) or width_default
    height_mm = _positive_number(overrides.get("height_mm")) or _positive_number(package.get("height_mm")) or height_default
    pitch_mm = _positive_number(overrides.get("pitch_mm")) or _positive_number(package.get("pitch_mm")) or pitch_default
    thickness_mm = _positive_number(overrides.get("thickness_mm")) or _positive_number(package.get("thickness_mm")) or thickness_default
    rows = max(2, math.ceil(math.sqrt(max(pin_count, 1)))) if package_type in {"WLCSP", "BGA", "UFBGA", "TFBGA", "CSP"} else 0
    cols = max(rows, math.ceil(max(pin_count, 1) / rows)) if rows else 0
    name = str(overrides.get("package_name") or package.get("name") or f"{package_type}-{pin_count}").strip() or f"{package_type}-{pin_count}"
    return {
        "name": name,
        "package_type": package_type,
        "pin_count": pin_count,
        "pins": pins,
        "width_mm": float(width_mm),
        "height_mm": float(height_mm),
        "pitch_mm": float(pitch_mm),
        "thickness_mm": float(thickness_mm),
        "rows": rows,
        "cols": cols,
    }


def _pad_name(pin: dict, index: int) -> str:
    number = pin.get("number")
    return str(number if number not in (None, "") else index)


def _escape_kicad_string(value: object) -> str:
    return str(value or "").replace('"', "'")


def _pad_metadata(pin: dict) -> str:
    name = str(pin.get("name") or "").strip()
    if not name:
        return ""
    upper = name.upper()
    if any(token in upper for token in ("GND", "VSS", "VDD", "VCC", "VBAT", "VREF", "VIO")):
        pin_type = "power_in"
    elif upper in {"NC", "DNC"}:
        pin_type = "no_connect"
    else:
        pin_type = "passive"
    return f' (pinfunction "{_escape_kicad_string(name)}") (pintype "{pin_type}")'


def _exposed_pad(pin: dict) -> bool:
    name = str(pin.get("name") or "").upper()
    return "EP" in name or "PAD" in name or name.startswith("THERMAL")


def _mm(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _quad_pad_lines(package: dict) -> list[str]:
    pins = package["pins"] or [{"number": index + 1, "name": str(index + 1)} for index in range(package["pin_count"])]
    perimeter = [pin for pin in pins if not _exposed_pad(pin)] or pins
    exposed = [pin for pin in pins if _exposed_pad(pin)]
    per_side = max(1, math.ceil(len(perimeter) / 4))
    pitch = package["pitch_mm"]
    pad_short = max(0.22, round(pitch * 0.55, 3))
    pad_long = 0.8 if package["package_type"] in {"QFN", "UFQFPN", "VFQFPN", "DFN", "LGA"} else 1.4
    offset_x = package["width_mm"] / 2 + pad_long / 2 + 0.25
    offset_y = package["height_mm"] / 2 + pad_long / 2 + 0.25
    span = (per_side - 1) * pitch / 2
    lines: list[str] = []

    for index, pin in enumerate(perimeter):
        side = min(3, index // per_side)
        side_index = index % per_side
        if side == 0:
            x = -offset_x
            y = span - side_index * pitch
            size_x, size_y = pad_long, pad_short
        elif side == 1:
            x = -span + side_index * pitch
            y = offset_y
            size_x, size_y = pad_short, pad_long
        elif side == 2:
            x = offset_x
            y = -span + side_index * pitch
            size_x, size_y = pad_long, pad_short
        else:
            x = span - side_index * pitch
            y = -offset_y
            size_x, size_y = pad_short, pad_long
        lines.append(
            f'  (pad "{_pad_name(pin, index + 1)}" smd rect (at {_mm(x)} {_mm(y)}) (size {_mm(size_x)} {_mm(size_y)}) (layers "F.Cu" "F.Paste" "F.Mask"){_pad_metadata(pin)})'
        )

    if exposed:
        ep_size_x = max(package["width_mm"] * 0.45, 1.0)
        ep_size_y = max(package["height_mm"] * 0.45, 1.0)
        lines.append(
            f'  (pad "{_pad_name(exposed[0], len(perimeter) + 1)}" smd rect (at 0 0) (size {_mm(ep_size_x)} {_mm(ep_size_y)}) (layers "F.Cu" "F.Paste" "F.Mask"){_pad_metadata(exposed[0])})'
        )
    return lines


def _bga_pad_lines(package: dict) -> list[str]:
    pins = package["pins"] or [{"number": index + 1, "name": str(index + 1)} for index in range(package["pin_count"])]
    rows = package["rows"] or max(2, math.ceil(math.sqrt(len(pins))))
    cols = package["cols"] or max(rows, math.ceil(len(pins) / rows))
    pitch = package["pitch_mm"]
    pad = max(0.2, round(pitch * 0.5, 3))
    x0 = -((cols - 1) * pitch) / 2
    y0 = -((rows - 1) * pitch) / 2
    lines: list[str] = []
    for index, pin in enumerate(pins):
        row = index // cols
        col = index % cols
        x = x0 + col * pitch
        y = y0 + row * pitch
        lines.append(
            f'  (pad "{_pad_name(pin, index + 1)}" smd circle (at {_mm(x)} {_mm(y)}) (size {_mm(pad)} {_mm(pad)}) (layers "F.Cu" "F.Paste" "F.Mask"){_pad_metadata(pin)})'
        )
    return lines


def generate_kicad_footprint(package: dict, component_name: str) -> str:
    normalized = normalize_package(package)
    module_name = f"{slugify(component_name)}_{slugify(normalized['name'])}"
    silk_w = normalized["width_mm"] / 2
    silk_h = normalized["height_mm"] / 2
    courtyard_x = silk_w + 1.0
    courtyard_y = silk_h + 1.0
    pad_lines = _bga_pad_lines(normalized) if normalized["package_type"] in {"WLCSP", "BGA", "UFBGA", "TFBGA", "CSP"} else _quad_pad_lines(normalized)
    return "\n".join([
        f'(module "{module_name}" (layer "F.Cu")',
        f'  (descr "Auto-generated {normalized["name"]} footprint for {component_name}")',
        '  (attr smd)',
        f'  (fp_text reference "REF**" (at 0 -{_mm(courtyard_y + 1.2)}) (layer "F.SilkS"))',
        '  (fp_text value "${VALUE}" (at 0 0) (layer "F.Fab"))',
        f'  (fp_line (start -{_mm(silk_w)} -{_mm(silk_h)}) (end {_mm(silk_w)} -{_mm(silk_h)}) (layer "F.SilkS") (width 0.12))',
        f'  (fp_line (start {_mm(silk_w)} -{_mm(silk_h)}) (end {_mm(silk_w)} {_mm(silk_h)}) (layer "F.SilkS") (width 0.12))',
        f'  (fp_line (start {_mm(silk_w)} {_mm(silk_h)}) (end -{_mm(silk_w)} {_mm(silk_h)}) (layer "F.SilkS") (width 0.12))',
        f'  (fp_line (start -{_mm(silk_w)} {_mm(silk_h)}) (end -{_mm(silk_w)} -{_mm(silk_h)}) (layer "F.SilkS") (width 0.12))',
        f'  (fp_circle (center -{_mm(silk_w + 0.6)} -{_mm(silk_h + 0.6)}) (end -{_mm(silk_w + 0.35)} -{_mm(silk_h + 0.6)}) (layer "F.SilkS") (width 0.12))',
        f'  (fp_line (start -{_mm(courtyard_x)} -{_mm(courtyard_y)}) (end {_mm(courtyard_x)} -{_mm(courtyard_y)}) (layer "F.CrtYd") (width 0.05))',
        f'  (fp_line (start {_mm(courtyard_x)} -{_mm(courtyard_y)}) (end {_mm(courtyard_x)} {_mm(courtyard_y)}) (layer "F.CrtYd") (width 0.05))',
        f'  (fp_line (start {_mm(courtyard_x)} {_mm(courtyard_y)}) (end -{_mm(courtyard_x)} {_mm(courtyard_y)}) (layer "F.CrtYd") (width 0.05))',
        f'  (fp_line (start -{_mm(courtyard_x)} {_mm(courtyard_y)}) (end -{_mm(courtyard_x)} -{_mm(courtyard_y)}) (layer "F.CrtYd") (width 0.05))',
        *pad_lines,
        ')',
    ])


def generate_wrl_model(package: dict, component_name: str) -> str:
    normalized = normalize_package(package)
    width = normalized["width_mm"] / 1000.0
    height = normalized["height_mm"] / 1000.0
    thickness = normalized["thickness_mm"] / 1000.0
    return textwrap.dedent(
        f'''
        #VRML V2.0 utf8
        WorldInfo {{ title "{component_name} {normalized['name']}" }}
        Transform {{
          children [
            Shape {{
              appearance Appearance {{
                material Material {{ diffuseColor 0.12 0.12 0.12 specularColor 0.3 0.3 0.3 }}
              }}
              geometry Box {{ size {width:.6f} {height:.6f} {thickness:.6f} }}
            }}
          ]
        }}
        '''
    ).strip()


def _guess_compatible(peripheral: str) -> str:
    lowered = peripheral.lower()
    for prefix, compatible in _MCU_COMPAT_MAP.items():
        if lowered.startswith(prefix):
            return compatible
    return f"vendor,{lowered}"


def _external_devices(external_devices: Optional[list[dict]]) -> list[ExternalDeviceConfig]:
    configs: list[ExternalDeviceConfig] = []
    for device in external_devices or []:
        if not isinstance(device, dict):
            continue
        device_id = str(device.get("id", "")).strip()
        if not device_id:
            continue
        configs.append(
            ExternalDeviceConfig(
                id=device_id,
                display=str(device.get("display", device_id)).strip(),
                category=str(device.get("category", "device")),
                bus=str(device.get("bus", "")),
                compatible=str(device.get("compatible", "")),
                address=str(device.get("address", "")),
                required_signals=[str(signal) for signal in device.get("required_signals", [])],
                frameworks=[str(framework) for framework in device.get("frameworks", [])],
                notes=str(device.get("notes", "")),
            )
        )
    return configs


def build_mcu_framework_outputs(
    info: DatasheetInfo,
    package: PackageInfo,
    board_name: str,
    external_devices: Optional[list[dict]] = None,
) -> dict[str, str]:
    package_pin_names = {pin.name for pin in package.pins}
    used_pins: set[str] = set()
    assignments: list[PinAssignment] = []
    peripheral_names: list[str] = []

    for pin in package.pins:
        for entry in info.pin_mux.get(pin.name, []):
            if pin.name in used_pins:
                break
            if not entry.peripheral or entry.peripheral.startswith("gpio") or not entry.signal:
                continue
            if any(existing.peripheral == entry.peripheral and existing.signal == entry.signal for existing in assignments):
                continue
            assignments.append(
                PinAssignment(
                    pin_name=pin.name,
                    pincm=entry.pincm,
                    function_id=entry.function_id,
                    af_name=entry.function_name,
                    peripheral=entry.peripheral,
                    signal=entry.signal,
                    direction=entry.direction,
                )
            )
            used_pins.add(pin.name)
            if entry.peripheral not in peripheral_names:
                peripheral_names.append(entry.peripheral)
            break

    if not assignments:
        for pin_name, entries in info.pin_mux.items():
            if pin_name not in package_pin_names:
                continue
            for entry in entries:
                if entry.peripheral.startswith("gpio"):
                    continue
                assignments.append(
                    PinAssignment(
                        pin_name=pin_name,
                        pincm=entry.pincm,
                        function_id=entry.function_id,
                        af_name=entry.function_name,
                        peripheral=entry.peripheral,
                        signal=entry.signal,
                        direction=entry.direction,
                    )
                )
                if entry.peripheral not in peripheral_names:
                    peripheral_names.append(entry.peripheral)
                if len(assignments) >= 4:
                    break
            if len(assignments) >= 4:
                break

    peripherals = [
        PeripheralConfig(
            name=peripheral,
            dts_node=f"&{peripheral}",
            compatible=_guess_compatible(peripheral),
            enabled=True,
        )
        for peripheral in peripheral_names
    ]

    generated = generate_targets(
        assignments,
        peripherals,
        board_name=board_name,
        targets=["zephyr", "arduino"],
        external_devices=_external_devices(external_devices),
    )

    files: dict[str, str] = {}
    for target_name in ("zephyr", "arduino"):
        for path, content in (generated.targets.get(target_name) or {}).items():
            files[f"{slugify(package.name)}/{target_name}/{path}"] = content
    return files


def build_sensor_framework_outputs(
    info: SensorDatasheetInfo,
    driver_name: Optional[str] = None,
    compatible: Optional[str] = None,
    bus: Optional[str] = None,
    custom_template: str = "",
    custom_template_path: str = "",
) -> dict[str, str]:
    part = info.summary.part_number or "sensor"
    vendor = info.summary.vendor or "vendor"
    resolved_name = driver_name or slugify(part)
    resolved_compatible = compatible or f"{vendor},{part.lower()}"
    resolved_bus = bus or ("spi" if "spi" in info.address.protocol.lower() and "i2c" not in info.address.protocol.lower() else "i2c")
    package = generate_sensor_driver_package(
        info,
        name=resolved_name,
        compatible=resolved_compatible,
        bus=resolved_bus,
        custom_template=custom_template,
        custom_template_path=custom_template_path,
    )
    outputs = {
        f"sensor/{resolved_name}.c": package.get("source_c", ""),
        f"sensor/{resolved_name}.h": package.get("header_h", ""),
        "sensor/Kconfig": package.get("kconfig", ""),
        "sensor/CMakeLists.txt": package.get("cmake", ""),
        "sensor/sample.overlay": package.get("overlay_sample", ""),
        "sensor/prj.conf": package.get("prj_conf_sample", ""),
        "sensor/README.md": package.get("readme", ""),
        f"sensor/{resolved_name}_test.c": package.get("test_c", ""),
        "sensor/register_header.h": package.get("register_header", ""),
        "sensor/register_defines.h": package.get("register_defines", ""),
        f"arduino/{resolved_name}.h": package.get("arduino_header", ""),
        f"arduino/{resolved_name}.cpp": package.get("arduino_source", ""),
        f"arduino/{resolved_name}.ino": package.get("arduino_example", ""),
    }
    template_output = package.get("custom_template_output", "")
    if template_output:
        outputs[package.get("custom_template_path") or f"custom/{resolved_name}_template.txt"] = template_output
    return outputs


def artifact_entries(files: dict[str, str], group: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path, content in files.items():
        if not content:
            continue
        entries.append({
            "id": path,
            "label": path.split("/")[-1],
            "path": path,
            "group": group,
            "content": content,
        })
    return entries