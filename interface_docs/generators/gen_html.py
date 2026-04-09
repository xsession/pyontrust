"""HTML documentation generator."""

from __future__ import annotations

from . import get_jinja_env


def gen_html(data: dict, types: dict) -> str:
    iface = data.get("interface", {})
    title = iface.get("title", "Unknown Interface")
    transport = iface.get("transport", "unknown")

    context: dict = {
        "title": title,
        "transport": transport,
        "versions": _prep_versions(iface),
    }

    if transport == "canopen":
        context["canopen"] = _prep_canopen(iface)
    elif transport == "uart":
        context["uart"] = _prep_uart(iface)
    elif transport == "rs485":
        context["modbus"] = _prep_modbus(iface)
    elif transport in ("tcp/udp", "tcp", "udp"):
        context["tcpudp"] = _prep_tcpudp(iface)
    elif transport == "i2c":
        context["i2c"] = _prep_i2c(iface)
    elif transport == "spi":
        context["spi"] = _prep_spi(iface)

    env = get_jinja_env()
    tpl = env.get_template("html_doc.html.j2")
    return tpl.render(**context)


def _prep_versions(iface: dict) -> list[dict]:
    versions = iface.get("version history", [])
    return [
        {
            "fw_version": str(v.get("fw-version", "")),
            "date": str(v.get("date", "")),
            "author": str(v.get("author", "")),
            "changes": str(v.get("changes", "")),
        }
        for v in versions
    ]


def _prep_canopen(iface: dict) -> dict:
    canopen = iface.get("canopen", {})
    nodes = [
        {
            "name": n.get("name", ""),
            "id": format(n.get("id", 0), "02x"),
            "doc": n.get("doc", ""),
        }
        for n in canopen.get("nodes", [])
    ]

    groups = []
    for group_name, group in canopen.get("object dictionary", {}).items():
        objects = []
        for obj_name, obj in group.items():
            objects.append({
                "name": obj_name,
                "mlx": f"0x{obj.get('mlx', 0):06x}",
                "type": str(obj.get("type", "")),
                "flags": ", ".join(obj.get("flags", [])),
                "doc": obj.get("doc", ""),
            })
        groups.append({"name": group_name, "objects": objects})
    return {"nodes": nodes, "groups": groups}


def _prep_uart(iface: dict) -> dict:
    uart = iface.get("uart", {})
    phys = uart.get("physical", {})

    commands = []
    for cmd_name, cmd in uart.get("commands", {}).items():
        req = ", ".join(
            f"{f['name']}:{f.get('type', '?')}"
            for f in cmd.get("request", {}).get("fields", [])
        )
        resp = ", ".join(
            f"{f['name']}:{f.get('type', '?')}"
            for f in cmd.get("response", {}).get("fields", [])
        )
        if not req:
            req = ", ".join(
                f"{f['name']}:{f.get('type', '?')}" for f in cmd.get("fields", [])
            )
        commands.append({
            "name": cmd_name,
            "id": f"0x{cmd.get('id', 0):02x}",
            "direction": cmd.get("direction", ""),
            "req": req or "—",
            "resp": resp or "—",
            "doc": cmd.get("doc", ""),
        })

    return {
        "tx_pin": phys.get("tx_pin", "?"),
        "rx_pin": phys.get("rx_pin", "?"),
        "baud_rate": phys.get("baud_rate", "?"),
        "data_bits": phys.get("data_bits", "8"),
        "parity": phys.get("parity", "N")[0].upper(),
        "commands": commands,
    }


def _prep_modbus(iface: dict) -> dict:
    rs485 = iface.get("rs485", {})
    modbus = rs485.get("modbus", {})

    register_groups = []
    for reg_type in ("holding", "input", "discrete"):
        regs = modbus.get("registers", {}).get(reg_type, [])
        if not regs:
            continue
        rows = []
        for reg in regs:
            flags = ", ".join(reg.get("flags", []))
            rows.append({
                "addr": f"0x{reg.get('addr', 0):04x}",
                "name": reg.get("name", ""),
                "type": str(reg.get("type", "bit")),
                "flags": flags or "R",
                "doc": reg.get("doc", ""),
            })
        register_groups.append({"title": reg_type.title(), "registers": rows})

    return {
        "slave_id": format(modbus.get("slave_id", 1), "#04x"),
        "register_groups": register_groups,
    }


