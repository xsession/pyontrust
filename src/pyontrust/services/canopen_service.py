"""CANopen master + simulated slave nodes for the pyontrust gateway.

Built on python-can *virtual* bus channels: every participant (the monitor,
the master, each simulated slave) opens its own ``can.Bus`` instance on the
same channel name; frames are broadcast to all other instances — exactly like
a real CAN segment, but in-process and hardware-free.

Classes
-------
:class:`CanopenSlaveSimulator`
    In-process CANopen slave node: NMT state machine, SDO server (expedited
    read/write) and heartbeat producer, backed by
    :class:`pyontrust.analysis.canopen.SimulatedCanopenNode`.
:class:`CanopenMaster`
    Synchronous CANopen master: NMT commands + SDO expedited read/write with
    request/response transaction handling.
:class:`CanopenService`
    Facade used by the blueprint: starts/stops a simulated segment, exposes
    ``nmt_command`` / ``sdo_read`` / ``sdo_write`` and derives per-node
    heartbeat state from captured traffic.

Wire format follows CiA 301 as implemented by CANopenNode (CO_SDOclient.c /
CO_SDOserver.c): byte-0 command classes are ``0x20`` initiate download,
``0xC0`` initiate upload, ``0x43|((4-n)<<2)`` expedited upload response,
``0x60`` download ack and ``0x80`` abort.
"""
from __future__ import annotations

import logging
import struct
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

from pyontrust.analysis.canopen import (  # noqa: E402
    HEARTBEAT_BASE,
    HEARTBEAT_STATES,
    NMT_COB_ID,
    SDO_CLIENT_BASE,
    SDO_SERVER_BASE,
    SimulatedCanopenNode,
    decode_emcy,
    nmt_frame,
    parse_sdo_response,
    sdo_download_request,
    sdo_upload_request,
)

# Standard SDO abort codes (CiA 301 §7.4.6.2)
SDO_ABORT_WRITE_DENIED = 0x0601_0000   # write access not possible
SDO_ABORT_OBJECT_MISSING = 0x0609_0011  # object does not exist in the OD

SIM_CHANNEL = "pyontrust-can-sim"      # virtual-bus channel name


def _fit_bytes(value: int) -> int:
    """Smallest expedited size (1/2/4 bytes) that fits *value*."""
    v = value & 0xFFFFFFFF
    if v <= 0xFF:
        return 1
    if v <= 0xFFFF:
        return 2
    return 4


