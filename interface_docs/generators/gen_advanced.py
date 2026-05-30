"""Additional low-level batch generators ported from yaml_docs-style workflows."""

from __future__ import annotations

import copy
import logging
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import yaml

from . import c_type_name, detect_hex_enum_types, load_yaml
from .gen_python import gen_python_driver


log = logging.getLogger(__name__)
REFERENCE_PREFIX = "EXT__"


def gen_xml_canether(data: dict, types: dict, od_name: str) -> str:
    merged = _merge_types(data, [], preloaded_types=types)
    od = _get_od(merged)
    lines = ["<?xml version = '1.0'?>", "", f"<ObjectDictionary type=\"{od_name.upper()}\" >"]
    for group_name, group in od.items():
        lines.append("")
        lines.append(f"    <group name=\"{group_name.upper()}\">")
        for entry_name, entry in group.items():
            lines.append(
                "        <ODE"
                f" name=\"{entry_name.upper()}\""
                f" mlx=\"{hex(entry['mlx'])}\""
                f" type=\"{_xml_atomic_type(entry['type'], merged['types'], entry_name)}\""
                f" RW=\"{_rw_flags(entry)}\"/>"
            )
        lines.append("    </group>")
    lines.append("")
    lines.append("</ObjectDictionary>")
    return "\n".join(lines) + "\n"


def gen_c_types(target: dict, base_dir: Path) -> str:
    data = _merge_types(load_yaml(base_dir / target["source"]), [base_dir / dep for dep in target.get("dependencies", [])])
    _prepare_types_for_codegen(data)
    _resolve_struct_fields(data["types"], ignore_naming=False)

    includes = _collect_includes(target)
    guard = f"INC_{Path(target['output']).stem.upper()}_H"
    lines = ["/*", " *  GENERATED FILE - DO NOT EDIT", " */", "", f"#ifndef {guard}", f"#define {guard}", ""]
    for include in includes:
        lines.append(f"#include {include}")
    if includes:
        lines.append("")

    for type_name, type_data in data["types"].items():
        fmt = type_data["format"]
        c_name = type_data["c_name"]
        if fmt == "bitfield":
            lines.append(f"typedef struct {c_name}")
            lines.append("{")
            base_type = f"uint{type_data['size']}_t" if type_data["size"] <= 32 else "uint32_t"
            for field_name, field_data in type_data["fields"].items():
                lines.append(f"    {base_type} {field_name}: {field_data['size']};")
            lines.append(f"}} {c_name};")
            lines.append("")
        elif fmt == "enum":
            lines.append(f"typedef enum {c_name}")
            lines.append("{")
            for enum_name, enum_value in type_data["values"].items():
                if isinstance(enum_value, int):
                    lines.append(f"    {enum_name} = {enum_value},")
                else:
                    lines.append(f"    {enum_name},")
            lines.append(f"}} {c_name};")
            lines.append("")
        elif fmt == "array":
            lines.append(f"typedef uint{type_data['bit_width']}_t {c_name}[{type_data['length']}];")
            lines.append("")
        elif fmt == "struct":
            lines.append(f"typedef struct {c_name}")
            lines.append("{")
            for field_name, field_data in type_data["fields"].items():
                lines.append(f"    {_field_c_type(field_data)} {field_name};")
            lines.append(f"}} {c_name};")
            lines.append("")

    lines.append("#endif")
    return "\n".join(lines) + "\n"