def _prep_tcpudp(iface: dict) -> dict:
    tcp_raw = iface.get("tcp", {})
    udp_raw = iface.get("udp", {})
    result: dict = {}

    if tcp_raw:
        result["tcp"] = {
            "port": tcp_raw.get("port", 5200),
            "commands": [
                {
                    "name": name,
                    "id": f"0x{cmd.get('id', 0):04x}",
                    "direction": cmd.get("direction", ""),
                    "doc": cmd.get("doc", ""),
                }
                for name, cmd in tcp_raw.get("commands", {}).items()
            ],
        }

    if udp_raw:
        result["udp"] = {
            "port": udp_raw.get("port", 5201),
            "messages": [
                {
                    "name": name,
                    "id": f"0x{msg.get('id', 0):04x}",
                    "rate": f"{msg.get('rate_hz', 0)} Hz",
                    "doc": msg.get("doc", ""),
                }
                for name, msg in udp_raw.get("messages", {}).items()
            ],
        }

    return result


def _prep_i2c(iface: dict) -> dict:
    i2c = iface.get("i2c", {})
    devices = []
    for device in i2c.get("devices", []):
        addr = device.get("address", 0)
        regs = []
        for reg in device.get("registers", []):
            ra = reg.get("addr")
            regs.append({
                "addr": f"0x{ra:02x}" if ra is not None else "—",
                "name": reg.get("name", ""),
                "type": str(reg.get("type", "")),
                "flags": ", ".join(reg.get("flags", [])),
                "doc": reg.get("doc", ""),
            })
        devices.append({
            "name": device.get("name", ""),
            "addr_hex": format(addr, "02x"),
            "part": device.get("part", ""),
            "doc": device.get("doc", ""),
            "registers": regs if regs else None,
        })
    return {"devices": devices}


def _prep_spi(iface: dict) -> dict:
    spi = iface.get("spi", {})
    devices = []
    for device in spi.get("devices", []):
        txns = []
        for tx_name, tx in device.get("transactions", {}).items():
            txns.append({
                "name": tx_name,
                "type": tx.get("type", ""),
                "word_size": str(tx.get("word_size", "")),
                "doc": tx.get("doc", ""),
            })

        cmds = []
        for cmd_name, cmd in device.get("commands", {}).items():
            cmds.append({
                "name": cmd_name,
                "opcode": f"0x{cmd.get('opcode', 0):02x}",
                "addr_bytes": str(cmd.get("addr_bytes", "—")),
                "doc": cmd.get("doc", ""),
            })

        regs = []
        for reg in device.get("registers", []):
            ra = reg.get("addr")
            regs.append({
                "addr": f"0x{ra:02x}" if ra is not None else "—",
                "name": reg.get("name", ""),
                "type": str(reg.get("type", "")),
                "flags": ", ".join(reg.get("flags", [])),
                "doc": reg.get("doc", ""),
            })

        mmap_raw = device.get("memory_map", {})
        memory_map = None
        if mmap_raw:
            regions = [
                {
                    "name": r.get("name", ""),
                    "start": f"0x{r.get('start', 0):06x}",
                    "size": f"0x{r.get('size', 0):06x}",
                    "doc": r.get("doc", ""),
                }
                for r in mmap_raw.get("regions", [])
            ]
            memory_map = {
                "total_size": f"{mmap_raw.get('total_size', 0):,}",
                "sector_size": f"{mmap_raw.get('sector_size', 0):,}",
                "page_size": f"{mmap_raw.get('page_size', 0):,}",
                "regions": regions if regions else None,
            }

        devices.append({
            "name": device.get("name", ""),
            "cs": device.get("cs", "?"),
            "part": device.get("part", ""),
            "doc": device.get("doc", ""),
            "transactions": txns if txns else None,
            "commands": cmds if cmds else None,
            "registers": regs if regs else None,
            "memory_map": memory_map,
        })
    return {"devices": devices}
