"""Jinja2 GUI widget block generator."""

from __future__ import annotations

import logging
from pathlib import Path

from . import esc, get_jinja_env

log = logging.getLogger(__name__)


def gen_gui_jinja(data: dict, types: dict, od_name: str) -> str:
    """Generate a Jinja2 GUI widget block (.html.j2) for the interface."""

    iface = data.get("interface", {})
    title = iface.get("title", "Unknown")
    transport = iface.get("transport", "unknown")

    panel = _gui_panel_for_transport(iface, transport, od_name)

    # Load the base template from the templates/ folder
    env = get_jinja_env(
        variable_start_string="<<",
        variable_end_string=">>",
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=False,
    )
    base = env.get_template("gui_base.html.j2")
    filename = f"{transport}_{od_name.lower()}_gui.html.j2"
    result = base.render(
        title=title,
        transport=transport,
        filename=filename,
        panel_content=panel,
    )
    return result


def _gui_panel_for_transport(iface: dict, transport: str, od_name: str) -> str:
    """Dispatch to the right GUI panel builder."""
    if transport == "canopen":
        return _gui_canopen(iface, od_name)
    elif transport == "uart":
        return _gui_uart(iface, od_name)
    elif transport == "rs485":
        return _gui_modbus(iface, od_name)
    elif transport in ("tcp/udp", "tcp", "udp"):
        return _gui_tcpudp(iface, od_name)
    elif transport == "i2c":
        return _gui_i2c(iface, od_name)
    elif transport == "spi":
        return _gui_spi(iface, od_name)
    return "<!-- unsupported transport -->"


def _gui_canopen(iface: dict, od_name: str) -> str:
    canopen = iface.get("canopen", {})
    od = canopen.get("object dictionary", {})
    title = esc(iface.get("title", "CANopen"))
    pid = od_name.lower()

    lines = [f'<div class="ifdoc-panel" id="{pid}-canopen-panel">',
             f'  <h3>{title}</h3>']

    for group_name, group in od.items():
        lines.append(f'  <h4>{esc(group_name)}</h4>')
        for obj_name, obj in group.items():
            mlx = obj.get("mlx")
            if mlx is None:
                continue
            flags = obj.get("flags", [])
            oid = f"{pid}_{obj_name}"
            lines.append(f'  <div class="ifdoc-row">')
            lines.append(f'    <label>{esc(obj_name)}</label>')
            lines.append(f'    <span class="ifdoc-badge">0x{mlx:06x}</span>')
            if "read" in flags:
                lines.append(f'    <button onclick="ifdocRead(\'/api/{pid}/sdo/{mlx:#08x}\','
                             f' document.getElementById(\'{oid}_r\'))">Read</button>')
            if "write" in flags:
                lines.append(f'    <input type="number" id="{oid}_v" placeholder="value">')
                lines.append(f'    <button onclick="ifdocFetch(\'/api/{pid}/sdo/{mlx:#08x}\','
                             f' {{value: Number(document.getElementById(\'{oid}_v\').value)}},'
                             f' document.getElementById(\'{oid}_r\'))">Write</button>')
            lines.append(f'    <div class="ifdoc-result" id="{oid}_r"></div>')
            lines.append(f'  </div>')

    lines.append('</div>')
    return "\n".join(lines)


def _gui_uart(iface: dict, od_name: str) -> str:
    uart = iface.get("uart", {})
    title = esc(iface.get("title", "UART"))
    pid = od_name.lower()

    lines = [f'<div class="ifdoc-panel" id="{pid}-uart-panel">',
             f'  <h3>{title}</h3>',
             f'  <h4>Commands</h4>']

    for cmd_name, cmd in uart.get("commands", {}).items():
        cmd_id = cmd.get("id", 0)
        cid = f"{pid}_{cmd_name}"
        req_fields = cmd.get("request", {}).get("fields", [])
        doc = esc(cmd.get("doc", ""))

        lines.append(f'  <div class="ifdoc-row" title="{doc}">')
        lines.append(f'    <label>{esc(cmd_name)}</label>')
        lines.append(f'    <span class="ifdoc-badge">0x{cmd_id:02x}</span>')

        if req_fields:
            lines.append(f'    <form id="{cid}_f" onsubmit="return false;" style="display:contents">')
            for f in req_fields:
                fname = f.get("name", "x")
                ftype = f.get("type", "uint8")
                inp_type = "text" if ftype in ("string", "bytes") else "number"
                lines.append(f'      <input type="{inp_type}" name="{fname}" placeholder="{fname}" title="{esc(f.get("doc", ""))}">')
            lines.append(f'      <button onclick="ifdocWrite(\'/api/{pid}/uart/{cmd_name}\','
                         f' document.getElementById(\'{cid}_f\'),'
                         f' document.getElementById(\'{cid}_r\'))">Send</button>')
            lines.append(f'    </form>')
        else:
            lines.append(f'    <button onclick="ifdocRead(\'/api/{pid}/uart/{cmd_name}\','
                         f' document.getElementById(\'{cid}_r\'))">Send</button>')

        lines.append(f'    <div class="ifdoc-result" id="{cid}_r"></div>')
        lines.append(f'  </div>')

    lines.append('</div>')
    return "\n".join(lines)


