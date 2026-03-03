from __future__ import annotations

import pathlib
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .base import Recorder
try:
    import serial
    from serial.tools import list_ports
except Exception as exc:  # pragma: no cover - optional dependency
    serial = None
    list_ports = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


DEFAULT_VID = 0x1915
DEFAULT_PIDS = (0x521F,)


@dataclass
class Nrf52840DongleRecorder(Recorder):
    """Record serial output from an nRF52840 USB dongle.

    Produces:
    - `recorders/<name>.log` (text) or `recorders/<name>.bin` (binary)
    """

    name: str = "nrf52840_dongle"
    port: Optional[str] = None
    baudrate: int = 115200
    timeout_s: float = 0.2
    read_mode: str = "text"  # "text" or "binary"
    encoding: str = "utf-8"
    errors: str = "replace"

    vid: int = DEFAULT_VID
    pids: tuple[int, ...] = DEFAULT_PIDS

    skip_if_missing: bool = True

    _serial: serial.Serial | None = field(default=None, init=False, repr=False)  # type: ignore[union-attr]
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _out_path: pathlib.Path | None = field(default=None, init=False, repr=False)

    @staticmethod
    def _ensure_serial() -> None:
        if serial is None:
            raise RuntimeError(
                "pyserial is required for nRF52840 dongle support. "
                "Install it with: pip install pyserial"
            ) from _IMPORT_ERROR

    def _resolve_port(self) -> str:
        if self.port:
            return self.port
        self._ensure_serial()
        assert list_ports is not None
        matches = []
        for port in list_ports.comports():
            if port.vid is None or port.pid is None:
                continue
            if port.vid == self.vid and port.pid in self.pids:
                matches.append(port)
        if not matches:
            raise RuntimeError("No nRF52840 dongle found")
        if len(matches) > 1:
            ports = ", ".join(p.device for p in matches)
            raise RuntimeError(f"Multiple dongles found; specify port. Ports: {ports}")
        return matches[0].device

    def start(self, ctx) -> None:
        if self._thread is not None:
            raise RuntimeError(f"Recorder '{self.name}' already started")

        if serial is None and self.skip_if_missing:
            ctx.recorder_outputs[self.name] = {
                "type": "nrf52840_dongle",
                "skipped": True,
                "reason": "pyserial not installed",
            }
            return

        port = self._resolve_port()
        out_dir = ctx.artifacts.recorders_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        ext = "log" if self.read_mode == "text" else "bin"
        out_path = out_dir / f"{self.name}.{ext}"
        self._out_path = out_path

        if out_path.exists():
            out_path.unlink()

        self._serial = serial.Serial(port=port, baudrate=self.baudrate, timeout=self.timeout_s)
        self._stop_event.clear()

        def _reader() -> None:
            assert self._serial is not None
            mode_text = self.read_mode == "text"
            if mode_text:
                with out_path.open("w", encoding=self.encoding, errors=self.errors, newline="") as f:
                    while not self._stop_event.is_set():
                        line = self._serial.readline()
                        if not line:
                            continue
                        f.write(line.decode(self.encoding, errors=self.errors))
                        f.flush()
            else:
                with out_path.open("ab") as f:
                    while not self._stop_event.is_set():
                        chunk = self._serial.read(256)
                        if not chunk:
                            continue
                        f.write(chunk)
                        f.flush()

        self._thread = threading.Thread(target=_reader, name=f"{self.name}_reader", daemon=True)
        self._thread.start()

        ctx.recorder_outputs[self.name] = {
            "type": "nrf52840_dongle",
            "skipped": False,
            "port": port,
            "baudrate": self.baudrate,
            "mode": self.read_mode,
            "out": str(out_path),
        }

    def stop(self, ctx) -> None:
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._thread = None

        if self._serial is not None:
            self._serial.close()
            self._serial = None

        ctx.recorder_outputs.setdefault(self.name, {})
        ctx.recorder_outputs[self.name]["stopped_at"] = time.time()
