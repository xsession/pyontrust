"""Python driver stub generator."""

from __future__ import annotations

from . import get_jinja_env, py_type_name, upper_snake


def gen_python_driver(
    data: dict,
    types: dict,
    od_name: str,
    *,
    enum_formats: list[str] | None = None,
) -> str:
    iface = data.get("interface", {})
    title = iface.get("title", "Unknown")
    transport = iface.get("transport", "unknown")
    all_types = dict(types)
    all_types.update(data.get("types", {}))

    context: dict = {
        "title": title,
        "transport": transport,
        "od_name": od_name,
        "enum_tables": _collect_enum_tables(all_types, set(enum_formats or [])),
        "bitfield_definitions": _collect_bitfield_definitions(all_types),
    }

    if transport == "canopen":
        context.update(_prep_canopen(iface, od_name, all_types, set(enum_formats or [])))
    elif transport == "uart":
        context["uart"] = _prep_uart(iface, od_name, all_types)
    elif transport == "rs485":
        context["modbus"] = _prep_modbus(iface, od_name, all_types)
    elif transport in ("tcp/udp", "tcp", "udp"):
        context["tcpudp"] = _prep_tcpudp(iface, od_name, all_types)
    elif transport == "i2c":
        context["i2c"] = _prep_i2c(iface, all_types)
    elif transport == "spi":
        context["spi"] = _prep_spi(iface, all_types)

    env = get_jinja_env()
    tpl = env.get_template("py_driver.py.j2")
    return tpl.render(**context)


def _prep_canopen(iface: dict, od_name: str, types: dict, enum_formats: set[str]) -> dict:
    canopen = iface.get("canopen", {})
    od = canopen.get("object dictionary", {})

    constants = []
    methods = []
    field_metadata_by_group: dict[str, dict[str, dict]] = {}
    for group_name, group in od.items():
        group_metadata: dict[str, dict] = {}
        for obj_name, obj in group.items():
            mlx = obj.get("mlx")
            if mlx is None:
                continue
            const = f"{upper_snake(group_name)}_{upper_snake(obj_name)}_MLX"
            constants.append({"name": const, "value": format(mlx, "#08x")})
            flags = obj.get("flags", [])
            metadata = {
                "mlx": format(mlx, "#08x"),
                "flags": list(flags),
                "doc": obj.get("doc", ""),
                "path": f"{od_name.upper()}/{group_name.upper()}/{obj_name.upper()}",
                "type": _describe_type(obj.get("type"), types),
                "reader_name": f"read_{obj_name}" if "read" in flags else None,
                "writer_name": f"write_{obj_name}" if "write" in flags else None,
            }
            unit = _normalize_unit(obj.get("unit"))
            if unit is not None:
                metadata["unit"] = unit
            conversion = obj.get("conversion")
            if conversion:
                metadata["conversion"] = conversion
            plot = _extract_plot_config(obj)
            if plot is not None:
                metadata["plot"] = plot

            enum_name = _resolve_enum_type_name(obj.get("type"), types)
            if enum_name is not None:
                metadata["enum_table"] = upper_snake(enum_name)

            bitfield_name = _resolve_bitfield_type_name(obj.get("type"), types)
            if bitfield_name is not None:
                metadata["bitfield"] = upper_snake(bitfield_name)

            group_metadata[obj_name] = metadata
            if "read" in flags:
                methods.append({
                    "type": "read",
                    "name": obj_name,
                    "mlx": format(mlx, "#08x"),
                    "doc": obj.get("doc", ""),
                })
            if "write" in flags:
                methods.append({
                    "type": "write",
                    "name": obj_name,
                    "mlx": format(mlx, "#08x"),
                    "doc": obj.get("doc", ""),
                })
        field_metadata_by_group[group_name] = group_metadata

    return {
        "constants": constants,
        "methods": methods,
        "field_metadata_by_group": field_metadata_by_group,
        "has_conversions": any(
            metadata.get("conversion")
            for group in field_metadata_by_group.values()
            for metadata in group.values()
        ),
    }


def _collect_enum_tables(types: dict, enum_formats: set[str]) -> list[dict]:
    tables = []
    for type_name, type_def in types.items():
        if type_def.get("format") != "enum":
            continue
        entries = []
        for name, value in type_def.get("values", {}).items():
            rendered = format(value, "#x") if type_name in enum_formats and isinstance(value, int) else repr(value)
            entries.append({"name": name, "value_repr": rendered})
        tables.append({"name": type_name, "const_name": upper_snake(type_name), "entries": entries})
    return tables