def _gui_modbus(iface: dict, od_name: str) -> str:
    rs485 = iface.get("rs485", {})
    modbus = rs485.get("modbus", {})
    title = esc(iface.get("title", "RS-485"))
    pid = od_name.lower()

    lines = [f'<div class="ifdoc-panel" id="{pid}-modbus-panel">',
             f'  <h3>{title}</h3>',
             f'  <p>Slave ID: <code>{modbus.get("slave_id", 1):#04x}</code></p>']

    for reg_type in ("holding", "input", "discrete"):
        regs = modbus.get("registers", {}).get(reg_type, [])
        if not regs:
            continue
        lines.append(f'  <h4>{reg_type.title()} Registers</h4>')
        lines.append(f'  <table><tr><th>Addr</th><th>Name</th><th>R/W</th><th style="width:100%">Actions</th></tr>')

        for reg in regs:
            addr = reg.get("addr", 0)
            name = reg.get("name", "unknown")
            flags = reg.get("flags", [])
            rid = f"{pid}_{reg_type}_{name}"
            doc = esc(reg.get("doc", ""))

            lines.append(f'  <tr title="{doc}">')
            lines.append(f'    <td>0x{addr:04x}</td><td>{esc(name)}</td>')
            lines.append(f'    <td>{", ".join(flags) or "R"}</td>')
            lines.append(f'    <td>')
            lines.append(f'      <div class="ifdoc-row">')
            if "read" in flags or reg_type in ("input", "discrete"):
                lines.append(f'        <button onclick="ifdocRead(\'/api/{pid}/modbus/{reg_type}/{addr:#06x}\','
                             f' document.getElementById(\'{rid}_r\'))">Read</button>')
            if "write" in flags:
                lines.append(f'        <input type="number" id="{rid}_v" placeholder="value" style="width:70px">')
                lines.append(f'        <button onclick="ifdocFetch(\'/api/{pid}/modbus/{reg_type}/{addr:#06x}\','
                             f' {{value: Number(document.getElementById(\'{rid}_v\').value)}},'
                             f' document.getElementById(\'{rid}_r\'))">Write</button>')
            lines.append(f'        <div class="ifdoc-result" id="{rid}_r"></div>')
            lines.append(f'      </div>')
            lines.append(f'    </td>')
            lines.append(f'  </tr>')

        lines.append(f'  </table>')

    lines.append('</div>')
    return "\n".join(lines)