def gen_c_od(target: dict, base_dir: Path) -> str:
    data = _prepare_od_job(target, base_dir, ignore_naming=False)
    includes = _collect_includes(target)
    guard = f"INC_{Path(target['output']).stem.upper()}_H"
    od = _get_od(data)

    lines = ["/*", " *  GENERATED FILE - DO NOT EDIT", " */", "", f"#ifndef {guard}", f"#define {guard}", ""]
    for include in includes:
        lines.append(f"#include {include}")
    if includes:
        lines.append("")

    for group_name, group in od.items():
        for obj_name, obj_value in group.items():
            lines.append(f"#define {group_name.upper()}_{obj_name.upper()}_MLX {obj_value['mlx']}")
    lines.append("")

    for group_name, group in od.items():
        lines.append(f"#define {group_name.upper()}_MLX(STRUCT) \\")
        entries = []
        for obj_name, obj_value in group.items():
            write_flag = "SDO_WRITE" if "write" in obj_value["flags"] else "SDO_NOWRITE"
            macro_name = "MLX_DEF_MACRO_STORED" if "stored" in obj_value["flags"] else "MLX_DEF_MACRO"
            entries.append(
                f"    {macro_name}(STRUCT.{obj_value['c_name']}, {group_name.upper()}_{obj_name.upper()}_MLX, SDO_READ, {write_flag})"
            )
        lines.append(", \\\n".join(entries))
        lines.append("")

    lines.append("#endif")
    return "\n".join(lines) + "\n"


def gen_xml_od(target: dict, base_dir: Path) -> str:
    data = _prepare_od_job(target, base_dir, ignore_naming=True)
    od = _get_od(data)
    od_name = target.get("template_params", {}).get("od_name") or target.get("od_name", "Generated")
    lines = ["<?xml version = '1.0'?>", "", f"<ObjectDictionary type=\"{od_name}\" >", ""]

    for group_name, group in od.items():
        lines.append(f"<group name=\"{group_name.upper()}\">")
        for obj_name, obj_value in group.items():
            lines.append(
                f"    <ODE name=\"{obj_name.upper()}\" mlx=\"{obj_value['mlx']}\""
                f" type=\"{_xml_od_type(obj_value['type'])}\" RW=\"{obj_value['flags']}\"/>"
            )
        lines.append("</group>")
    lines.append("")
    lines.append("</ObjectDictionary>")
    return "\n".join(lines) + "\n"


def gen_py_alias(target: dict, base_dir: Path) -> str:
    source_path = base_dir / target["source"]
    dep_paths = [base_dir / dep for dep in target.get("dependencies", [])]
    data = _merge_types(load_yaml(source_path), dep_paths)
    od_name = target.get("template_params", {}).get("od_name") or target.get("od_name", "Generated")
    enum_formats = detect_hex_enum_types([source_path, *dep_paths])
    return gen_python_driver(data, data.get("types", {}), od_name, enum_formats=enum_formats)


def gen_xml_to_yaml(target: dict, base_dir: Path) -> str:
    source_path = base_dir / target["source"]
    parsed = _parse_xml_od(source_path)
    yaml_data = {
        "interface": {
            "title": target.get("title") or parsed["title"],
            "transport": "canopen",
            "canopen": {
                "object dictionary": {
                    group["name"]: {
                        entry["name"]: {
                            "mlx": int(entry["mlx"], 16),
                            "flags": entry["flags"],
                            "type": entry["type"],
                        }
                        for entry in group["entries"]
                    }
                    for group in parsed["groups"]
                }
            },
        }
    }
    return yaml.safe_dump(yaml_data, sort_keys=False)


def gen_c_pdo_macro(target: dict, base_dir: Path) -> str:
    source_path = base_dir / target["source"]
    data = load_yaml(source_path)
    dep_paths = [base_dir / dep for dep in target.get("dependencies", [])]
    objdict = _merge_included_object_dictionary([source_path, *dep_paths])
    types = _merge_types({}, dep_paths).get("types", {})
    _update_sizes_for_objects(types, objdict)
    includes = _collect_includes(target)
    guard = f"INC_{Path(target['output']).stem.upper()}_H"

    lines = ["/*", " *  GENERATED FILE - DO NOT EDIT", " */", "", f"#ifndef {guard}", f"#define {guard}", ""]
    for include in includes:
        lines.append(f"#include {include}")
    if includes:
        lines.append("")

    pdo = data.get("pdo", {})
    generated_names: list[str] = []
    for component, tracks in pdo.items():
        for track, track_data in tracks.items():
            if not isinstance(track_data, dict):
                continue
            name = f"{component}_{track}".upper()
            generated_names.append(name)
            lines.append(f"#define {name} \\")
            lines.append("    { \\")
            for current in track_data.get("data", []):
                sdo_name = current["sdo_name"] if isinstance(current, dict) else current
                package, module = sdo_name.split(":", 1)
                obj = objdict[package][module]
                lines.append(
                    f"        /* {package}:{module} mlx={hex(obj['mlx'])} size={obj['data_size']} */ \\")
            lines.append("    }")
            lines.append("")

    roles = sorted({_pdo_role_name(name) for name in generated_names})
    for role in roles:
        for suffix in ("RX", "TX"):
            matching = [name for name in generated_names if _pdo_role_name(name) == role and name.endswith(suffix)]
            lines.append(f"#define {role}_{suffix}_PDO_DEFAULTS {{ \\")
            for match in matching:
                lines.append(f"    {match}, \\")
            lines.append("    PDO_CONFIG_TERMINATOR, \\")
            lines.append("}")
            lines.append("")

    lines.append("#endif")
    return "\n".join(lines) + "\n"


