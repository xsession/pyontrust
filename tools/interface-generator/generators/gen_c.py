"""C code generators — typedefs, object dictionaries, register headers."""

from __future__ import annotations

from . import c_type_name, get_jinja_env, upper_snake


# ── C typedef generator ─────────────────────────────────────────


def gen_c_typedefs(data: dict, includes: list[str]) -> str:
    types_raw = data.get("types", {})
    types = []

    for tname, tdef in types_raw.items():
        fmt = tdef.get("format", "")
        entry: dict = {"name": tname, "format": fmt, "size": tdef.get("size", 0)}

        if fmt == "enum":
            entry["enum_values"] = [
                {"name": upper_snake(vname), "hex_value": format(vval, "#x")}
                for vname, vval in tdef.get("values", {}).items()
            ]
        elif fmt == "bitfield":
            entry["fields"] = [
                {"name": fname.lower(), "bits": fdef.get("size", 1)}
                for fname, fdef in tdef.get("fields", {}).items()
            ]
        elif fmt == "union":
            fields = []
            for fname, fdef in tdef.get("fields", {}).items():
                if isinstance(fdef, str) and fdef.startswith("EXT__"):
                    fields.append({"c_type": f"{fdef[5:]}_t", "name": fname})
                elif isinstance(fdef, dict):
                    fields.append({"c_type": c_type_name(fdef), "name": fname})
            entry["fields"] = fields

        types.append(entry)

    env = get_jinja_env()
    tpl = env.get_template("c_typedefs.h.j2")
    return tpl.render(guard="GENERATED_TYPES_H", includes=includes, types=types)


# ── C object dictionary generator (CANopen) ─────────────────────


def gen_c_objdict(data: dict, types: dict, includes: list[str]) -> str:
    iface = data.get("interface", {})
    title = iface.get("title", "Unknown")
    canopen = iface.get("canopen", {})
    od = canopen.get("object dictionary", {})

    guard = upper_snake(title.split()[0]) + "_CAN_IF_H"
    groups = []

    for group_name, group in od.items():
        defines = []
        entries = []

        for obj_name, obj in group.items():
            mlx = obj.get("mlx")
            if mlx is None:
                continue
            macro = f"{upper_snake(group_name)}_{upper_snake(obj_name)}_MLX"
            defines.append({"name": macro, "value": format(mlx, "#08x")})

            flags = obj.get("flags", [])
            read = "SDO_READ" if "read" in flags else "SDO_NOREAD"
            write = "SDO_WRITE" if "write" in flags else "SDO_NOWRITE"
            suffix = _c_var_suffix(obj.get("type", ""))
            entries.append(
                f"    MLX_DEF_MACRO( STRUCT.{obj_name}{suffix}, {macro:<55s} {read}, {write} )"
            )

        macro_name = f"{upper_snake(group_name)}_MLX"
        groups.append({
            "defines": defines,
            "macro_name": macro_name,
            "entries_block": ", \\\n".join(entries),
        })

    env = get_jinja_env()
    tpl = env.get_template("c_objdict.h.j2")
    return tpl.render(guard=guard, title=title, includes=includes, groups=groups)


def _c_var_suffix(yaml_type: str | dict) -> str:
    if isinstance(yaml_type, dict):
        size = yaml_type.get("size", 32)
        fmt = yaml_type.get("format", "uint")
        prefix = "i" if fmt == "int" else "u"
        return f"_{prefix}{size}"
    if isinstance(yaml_type, str):
        if yaml_type == "string":
            return "_ac"
        if yaml_type.startswith("EXT__"):
            stem = yaml_type[5:]
            if stem.endswith("_tun"):
                return "_un"
            return "_t"
        return f"_{yaml_type}"
    return ""


# ── C register header generators ────────────────────────────────


