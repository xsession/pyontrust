"""CAN bus diagnostic service — sniffing, sending, CANopen, reverse-engineering.

Wraps ``python-can`` (with PCAN / SocketCAN / Virtual backends) and provides:

- **Live capture** with configurable bitrate, filters, ring-buffer
- **Message statistics** — period, rate, jitter, byte-change tracking
- **CANopen dictionary** — heartbeat, SDO, PDO, NMT, EMCY decoding
- **Reverse-engineering toolkit** — bit-flip detection, counter/CRC guessing,
  value correlation, DBC-stub generation
- **Logging** — ASC / BLF / CSV export
- **Thread-safe design** — capture runs in a daemon thread, stats are
  snapshotted on demand via ``get_snapshot()``

No hardware is required for development — set ``interface="virtual"``
and the service will use python-can's virtual loopback.
"""
from __future__ import annotations

import collections
import copy
import io
import logging
import math
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pyontrust.services.can_service")

# ═══════════════════════════════════════════════════════════════════════
#  Data models
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MsgStats:
    """Per-ID running statistics."""
    arb_id: int
    count: int = 0
    first_ts: float = 0.0
    last_ts: float = 0.0
    period_s: float = 0.0          # rolling average period
    min_period_s: float = float("inf")
    max_period_s: float = 0.0
    jitter_s: float = 0.0          # max_period - min_period
    last_data: bytes = b""
    byte_change_mask: int = 0      # which bytes have ever changed
    dlc: int = 0
    is_extended: bool = False
    # Reverse-engineering hints
    suspected_counter_byte: int = -1
    suspected_crc_byte: int = -1
    monotonic_bytes: list[int] = field(default_factory=list)


@dataclass
class CanOpenInfo:
    """Decoded CANopen layer info for a single frame."""
    cob_id: int = 0
    node_id: int = 0
    function: str = ""             # NMT, SYNC, EMCY, PDO1_TX, SDO_TX, HB, …
    detail: str = ""               # human-readable payload summary


# ═══════════════════════════════════════════════════════════════════════
#  CANopen decoder
# ═══════════════════════════════════════════════════════════════════════

# CANopen function codes (COB-ID ranges)
_CANOPEN_FUNCTIONS = [
    (0x000, 0x000, "NMT"),
    (0x080, 0x080, "SYNC"),
    (0x081, 0x0FF, "EMCY"),
    (0x100, 0x100, "TIMESTAMP"),
    (0x180, 0x1FF, "PDO1_TX"),
    (0x200, 0x27F, "PDO1_RX"),
    (0x280, 0x2FF, "PDO2_TX"),
    (0x300, 0x37F, "PDO2_RX"),
    (0x380, 0x3FF, "PDO3_TX"),
    (0x400, 0x47F, "PDO3_RX"),
    (0x480, 0x4FF, "PDO4_TX"),
    (0x500, 0x57F, "PDO4_RX"),
    (0x580, 0x5FF, "SDO_TX"),
    (0x600, 0x67F, "SDO_RX"),
    (0x700, 0x77F, "HEARTBEAT"),
    (0x7E4, 0x7E4, "LSS_TX"),
    (0x7E5, 0x7E5, "LSS_RX"),
]

_NMT_COMMANDS = {0x01: "Start", 0x02: "Stop", 0x80: "Pre-Op",
                 0x81: "Reset Node", 0x82: "Reset Comm"}
_HB_STATES = {0x00: "Boot-up", 0x04: "Stopped", 0x05: "Operational",
              0x7F: "Pre-operational"}