class CanopenSlaveSimulator:
    """A simulated CANopen slave node living on a python-can virtual channel.

    Handles, for its own ``node_id`` only:

    - NMT master frames (COB-ID 0x000) → state machine transitions
    - SDO server requests (COB-ID 0x600+N) → expedited read/write + ack/abort
    - Heartbeat producer (COB-ID 0x700+N), one frame per ``heartbeat_ms``

    The node's object dictionary is the standard simulated OD from
    :class:`SimulatedCanopenNode` (identity, status word, PDO mappings and a
    small vendor block: speed setpoint / torque limit / axis position).
    """

    def __init__(self, channel: str = SIM_CHANNEL, node_id: int = 1,
                 heartbeat_ms: int = 200) -> None:
        if not (1 <= node_id <= 127):
            raise ValueError("node_id must be 1..127")
        self.channel = channel
        self.node_id = node_id
        self.heartbeat_s = max(50, heartbeat_ms) / 1000.0
        self.node = SimulatedCanopenNode(node_id=node_id)
        self._bus: Any = None
        self._thread: threading.Thread | None = None
        self._running = False

    # ── lifecycle -------------------------------------------------------
    def start(self) -> dict:
        if self._running:
            return {"ok": True}
        try:
            import can  # noqa: F401
        except ImportError:
            return {"ok": False, "error": "python-can not installed"}
        try:
            self._bus = __import__("can").Bus(interface="virtual", channel=self.channel)
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": f"slave bus open failed: {exc}"}
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name=f"canopen-slave-{self.node_id}")
        self._thread.start()
        logger.info("CANopen slave node %d started on channel %r",
                    self.node_id, self.channel)
        return {"ok": True}

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:  # pragma: no cover - defensive
                pass
            self._bus = None

    @property
    def running(self) -> bool:
        return self._running

    # ── main loop --------------------------------------------------------
    def _loop(self) -> None:
        next_hb = time.time() + 0.05          # first heartbeat almost immediately
        while self._running and self._bus is not None:
            now = time.time()
            if now >= next_hb:
                self._send_heartbeat()
                next_hb += self.heartbeat_s
            try:
                msg = self._bus.recv(timeout=0.02)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("slave %d recv error: %s", self.node_id, exc)
                continue
            if msg is None:
                continue
            try:
                self._handle(msg)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("slave %d frame handling failed: %s", self.node_id, exc)

    def _send_heartbeat(self) -> None:
        if self._bus is None:
            return
        import can
        try:
            self._bus.send(can.Message(
                arbitration_id=0x700 + self.node_id,
                data=bytes([self.node.heartbeat_byte()]),
            ))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("slave %d heartbeat send failed: %s", self.node_id, exc)

    def _handle(self, msg: Any) -> None:
        arb = msg.arbitration_id & 0x7FF
        data = bytes(msg.data)

        if arb == NMT_COB_ID and len(data) >= 2:
            target = data[1]
            if target in (self.node_id, 0x00):      # 0x00 = broadcast "start all"
                self.node.handle_nmt(data[0])
            return

        if arb == SDO_SERVER_BASE + self.node_id and len(data) >= 4:
            self._handle_sdo_request(data)
            return

    def _handle_sdo_request(self, data: bytes) -> None:
        """SDO server side (client→server request on COB-ID 0x600+N)."""
        b0 = data[0]
        index = struct.unpack_from("<H", data, 1)[0]
        subindex = data[3]

        if (b0 & 0xF0) == 0xC0:                     # initiate upload (read)
            ok, value = self.node.sdo_read(index, subindex)
            if not ok:
                self._sdo_abort(index, subindex, SDO_ABORT_OBJECT_MISSING)
                return
            nbytes = _fit_bytes(value)
            byte0 = 0x43 | ((4 - nbytes) << 2)      # CANopenNode expedited response
            payload = bytes([byte0]) + struct.pack("<HB", index & 0xFFFF, subindex) \
                + (value & 0xFFFFFFFF).to_bytes(4, "little")[:nbytes].ljust(4, b"\x00")
            self._send_frame(SDO_CLIENT_BASE + self.node_id, payload)

        elif (b0 & 0xF0) == 0x20:                   # initiate download (write)
            value = int.from_bytes(data[4:8], "little") if len(data) >= 8 else 0
            ok = self.node.sdo_write(index, subindex, value)
            if ok:
                payload = bytes([0x60]) + struct.pack("<HB", index & 0xFFFF, subindex)
                self._send_frame(SDO_CLIENT_BASE + self.node_id, payload)
            else:
                code = SDO_ABORT_WRITE_DENIED
                # distinguish "object missing" from "read-only" for better UX
                probe_ok, _ = self.node.sdo_read(index, subindex)
                if not probe_ok:
                    code = SDO_ABORT_OBJECT_MISSING
                self._sdo_abort(index, subindex, code)

    def _sdo_abort(self, index: int, subindex: int, code: int) -> None:
        payload = bytes([0x80]) + struct.pack("<HB", index & 0xFFFF, subindex) \
            + (code & 0xFFFFFFFF).to_bytes(4, "little")
        self._send_frame(SDO_CLIENT_BASE + self.node_id, payload)

    def _send_frame(self, arb_id: int, data: bytes) -> None:
        if self._bus is None:
            return
        import can
        try:
            self._bus.send(can.Message(arbitration_id=arb_id, data=data))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("slave %d send failed: %s", self.node_id, exc)


