"""Directory scaffold generators for pyontrust-native GUI apps and test sequences."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

from generators.gen_python import gen_python_driver


_RENDER_ENV = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class ScaffoldContext:
    output_root: Path
    title: str
    transport: str
    driver_class_name: str
    driver_module_name: str
    summary: dict[str, Any]
    metadata: dict[str, Any]
    read_methods: list[str]
    write_methods: list[str]
    python_driver_source: str
    slug: str
    class_base_name: str
    extra: dict[str, Any]


def gen_gui_app_scaffold(job_context) -> None:
    scaffold = _build_scaffold_context(job_context)
    output_root = scaffold.output_root
    _prepare_output_root(output_root, overwrite_if_exists=bool(job_context.target.get("overwrite_if_exists", False)))

    context = {
        **_default_gui_context(scaffold, job_context),
        **_collect_extra_context(job_context.target, job_context.base_dir),
    }
    _validate_required(context, ("app_name", "route_prefix", "page_title", "api_prefix", "default_port"))

    _render_tree(_TEMPLATES_DIR / "gui_app", output_root, context)
    (output_root / "driver.py").write_text(scaffold.python_driver_source, encoding="utf-8")


def gen_test_sequence_scaffold(job_context) -> None:
    scaffold = _build_scaffold_context(job_context)
    output_root = scaffold.output_root
    _prepare_output_root(output_root, overwrite_if_exists=bool(job_context.target.get("overwrite_if_exists", False)))

    context = {
        **_default_test_context(scaffold, job_context),
        **_collect_extra_context(job_context.target, job_context.base_dir),
    }
    _validate_required(
        context,
        (
            "sequence_class_name",
            "device_label",
            "device_key",
            "board_module",
            "board_symbol",
            "hil_app_path",
        ),
    )

    _render_tree(_TEMPLATES_DIR / "test_sequence", output_root, context)
    (output_root / "driver.py").write_text(scaffold.python_driver_source, encoding="utf-8")


def _build_scaffold_context(job_context) -> ScaffoldContext:
    interface = job_context.data.get("interface", {})
    title = str(interface.get("title") or job_context.source_path.stem)
    transport = str(interface.get("transport") or "canopen")
    class_base_name = str(job_context.target.get("od_name") or _camel_case(_strip_interface_suffix(title)))
    driver_class_name = f"{class_base_name}OD" if transport == "canopen" else f"{class_base_name}Driver"
    driver_module_name = str(job_context.target.get("driver_module_name") or "driver")
    summary = _build_summary(job_context.data)
    metadata = _build_metadata(job_context.data)
    method_lists = _extract_method_names(job_context.data)
    python_driver_source = gen_python_driver(
        job_context.data,
        job_context.types,
        class_base_name,
        enum_formats=job_context.enum_formats,
    )
    return ScaffoldContext(
        output_root=job_context.output_path,
        title=title,
        transport=transport,
        driver_class_name=driver_class_name,
        driver_module_name=driver_module_name,
        summary=summary,
        metadata=metadata,
        read_methods=method_lists["read_methods"],
        write_methods=method_lists["write_methods"],
        python_driver_source=python_driver_source,
        slug=_snake_case(_strip_interface_suffix(title)),
        class_base_name=class_base_name,
        extra=_collect_extra_context(job_context.target, job_context.base_dir),
    )


def _default_gui_context(scaffold: ScaffoldContext, job_context) -> dict[str, Any]:
    app_name = str(job_context.target.get("app_name") or _strip_interface_suffix(scaffold.title))
    route_prefix = str(job_context.target.get("route_prefix") or f"/{scaffold.slug}")
    return {
        "title": scaffold.title,
        "transport": scaffold.transport,
        "driver_class_name": scaffold.driver_class_name,
        "driver_module_name": scaffold.driver_module_name,
        "summary_json": json.dumps(scaffold.summary, indent=2, sort_keys=True),
        "metadata_json": json.dumps(scaffold.metadata, indent=2, sort_keys=True),
        "read_methods_json": json.dumps(scaffold.read_methods, indent=2),
        "write_methods_json": json.dumps(scaffold.write_methods, indent=2),
        "app_name": app_name,
        "page_title": str(job_context.target.get("page_title") or f"{app_name} Dashboard"),
        "route_prefix": route_prefix,
        "route_segment": route_prefix.strip("/") or scaffold.slug,
        "api_prefix": str(job_context.target.get("api_prefix") or f"{route_prefix}/api"),
        "default_host": str(job_context.target.get("host") or "127.0.0.1"),
        "default_port": int(job_context.target.get("port") or 5210),
        "app_version": str(job_context.target.get("app_version") or "0.1.0"),
        "build_backend": str(job_context.target.get("build_backend") or "pyinstaller"),
        "build_icon_path": str(job_context.target.get("build_icon_path") or ""),
    }


def _default_test_context(scaffold: ScaffoldContext, job_context) -> dict[str, Any]:
    sequence_class_name = str(
        job_context.target.get("sequence_class_name") or f"{scaffold.class_base_name}Sequence"
    )
    device_label = str(job_context.target.get("device_label") or _strip_interface_suffix(scaffold.title))
    device_key = str(job_context.target.get("device_key") or scaffold.slug)
    return {
        "title": scaffold.title,
        "transport": scaffold.transport,
        "driver_class_name": scaffold.driver_class_name,
        "driver_module_name": scaffold.driver_module_name,
        "summary_json": json.dumps(scaffold.summary, indent=2, sort_keys=True),
        "metadata_json": json.dumps(scaffold.metadata, indent=2, sort_keys=True),
        "read_methods_json": json.dumps(scaffold.read_methods, indent=2),
        "write_methods_json": json.dumps(scaffold.write_methods, indent=2),
        "sequence_class_name": sequence_class_name,
        "device_label": device_label,
        "device_key": device_key,
        "device_serial_regex": str(job_context.target.get("device_serial_regex") or f"{device_key.upper()}-(\\d+)"),
        "board_module": str(job_context.target.get("board_module") or "pyontrust.boards.locator_base"),
        "board_symbol": str(job_context.target.get("board_symbol") or "LOCATOR_BASE"),
        "hil_app_path": str(job_context.target.get("hil_app_path") or "samples/basic/blink"),
        "report_name": str(job_context.target.get("report_name") or f"{device_key}_hil_report.json"),
    }


def _build_summary(data: dict[str, Any]) -> dict[str, Any]:
    interface = data.get("interface", {})
    transport = str(interface.get("transport") or "")
    summary: dict[str, Any] = {
        "title": interface.get("title", "Generated Interface"),
        "transport": transport,
    }

    if transport == "canopen":
        objdict = interface.get("canopen", {}).get("object dictionary", {})
        summary["group_count"] = len(objdict)
        summary["field_count"] = sum(len(group or {}) for group in objdict.values())
    elif transport == "uart":
        commands = interface.get("uart", {}).get("commands", [])
        summary["command_count"] = len(commands)
    elif transport == "rs485":
        registers = interface.get("rs485", {}).get("modbus", {}).get("registers", {})
        summary["register_count"] = sum(len(registers.get(group, []) or []) for group in ("holding", "input", "coil", "discrete"))
    elif transport in {"tcp/udp", "tcp", "udp"}:
        tcpudp = interface.get("tcp/udp", {}) or interface.get("tcp_udp", {}) or interface.get("tcp", {}) or interface.get("udp", {})
        summary["command_count"] = len(tcpudp.get("commands", []) or [])
        summary["message_count"] = len(tcpudp.get("messages", []) or [])
    elif transport == "i2c":
        devices = interface.get("i2c", {}).get("devices", []) or []
        summary["device_count"] = len(devices)
        summary["register_count"] = sum(len(device.get("registers", []) or []) for device in devices)
    elif transport == "spi":
        devices = interface.get("spi", {}).get("devices", []) or []
        summary["device_count"] = len(devices)
        summary["command_count"] = sum(len(device.get("commands", []) or []) for device in devices)

    return summary


def _build_metadata(data: dict[str, Any]) -> dict[str, Any]:
    interface = data.get("interface", {})
    transport = str(interface.get("transport") or "")

    if transport == "canopen":
        object_dictionary = interface.get("canopen", {}).get("object dictionary", {})
        return {
            "groups": {
                group_name: {
                    field_name: {
                        "mlx": field.get("mlx"),
                        "flags": field.get("flags", []),
                        "doc": field.get("doc", ""),
                        "unit": field.get("unit"),
                    }
                    for field_name, field in (fields or {}).items()
                }
                for group_name, fields in object_dictionary.items()
            }
        }
    if transport == "uart":
        commands = interface.get("uart", {}).get("commands", []) or []
        return {
            "commands": {
                command.get("name", f"cmd_{index}"): {
                    "id": command.get("id"),
                    "doc": command.get("doc", ""),
                    "flags": command.get("flags", []),
                }
                for index, command in enumerate(commands)
            }
        }
    if transport == "rs485":
        registers = interface.get("rs485", {}).get("modbus", {}).get("registers", {})
        return {
            "registers": {
                group_name: {
                    register.get("name", f"register_{index}"): {
                        "addr": register.get("addr"),
                        "doc": register.get("doc", ""),
                        "flags": register.get("flags", []),
                        "unit": register.get("unit"),
                    }
                    for index, register in enumerate(registers.get(group_name, []) or [])
                }
                for group_name in ("holding", "input", "coil", "discrete")
            }
        }
    if transport in {"tcp/udp", "tcp", "udp"}:
        tcpudp = interface.get("tcp/udp", {}) or interface.get("tcp_udp", {}) or interface.get("tcp", {}) or interface.get("udp", {})
        return {
            "commands": {
                command.get("name", f"command_{index}"): {
                    "id": command.get("id"),
                    "doc": command.get("doc", ""),
                }
                for index, command in enumerate(tcpudp.get("commands", []) or [])
            },
            "messages": {
                message.get("name", f"message_{index}"): {
                    "doc": message.get("doc", ""),
                }
                for index, message in enumerate(tcpudp.get("messages", []) or [])
            },
        }
    if transport in {"i2c", "spi"}:
        bus = interface.get(transport, {})
        devices = bus.get("devices", []) or []
        metadata: dict[str, Any] = {"devices": {}}
        for index, device in enumerate(devices):
            name = device.get("name", f"device_{index}")
            registers = device.get("registers", []) or []
            commands = device.get("commands", []) or []
            metadata["devices"][name] = {
                "address": device.get("address"),
                "part": device.get("part"),
                "doc": device.get("doc", ""),
                "registers": {
                    register.get("name", f"register_{reg_index}"): {
                        "addr": register.get("addr"),
                        "doc": register.get("doc", ""),
                        "flags": register.get("flags", []),
                        "unit": register.get("unit"),
                    }
                    for reg_index, register in enumerate(registers)
                },
                "commands": {
                    command.get("name", f"command_{cmd_index}"): {
                        "doc": command.get("doc", ""),
                    }
                    for cmd_index, command in enumerate(commands)
                },
            }
        return metadata
    return {}


def _extract_method_names(data: dict[str, Any]) -> dict[str, list[str]]:
    interface = data.get("interface", {})
    transport = str(interface.get("transport") or "")
    read_methods: list[str] = []
    write_methods: list[str] = []

    if transport == "canopen":
        object_dictionary = interface.get("canopen", {}).get("object dictionary", {})
        for fields in object_dictionary.values():
            for field_name, field in (fields or {}).items():
                flags = set(field.get("flags", []))
                if "read" in flags:
                    read_methods.append(f"read_{field_name}")
                if "write" in flags:
                    write_methods.append(f"write_{field_name}")
    elif transport == "rs485":
        registers = interface.get("rs485", {}).get("modbus", {}).get("registers", {})
        for group_name, values in registers.items():
            for register in values or []:
                name = register.get("name")
                if not name:
                    continue
                flags = set(register.get("flags", []))
                if group_name in {"input", "discrete"} or "read" in flags:
                    read_methods.append(f"read_{name}")
                if group_name in {"holding", "coil"} and "write" in flags:
                    write_methods.append(f"write_{name}")
    elif transport == "i2c":
        for device in interface.get("i2c", {}).get("devices", []) or []:
            device_name = device.get("name") or "device"
            for register in device.get("registers", []) or []:
                register_name = register.get("name") or "register"
                flags = set(register.get("flags", []))
                if "read" in flags:
                    read_methods.append(f"read_{device_name}_{register_name}")
                if "write" in flags:
                    write_methods.append(f"write_{device_name}_{register_name}")
    return {
        "read_methods": sorted(dict.fromkeys(read_methods)),
        "write_methods": sorted(dict.fromkeys(write_methods)),
    }


def _prepare_output_root(output_root: Path, overwrite_if_exists: bool) -> None:
    if output_root.exists():
        if not overwrite_if_exists:
            raise FileExistsError(f"Output directory already exists: {output_root}")
        if not output_root.is_dir():
            raise FileExistsError(f"Output target exists but is not a directory: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)


def _render_tree(template_root: Path, output_root: Path, context: dict[str, Any]) -> None:
    for source_item in sorted(template_root.rglob("*")):
        relative_path = source_item.relative_to(template_root)
        rendered_parts = [_render_string(part, context) for part in relative_path.parts]
        target_path = output_root.joinpath(*rendered_parts)
        if source_item.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        final_target = target_path
        if final_target.suffix == ".j2":
            final_target = final_target.with_suffix("")

        final_target.parent.mkdir(parents=True, exist_ok=True)
        template_text = source_item.read_text(encoding="utf-8")
        final_target.write_text(_render_string(template_text, context), encoding="utf-8")


def _render_string(template_text: str, context: dict[str, Any]) -> str:
    return _RENDER_ENV.from_string(template_text).render(**context)


def _collect_extra_context(target: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    raw_context = target.get("context", {}) or {}
    if not isinstance(raw_context, dict):
        raise ValueError("Scaffold job 'context' must be a mapping")

    context = dict(raw_context)
    context_file = target.get("context_file")
    if context_file:
        context_path = Path(context_file)
        if not context_path.is_absolute():
            context_path = base_dir / context_path
        context.update(json.loads(context_path.read_text(encoding="utf-8")))
    return context


def _validate_required(context: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if not context.get(key)]
    if missing:
        raise ValueError(f"Missing required scaffold context values: {', '.join(missing)}")


def _strip_interface_suffix(value: str) -> str:
    return value.replace(" Interface", "").strip()


def _snake_case(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_")
    slug = re.sub(r"_+", "_", slug).lower()
    if not slug:
        return "generated_interface"
    if slug[0].isdigit():
        return f"iface_{slug}"
    return slug


def _camel_case(value: str) -> str:
    parts = re.split(r"[^0-9A-Za-z]+", value)
    normalized = "".join(part[:1].upper() + part[1:] for part in parts if part)
    if not normalized:
        return "GeneratedInterface"
    if normalized[0].isdigit():
        return f"Interface{normalized}"
    return normalized