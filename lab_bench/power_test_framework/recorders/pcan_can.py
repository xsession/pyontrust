from __future__ import annotations

import pathlib
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .base import Recorder

if TYPE_CHECKING:
    from ..core import TestContext


def _decode_canopen_cob_id(arbitration_id: int) -> dict[str, Any]:
    # CANopen 11-bit: function code (4 bits) + node id (7 bits)
    fc = (arbitration_id >> 7) & 0x0F
    node_id = arbitration_id & 0x7F
    return {"canopen_fc": fc, "canopen_node_id": node_id}


@dataclass
class PcanCanRecorder(Recorder):
    """PEAK-CAN recorder (python-can backend).

    Requires optional dependency `python-can` and PCAN drivers installed.

    Logs frames to `recorders/<name>.csv` with a basic CANopen COB-ID decode.
    """

    name: str = "pcan"
    channel: str = "PCAN_USBBUS1"
    bitrate: int = 500000
    bustype: str = "pcan"
    poll_timeout_s: float = 0.1

    _stop_evt: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _csv_path: pathlib.Path | None = field(default=None, init=False, repr=False)

    def start(self, ctx: TestContext) -> None:
        try:
            import can  # type: ignore
        except Exception as exc:  # noqa: BLE001
            ctx.recorder_outputs[self.name] = {
                "type": "pcan_can",
                "skipped": True,
                "reason": "python-can not installed",
                "error": repr(exc),
            }
            return

        self._stop_evt.clear()
        csv_path = ctx.artifacts.recorders_dir / f"{self.name}.csv"
        self._csv_path = csv_path

        def _worker() -> None:
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                f.write("t_s,arbitration_id,dlc,data_hex,canopen_fc,canopen_node_id\n")
                bus = can.interface.Bus(bustype=self.bustype, channel=self.channel, bitrate=self.bitrate)
                try:
                    while not self._stop_evt.is_set():
                        msg = bus.recv(timeout=self.poll_timeout_s)
                        if msg is None:
                            continue
                        now = ctx.now_s()
                        arb = int(msg.arbitration_id)
                        data_hex = (msg.data.hex() if msg.data else "")
                        dec = _decode_canopen_cob_id(arb)
                        f.write(
                            f"{now:.9f},{arb},{int(msg.dlc)},{data_hex},{dec['canopen_fc']},{dec['canopen_node_id']}\n"
                        )
                        f.flush()
                finally:
                    bus.shutdown()

        self._thread = threading.Thread(target=_worker, name=f"pcan:{self.name}", daemon=True)
        self._thread.start()
        ctx.recorder_outputs[self.name] = {
            "type": "pcan_can",
            "skipped": False,
            "channel": self.channel,
            "bitrate": self.bitrate,
            "file": str(csv_path),
        }

    def stop(self, ctx: TestContext) -> None:
        if self._thread is None:
            return
        self._stop_evt.set()
        self._thread.join(timeout=2.0)
        ctx.recorder_outputs.setdefault(self.name, {})
        ctx.recorder_outputs[self.name]["stopped"] = True
        self._thread = None