def _collect_bitfield_definitions(types: dict) -> list[dict]:
    definitions = []
    for type_name, type_def in types.items():
        if type_def.get("format") != "bitfield":
            continue
        bits = []
        for bit_name, bit_def in type_def.get("fields", {}).items():
            bits.append({
                "name": bit_name,
                "size": bit_def.get("size", 1),
                "doc": bit_def.get("doc", ""),
            })
        definitions.append({"name": type_name, "const_name": upper_snake(type_name), "bits": bits})
    return definitions


def _resolve_type_definition(type_ref: str | dict | None, types: dict) -> tuple[str | None, dict | None]:
    if isinstance(type_ref, dict):
        return None, type_ref
    if isinstance(type_ref, str) and type_ref.startswith("EXT__"):
        type_name = type_ref[5:]
        return type_name, types.get(type_name)
    return None, None


def _resolve_enum_type_name(type_ref: str | dict | None, types: dict) -> str | None:
    type_name, type_def = _resolve_type_definition(type_ref, types)
    if type_def and type_def.get("format") == "enum":
        return type_name
    return None


def _resolve_bitfield_type_name(type_ref: str | dict | None, types: dict) -> str | None:
    type_name, type_def = _resolve_type_definition(type_ref, types)
    if type_def is None:
        return None

    if type_def.get("format") == "bitfield":
        return type_name

    if type_def.get("format") == "union":
        display_field = type_def.get("codegen", {}).get("py", {}).get("display")
        if not display_field:
            return None
        display_type = type_def.get("fields", {}).get(display_field)
        if isinstance(display_type, str) and display_type.startswith("EXT__"):
            bitfield_name = display_type[5:]
            bitfield_def = types.get(bitfield_name)
            if bitfield_def and bitfield_def.get("format") == "bitfield":
                return bitfield_name
    return None


def _describe_type(type_ref: str | dict | None, types: dict) -> str:
    type_name, type_def = _resolve_type_definition(type_ref, types)
    if type_name is not None:
        return type_name
    if isinstance(type_ref, dict):
        fmt = type_ref.get("format", "unknown")
        size = type_ref.get("size")
        return f"{fmt}{size}" if size is not None else fmt
    if isinstance(type_ref, str):
        return type_ref
    return "unknown"


def _normalize_unit(unit: object) -> str | None:
    if unit is None:
        return None
    normalized = str(unit).strip()
    unit_aliases = {
        "Â°C": "degC",
        "°C": "degC",
        "C": "degC",
    }
    return unit_aliases.get(normalized, normalized)


def _extract_plot_config(obj: dict) -> dict | None:
    codegen_py = obj.get("codegen", {}).get("py", {})
    if isinstance(codegen_py.get("plot"), dict):
        return dict(codegen_py["plot"])

    conversion_codegen = obj.get("conversion", {}).get("codegen", {}).get("py", {})
    if isinstance(conversion_codegen.get("plot"), dict):
        return dict(conversion_codegen["plot"])

    return None


def _prep_uart(iface: dict, od_name: str, types: dict) -> dict:
    uart = iface.get("uart", {})
    phys = uart.get("physical", {})

    cmd_constants = [
        {"name": upper_snake(name), "id": format(cmd.get("id", 0), "#04x")}
        for name, cmd in uart.get("commands", {}).items()
    ]

    commands = []
    command_metadata = {}
    for cmd_name, cmd in uart.get("commands", {}).items():
        req_fields = cmd.get("request", {}).get("fields", [])
        params = ", ".join(
            f"{f['name']}: {py_type_name(f.get('type', 'uint8'))}" for f in req_fields
        )
        sig = f"self, {params}" if params else "self"
        commands.append({"name": cmd_name, "sig": sig, "doc": cmd.get("doc", "")})
        command_metadata[cmd_name] = {
            "id": format(cmd.get("id", 0), "#04x"),
            "doc": cmd.get("doc", ""),
            "request_fields": [
                {
                    "name": field.get("name", ""),
                    "type": _describe_type(field.get("type"), types),
                    "doc": field.get("doc", ""),
                }
                for field in req_fields
            ],
            "response_fields": [
                {
                    "name": field.get("name", ""),
                    "type": _describe_type(field.get("type"), types),
                    "doc": field.get("doc", ""),
                }
                for field in cmd.get("response", {}).get("fields", [])
            ],
        }

    return {
        "baud_rate": phys.get("baud_rate", 115200),
        "cmd_constants": cmd_constants,
        "commands": commands,
        "command_metadata": command_metadata,
    }


