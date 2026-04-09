"""Python driver stub generator."""

from __future__ import annotations

from . import get_jinja_env, py_type_name, upper_snake


def gen_python_driver(data: dict, types: dict, od_name: str) -> str:
    iface = data.get("interface", {})
    title = iface.get("title", "Unknown")
    transport = iface.get("transport", "unknown")

    context: dict = {
        "title": title,
        "transport": transport,
        "od_name": od_name,
    }

    if transport == "canopen":
        context.update(_prep_canopen(iface, od_name))
    elif transport == "uart":
        context["uart"] = _prep_uart(iface, od_name)
    elif transport == "rs485":
        context["modbus"] = _prep_modbus(iface, od_name)
    elif transport in ("tcp/udp", "tcp", "udp"):
        context["tcpudp"] = _prep_tcpudp(iface, od_name)
    elif transport == "i2c":
        context["i2c"] = _prep_i2c(iface)
    elif transport == "spi":
        context["spi"] = _prep_spi(iface)

    env = get_jinja_env()
    tpl = env.get_template("py_driver.py.j2")
    return tpl.render(**context)


def _prep_canopen(iface: dict, od_name: str) -> dict:
    canopen = iface.get("canopen", {})
    od = canopen.get("object dictionary", {})

    constants = []
    methods = []
    for group_name, group in od.items():
        for obj_name, obj in group.items():
            mlx = obj.get("mlx")
            if mlx is None:
                continue
            const = f"{upper_snake(group_name)}_{upper_snake(obj_name)}_MLX"
            constants.append({"name": const, "value": format(mlx, "#08x")})
            flags = obj.get("flags", [])
            if "read" in flags:
                methods.append({"type": "read", "name": obj_name, "mlx": format(mlx, "#08x")})
            if "write" in flags:
                methods.append({"type": "write", "name": obj_name, "mlx": format(mlx, "#08x")})
    return {"constants": constants, "methods": methods}


def _prep_uart(iface: dict, od_name: str) -> dict:
    uart = iface.get("uart", {})
    phys = uart.get("physical", {})

    cmd_constants = [
        {"name": upper_snake(name), "id": format(cmd.get("id", 0), "#04x")}
        for name, cmd in uart.get("commands", {}).items()
    ]

    commands = []
    for cmd_name, cmd in uart.get("commands", {}).items():
        req_fields = cmd.get("request", {}).get("fields", [])
        params = ", ".join(
            f"{f['name']}: {py_type_name(f.get('type', 'uint8'))}" for f in req_fields
        )
        sig = f"self, {params}" if params else "self"
        commands.append({"name": cmd_name, "sig": sig, "doc": cmd.get("doc", "")})

    return {
        "baud_rate": phys.get("baud_rate", 115200),
        "cmd_constants": cmd_constants,
        "commands": commands,
    }


def _prep_modbus(iface: dict, od_name: str) -> dict:
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
    for reg in modbus.get("registers", {}).get("holding", []):
        name = reg.get("name", "unknown")
        flags = reg.get("flags", [])
        if "read" in flags:
            holding_methods.append({"type": "read", "name": name, "doc": reg.get("doc", "")})
        if "write" in flags:
            holding_methods.append({"type": "write", "name": name, "doc": reg.get("doc", "")})

    input_methods = [
        {"name": reg.get("name", "unknown"), "doc": reg.get("doc", "")}
        for reg in modbus.get("registers", {}).get("input", [])
    ]

    return {
        "slave_id": slave_id,
        "reg_constants": reg_constants,
        "holding_methods": holding_methods,
        "input_methods": input_methods,
    }


def _prep_tcpudp(iface: dict, od_name: str) -> dict:
    tcp = iface.get("tcp", {})
    udp = iface.get("udp", {})

    cmd_constants = [
        {"name": upper_snake(name), "id": format(cmd.get("id", 0), "#06x")}
        for name, cmd in tcp.get("commands", {}).items()
    ]

    commands = []
    for cmd_name, cmd in tcp.get("commands", {}).items():
        req_fields = cmd.get("request", {}).get("fields", [])
        params = ", ".join(
            f"{f['name']}: {py_type_name(f.get('type', 'uint8'))}" for f in req_fields
        )
        sig = f"self, {params}" if params else "self"
        commands.append({"name": cmd_name, "sig": sig, "doc": cmd.get("doc", "")})

    return {
        "tcp_port": tcp.get("port") if tcp else None,
        "udp_port": udp.get("port") if udp else None,
        "default_port": tcp.get("port", 5200),
        "cmd_constants": cmd_constants,
        "commands": commands,
    }


def _prep_i2c(iface: dict) -> dict:
    i2c = iface.get("i2c", {})

    addr_constants = [
        {"name": upper_snake(dev.get("name", "dev")), "addr": format(dev.get("address", 0), "#04x")}
        for dev in i2c.get("devices", [])
    ]

    methods = []
    for device in i2c.get("devices", []):
        dev_name = device.get("name", "dev")
        for reg in device.get("registers", []):
            reg_name = reg.get("name", "unknown")
            flags = reg.get("flags", [])
            if "read" in flags:
                methods.append({"type": "read", "dev": dev_name, "reg": reg_name, "doc": reg.get("doc", "")})
            if "write" in flags:
                methods.append({"type": "write", "dev": dev_name, "reg": reg_name, "doc": reg.get("doc", "")})

    return {"addr_constants": addr_constants, "methods": methods}


def _prep_spi(iface: dict) -> dict:
    spi = iface.get("spi", {})

    methods = []
    for device in spi.get("devices", []):
        dev_name = device.get("name", "dev")
        for tx_name, tx in device.get("transactions", {}).items():
            methods.append({"dev": dev_name, "name": tx_name, "doc": tx.get("doc", "")})
        for cmd_name, cmd in device.get("commands", {}).items():
            methods.append({"dev": dev_name, "name": cmd_name, "doc": cmd.get("doc", "")})

    return {"methods": methods}