def _gui_tcpudp(iface: dict, od_name: str) -> str:
    tcp = iface.get("tcp", {})
    udp = iface.get("udp", {})
    title = esc(iface.get("title", "TCP/UDP"))
    pid = od_name.lower()

    lines = [f'<div class="ifdoc-panel" id="{pid}-tcpudp-panel">',
             f'  <h3>{title}</h3>']

    if tcp:
        lines.append(f'  <h4>TCP Commands (port {tcp.get("port", 5200)})</h4>')
        for cmd_name, cmd in tcp.get("commands", {}).items():
            cid = f"{pid}_tcp_{cmd_name}"
            doc = esc(cmd.get("doc", ""))
            req_fields = cmd.get("request", {}).get("fields", [])

            lines.append(f'  <div class="ifdoc-row" title="{doc}">')
            lines.append(f'    <label>{esc(cmd_name)}</label>')
            lines.append(f'    <span class="ifdoc-badge">0x{cmd.get("id", 0):04x}</span>')

            if req_fields:
                lines.append(f'    <form id="{cid}_f" onsubmit="return false;" style="display:contents">')
                for f in req_fields:
                    fname = f.get("name", "x")
                    ftype = f.get("type", "uint8")
                    inp_type = "text" if ftype in ("string", "bytes") else "number"
                    lines.append(f'      <input type="{inp_type}" name="{fname}" placeholder="{fname}">')
                lines.append(f'      <button onclick="ifdocWrite(\'/api/{pid}/tcp/{cmd_name}\','
                             f' document.getElementById(\'{cid}_f\'),'
                             f' document.getElementById(\'{cid}_r\'))">Send</button>')
                lines.append(f'    </form>')
            else:
                lines.append(f'    <button onclick="ifdocRead(\'/api/{pid}/tcp/{cmd_name}\','
                             f' document.getElementById(\'{cid}_r\'))">Send</button>')

            lines.append(f'    <div class="ifdoc-result" id="{cid}_r"></div>')
            lines.append(f'  </div>')

    if udp:
        lines.append(f'  <h4>UDP Telemetry (port {udp.get("port", 5201)})</h4>')
        lines.append(f'  <table><tr><th>Message</th><th>ID</th><th>Rate</th><th>Live</th></tr>')
        for msg_name, msg in udp.get("messages", {}).items():
            mid = f"{pid}_udp_{msg_name}"
            lines.append(f'  <tr>')
            lines.append(f'    <td>{esc(msg_name)}</td>')
            lines.append(f'    <td><code>0x{msg.get("id", 0):04x}</code></td>')
            lines.append(f'    <td>{msg.get("rate_hz", 0)} Hz</td>')
            lines.append(f'    <td><div class="ifdoc-result" id="{mid}_r">—</div></td>')
            lines.append(f'  </tr>')
        lines.append(f'  </table>')
        # EventSource SSE listener stub
        lines.append(f'  <script>')
        lines.append(f'  (function() {{')
        lines.append('    const es = new EventSource("{{ api_base|default(' + "'" + "'" + ') }}/api/' + pid + '/udp/stream");')
        lines.append(f'    es.onmessage = function(ev) {{')
        lines.append(f'      try {{')
        lines.append(f'        const d = JSON.parse(ev.data);')
        lines.append(f'        const el = document.getElementById("{pid}_udp_" + d.type + "_r");')
        lines.append(f'        if (el) el.textContent = JSON.stringify(d.payload, null, 2);')
        lines.append(f'      }} catch(e) {{}}')
        lines.append(f'    }};')
        lines.append(f'  }})();')
        lines.append(f'  </script>')

    lines.append('</div>')
    return "\n".join(lines)


def _gui_i2c(iface: dict, od_name: str) -> str:
    i2c = iface.get("i2c", {})
    title = esc(iface.get("title", "I2C"))
    pid = od_name.lower()

    lines = [f'<div class="ifdoc-panel" id="{pid}-i2c-panel">',
             f'  <h3>{title}</h3>']

    for device in i2c.get("devices", []):
        dev_name = device.get("name", "dev")
        addr = device.get("address", 0)
        part = device.get("part", "")
        lines.append(f'  <h4>{esc(dev_name)} — 0x{addr:02x} ({esc(part)})</h4>')
        lines.append(f'  <table><tr><th>Addr</th><th>Register</th><th style="width:100%">Actions</th></tr>')

        for reg in device.get("registers", []):
            reg_name = reg.get("name", "unknown")
            reg_addr = reg.get("addr")
            flags = reg.get("flags", [])
            doc = esc(reg.get("doc", ""))
            rid = f"{pid}_{dev_name}_{reg_name}"
            ra_str = f"0x{reg_addr:02x}" if reg_addr is not None else "—"
            ra_api = f"{reg_addr:#04x}" if reg_addr is not None else "0x00"

            lines.append(f'  <tr title="{doc}">')
            lines.append(f'    <td>{ra_str}</td><td>{esc(reg_name)}</td>')
            lines.append(f'    <td>')
            lines.append(f'      <div class="ifdoc-row">')
            if "read" in flags and reg_addr is not None:
                lines.append(f'        <button onclick="ifdocRead(\'/api/{pid}/i2c/{addr:#04x}/{ra_api}\','
                             f' document.getElementById(\'{rid}_r\'))">Read</button>')
            if "write" in flags and reg_addr is not None:
                lines.append(f'        <input type="number" id="{rid}_v" placeholder="value" style="width:80px">')
                lines.append(f'        <button onclick="ifdocFetch(\'/api/{pid}/i2c/{addr:#04x}/{ra_api}\','
                             f' {{value: Number(document.getElementById(\'{rid}_v\').value)}},'
                             f' document.getElementById(\'{rid}_r\'))">Write</button>')
            lines.append(f'        <div class="ifdoc-result" id="{rid}_r"></div>')
            lines.append(f'      </div>')
            lines.append(f'    </td>')
            lines.append(f'  </tr>')

        lines.append(f'  </table>')

    lines.append('</div>')
    return "\n".join(lines)