def _prep_modbus(iface: dict, od_name: str, types: dict) -> dict:
    rs485 = iface.get("rs485", {})
    modbus = rs485.get("modbus", {})
    slave_id = format(modbus.get("slave_id", 0x01), "#04x")

    reg_constants = []
    for reg_type in ("holding", "input"):
        regs = modbus.get("registers", {}).get(reg_type, [])
        prefix = "HREG" if reg_type == "holding" else "IREG"
        for reg in regs:
            reg_constants.append({
                "prefix": prefix,
                "name": upper_snake(reg.get("name", "unknown")),
                "addr": format(reg.get("addr", 0), "#06x"),
            })

    holding_methods = []
    register_metadata = {"holding": {}, "input": {}, "discrete": {}}
    for reg in modbus.get("registers", {}).get("holding", []):
        name = reg.get("name", "unknown")
        flags = reg.get("flags", [])
        register_metadata["holding"][name] = _field_metadata(
            reg,
            reg.get("type"),
            types,
            path=f"{od_name.upper()}/HOLDING/{name.upper()}",
            flags=flags,
            extra={"addr": format(reg.get("addr", 0), "#06x"), "register_group": "holding"},
        )
        if "read" in flags:
            holding_methods.append({"type": "read", "name": name, "doc": reg.get("doc", "")})
        if "write" in flags:
            holding_methods.append({"type": "write", "name": name, "doc": reg.get("doc", "")})

    input_methods = []
    for reg in modbus.get("registers", {}).get("input", []):
        register_metadata["input"][reg.get("name", "unknown")] = _field_metadata(
            reg,
            reg.get("type"),
            types,
            path=f"{od_name.upper()}/INPUT/{reg.get('name', 'unknown').upper()}",
            flags=reg.get("flags", []),
            extra={"addr": format(reg.get("addr", 0), "#06x"), "register_group": "input"},
        )
        input_methods.append({"name": reg.get("name", "unknown"), "doc": reg.get("doc", "")})

    for reg in modbus.get("registers", {}).get("discrete", []):
        register_metadata["discrete"][reg.get("name", "unknown")] = {
            "addr": format(reg.get("addr", 0), "#06x"),
            "register_group": "discrete",
            "doc": reg.get("doc", ""),
            "flags": list(reg.get("flags", ["read"])),
            "path": f"{od_name.upper()}/DISCRETE/{reg.get('name', 'unknown').upper()}",
            "type": "bool",
        }

    return {
        "slave_id": slave_id,
        "reg_constants": reg_constants,
        "holding_methods": holding_methods,
        "input_methods": input_methods,
        "register_metadata": register_metadata,
    }


def _prep_tcpudp(iface: dict, od_name: str, types: dict) -> dict:
    tcp = iface.get("tcp", {})
    udp = iface.get("udp", {})

    cmd_constants = [
        {"name": upper_snake(name), "id": format(cmd.get("id", 0), "#06x")}
        for name, cmd in tcp.get("commands", {}).items()
    ]

    commands = []
    command_metadata = {}
    for cmd_name, cmd in tcp.get("commands", {}).items():
        req_fields = cmd.get("request", {}).get("fields", [])
        params = ", ".join(
            f"{f['name']}: {py_type_name(f.get('type', 'uint8'))}" for f in req_fields
        )
        sig = f"self, {params}" if params else "self"
        commands.append({"name": cmd_name, "sig": sig, "doc": cmd.get("doc", "")})
        command_metadata[cmd_name] = {
            "id": format(cmd.get("id", 0), "#06x"),
            "doc": cmd.get("doc", ""),
            "request_fields": [
                {
                    "name": field.get("name", ""),
                    "type": _describe_type(field.get("type"), types),
                    "doc": field.get("doc", ""),
                }
                for field in req_fields
            ],
        }

    message_metadata = {
        name: {
            "id": format(msg.get("id", 0), "#06x"),
            "doc": msg.get("doc", ""),
            "rate_hz": msg.get("rate_hz", 0),
        }
        for name, msg in udp.get("messages", {}).items()
    }

    return {
        "tcp_port": tcp.get("port") if tcp else None,
        "udp_port": udp.get("port") if udp else None,
        "default_port": tcp.get("port", 5200),
        "cmd_constants": cmd_constants,
        "commands": commands,
        "command_metadata": command_metadata,
        "message_metadata": message_metadata,
    }