def decode_canopen(arb_id: int, data: bytes) -> CanOpenInfo | None:
    """Decode a CAN frame as CANopen, or return None if not CANopen."""
    info = CanOpenInfo(cob_id=arb_id)

    for lo, hi, func in _CANOPEN_FUNCTIONS:
        if lo <= arb_id <= hi:
            info.function = func
            if func != "NMT" and func != "SYNC" and func != "TIMESTAMP":
                info.node_id = arb_id - lo + (0 if lo == hi else 0)
                # Standard CANopen: node_id = COB-ID & 0x7F
                info.node_id = arb_id & 0x7F
            break
    else:
        return None  # not a standard CANopen COB-ID

    # Decode payload
    if info.function == "NMT" and len(data) >= 2:
        cmd = _NMT_COMMANDS.get(data[0], f"0x{data[0]:02X}")
        info.node_id = data[1]
        info.detail = f"NMT {cmd} → Node {data[1]}"
    elif info.function == "HEARTBEAT" and len(data) >= 1:
        state = _HB_STATES.get(data[0], f"0x{data[0]:02X}")
        info.detail = f"HB Node {info.node_id}: {state}"
    elif info.function == "EMCY" and len(data) >= 3:
        eec = struct.unpack_from("<H", data, 0)[0]
        er = data[2]
        info.detail = f"EMCY Node {info.node_id}: EEC=0x{eec:04X} ER=0x{er:02X}"
    elif info.function.startswith("SDO"):
        if len(data) >= 1:
            cs = (data[0] >> 5) & 0x07
            sdo_cmds = {0: "Download seg", 1: "Initiate download",
                        2: "Initiate upload", 3: "Upload seg",
                        4: "Abort"}
            cmd = sdo_cmds.get(cs, f"cs={cs}")
            if len(data) >= 4:
                idx = struct.unpack_from("<H", data, 1)[0]
                sub = data[3]
                info.detail = f"SDO {cmd} 0x{idx:04X}.{sub:02X}"
            else:
                info.detail = f"SDO {cmd}"
    elif info.function.startswith("PDO"):
        info.detail = f"{info.function} Node {info.node_id}: {data.hex(' ').upper()}"
    elif info.function == "SYNC":
        info.detail = "SYNC"
    elif info.function == "TIMESTAMP" and len(data) >= 6:
        info.detail = f"TIME: {data.hex(' ')}"

    return info


# ═══════════════════════════════════════════════════════════════════════
#  Reverse-engineering helpers
# ═══════════════════════════════════════════════════════════════════════

def find_counter_bytes(history: list[bytes]) -> list[int]:
    """Identify byte positions that increment monotonically (mod 256).

    Returns list of byte indices that look like rolling counters.
    """
    if len(history) < 10:
        return []
    dlc = min(len(d) for d in history)
    counters: list[int] = []
    for byte_idx in range(dlc):
        mono_up = 0
        for i in range(1, len(history)):
            diff = (history[i][byte_idx] - history[i - 1][byte_idx]) & 0xFF
            if 1 <= diff <= 2:
                mono_up += 1
        if mono_up > len(history) * 0.8:
            counters.append(byte_idx)
    return counters


def find_crc_bytes(history: list[bytes]) -> list[int]:
    """Identify byte positions that change every frame but aren't counters.

    Heuristic: high entropy byte that changes nearly every frame and
    doesn't correlate with adjacent bytes.
    """
    if len(history) < 10:
        return []
    dlc = min(len(d) for d in history)
    counters = set(find_counter_bytes(history))
    candidates: list[int] = []
    for byte_idx in range(dlc):
        if byte_idx in counters:
            continue
        changes = sum(1 for i in range(1, len(history))
                      if history[i][byte_idx] != history[i - 1][byte_idx])
        if changes > len(history) * 0.9:
            # High change rate — could be CRC
            vals = set(h[byte_idx] for h in history)
            if len(vals) > len(history) * 0.5:
                candidates.append(byte_idx)
    return candidates


def compute_bit_transitions(history: list[bytes]) -> list[list[int]]:
    """For each bit in the frame, count how many times it flipped.

    Returns a 2D list: [byte_idx][bit_idx] → flip count.
    Useful for identifying static vs dynamic bits.
    """
    if len(history) < 2:
        return []
    dlc = min(len(d) for d in history)
    transitions = [[0] * 8 for _ in range(dlc)]
    for i in range(1, len(history)):
        for b in range(dlc):
            xor = history[i][b] ^ history[i - 1][b]
            for bit in range(8):
                if xor & (1 << bit):
                    transitions[b][bit] += 1
    return transitions