def _prepare_od_job(target: dict, base_dir: Path, *, ignore_naming: bool) -> dict:
    data = _merge_types(load_yaml(base_dir / target["source"]), [base_dir / dep for dep in target.get("dependencies", [])])
    _prepare_types_for_codegen(data)
    od = _get_od(data)
    _resolve_struct_fields(data["types"], ignore_naming=ignore_naming)
    _generate_groups_from_types(od, data["types"], ignore_naming=ignore_naming)
    _compile_multiplexors(od, data["types"])
    if ignore_naming:
        _resolve_rw_flags(od)
    return data


def _merge_types(data: dict, dep_paths: list[Path], *, preloaded_types: dict | None = None) -> dict:
    merged = copy.deepcopy(data)
    merged.setdefault("types", {})
    if preloaded_types:
        merged["types"].update(copy.deepcopy(preloaded_types))
    for dep_path in dep_paths:
        dep_data = load_yaml(dep_path)
        merged["types"].update(copy.deepcopy(dep_data.get("types", {})))
    return merged


def _collect_includes(target: dict) -> list[str]:
    includes = list(target.get("includes", []))
    template_params = target.get("template_params", {})
    for include in template_params.get("includes", []):
        if include not in includes:
            includes.append(include)
    return includes


def _prepare_types_for_codegen(data: dict) -> None:
    _precalc_data_sizes(data["types"])
    _precalc_enum_values(data["types"])
    _generate_c_names(data["types"])


def _precalc_data_sizes(types: dict) -> None:
    for type_data in types.values():
        size = type_data.get("size")
        if isinstance(size, int):
            continue
        if type_data.get("format") == "array":
            type_data["size"] = type_data["bit_width"] * type_data["length"]
        elif type_data.get("format") == "bitfield":
            type_data["size"] = sum(field["size"] for field in type_data.get("fields", {}).values())


def _precalc_enum_values(types: dict) -> None:
    for type_data in types.values():
        if type_data.get("format") != "enum":
            continue
        next_value = 0
        for name, value in list(type_data.get("values", {}).items()):
            if isinstance(value, int):
                next_value = value + 1
            else:
                type_data["values"][name] = next_value
                next_value += 1


def _generate_c_names(types: dict) -> None:
    for type_name, type_data in types.items():
        type_data["type_name"] = type_name
        type_data["c_name"] = type_name
        naming = type_data.get("codegen", {}).get("c", {}).get("naming")
        if naming != "snake_case":
            continue
        new_type_name = "".join("_" + ch.lower() if ch.isupper() else ch for ch in type_name).lstrip("_")
        fmt = type_data["format"]
        if fmt == "bitfield":
            new_type_name = f"{new_type_name}_tst"
        elif fmt == "enum":
            new_type_name = f"{new_type_name}_ten"
        elif fmt == "struct":
            new_type_name = f"{new_type_name}_tst"
        elif fmt == "array":
            new_type_name = f"{new_type_name}_tau{type_data['bit_width']}"
        type_data["c_name"] = new_type_name