def _prep_i2c(iface: dict, types: dict) -> dict:
    i2c = iface.get("i2c", {})

    addr_constants = [
        {"name": upper_snake(dev.get("name", "dev")), "addr": format(dev.get("address", 0), "#04x")}
        for dev in i2c.get("devices", [])
    ]

    methods = []
    device_metadata = {}
    for device in i2c.get("devices", []):
        dev_name = device.get("name", "dev")
        registers_metadata = {}
        for reg in device.get("registers", []):
            reg_name = reg.get("name", "unknown")
            flags = reg.get("flags", [])
            registers_metadata[reg_name] = _field_metadata(
                reg,
                reg.get("type"),
                types,
                path=f"{dev_name.upper()}/{reg_name.upper()}",
                flags=flags,
                extra={
                    "addr": format(reg.get("addr", 0), "#04x") if reg.get("addr") is not None else None,
                    "length": reg.get("length"),
                    "reset_value": reg.get("reset_value"),
                    "device_name": dev_name,
                },
            )
            if "read" in flags:
                methods.append({"type": "read", "dev": dev_name, "reg": reg_name, "doc": reg.get("doc", "")})
            if "write" in flags:
                methods.append({"type": "write", "dev": dev_name, "reg": reg_name, "doc": reg.get("doc", "")})

        device_metadata[dev_name] = {
            "address": format(device.get("address", 0), "#04x"),
            "part": device.get("part", ""),
            "doc": device.get("doc", ""),
            "registers": registers_metadata,
        }

    return {"addr_constants": addr_constants, "methods": methods, "device_metadata": device_metadata}


def _prep_spi(iface: dict, types: dict) -> dict:
    spi = iface.get("spi", {})

    methods = []
    device_metadata = {}
    for device in spi.get("devices", []):
        dev_name = device.get("name", "dev")
        device_entry = {
            "doc": device.get("doc", ""),
            "part": device.get("part", ""),
            "transactions": {},
            "commands": {},
        }
        for tx_name, tx in device.get("transactions", {}).items():
            methods.append({"dev": dev_name, "name": tx_name, "doc": tx.get("doc", "")})
            device_entry["transactions"][tx_name] = {
                "doc": tx.get("doc", ""),
                "type": tx.get("type", ""),
                "word_size": tx.get("word_size"),
            }
        for cmd_name, cmd in device.get("commands", {}).items():
            methods.append({"dev": dev_name, "name": cmd_name, "doc": cmd.get("doc", "")})
            device_entry["commands"][cmd_name] = {
                "doc": cmd.get("doc", ""),
                "opcode": format(cmd.get("opcode", 0), "#04x"),
                "addr_bytes": cmd.get("addr_bytes"),
            }
        device_metadata[dev_name] = device_entry

    return {"methods": methods, "device_metadata": device_metadata}


def _field_metadata(
    obj: dict,
    type_ref: str | dict | None,
    types: dict,
    *,
    path: str,
    flags: list[str],
    extra: dict | None = None,
) -> dict:
    metadata = {
        "doc": obj.get("doc", ""),
        "flags": list(flags),
        "path": path,
        "type": _describe_type(type_ref, types),
    }
    unit = _normalize_unit(obj.get("unit"))
    if unit is not None:
        metadata["unit"] = unit
    conversion = obj.get("conversion")
    if conversion:
        metadata["conversion"] = conversion
    plot = _extract_plot_config(obj)
    if plot is not None:
        metadata["plot"] = plot
    enum_name = _resolve_enum_type_name(type_ref, types)
    if enum_name is not None:
        metadata["enum_table"] = upper_snake(enum_name)
    bitfield_name = _resolve_bitfield_type_name(type_ref, types)
    if bitfield_name is not None:
        metadata["bitfield"] = upper_snake(bitfield_name)
    if extra:
        metadata.update({key: value for key, value in extra.items() if value is not None})
    return metadata