def extract_signals_heuristic(history: list[bytes]) -> list[dict]:
    """Heuristic signal extraction — find likely multi-bit signals.

    Identifies groups of bits that change together (correlated transitions).
    Returns a list of candidate signal descriptors.
    """
    if len(history) < 20:
        return []
    dlc = min(len(d) for d in history)
    transitions = compute_bit_transitions(history)

    # Flatten to bit-level transition counts
    flat: list[int] = []
    for b in range(dlc):
        flat.extend(transitions[b])

    signals: list[dict] = []
    n_bits = dlc * 8
    visited = [False] * n_bits

    for i in range(n_bits):
        if visited[i] or flat[i] < len(history) * 0.05:
            continue
        # Find contiguous bits with similar transition count
        group = [i]
        visited[i] = True
        for j in range(i + 1, min(i + 16, n_bits)):
            if visited[j]:
                break
            ratio = flat[j] / flat[i] if flat[i] > 0 else 0
            if 0.5 <= ratio <= 2.0 and flat[j] > len(history) * 0.05:
                group.append(j)
                visited[j] = True
            else:
                break
        if len(group) >= 2:
            start_byte, start_bit = group[0] // 8, group[0] % 8
            signals.append({
                "start_byte": start_byte,
                "start_bit": start_bit,
                "length_bits": len(group),
                "transitions": sum(flat[g] for g in group) // len(group),
                "suspected_type": "counter" if len(group) <= 8 and
                    all((flat[g] - flat[group[0]]) < len(history) * 0.1 for g in group)
                    else "value",
            })
    return signals


def generate_dbc_stub(msg_stats: dict[int, MsgStats],
                      msg_history: dict[int, list[bytes]]) -> str:
    """Generate a minimal DBC file from observed traffic.

    Creates message definitions with heuristic signal extraction.
    """
    lines = [
        'VERSION ""',
        "",
        "NS_ :",
        "",
        "BS_:",
        "",
        'BU_: Observer',
        "",
    ]

    for arb_id in sorted(msg_stats.keys()):
        st = msg_stats[arb_id]
        name = f"MSG_0x{arb_id:03X}"
        lines.append(f'BO_ {arb_id} {name}: {st.dlc} Vector__XXX')

        # Try to extract signals
        history = msg_history.get(arb_id, [])
        if history:
            signals = extract_signals_heuristic(history)
            for idx, sig in enumerate(signals):
                sname = f"SIG_{arb_id:03X}_{idx}"
                sb = sig["start_byte"] * 8 + sig["start_bit"]
                bits = sig["length_bits"]
                lines.append(
                    f' SG_ {sname} : {sb}|{bits}@1+ (1,0) [0|0] "" Vector__XXX'
                )
        lines.append("")

    lines.append("")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  CAN Diagnostic Service
# ═══════════════════════════════════════════════════════════════════════

# Maximum history frames kept per arb_id for reverse-engineering
_MAX_HISTORY = 200
# Maximum number of distinct IDs tracked
_MAX_IDS = 2048
# Ring buffer size for live traffic view
_RING_SIZE = 5000