class CanopenMaster:
    """Synchronous CANopen master (NMT + SDO expedited read/write).

    Opens its own bus instance on the channel; request/response transactions
    are serialized with a lock and matched by response COB-ID.
    """

    def __init__(self, channel: str = SIM_CHANNEL, timeout_s: float = 1.0) -> None:
        self.channel = channel
        self.timeout_s = timeout_s
        self._bus: Any = None
        self._lock = threading.Lock()
        # node_id -> (heartbeat_state_name, last_seen_ts); filled by the sniffer
        self.node_hb: dict[int, tuple[str, float]] = {}
        self._sniff_bus: Any = None          # dedicated instance — no recv() race with _transact
        self._sniff_thread: threading.Thread | None = None

    # ── lifecycle -------------------------------------------------------
    def start(self) -> dict:
        if self._bus is not None:
            return {"ok": True}
        try:
            import can  # noqa: F401
        except ImportError:
            return {"ok": False, "error": "python-can not installed"}
        try:
            self._bus = __import__("can").Bus(interface="virtual", channel=self.channel)
            self._sniff_bus = __import__("can").Bus(interface="virtual", channel=self.channel)
        except Exception as exc:  # pragma: no cover - defensive
            if self._bus is not None:
                try:
                    self._bus.shutdown()
                except Exception:
                    pass
            self._bus = None
            return {"ok": False, "error": f"master bus open failed: {exc}"}
        self.node_hb.clear()
        self._sniff_thread = threading.Thread(target=self._sniff_loop, daemon=True,
                                              name="canopen-hb-sniffer")
        self._sniff_thread.start()
        logger.info("CANopen master started on channel %r", self.channel)
        return {"ok": True}

    def stop(self) -> None:
        for bus in (self._bus, self._sniff_bus):
            if bus is not None:
                try:
                    bus.shutdown()
                except Exception:  # pragma: no cover - defensive
                    pass
        self._bus = None
        self._sniff_bus = None
        self.node_hb.clear()

    @property
    def running(self) -> bool:
        return self._bus is not None

    # ── heartbeat sniffer --------------------------------------------------
    def _sniff_loop(self) -> None:
        """Passively record node heartbeats (COB-ID 0x701..0x780)."""
        while self._sniff_bus is not None:
            try:
                msg = self._sniff_bus.recv(timeout=0.05)
            except Exception:  # pragma: no cover - defensive
                break
            if msg is None:
                continue
            arb = msg.arbitration_id & 0x7FF
            data = bytes(msg.data)
            if HEARTBEAT_BASE < arb <= HEARTBEAT_BASE + 127 and len(data) >= 1 \
                    and data[0] in HEARTBEAT_STATES:
                self.node_hb[arb - HEARTBEAT_BASE] = (HEARTBEAT_STATES[data[0]], time.time())

    # ── transactions -----------------------------------------------------
    def _transact(self, arb_id: int, data: bytes, resp_arb: int | None) -> dict:
        """Send *data* on *arb_id*; if *resp_arb* given wait for that frame."""
        import can
        with self._lock:
            bus = self._bus
            if bus is None:
                return {"ok": False, "error": "master not started"}
            try:
                bus.send(can.Message(arbitration_id=arb_id, data=data))
            except Exception as exc:
                return {"ok": False, "error": f"send failed: {exc}"}

            if resp_arb is None:
                return {"ok": True}

            deadline = time.time() + self.timeout_s
            while time.time() < deadline:
                try:
                    msg = bus.recv(timeout=0.02)
                except Exception as exc:  # pragma: no cover - defensive
                    return {"ok": False, "error": f"recv failed: {exc}"}
                if msg is None:
                    continue
                if (msg.arbitration_id & 0x7FF) == resp_arb:
                    return parse_sdo_response(bytes(msg.data))
                # other traffic on the segment — ignore, keep waiting

        return {"ok": False, "error": f"timeout after {self.timeout_s:.1f}s"}

    # ── public API -------------------------------------------------------
    def nmt_command(self, node_id: int, command: int) -> dict:
        """Send an NMT master frame (COB-ID 0x000)."""
        try:
            arb, data = nmt_frame(node_id, command)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        out = self._transact(arb, data, resp_arb=None)
        if out.get("ok"):
            from pyontrust.analysis.canopen import NMT_COMMANDS
            out["command"] = NMT_COMMANDS.get(command, f"0x{command:02X}")
            out["node_id"] = node_id
        return out

    def sdo_read(self, node_id: int, index: int, subindex: int) -> dict:
        """SDO expedited upload (read) from a slave's object dictionary."""
        try:
            arb, data = sdo_upload_request(node_id, index, subindex)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        out = self._transact(arb, data, resp_arb=SDO_CLIENT_BASE + node_id)
        if out.get("ok") and "value" in out:
            out["index"] = index
            out["subindex"] = subindex
        return out

    def sdo_write(self, node_id: int, index: int, subindex: int, value: int) -> dict:
        """SDO expedited download (write) to a slave's object dictionary."""
        try:
            arb, data = sdo_download_request(node_id, index, subindex, value)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        out = self._transact(arb, data, resp_arb=SDO_CLIENT_BASE + node_id)
        if not out.get("ok") and "error_code" in out:
            from pyontrust.analysis.canopen import SDO_ABORT_CODES
            out["abort"] = SDO_ABORT_CODES.get(out["error_code"],
                                               f"0x{out['error_code']:08X}")
        return out


