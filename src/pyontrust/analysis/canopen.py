"""CANopen protocol core — NMT, SDO codec, EMCY decode, EDS parse/write.

Pure Python (no hardware), modelled on CiA 301 / the CANopenNode project's
object-dictionary conventions:

- :func:`nmt_frame` / :data:`NMT_COMMANDS`      — NMT master command frames
- :func:`sdo_upload_request`, :func:`sdo_download_request`,
  :func:`parse_sdo_response`                     — SDO expedited codec
- :func:`decode_emcy`                            — emergency message decode
- :class:`EdsDocument`, :func:`parse_eds`, :func:`write_eds`
                                                 — EDS (object dictionary) round-trip
- :class:`SimulatedCanopenNode`                  — in-process CANopen node with a
  standard object dictionary, NMT state machine and SDO read/write service

The simulated node is what makes the ``/can`` GUI fully functional without
hardware: it answers NMT commands and SDO reads/writes exactly like a real
CANopen device would on the bus.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Any

# ── CANopen COB-ID ranges (CiA 301) ───────────────────────────────────
NMT_COB_ID = 0x000
SYNC_COB_ID = 0x080
EMCY_BASE = 0x080          # EMCY node N: 0x080 + N
TIME_STAMP_COB_ID = 0x100
TPDO1_BASE = 0x200         # TPDO1 node N: 0x200 + N
RPDO1_BASE = 0x300         # RPDO1 node N: 0x300 + N
SDO_CLIENT_BASE = 0x580    # SDO client (server->client) node N: 0x580 + N
SDO_SERVER_BASE = 0x600    # SDO server request (client->server): 0x600 + N
HEARTBEAT_BASE = 0x700     # Heartbeat node N: 0x700 + N

NMT_COMMANDS: dict[int, str] = {
    0x01: "Pre-Operational",
    0x02: "Operational",
    0x03: "Stopped",
    0x80: "Reset node",
    0x81: "Reset communication",
}

NMT_STATES: dict[int, str] = {
    0x00: "Bootstrap",
    0x40: "Stopped",
    0x50: "Operational",
    0x7F: "Pre-Operational",
}

HEARTBEAT_STATES: dict[int, str] = {
    0x00: "Startup",
    0x04: "Stopped",
    0x05: "Operational",
    0x07: "Pre-operational",
}

# Common CiA 306 / vendor emergency error codes (subset, 16-bit EEC)
EMCY_CODES: dict[int, str] = {
    0x1000: "Generic error",
    0x4000: "Internal device error",
    0x4200: "Device profile specific error",
    0x4300: "Communication profile specific error",
    0x4700: "Configuration parameter error",
    0x5040: "SDO protocol timeout",
}

ERROR_REGISTER_BITS: dict[int, str] = {
    0: "Generic error",
    1: "Warning",
    2: "Manufacturer specific",
    3: "Communication error (PDO)",
    4: "SDO protocol timeout",
    5: "SDO transfer timeout",
    6: "Data type value range error",
    7: "Data type not supported",
    8: "Inconsistent internal state",
}

# Standard SDO abort codes (CiA 301 §7.4.6.2)
SDO_ABORT_CODES: dict[int, str] = {
    0x0601_0000: "Write access not possible",
    0x0601_0001: "Read access not possible",
    0x0602_0000: "Cannot download — parameter configuration error",
    0x0602_0001: "Cannot upload — parameter configuration error",
    0x0606_0000: "Data type mismatch (parameter length)",
    0x0607_0000: "Data type mismatch (value out of range)",
    0x0609_0011: "Object does not exist in the object dictionary",
    0x0609_0030: "Strongly typed OD entry — access not possible",
    0x0609_0031: "General reading not possible (e.g. no file)",
    0x0609_0032: "General writing not possible",
    0x060A_0000: "SDO protocol timeout",
    0x060A_0001: "SDO transfer timeout",
    0x060B_0000: "Sub-index does not exist",
}


def nmt_frame(node_id: int, command: int) -> tuple[int, bytes]:
    """Build an NMT master frame: (COB-ID 0x000, [command, node_id])."""
    if not (1 <= node_id <= 127):
        raise ValueError("node_id must be 1..127")
    if command not in NMT_COMMANDS:
        raise ValueError(f"unknown NMT command {command:#x}")
    return NMT_COB_ID, bytes([command & 0xFF, node_id])


def sdo_upload_request(node_id: int, index: int, subindex: int) -> tuple[int, bytes]:
    """SDO expedited upload (read) request — client→server, COB-ID 0x600+N.

    Byte layout per CiA 301 / CANopenNode ``CO_SDOclient.c``::

        [0xC0, index_lo, index_hi, subindex]          DLC 4
    """
    if not (1 <= node_id <= 127):
        raise ValueError("node_id must be 1..127")
    return SDO_SERVER_BASE + node_id, bytes([0xC0]) + struct.pack(
        "<HB", index & 0xFFFF, subindex & 0xFF)


def sdo_download_request(node_id: int, index: int, subindex: int, value: int) -> tuple[int, bytes]:
    """SDO expedited download (write) request — client→server, COB-ID 0x600+N.

    ``byte0 = 0x23 | ((4 - nbytes) << 2)`` where ``nbytes`` is the value size
    (1/2/4); data follows at bytes [4..7] little-endian, zero-padded::

        [byte0, index_lo, index_hi, subindex, d0, d1, d2, d3]   DLC 8
    """
    if not (1 <= node_id <= 127):
        raise ValueError("node_id must be 1..127")
    v = value & 0xFFFFFFFF
    nbytes = 1 if v <= 0xFF else (2 if v <= 0xFFFF else 4)
    byte0 = 0x23 | ((4 - nbytes) << 2)
    return SDO_SERVER_BASE + node_id, bytes([byte0]) + struct.pack(
        "<HB", index & 0xFFFF, subindex & 0xFF) \
        + v.to_bytes(nbytes, "little").ljust(4, b"\x00")


def parse_sdo_response(data: bytes) -> dict[str, Any]:
    """Parse an SDO server response payload (COB-ID 0x580+N).

    Handles the three expedited-transfer responses per CANopenNode::

    - upload response : ``byte0 = 0x43 | ((4-nbytes)<<2)``, value at [4..7]
    - download ack    : ``byte0 & 0xF0 == 0x60``
    - abort           : ``byte0 == 0x80``, u32 LE abort code at [4..7]

    Returns ``{"ok": bool, "value"?: int, "ack"?: bool, "error_code"?: int}``.
    """
    if len(data) < 4:
        return {"ok": False, "error": "short frame"}
    index = struct.unpack_from("<H", data, 1)[0]
    subindex = data[3]
    b0 = data[0]

    if (b0 & 0xF0) == 0x40:                      # expedited upload response
        nbytes = 4 - ((b0 >> 2) & 0x03)          # CANopenNode: 0x43 | ((4-count)<<2)
        value = int.from_bytes(data[4:4 + nbytes], "little") if len(data) >= 4 + nbytes else 0
        return {"ok": True, "index": index, "subindex": subindex, "value": value}

    if (b0 & 0xF0) == 0x60:                      # download OK ack
        return {"ok": True, "ack": True, "index": index, "subindex": subindex}

    if b0 == 0x80 and len(data) >= 8:            # abort
        error_code = struct.unpack_from("<I", data, 4)[0]
        return {"ok": False, "error_code": error_code,
                "index": index, "subindex": subindex}

    return {"ok": False, "error": f"unsupported SCS {b0:#x}",
            "index": index, "subindex": subindex}


def decode_emcy(data: bytes) -> dict[str, Any]:
    """Decode an EMCY payload (EEC u16 + error register u8)."""
    out: dict[str, Any] = {}
    if len(data) >= 2:
        eec = struct.unpack_from("<H", data, 0)[0]
        out["eec"] = eec
        out["description"] = EMCY_CODES.get(eec, f"vendor/unknown (0x{eec:04X})")
    if len(data) >= 3:
        er = data[2]
        out["error_register"] = er
        out["flags"] = [ERROR_REGISTER_BITS[b] for b in range(9) if er & (1 << b)]
    return out


# ════════════════════════════════════════════════════════════════════
#  EDS — Electronic Data Sheet (object dictionary description)
# ════════════════════════════════════════════════════════════════════

EDS_TYPES: dict[int, str] = {
    0x0001: "BOOLEAN", 0x0002: "INTEGER8", 0x0003: "INTEGER16", 0x0004: "INTEGER32",
    0x0005: "UNSIGNED8", 0x0006: "UNSIGNED16", 0x0007: "UNSIGNED32",
    0x0008: "REAL32", 0x0009: "VISIBLE_STRING",
    0x0020: "DOMAIN (visible)", 0x0030: "OD dictionary",
}


@dataclass
class EdsEntry:
    index: int
    subindex: int = 0
    name: str = ""
    type: int = 0x0007          # default UNSIGNED32
    access: str = "rw"          # ro / rw / wo
    pdo_consumer: bool = False
    pdo_producer: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "subindex": self.subindex, "name": self.name,
            "type": self.type, "access": self.access,
            "pdo_consumer": self.pdo_consumer, "pdo_producer": self.pdo_producer,
        }


@dataclass
class EdsDocument:
    device_info: dict[str, str] = field(default_factory=dict)
    entries: list[EdsEntry] = field(default_factory=list)

    def entry(self, index: int, subindex: int = 0) -> EdsEntry | None:
        for e in self.entries:
            if e.index == index and e.subindex == subindex:
                return e
        return None


def _parse_hex(value: str) -> int:
    v = value.strip()
    if v.lower().startswith("0x"):
        return int(v, 16)
    return int(v, 10)


def parse_eds(text: str) -> EdsDocument:
    """Parse an EDS file (INI-style) into an :class:`EdsDocument`.

    Understands ``[FileInfo]``, ``[CANopenDevice]`` and object-dictionary
    sections ``[0xNNNN]`` / ``[0xNNNN.MM]`` with the standard keys.
    """
    doc = EdsDocument()
    section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        m = re.fullmatch(r"\[(.+?)\]", line)
        if m:
            section = m.group(1).strip()
            continue
        if "=" not in line or section is None:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()
        sec = section.lower()

        if sec == "canopendevice":
            doc.device_info[key] = value
            continue
        if sec in ("fileinfo", "canopennode"):
            continue

        # object dictionary sections: 0xNNNN (parent descriptor) or 0xNNNN.MM
        m_idx = re.fullmatch(r"(0[xX][0-9a-fA-F]+|\d+)", section)
        m_sub = re.fullmatch(r"((?:0[xX][0-9a-fA-F]+|\d+)\.(\d+))", section)

        def _num(s: str) -> int:
            # CiA 306 / CANopenNode convention: unprefixed OD numbers are hex
            try:
                return int(s, 16)
            except ValueError:
                return int(s)

        entry: EdsEntry | None = None
        if m_idx:
            idx = _num(section)
            # parent descriptor row is modelled with subindex -1 so it can
            # coexist with a real [0xNNNN.00] subindex entry
            entry = doc.entry(idx, -1) or EdsEntry(index=idx, subindex=-1)
            if not any(e is entry for e in doc.entries):
                doc.entries.append(entry)
        elif m_sub:
            head = m_sub.group(1).split(".")[0]
            idx = _num(head)
            sub = _num(m_sub.group(2))
            entry = doc.entry(idx, sub) or EdsEntry(index=idx, subindex=sub)
            if not any(e is entry for e in doc.entries):
                doc.entries.append(entry)
        else:
            continue

        if key == "parametername":
            entry.name = value
        elif key == "objecttype":
            try:
                entry.type = _parse_hex(value)
            except ValueError:
                pass
        elif key in ("access", "accesstype"):
            entry.access = value.lower()[:2]
        elif key in ("pdoconsumer",):
            entry.pdo_consumer = value.strip().lower() not in ("0", "")
        elif key in ("pdoproducer",):
            entry.pdo_producer = value.strip().lower() not in ("0", "")

    doc.entries.sort(key=lambda e: (e.index, e.subindex))
    return doc


def write_eds(doc: EdsDocument) -> str:
    """Serialise an :class:`EdsDocument` back to EDS text (round-trip safe)."""
    lines: list[str] = []
    lines.append("[FileInfo]")
    lines.append("FileName=pyontrust.eds")
    lines.append("FileRevision=1")
    lines.append("FileType=1")
    lines.append("FileDescription=CANopen device description (generated by pyontrust)")
    lines.append("")

    di = doc.device_info or {}
    lines.append("[CANopenDevice]")
    for key in ("producername", "producernumber", "productnumber", "revisionnumber"):
        if key in di:
            lines.append(f"{key.capitalize()}={di[key]}")
    lines.append("BaudRate_500=1")
    lines.append("")

    # one [0xNNNN] parent section per index (synthesised if not in the doc)
    indices = sorted({e.index for e in doc.entries})
    for idx in indices:
        subs = [x for x in doc.entries if x.index == idx and x.subindex >= 0]
        parent = next((e for e in doc.entries if e.index == idx and e.subindex == -1), None)
        lines.append(f"[{idx:#06x}]")
        lines.append(f"SubNumber={len(subs)}")
        if parent is not None:
            _emit_entry(lines, parent)
        else:
            lines.append(f"ParameterName=Object {idx:#06x}")
            lines.append("ObjectType=0x0030")
            lines.append("AccessType=rw")
            lines.append("")

    # subindex sections (including .00), EDS convention allows any order
    for e in doc.entries:
        if e.subindex >= 0:
            lines.append(f"[{e.index:#06x}.{e.subindex:02d}]")
            _emit_entry(lines, e)

    return "\n".join(l for l in lines if l is not None).rstrip() + "\n"


def _emit_entry(lines: list[str], e: EdsEntry) -> None:
    if e.name:
        lines.append(f"ParameterName={e.name}")
    lines.append(f"ObjectType={e.type:#06x}")
    lines.append(f"AccessType={e.access}")
    if e.pdo_consumer:
        lines.append("PdoConsumer=1")
    if e.pdo_producer:
        lines.append("PdoProducer=1")
    lines.append("")


# ════════════════════════════════════════════════════════════════════
#  Simulated CANopen node (in-process, answers NMT + SDO)
# ════════════════════════════════════════════════════════════════════

class SimulatedCanopenNode:
    """A small but standards-shaped CANopen device.

    Object dictionary (all 32-bit-or-smaller for expedited SDO):

    ============  =====================  =====================================
    Index         Name                   Value / notes
    ============  =====================  =====================================
    0x1000        Device type            0x00204027 (application profile)
    0x1008.00-03  Identity               producer/product/revision/serial
    0x1014        Error register         ro, set on SDO protocol errors
    0x1015        Status word            rw, reflects NMT state
    0x1016        RPDO1 mapping          ro
    0x1018        TPDO1 mapping          ro
    0x2000.00     Speed setpoint (rpm)   rw, default 1500
    0x2000.01     Torque limit (%)       rw, default 42
    0x3000.00     Axis position (mm)     ro, advances while Operational
    ============  =====================  =====================================
    """

    def __init__(self, node_id: int = 1) -> None:
        self.node_id = node_id
        self.state = "Pre-Operational"          # NMT state name
        self._od: dict[tuple[int, int], int] = {
            (0x1000, 0): 0x00204027,
            (0x1008, 0): 0x00000001,             # producer specific ID
            (0x1008, 1): 0x00000042,             # product number
            (0x1008, 2): 0x00010000,             # revision
            (0x1008, 3): 0x00000007,             # serial
            (0x1014, 0): 0x00,                   # error register
            (0x1015, 0): 0x0012,                 # status word: pre-op, ready to switch
            (0x1016, 0): 0x00200011,             # RPDO1 maps 0x2000.01 (8 bit)
            (0x1018, 0): 0x00300021,             # TPDO1 maps 0x3000.01 (8 bit)
            (0x2000, 0): 1500,                   # speed setpoint rpm
            (0x2000, 1): 42,                     # torque limit %
            (0x3000, 0): 0,                      # axis position mm
        }
        self._access: dict[tuple[int, int], str] = {}   # from imported EDS docs
        self._position_mm = 0.0

    def import_eds(self, doc) -> int:
        """Merge an :class:`EdsDocument`'s object dictionary into this node.

        New objects start at value ``0`` (EDS files describe structure, not
        runtime values); access rights are enforced by :meth:`sdo_write`.
        Existing keys keep their live value but adopt the EDS's access right.
        Returns the number of newly added objects.
        """
        added = 0
        for e in doc.entries:
            if getattr(e, "subindex", -1) < 0:      # parent descriptor row
                continue
            key = (e.index, e.subindex)
            self._access[key] = (getattr(e, "access", None) or "rw").lower()
            if key not in self._od:
                self._od[key] = 0
                added += 1
        return added

    # -- NMT -------------------------------------------------------------
    def handle_nmt(self, command: int) -> None:
        if command == 0x01:
            self.state = "Pre-Operational"
            self._od[(0x1015, 0)] = 0x0012
        elif command == 0x02:
            self.state = "Operational"
            self._od[(0x1015, 0)] = 0x0020
        elif command == 0x03:
            self.state = "Stopped"
            self._od[(0x1015, 0)] = 0x0040
        elif command in (0x80, 0x81):
            # reset: back to defaults + Pre-Operational
            self._od[(0x2000, 0)] = 1500
            self._od[(0x2000, 1)] = 42
            self._position_mm = 0.0
            self._od[(0x3000, 0)] = 0
            self.state = "Pre-Operational"
            self._od[(0x1015, 0)] = 0x0012

    def heartbeat_byte(self) -> int:
        return {"Startup": 0x00, "Stopped": 0x04,
                "Operational": 0x05, "Pre-Operational": 0x07}[self.state]

    # -- SDO -------------------------------------------------------------
    def sdo_read(self, index: int, subindex: int) -> tuple[bool, int]:
        key = (index, subindex)
        if key not in self._od:
            return False, 0x0609_0011 & 0xFFFFFFFF   # "object does not exist"
        if index == 0x3000 and self.state == "Operational":
            self._position_mm += 0.5                 # live motion while running
            self._od[key] = int(self._position_mm)
        return True, self._od[key] & 0xFFFFFFFF

    def sdo_write(self, index: int, subindex: int, value: int) -> bool:
        key = (index, subindex)
        if key not in self._od:
            return False
        ro_entries = {(0x1000, 0), (0x1008, 0), (0x1008, 1), (0x1008, 2), (0x1008, 3),
                      (0x1014, 0), (0x1016, 0), (0x1018, 0)}
        if key in ro_entries:
            return False
        if self._access.get(key) == "ro":           # imported EDS access right
            return False
        self._od[key] = value & 0xFFFFFFFF
        return True

    # -- EDS -------------------------------------------------------------
    def to_eds(self) -> EdsDocument:
        """Export the node's object dictionary as an :class:`EdsDocument`.

        Simple objects become a single parent row (``[0xNNNN]``); arrays get
        a parent descriptor row plus one ``.NN`` member row each — matching
        the EDS conventions used by :func:`parse_eds`/:func:`write_eds`.
        """
        doc = EdsDocument(device_info={
            "producername": "pyontrust",
            "producernumber": "0x00000001",
            "productnumber": "0x00000042",
            "revisionnumber": "0x00010000",
        })
        # (index, subindex) -> (name, type, access); parent rows keyed by -1
        names = {
            (0x1000, -1): ("Device type", 0x0007, "ro"),
            (0x1008, -1): ("Identity object", 0x0030, "ro"),
            (0x1008, 0): ("Producer specific ID", 0x0007, "ro"),
            (0x1008, 1): ("Product number", 0x0007, "ro"),
            (0x1008, 2): ("Revision number", 0x0007, "ro"),
            (0x1008, 3): ("Serial number", 0x0007, "ro"),
            (0x1014, -1): ("Error register", 0x0005, "ro"),
            (0x1015, -1): ("Status word", 0x0006, "rw"),
            (0x1016, -1): ("RPDO1 mapping", 0x0007, "ro"),
            (0x1018, -1): ("TPDO1 mapping", 0x0007, "ro"),
            (0x2000, -1): ("Motor control", 0x0030, "rw"),
            (0x2000, 0): ("Speed setpoint [rpm]", 0x0006, "rw"),
            (0x2000, 1): ("Torque limit [%]", 0x0005, "rw"),
            (0x3000, -1): ("Axis position [mm]", 0x0007, "ro"),
        }

        groups: dict[int, list[tuple[int, int]]] = {}
        for key in sorted(self._od):
            groups.setdefault(key[0], []).append(key)

        for idx, keys in sorted(groups.items()):
            if len(keys) == 1 and keys[0][1] == 0:
                # simple object -> single parent row
                name, typ, access = names.get((idx, -1),
                                              names.get((idx, 0), (f"Object {idx:#06x}", 0x0007, "rw")))
                doc.entries.append(EdsEntry(index=idx, subindex=-1, name=name,
                                            type=typ, access=access))
            else:
                # array -> parent descriptor row + member rows
                pname = names.get((idx, -1), (f"Object {idx:#06x}", 0x0030, "ro"))[0]
                doc.entries.append(EdsEntry(index=idx, subindex=-1, name=pname,
                                            type=0x0030, access="ro"))
                for (i2, s) in keys:
                    mname, mtyp, maccess = names.get((i2, s), (f"Sub {s}", 0x0007, "rw"))
                    doc.entries.append(EdsEntry(index=idx, subindex=s, name=mname,
                                                type=mtyp, access=maccess))
        return doc


__all__ = [
    "NMT_COB_ID", "SYNC_COB_ID", "EMCY_BASE", "TIME_STAMP_COB_ID",
    "TPDO1_BASE", "RPDO1_BASE", "SDO_CLIENT_BASE", "SDO_SERVER_BASE", "HEARTBEAT_BASE",
    "NMT_COMMANDS", "NMT_STATES", "HEARTBEAT_STATES", "EMCY_CODES", "ERROR_REGISTER_BITS",
    "nmt_frame", "sdo_upload_request", "sdo_download_request", "parse_sdo_response",
    "decode_emcy", "EDS_TYPES", "SDO_ABORT_CODES", "EdsEntry", "EdsDocument", "parse_eds", "write_eds",
    "SimulatedCanopenNode",
]
