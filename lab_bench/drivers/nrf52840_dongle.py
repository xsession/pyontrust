from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Optional

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
class DonglePort:
    device: str
    description: str
    hwid: str
    vid: Optional[int]
    pid: Optional[int]
    serial_number: Optional[str]


class Nrf52840Dongle:
    """Minimal serial helper for the nRF52840 USB dongle.

    This utility focuses on discovery + serial I/O and keeps dependencies optional.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        timeout_s: float = 0.2,
        vid: int = DEFAULT_VID,
        pids: Iterable[int] = DEFAULT_PIDS,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self.vid = vid
        self.pids = tuple(pids)
        self._serial: Optional[serial.Serial] = None  # type: ignore[union-attr]

    @staticmethod
    def _ensure_serial() -> None:
        if serial is None:
            raise RuntimeError(
                "pyserial is required for nRF52840 dongle support. "
                "Install it with: pip install pyserial"
            ) from _IMPORT_ERROR

    @classmethod
    def list_dongles(
        cls, vid: int = DEFAULT_VID, pids: Iterable[int] = DEFAULT_PIDS
    ) -> list[DonglePort]:
        cls._ensure_serial()
        assert list_ports is not None

        out: list[DonglePort] = []
        pids = tuple(pids)
        for port in list_ports.comports():
            if port.vid is None or port.pid is None:
                continue
            if port.vid != vid or port.pid not in pids:
                continue
            out.append(
                DonglePort(
                    device=port.device,
                    description=port.description or "",
                    hwid=port.hwid or "",
                    vid=port.vid,
                    pid=port.pid,
                    serial_number=port.serial_number,
                )
            )
        return out

    @classmethod
    def find_port(
        cls, vid: int = DEFAULT_VID, pids: Iterable[int] = DEFAULT_PIDS
    ) -> str:
        matches = cls.list_dongles(vid=vid, pids=pids)
        if not matches:
            raise RuntimeError("No nRF52840 dongle found")
        if len(matches) > 1:
            ports = ", ".join(m.device for m in matches)
            raise RuntimeError(f"Multiple dongles found; specify port. Ports: {ports}")
        return matches[0].device

    def open(self) -> None:
        self._ensure_serial()
        if self._serial is not None:
            return
        port = self.port or self.find_port(vid=self.vid, pids=self.pids)
        self._serial = serial.Serial(port=port, baudrate=self.baudrate, timeout=self.timeout_s)

    def close(self) -> None:
        if self._serial is None:
            return
        self._serial.close()
        self._serial = None

    def reset(self, pulse_s: float = 0.1) -> None:
        if self._serial is None:
            raise RuntimeError("Serial port not open")
        self._serial.dtr = False
        time.sleep(pulse_s)
        self._serial.dtr = True

    def write(self, data: bytes) -> int:
        if self._serial is None:
            raise RuntimeError("Serial port not open")
        return self._serial.write(data)

    def read(self, size: int = 1) -> bytes:
        if self._serial is None:
            raise RuntimeError("Serial port not open")
        return self._serial.read(size)

    def readline(self) -> bytes:
        if self._serial is None:
            raise RuntimeError("Serial port not open")
        return self._serial.readline()
