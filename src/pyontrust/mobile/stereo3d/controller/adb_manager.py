"""ADB connection management: device discovery, TCP/IP mode, port forwarding."""

from __future__ import annotations

import re
import os
import subprocess
from dataclasses import dataclass


@dataclass
class DeviceInfo:
    serial: str          # USB serial or host:port for TCP devices
    transport: str       # "usb" | "tcpip"
    state: str           # adb state string ("device", "offline", ...)

    @property
    def is_tcp(self) -> bool:
        return ":" in self.serial


class ADBManager:
    """Manage the set of Android devices visible to ``adb``.

    Works over USB (default) and Wi-Fi TCP/IP (``connect_device(ip, port)``).
    Port forwarding (``forward(port)``) is used for low-latency streaming
    back to the PC instead of pushing files per frame.
    """

    def __init__(self, adb_path: str = "adb", serial: str | None = None) -> None:
        """Args:
            adb_path: path to the ``adb`` binary.
            serial: target device serial.  When omitted it is resolved from
                ``PYONTRUST_ADB_SERIAL``, or auto-selected when exactly one
                device is connected (with several attached, set the env var).
        """
        self.adb = adb_path
        if serial is None:
            serial = os.environ.get("PYONTRUST_ADB_SERIAL") or None
        if serial is None:
            try:
                devs = [d.serial for d in self.get_connected_devices()]
                if len(devs) == 1:
                    serial = devs[0]
            except Exception:
                pass
        self.serial = serial

    # ── discovery ────────────────────────────────────────────────
    def get_connected_devices(self) -> list[DeviceInfo]:
        out = self._run("devices", "-l")
        devices: list[DeviceInfo] = []
        for line in out.splitlines()[1:]:
            m = re.match(r"^([\w.:-]+)\s+(device|offline|unauthorized)", line.strip())
            if not m:
                continue
            serial, state = m.group(1), m.group(2)
            transport = "tcpip" if ":" in serial else "usb"
            devices.append(DeviceInfo(serial=serial, transport=transport, state=state))
        return [d for d in devices if d.state == "device"]

    def get_device(self, index: int = 0) -> DeviceInfo:
        devs = self.get_connected_devices()
        if not devs:
            raise RuntimeError("no ADB device connected")
        return devs[min(index, len(devs) - 1)]

    # ── TCP/IP mode ──────────────────────────────────────────────
    def connect_device(self, ip: str, port: int = 5555) -> None:
        """Attach a device over Wi-Fi (device must have ADB-over-network enabled)."""
        self._run("connect", f"{ip}:{port}")

    def disconnect_device(self, serial: str) -> None:
        self._run("disconnect", serial)

    # ── port forwarding ──────────────────────────────────────────
    def forward(self, local_port: int, remote_port: int | None = None,
                serial: str | None = None) -> int:
        """``adb forward tcp:L tcp:R`` — stream raw frames/mic audio to the PC."""
        args = ["forward"]
        if serial:
            args += ["-s", serial]
        args.append(f"tcp:{local_port}")
        args.append(f"tcp:{remote_port or local_port}")
        self._run(*args)
        return int(local_port)

    def forward_list(self, serial: str | None = None) -> list[str]:
        out = self._run("forward", "--list") if not serial else self._run("-s", serial, "forward", "--list")
        return [l.strip() for l in out.splitlines() if l.strip()]

    def remove_forward(self, local_port: int) -> None:
        try:
            self._run("forward", "--remove", f"tcp:{local_port}")
        except RuntimeError:
            pass  # not present — fine

    # ── shell helpers ────────────────────────────────────────────
    def shell(self, *cmd: str, serial: str | None = None, timeout: int = 30) -> str:
        args = ["-s", serial] if serial else []
        out = self._run(*args, "shell", *cmd, timeout=timeout)
        return out

    def push(self, local: str, remote: str, serial: str | None = None) -> None:
        args = ["-s", serial] if serial else []
        self._run(*args, "push", local, remote)

    def pull(self, remote: str, local: str, serial: str | None = None) -> None:
        args = ["-s", serial] if serial else []
        self._run(*args, "pull", remote, local)

    # ── low level ────────────────────────────────────────────────
    def _run(self, *args: str, timeout: int = 30) -> str:
        cmd = [self.adb]
        if self.serial and not any(str(a).startswith("-s") for a in args):
            cmd += ["-s", self.serial]
        r = subprocess.run(cmd + [str(a) for a in args],
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and "error" in out.lower():
            raise RuntimeError(f"adb {' '.join(map(str, args[:4]))} failed: {out.strip()[:200]}")
        return out


__all__ = ["ADBManager", "DeviceInfo"]