def _resolve_struct_fields(types: dict, *, ignore_naming: bool) -> None:
    for type_name, type_data in types.items():
        if type_data.get("format") != "struct":
            continue
        resolved_fields = {}
        for field_name, field_data in type_data.get("fields", {}).items():
            current = field_data
            if isinstance(field_data, str) and field_data.startswith(REFERENCE_PREFIX):
                current = copy.deepcopy(types[field_data[len(REFERENCE_PREFIX):]])
            if not ignore_naming and type_data.get("codegen", {}).get("c", {}).get("naming") == "snake_case":
                field_name = _snake_case(field_name)
            resolved_fields[field_name] = current
        type_data["fields"] = resolved_fields


def _generate_groups_from_types(od: dict, types: dict, *, ignore_naming: bool) -> None:
    for group in od.values():
        names = tuple(group.keys())
        for name in names:
            obj = group[name]
            if name != "__struct":
                continue
            type_name = obj["fields"][len(REFERENCE_PREFIX):]
            type_data = types[type_name]
            for field_name, field_data in type_data["fields"].items():
                group[_snake_case(field_name) if not ignore_naming and type_data.get("codegen", {}).get("c", {}).get("naming") == "snake_case" else field_name] = {
                    "mlx": obj["mlx"],
                    "type": field_data,
                    "flags": obj["flags"],
                }
            del group["__struct"]


def _compile_multiplexors(od: dict, types: dict) -> None:
    mlx_db: dict[int, int] = {}
    for group in od.values():
        for name, obj in group.items():
            type_ref = obj["type"]
            if isinstance(type_ref, str) and type_ref.startswith(REFERENCE_PREFIX):
                obj["type"] = copy.deepcopy(types[type_ref[len(REFERENCE_PREFIX):]])
            mlx = obj["mlx"]
            if isinstance(mlx, str) and mlx.endswith("+"):
                mlx_group = int(mlx[:-1], 0)
                mlx_db.setdefault(mlx_group, mlx_group & 0xFF)
                mlx_db[mlx_group] += 1
                obj["mlx"] = hex(mlx_group + mlx_db[mlx_group])
            elif isinstance(mlx, int):
                obj["mlx"] = hex(mlx)
            obj["c_name"] = _get_var_name(name, obj["type"])


def _resolve_rw_flags(od: dict) -> None:
    for group in od.values():
        for obj in group.values():
            obj["flags"] = _rw_flags(obj)


def _get_od(data: dict) -> dict:
    return data["interface"]["canopen"]["object dictionary"]


def _rw_flags(entry: dict) -> str:
    flags = entry.get("flags", [])
    if isinstance(flags, str):
        return flags
    return ("R" if "read" in flags else "") + ("W" if "write" in flags else "") or "R"


def _xml_atomic_type(type_ref: str | dict, types: dict, object_name: str) -> str:
    if isinstance(type_ref, str):
        if type_ref.startswith(REFERENCE_PREFIX):
            type_name = type_ref[len(REFERENCE_PREFIX):]
            return _xml_atomic_type(types[type_name], types, type_name)
        if type_ref in ("string", "bytearray"):
            return type_ref
        raise ValueError(f"Unknown type {type_ref} in {object_name}")
    fmt = type_ref["format"]
    size = type_ref.get("size", 0)
    if fmt in ("enum", "union", "bitfield"):
        return f"uint{size}"
    if fmt in ("int", "uint"):
        return f"{fmt}{size}"
    if fmt == "float":
        return f"real{size}"
    if fmt == "bool":
        return f"uint{size}"
    if fmt == "bytearray":
        return "bytearray"
    raise ValueError(f"Unknown type format {fmt} in {object_name}")


def _xml_od_type(type_ref: str | dict) -> str:
    if type_ref == "string":
        return "string"
    if isinstance(type_ref, dict):
        fmt = type_ref["format"]
        size = type_ref.get("size", 0)
        if fmt in ("bitfield", "enum", "uint"):
            return f"uint{size}" if size <= 32 else "bytearray"
        if fmt == "int":
            return f"int{size}"
        if fmt == "array":
            return "bytearray"
    return "unknown"