class CanDiagService:
    """Thread-safe CAN bus diagnostic engine.

    Usage::

        svc = CanDiagService()
        svc.start("pcan", "PCAN_USBBUS1", 500_000)
        snapshot = svc.get_snapshot()   # {messages, stats, canopen}
        svc.send_frame(0x123, bytes([0x01, 0x02]))
        svc.stop()
    """

    def __init__(self) -> None:
        self._bus: Any = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Live ring buffer
        self._ring: collections.deque[dict] = collections.deque(maxlen=_RING_SIZE)
        self._total_frames: int = 0
        self._start_ts: float = 0.0
        self._bus_load_count: int = 0       # frames in current 1s window
        self._bus_load_ts: float = 0.0
        self._bus_load_pct: float = 0.0

        # Per-ID statistics
        self._stats: dict[int, MsgStats] = {}
        # Per-ID data history (for reverse-engineering)
        self._history: dict[int, list[bytes]] = {}

        # Filters
        self._id_filter: set[int] | None = None   # None = accept all
        self._id_mask_filter: tuple[int, int] | None = None  # (id, mask)

        # Connection info
        self._interface: str = ""
        self._channel: str = ""
        self._bitrate: int = 500_000

        # Error tracking
        self._errors: list[str] = []
        self._error_count: int = 0

    # ── Connection management ────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, interface: str = "pcan",
              channel: str = "PCAN_USBBUS1",
              bitrate: int = 500_000,
              fd: bool = False) -> dict:
        """Open CAN bus and start capture thread.

        Returns ``{"ok": True}`` or ``{"ok": False, "error": "..."}``
        """
        if self._running:
            return {"ok": False, "error": "Already running — stop first"}

        self._interface = interface
        self._channel = channel
        self._bitrate = bitrate

        try:
            import can
            kwargs: dict[str, Any] = {
                "interface": interface,
                "channel": channel,
                "bitrate": bitrate,
            }
            if fd:
                kwargs["fd"] = True
            self._bus = can.Bus(**kwargs)
        except ImportError:
            return {"ok": False,
                    "error": "python-can not installed: pip install python-can"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        self._running = True
        self._start_ts = time.time()
        self._total_frames = 0
        self._errors.clear()
        self._error_count = 0
        self._bus_load_ts = time.time()
        self._bus_load_count = 0

        self._thread = threading.Thread(target=self._capture_loop, daemon=True,
                                        name="can-capture")
        self._thread.start()
        logger.info("CAN capture started: %s/%s @ %d bps", interface, channel, bitrate)
        return {"ok": True}

    def stop(self) -> dict:
        """Stop capture and close bus."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self._bus:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None
        logger.info("CAN capture stopped. Total frames: %d", self._total_frames)
        return {"ok": True, "total_frames": self._total_frames}

    def clear(self) -> None:
        """Clear all captured data and statistics."""
        with self._lock:
            self._ring.clear()
            self._stats.clear()
            self._history.clear()
            self._total_frames = 0
            self._errors.clear()
            self._error_count = 0

    # ── Capture loop ─────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Background thread: read frames, update stats, fill ring buffer."""
        while self._running and self._bus is not None:
            try:
                msg = self._bus.recv(timeout=0.1)
                if msg is None:
                    continue
                if msg.is_error_frame:
                    self._error_count += 1
                    with self._lock:
                        self._errors.append(
                            f"t={msg.timestamp:.3f} Error frame")
                        if len(self._errors) > 100:
                            self._errors.pop(0)
                    continue

                ts = msg.timestamp or time.time()
                arb_id = msg.arbitration_id
                data = bytes(msg.data)
                dlc = msg.dlc
                is_ext = msg.is_extended_id

                # Apply filter
                if self._id_filter is not None and arb_id not in self._id_filter:
                    continue
                if self._id_mask_filter is not None:
                    fid, fmask = self._id_mask_filter
                    if (arb_id & fmask) != (fid & fmask):
                        continue

                self._total_frames += 1

                # Bus load estimation (frames per second)
                self._bus_load_count += 1
                now = time.time()
                if now - self._bus_load_ts >= 1.0:
                    self._bus_load_pct = min(100.0,
                        self._bus_load_count / 80.0 * 100)  # ~8000 max for 500k
                    self._bus_load_count = 0
                    self._bus_load_ts = now

                # CANopen decode
                co = decode_canopen(arb_id, data)

                # Build ring entry
                entry = {
                    "ts": round(ts, 6),
                    "id": arb_id,
                    "hex_id": f"0x{arb_id:03X}",
                    "dlc": dlc,
                    "data": data.hex(" ").upper(),
                    "ext": is_ext,
                    "canopen": co.function if co else "",
                    "canopen_detail": co.detail if co else "",
                }

                with self._lock:
                    self._ring.append(entry)
                    self._update_stats(arb_id, data, ts, dlc, is_ext)

            except Exception as exc:
                self._error_count += 1
                logger.debug("CAN recv error: %s", exc)
                time.sleep(0.01)

    def _update_stats(self, arb_id: int, data: bytes, ts: float,
                      dlc: int, is_ext: bool) -> None:
        """Update per-ID statistics (called under lock)."""
        if arb_id not in self._stats:
            if len(self._stats) >= _MAX_IDS:
                return
            self._stats[arb_id] = MsgStats(arb_id=arb_id, first_ts=ts)
            self._history[arb_id] = []

        st = self._stats[arb_id]
        st.count += 1
        st.dlc = dlc
        st.is_extended = is_ext

        # Period tracking
        if st.last_ts > 0:
            dt = ts - st.last_ts
            if dt > 0:
                if st.period_s == 0:
                    st.period_s = dt
                else:
                    st.period_s = 0.9 * st.period_s + 0.1 * dt  # EWMA
                st.min_period_s = min(st.min_period_s, dt)
                st.max_period_s = max(st.max_period_s, dt)
                st.jitter_s = st.max_period_s - st.min_period_s
        st.last_ts = ts

        # Byte change mask
        if st.last_data:
            for i in range(min(len(data), len(st.last_data))):
                if data[i] != st.last_data[i]:
                    st.byte_change_mask |= (1 << i)
        st.last_data = data

        # History for RE
        hist = self._history[arb_id]
        hist.append(data)
        if len(hist) > _MAX_HISTORY:
            hist.pop(0)

    # ── Send ─────────────────────────────────────────────────────────

    def send_frame(self, arb_id: int, data: bytes,
                   is_extended: bool = False) -> dict:
        """Send a single CAN frame."""
        if not self._bus:
            return {"ok": False, "error": "Bus not open"}
        try:
            import can
            msg = can.Message(arbitration_id=arb_id, data=data,
                              is_extended_id=is_extended)
            self._bus.send(msg)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ── Filters ──────────────────────────────────────────────────────

    def set_id_filter(self, ids: list[int] | None) -> None:
        """Filter capture to specific IDs, or None to accept all."""
        self._id_filter = set(ids) if ids else None

    def set_mask_filter(self, arb_id: int, mask: int) -> None:
        """Filter by ID/mask pair."""
        self._id_mask_filter = (arb_id, mask)

    def clear_filters(self) -> None:
        self._id_filter = None
        self._id_mask_filter = None

    # ── Snapshot / query ─────────────────────────────────────────────

    def get_snapshot(self, last_n: int = 200) -> dict:
        """Get current state: recent messages, stats, connection info."""
        with self._lock:
            msgs = list(self._ring)[-last_n:]
            stats = {}
            for arb_id, st in self._stats.items():
                stats[arb_id] = {
                    "arb_id": arb_id,
                    "hex_id": f"0x{arb_id:03X}",
                    "count": st.count,
                    "dlc": st.dlc,
                    "period_ms": round(st.period_s * 1000, 2) if st.period_s else 0,
                    "min_period_ms": round(st.min_period_s * 1000, 2) if st.min_period_s != float("inf") else 0,
                    "max_period_ms": round(st.max_period_s * 1000, 2),
                    "jitter_ms": round(st.jitter_s * 1000, 2),
                    "rate_hz": round(1.0 / st.period_s, 1) if st.period_s > 0 else 0,
                    "last_data": st.last_data.hex(" ").upper() if st.last_data else "",
                    "byte_change_mask": f"0x{st.byte_change_mask:02X}",
                    "is_extended": st.is_extended,
                }

        return {
            "running": self._running,
            "interface": self._interface,
            "channel": self._channel,
            "bitrate": self._bitrate,
            "total_frames": self._total_frames,
            "unique_ids": len(stats),
            "bus_load_pct": round(self._bus_load_pct, 1),
            "error_count": self._error_count,
            "messages": msgs,
            "stats": stats,
            "uptime_s": round(time.time() - self._start_ts, 1) if self._start_ts else 0,
        }

    def get_stats_table(self) -> list[dict]:
        """Get per-ID stats sorted by arb_id."""
        with self._lock:
            rows = []
            for arb_id in sorted(self._stats.keys()):
                st = self._stats[arb_id]
                co = decode_canopen(arb_id, st.last_data) if st.last_data else None
                rows.append({
                    "arb_id": arb_id,
                    "hex_id": f"0x{arb_id:03X}",
                    "count": st.count,
                    "dlc": st.dlc,
                    "period_ms": round(st.period_s * 1000, 2) if st.period_s else 0,
                    "jitter_ms": round(st.jitter_s * 1000, 2),
                    "rate_hz": round(1.0 / st.period_s, 1) if st.period_s > 0 else 0,
                    "last_data": st.last_data.hex(" ").upper() if st.last_data else "",
                    "byte_change_mask": f"0x{st.byte_change_mask:02X}",
                    "canopen": co.function if co else "",
                    "canopen_detail": co.detail if co else "",
                })
        return rows

    # ── Reverse-engineering ──────────────────────────────────────────

    def analyze_message(self, arb_id: int) -> dict:
        """Deep analysis of a single message ID for reverse engineering."""
        with self._lock:
            st = self._stats.get(arb_id)
            hist = list(self._history.get(arb_id, []))
        if not st:
            return {"error": f"No data for 0x{arb_id:03X}"}

        counters = find_counter_bytes(hist)
        crcs = find_crc_bytes(hist)
        transitions = compute_bit_transitions(hist)
        signals = extract_signals_heuristic(hist)
        co = decode_canopen(arb_id, st.last_data) if st.last_data else None

        # Byte value ranges
        byte_ranges = []
        if hist:
            dlc = min(len(d) for d in hist)
            for b in range(dlc):
                vals = [h[b] for h in hist]
                byte_ranges.append({
                    "byte": b,
                    "min": min(vals),
                    "max": max(vals),
                    "unique": len(set(vals)),
                    "is_static": min(vals) == max(vals),
                })

        return {
            "arb_id": arb_id,
            "hex_id": f"0x{arb_id:03X}",
            "count": st.count,
            "dlc": st.dlc,
            "period_ms": round(st.period_s * 1000, 2) if st.period_s else 0,
            "jitter_ms": round(st.jitter_s * 1000, 2),
            "counter_bytes": counters,
            "crc_bytes": crcs,
            "signals": signals,
            "bit_transitions": transitions,
            "byte_ranges": byte_ranges,
            "canopen": {
                "function": co.function if co else "",
                "node_id": co.node_id if co else 0,
                "detail": co.detail if co else "",
            },
            "sample_count": len(hist),
        }

    def generate_dbc(self) -> str:
        """Generate a DBC file stub from all observed traffic."""
        with self._lock:
            stats_copy = dict(self._stats)
            hist_copy = {k: list(v) for k, v in self._history.items()}
        return generate_dbc_stub(stats_copy, hist_copy)

    # ── Export / logging ─────────────────────────────────────────────

    def export_log(self, fmt: str = "asc") -> str:
        """Export captured messages as ASC or CSV string."""
        with self._lock:
            msgs = list(self._ring)

        if fmt == "csv":
            lines = ["timestamp,id,dlc,data,canopen"]
            for m in msgs:
                lines.append(f"{m['ts']},{m['hex_id']},{m['dlc']},{m['data']},{m['canopen']}")
            return "\n".join(lines)

        # ASC format (PEAK compatible)
        lines = [f"date {time.strftime('%a %b %d %I:%M:%S %p %Y')}",
                 "base hex  timestamps absolute",
                 "internal events logged",
                 ""]
        for m in msgs:
            data_str = m["data"].replace(" ", " ")
            lines.append(
                f"  {m['ts']:.6f} 1  {m['hex_id']:>8s}       Rx   d {m['dlc']} "
                f" {data_str}")
        return "\n".join(lines)

    def export_blf(self) -> bytes:
        """Export as BLF (Binary Logging Format) bytes."""
        try:
            import can
            buf = io.BytesIO()
            with can.BLFWriter(buf) as writer:
                with self._lock:
                    for m in self._ring:
                        msg = can.Message(
                            timestamp=m["ts"],
                            arbitration_id=m["id"],
                            data=bytes.fromhex(m["data"].replace(" ", "")),
                            dlc=m["dlc"],
                            is_extended_id=m.get("ext", False),
                        )
                        writer.on_message_received(msg)
            return buf.getvalue()
        except ImportError:
            raise RuntimeError("python-can required for BLF export")