def _gui_spi(iface: dict, od_name: str) -> str:
    spi = iface.get("spi", {})
    title = esc(iface.get("title", "SPI"))
    pid = od_name.lower()

    lines = [f'<div class="ifdoc-panel" id="{pid}-spi-panel">',
             f'  <h3>{title}</h3>']

    for device in spi.get("devices", []):
        dev_name = device.get("name", "dev")
        cs = device.get("cs", "?")
        part = device.get("part", "")
        lines.append(f'  <h4>{esc(dev_name)} — CS: {esc(cs)} ({esc(part)})</h4>')

        # Transactions (e.g. DAC write)
        txns = device.get("transactions", {})
        if txns:
            for tx_name, tx in txns.items():
                tid = f"{pid}_{dev_name}_{tx_name}"
                doc = esc(tx.get("doc", ""))
                lines.append(f'  <div class="ifdoc-row" title="{doc}">')
                lines.append(f'    <label>{esc(tx_name)}</label>')
                lines.append(f'    <input type="number" id="{tid}_v" placeholder="data">')
                lines.append(f'    <button onclick="ifdocFetch(\'/api/{pid}/spi/{dev_name}/{tx_name}\','
                             f' {{value: Number(document.getElementById(\'{tid}_v\').value)}},'
                             f' document.getElementById(\'{tid}_r\'))">Send</button>')
                lines.append(f'    <div class="ifdoc-result" id="{tid}_r"></div>')
                lines.append(f'  </div>')

        # Commands (e.g. flash operations)
        cmds = device.get("commands", {})
        if cmds:
            lines.append(f'  <table><tr><th>Command</th><th>Opcode</th><th style="width:100%">Actions</th></tr>')
            for cmd_name, cmd in cmds.items():
                cid = f"{pid}_{dev_name}_{cmd_name}"
                doc = esc(cmd.get("doc", ""))
                opcode = cmd.get("opcode", 0)
                addr_bytes = cmd.get("addr_bytes", 0)

                lines.append(f'  <tr title="{doc}">')
                lines.append(f'    <td>{esc(cmd_name)}</td><td><code>0x{opcode:02x}</code></td>')
                lines.append(f'    <td>')
                lines.append(f'      <div class="ifdoc-row">')
                if addr_bytes:
                    lines.append(f'        <input type="text" id="{cid}_a" placeholder="addr (hex)" style="width:80px">')
                    lines.append(f'        <input type="number" id="{cid}_n" placeholder="len" style="width:60px">')
                lines.append(f'        <button onclick="ifdocFetch(' + "'" + f'/api/{pid}/spi/{dev_name}/{cmd_name}' + "',"
                             f" {{addr: document.getElementById('{cid}_a')?.value || '',"
                             f" len: Number(document.getElementById('{cid}_n')?.value || 0)}},"
                             f" document.getElementById('{cid}_r'))" + '">Execute</button>')
                lines.append(f'        <div class="ifdoc-result" id="{cid}_r"></div>')
                lines.append(f'      </div>')
                lines.append(f'    </td>')
                lines.append(f'  </tr>')
            lines.append(f'  </table>')

        # Registers
        regs = device.get("registers", [])
        if regs:
            lines.append(f'  <table><tr><th>Addr</th><th>Register</th><th style="width:100%">Actions</th></tr>')
            for reg in regs:
                reg_name = reg.get("name", "unknown")
                reg_addr = reg.get("addr")
                flags = reg.get("flags", [])
                rid = f"{pid}_{dev_name}_{reg_name}"
                ra_str = f"0x{reg_addr:02x}" if reg_addr is not None else "—"

                lines.append(f'  <tr title="{esc(reg.get("doc", ""))}">')
                lines.append(f'    <td>{ra_str}</td><td>{esc(reg_name)}</td>')
                lines.append(f'    <td>')
                lines.append(f'      <div class="ifdoc-row">')
                if "read" in flags:
                    lines.append(f'        <button onclick="ifdocRead(\'/api/{pid}/spi/{dev_name}/reg/{reg_addr:#04x}\','
                                 f' document.getElementById(\'{rid}_r\'))">Read</button>')
                if "write" in flags:
                    lines.append(f'        <input type="number" id="{rid}_v" placeholder="value" style="width:80px">')
                    lines.append(f'        <button onclick="ifdocFetch(\'/api/{pid}/spi/{dev_name}/reg/{reg_addr:#04x}\','
                                 f' {{value: Number(document.getElementById(\'{rid}_v\').value)}},'
                                 f' document.getElementById(\'{rid}_r\'))">Write</button>')
                lines.append(f'        <div class="ifdoc-result" id="{rid}_r"></div>')
                lines.append(f'      </div>')
                lines.append(f'    </td>')
                lines.append(f'  </tr>')
            lines.append(f'  </table>')

    lines.append('</div>')
    return "\n".join(lines)