def _field_c_type(field_data: str | dict) -> str:
    if isinstance(field_data, dict):
        return field_data.get("c_name") or c_type_name(field_data)
    if isinstance(field_data, str) and field_data.startswith(REFERENCE_PREFIX):
        return f"{field_data[len(REFERENCE_PREFIX):]}"
    return c_type_name(field_data)


def _snake_case(name: str) -> str:
    return "".join("_" + ch.lower() if ch.isupper() else ch for ch in name).lstrip("_")


def _get_var_name(name: str, type_data: str | dict) -> str:
    if isinstance(type_data, dict):
        fmt = type_data["format"]
        if fmt == "bitfield":
            postfix = "_st"
        elif fmt == "struct":
            postfix = "_st"
        elif fmt == "uint":
            postfix = f"_u{type_data['size']}"
        elif fmt == "int":
            postfix = f"_s{type_data['size']}"
        elif fmt == "enum":
            postfix = "_en"
        elif fmt == "array":
            postfix = f"_au{type_data['bit_width']}"
        else:
            postfix = ""
    else:
        postfix = "_ac" if type_data == "string" else ""
    return name if postfix and name.endswith(postfix) else f"{name}{postfix}"


def _parse_xml_od(xml_file: str | Path) -> dict:
    root = ET.parse(xml_file).getroot()
    data = {"title": root.attrib.get("title") or root.attrib.get("type", "MCU Interface"), "groups": []}
    for group_elem in root.findall("group"):
        group = {"name": group_elem.attrib.get("name", "unnamed_group").strip().lower(), "entries": []}
        for entry_elem in group_elem.findall("ODE"):
            group["entries"].append(
                {
                    "name": entry_elem.attrib.get("name", "unnamed_entry").strip().lower(),
                    "mlx": entry_elem.attrib.get("mlx", "0x000000"),
                    "flags": _parse_xml_flags(entry_elem.attrib.get("RW")),
                    "type": _parse_xml_type(entry_elem.attrib.get("type", "uint8")),
                }
            )
        data["groups"].append(group)
    return data


def _parse_xml_type(type_str: str) -> dict:
    type_str = type_str.strip().lower()
    if type_str.startswith("uint"):
        return {"format": "uint", "size": int(type_str.replace("uint", ""))}
    if type_str.startswith("int"):
        return {"format": "int", "size": int(type_str.replace("int", ""))}
    if type_str.startswith("real"):
        return {"format": "float", "size": int(type_str.replace("real", ""))}
    if type_str == "bool":
        return {"format": "bool", "size": 1}
    return {"format": type_str, "size": 0}


def _parse_xml_flags(rw_value: str | None) -> list[str]:
    rw_text = (rw_value or "R").strip().upper()
    if rw_text == "RW":
        return ["read", "write"]
    if rw_text == "W":
        return ["write"]
    return ["read"]


def _merge_included_object_dictionary(paths: list[Path]) -> dict:
    objdict: dict = {}
    for path in paths:
        data = load_yaml(path)
        current = data.get("interface", {}).get("canopen", {}).get("object dictionary", {})
        if current:
            objdict.update(copy.deepcopy(current))
    return objdict


def _update_sizes_for_objects(types: dict, objdict: dict) -> None:
    for group in objdict.values():
        for current in group.values():
            current_type = current.get("type")
            current["data_size"] = 0
            if isinstance(current_type, dict) and current_type.get("size"):
                current["data_size"] = current_type["size"]
            elif isinstance(current_type, str) and current_type.startswith(REFERENCE_PREFIX):
                exttype = current_type[len(REFERENCE_PREFIX):]
                if exttype in types and "size" in types[exttype]:
                    current["data_size"] = types[exttype]["size"]


def _pdo_role_name(name: str) -> str:
    parts = name.split("_")
    if len(parts) >= 3 and parts[-1] in {"RX", "TX"} and parts[-2].isdigit():
        return "_".join(parts[:-2])
    if len(parts) >= 2 and parts[-1] in {"RX", "TX"}:
        return "_".join(parts[:-1])
    return name