class CanopenService:
    """Facade for the gateway blueprint.

    Owns one :class:`CanopenMaster` plus zero or more
    :class:`CanopenSlaveSimulator` instances on a shared virtual channel, and
    derives per-node heartbeat state from captured traffic (any source).
    """

    def __init__(self) -> None:
        self.channel = SIM_CHANNEL
        self.master = CanopenMaster(channel=self.channel)
        self.slaves: dict[int, CanopenSlaveSimulator] = {}
        self._lock = threading.Lock()
        # EDS document loaded via the GUI (for object-dictionary browsing)
        self.loaded_eds_text: str | None = None
        self.loaded_eds_doc: Any = None

    # ── simulation lifecycle ---------------------------------------------
    def start_simulation(self, node_ids: list[int] | None = None,
                         heartbeat_ms: int = 200) -> dict:
        """Open the virtual segment and spawn simulated slave nodes."""
        with self._lock:
            if self.master.running or self.slaves:
                return {"ok": False, "error": "simulation already running — stop first"}
            node_ids = [n for n in (node_ids or [1]) if 1 <= int(n) <= 127]
            if not node_ids:
                return {"ok": False, "error": "no valid node ids"}

            mres = self.master.start()
            if not mres.get("ok"):
                return mres

            started: list[int] = []
            for nid in sorted(set(node_ids)):
                sim = CanopenSlaveSimulator(self.channel, nid, heartbeat_ms)
                res = sim.start()
                if not res.get("ok"):
                    # roll back what we started
                    self.stop_simulation()
                    return {"ok": False, "error": f"node {nid}: {res.get('error')}"}
                if self.loaded_eds_doc is not None:
                    try:
                        sim.node.import_eds(self.loaded_eds_doc)
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning("EDS merge into node %d failed: %s", nid, exc)
                self.slaves[nid] = sim
                started.append(nid)
            logger.info("CANopen simulation running: nodes %s on %r", started, self.channel)
            return {"ok": True, "nodes": started, "channel": self.channel}

    def stop_simulation(self) -> dict:
        with self._lock:
            for sim in list(self.slaves.values()):
                sim.stop()
            self.slaves.clear()
            self.master.stop()
            return {"ok": True}

    @property
    def running(self) -> bool:
        return self.master.running or bool(self.slaves)

    # ── master operations --------------------------------------------------
    def nmt_command(self, node_id: int, command: int) -> dict:
        if not self.master.running:
            return {"ok": False, "error": "bus not running — start simulation first"}
        return self.master.nmt_command(node_id, command)

    def sdo_read(self, node_id: int, index: int, subindex: int) -> dict:
        if not self.master.running:
            return {"ok": False, "error": "bus not running — start simulation first"}
        return self.master.sdo_read(node_id, index, subindex)

    def sdo_write(self, node_id: int, index: int, subindex: int, value: int) -> dict:
        if not self.master.running:
            return {"ok": False, "error": "bus not running — start simulation first"}
        return self.master.sdo_write(node_id, index, subindex, value)

    # ── node state ----------------------------------------------------------
    def get_nodes(self, snapshot: dict | None = None) -> list[dict]:
        """Per-node status: heartbeat state + last-seen age.

        *snapshot* is a ``CanDiagService.get_snapshot()`` result; when given,
        recent HEARTBEAT frames are scanned for the freshest state per node.
        Simulated nodes also report their authoritative NMT state directly.
        """
        hb: dict[int, tuple[str, float]] = {}   # node_id -> (state_name, ts)
        for nid, (st, ts) in self.master.node_hb.items():
            hb[nid] = (st, ts)
        if snapshot:
            for m in reversed(snapshot.get("messages", [])):
                co = m.get("canopen") or ""
                det = m.get("canopen_detail") or ""
                if co == "HEARTBEAT" and ": " in det:
                    try:
                        nid_s, state = det.split(": ", 1)
                        nid = int(nid_s.replace("Node", "").strip())
                    except (ValueError, AttributeError):
                        continue
                    if nid not in hb:
                        hb[nid] = (state, float(m.get("ts") or 0.0))

        now = time.time()
        nodes: list[dict] = []
        for nid in sorted(set(list(self.slaves.keys()) + list(hb.keys()))):
            sim = self.slaves.get(nid)
            entry: dict[str, Any] = {"node_id": nid}
            if sim is not None:
                entry["nmt_state"] = sim.node.state
                entry["simulated"] = True
            hstate, ts = hb.get(nid, (None, 0.0))
            entry["heartbeat_state"] = hstate
            entry["last_seen_s"] = round(now - ts, 3) if ts else None
            nodes.append(entry)
        return nodes

    def decode_emcy_frame(self, data: bytes) -> dict:
        """Decode an EMCY payload (used by the GUI diagnostics panel)."""
        return decode_emcy(bytes(data))

    # ── EDS / object dictionary -------------------------------------------
    def load_eds(self, text: str) -> dict:
        """Parse and store an uploaded EDS document.

        The object dictionary is also merged into every running simulated
        slave (new objects start at 0; access rights are enforced), so the
        SDO panel can be exercised against your own device description.
        """
        from pyontrust.analysis.canopen import parse_eds
        try:
            doc = parse_eds(text or "")
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": f"EDS parse failed: {exc}"}
        self.loaded_eds_text = text
        self.loaded_eds_doc = doc
        added_total = 0
        for sim in self.slaves.values():
            try:
                added_total += sim.node.import_eds(doc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("EDS merge into node %d failed: %s", sim.node_id, exc)
        return {"ok": True, "entries": len(doc.entries),
                "device": dict(doc.device_info), "imported_objects": added_total}

    def get_object_dictionary(self) -> list[dict]:
        """Rows for the OD browser: loaded EDS first, else simulated node."""
        if self.loaded_eds_doc is not None:
            return [e.to_dict() for e in self.loaded_eds_doc.entries]
        sims = sorted(self.slaves.values(), key=lambda s: s.node_id)
        if sims:
            return [e.to_dict() for e in sims[0].node.to_eds().entries]
        from pyontrust.analysis.canopen import SimulatedCanopenNode
        return [e.to_dict() for e in SimulatedCanopenNode(node_id=1).to_eds().entries]

    def export_eds(self, node_id: int | None = None) -> str:
        """EDS text for download: simulated node's OD or the loaded document."""
        from pyontrust.analysis.canopen import write_eds
        if node_id is not None and node_id in self.slaves:
            return write_eds(self.slaves[node_id].node.to_eds())
        if self.loaded_eds_doc is not None:
            return self.loaded_eds_text or ""
        sims = sorted(self.slaves.values(), key=lambda s: s.node_id)
        if sims:
            return write_eds(sims[0].node.to_eds())
        from pyontrust.analysis.canopen import SimulatedCanopenNode
        return write_eds(SimulatedCanopenNode(node_id=1).to_eds())


__all__ = [
    "SIM_CHANNEL",
    "SDO_ABORT_WRITE_DENIED",
    "SDO_ABORT_OBJECT_MISSING",
    "CanopenSlaveSimulator",
    "CanopenMaster",
    "CanopenService",
]