def gen_c_registers(data: dict, types: dict, includes: list[str], transport: str) -> str:
    iface = data.get("interface", {})
    title = iface.get("title", "Unknown")
    guard = upper_snake(title.replace(" ", "_")[:40]) + "_H"

    transport_data = iface.get(transport, iface.get("uart", iface.get("spi", {})))

    context: dict = {
        "guard": guard,
        "title": title,
        "includes": includes,
        "transport": transport,
    }

    if transport in ("uart",):
        context["uart"] = _prep_uart_context(transport_data)
    elif transport in ("rs485",):
        context["modbus"] = _prep_modbus_context(transport_data)
    elif transport in ("i2c",):
        context["i2c"] = _prep_i2c_context(transport_data)
    elif transport in ("spi",):
        context["spi"] = _prep_spi_context(transport_data)
    elif transport in ("tcp", "udp", "tcp/udp"):
        tcp = iface.get("tcp", {})
        udp = iface.get("udp", {})
        context["tcp"] = _prep_tcp_context(tcp) if tcp else None
        context["udp"] = _prep_udp_context(udp) if udp else None

    env = get_jinja_env()
    tpl = env.get_template("c_registers.h.j2")
    return tpl.render(**context)


def _prep_uart_context(uart: dict) -> dict:
    phys = uart.get("physical", {})
    framing = uart.get("framing", {})
    return {
        "tx_pin": phys.get("tx_pin", "?"),
        "rx_pin": phys.get("rx_pin", "?"),
        "baud_rate": phys.get("baud_rate", 115200),
        "start_byte": format(framing.get("start_byte", 0xAA), "#04x"),
        "end_byte": format(framing.get("end_byte", 0x55), "#04x"),
        "commands": [
            {"name": upper_snake(name), "id": format(cmd.get("id", 0), "#04x")}
            for name, cmd in uart.get("commands", {}).items()
        ],
    }


def _prep_modbus_context(rs485: dict) -> dict:
    modbus = rs485.get("modbus", {})
    register_groups = []
    for reg_type in ("holding", "input", "discrete"):
        regs = modbus.get("registers", {}).get(reg_type, [])
        if not regs:
            continue
        prefix = {"holding": "HREG", "input": "IREG", "discrete": "DREG"}[reg_type]
        register_groups.append({
            "prefix": prefix,
            "registers": [
                {"name": upper_snake(reg.get("name", "unknown")), "addr": format(reg.get("addr", 0), "#06x")}
                for reg in regs
            ],
        })
    return {
        "slave_id": format(modbus.get("slave_id", 0x01), "#04x"),
        "register_groups": register_groups,
    }


def _prep_i2c_context(i2c: dict) -> dict:
    devices = []
    for device in i2c.get("devices", []):
        dev_name = upper_snake(device.get("name", "dev"))
        addr = device.get("address", 0)
        regs = []
        for reg in device.get("registers", []):
            reg_addr = reg.get("addr")
            if reg_addr is None:
                continue
            regs.append({
                "name": upper_snake(reg.get("name", "unknown")),
                "addr": format(reg_addr, "#04x"),
            })
        devices.append({"name": dev_name, "addr": format(addr, "#04x"), "registers": regs})
    return {"devices": devices}


def _prep_spi_context(spi: dict) -> dict:
    phys = spi.get("physical", {})
    cs_pins = [
        {"device": upper_snake(cs.get("device", "dev")), "pin": repr(cs.get("pin", "?"))}
        for cs in phys.get("cs_pins", [])
    ]
    devices = []
    for device in spi.get("devices", []):
        dev_name = upper_snake(device.get("name", "dev"))
        cmds = [
            {"name": upper_snake(cname), "opcode": format(cmd.get("opcode", 0), "#04x")}
            for cname, cmd in device.get("commands", {}).items()
        ]
        regs = []
        for reg in device.get("registers", []):
            reg_addr = reg.get("addr")
            if reg_addr is None:
                continue
            regs.append({
                "name": upper_snake(reg.get("name", "unknown")),
                "addr": format(reg_addr, "#04x"),
            })
        devices.append({"name": dev_name, "commands": cmds, "registers": regs})
    return {
        "clock_hz": phys.get("clock_hz", 1000000),
        "mode": phys.get("mode", 0),
        "cs_pins": cs_pins,
        "devices": devices,
    }


def _prep_tcp_context(tcp: dict) -> dict:
    return {
        "port": tcp.get("port", 5200),
        "commands": [
            {"name": upper_snake(name), "id": format(cmd.get("id", 0), "#06x")}
            for name, cmd in tcp.get("commands", {}).items()
        ],
    }


def _prep_udp_context(udp: dict) -> dict:
    return {
        "port": udp.get("port", 5201),
        "messages": [
            {"name": upper_snake(name), "id": format(msg.get("id", 0), "#06x")}
            for name, msg in udp.get("messages", {}).items()
        ],
    }
