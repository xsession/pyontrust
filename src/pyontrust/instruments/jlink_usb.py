"""SEGGER J-Link over raw USB — identity and target voltage without SEGGER software.

Uses two read-only commands of the J-Link USB protocol (the same ones
libjaylink/OpenOCD use): ``0x01`` firmware version string and ``0x07``
hardware status (target voltage in mV + JTAG pin levels).  Nothing is sent
to the target; the probe's state is not changed.
"""
from __future__ import annotations

import struct
from typing import Any

SEGGER_VID = 0x1366
_CMD_VERSION = 0x01
_CMD_HW_STATUS = 0x07


class JLinkUsbError(RuntimeError):
    pass


class JLinkUsb:
    """One J-Link opened over USB (``serial`` = USB serial number, optional)."""

    def __init__(self, serial: str = "", timeout_ms: int = 1000) -> None:
        self.serial = serial
        self.timeout_ms = timeout_ms
        self._dev: Any = None
        self._intf = None
        self._ep_in = self._ep_out = None

    def open(self) -> "JLinkUsb":
        try:
            import usb.core
            import usb.util
        except ImportError as exc:  # pragma: no cover
            raise JLinkUsbError("pyusb is not installed (pip install pyusb)") from exc

        def match(d: Any) -> bool:
            if not self.serial:
                return True
            try:
                return (d.serial_number or "").lstrip("0") == self.serial.lstrip("0")
            except Exception:
                return False

        devs = list(usb.core.find(find_all=True, idVendor=SEGGER_VID, custom_match=match) or [])
        if not devs:
            raise JLinkUsbError(f"J-Link {self.serial or ''} not found on USB".replace("  ", " "))
        dev = devs[0]
        try:
            cfg = dev.get_active_configuration()
            intf = next(i for i in cfg if i.bInterfaceClass == 0xFF)
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                raise JLinkUsbError("the J-Link interface is held by a kernel driver")
            usb.util.claim_interface(dev, intf.bInterfaceNumber)
        except usb.core.USBError as exc:
            if exc.errno in (13, 16):   # EACCES / EBUSY
                raise JLinkUsbError("J-Link is in use by another program (J-Link Commander, a debugger …)"
                                    if exc.errno == 16 else
                                    "no USB access to the J-Link — install SEGGER's udev rule (99-jlink.rules)") from exc
            raise JLinkUsbError(str(exc)) from exc
        except StopIteration as exc:
            raise JLinkUsbError("no J-Link vendor interface on this device") from exc
        self._dev, self._intf = dev, intf.bInterfaceNumber
        out = usb.util.ENDPOINT_OUT
        self._ep_out = next(e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress) == out)
        self._ep_in = next(e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress) != out)
        return self

    def close(self) -> None:
        if self._dev is None:
            return
        import usb.util

        try:
            usb.util.release_interface(self._dev, self._intf)
        except Exception:
            pass
        usb.util.dispose_resources(self._dev)
        self._dev = None

    def __enter__(self) -> "JLinkUsb":
        return self.open()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _cmd(self, cmd: int, n: int) -> bytes:
        if self._dev is None:
            raise JLinkUsbError("J-Link not open")
        self._ep_out.write(bytes([cmd]), self.timeout_ms)
        return bytes(self._ep_in.read(max(n, 64), self.timeout_ms))

    def firmware(self) -> str:
        r = self._cmd(_CMD_VERSION, 0x200)
        n = struct.unpack("<H", r[:2])[0]
        body = r[2:]
        while len(body) < n:
            body += bytes(self._ep_in.read(0x200, self.timeout_ms))
        return body[:n].split(b"\0")[0].decode(errors="replace").strip()

    def hw_status(self) -> dict[str, Any]:
        """Target voltage (V) and JTAG pin levels."""
        r = self._cmd(_CMD_HW_STATUS, 8)
        mv, tck, tdi, tdo, tms, tres, trst = struct.unpack("<HBBBBBB", r[:8])
        return {"vtarget_v": mv / 1000.0, "tck": tck, "tdi": tdi, "tdo": tdo, "tms": tms,
                "tres": tres, "trst": trst}

    def serial_number(self) -> str:
        try:
            return (self._dev.serial_number or "").lstrip("0")
        except Exception:
            return ""
