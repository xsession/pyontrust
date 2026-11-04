"""Per-subsystem access to a phone over ADB — control + measured values.

Design: every controller takes a ``runner`` callable ``(args: list[str]) -> str``
that executes an *adb* command and returns stdout. The default :class:`AdbShell`
uses the real adb binary (honours ``ADB_PATH``); tests inject a fake runner so
the whole layer is verifiable without hardware.

Subsystems covered
------------------
* :class:`BluetoothCtl`   state, enable/disable, discovery, paired devices
* :class:`GsmCtl`         airplane mode, radio/data, SIM + signal status, AT passthrough
* :class:`NfcCtl`         adapter state, enable/disable, dumpsys snapshot
* :class:`AudioCtl`       per-stream volume get/set, mute, routing, device list
* :class:`VibrationCtl`   vibrate patterns (best-effort command + helper-APK fallback)
* :class:`CamerasCtl`     camera-island enumeration: id, facing, state, resolution
* :class:`TouchscreenCtl` tap/swipe injection + raw touch event capture (getevent)
* :class:`PeripheralsCtl` battery, sensors, storage, network, USB, thermal

Facade: :class:`PhoneSubsystems` — one object for the whole phone.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

logger = logging.getLogger(__name__)


class Runner(Protocol):
    """Executes one adb command; returns stdout (str). Raises on failure."""

    def __call__(self, args: list[str]) -> str: ...


@dataclass(frozen=True)
class AdbShell:
    """Default runner — real adb binary. ``serial`` pins a specific device."""

    serial: str | None = None
    timeout_s: float = 15.0
    adb_path: str = field(default_factory=lambda: os.environ.get("ADB_PATH", "adb"))

    def __call__(self, args: list[str]) -> str:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_s)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "adb not found. Install Android SDK Platform-Tools or set ADB_PATH."
            ) from exc
        if res.returncode != 0:
            raise RuntimeError(f"adb {' '.join(shlex.quote(a) for a in cmd[1:])} failed: {res.stderr.strip()}")
        return res.stdout



def _parse_bool_state(text: str, *needles: str) -> bool | None:
    """True if any needle present (case-insensitive), False if 'off/disabled' seen first."""
    low = text.lower()
    for n in needles:
        if n in low:
            return True
    if "off" in low or "disabled" in low or "state=0" in low:
        return False
    return None


class BluetoothCtl:
    """Bluetooth adapter state + control (best-effort, vendor-dependent)."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    def state(self) -> bool | None:
        out = self._run(["shell", "dumpsys", "bluetooth_manager"])
        return _parse_bool_state(out, "controller state: on", "mstate=on", "adapter is enabled")

    def enable(self) -> str:
        return self._run(["shell", "svc", "bluetooth", "enable"]).strip()

    def disable(self) -> str:
        return self._run(["shell", "svc", "bluetooth", "disable"]).strip()

    def paired_devices(self) -> list[dict[str, str]]:
        out = self._run(["shell", "dumpsys", "bluetooth_manager"])
        devs: list[dict[str, str]] = []
        for m in re.finditer(r"Device:\s*([0-9A-Fa-f:]{17})[^A-Za-z]*Name:\s*(.+?)\s*$", out, re.M):
            devs.append({"address": m.group(1), "name": m.group(2)})
        return devs

    def dump(self) -> str:
        return self._run(["shell", "dumpsys", "bluetooth_manager"])


class NfcCtl:
    """NFC adapter state + control."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    def state(self) -> bool | None:
        out = self._run(["shell", "dumpsys", "nfc"])
        return _parse_bool_state(out, "madapterstate: on", "controller is enabled")

    def enable(self) -> str:
        return self._run(["shell", "svc", "nfc", "enable"]).strip()

    def disable(self) -> str:
        return self._run(["shell", "svc", "nfc", "disable"]).strip()

    def dump(self) -> str:
        return self._run(["shell", "dumpsys", "nfc"])



class GsmCtl:
    """GSM/telephony: airplane mode, data radio, SIM + signal status, AT passthrough."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    # -- control ---------------------------------------------------------
    def airplane_mode(self, on: bool) -> str:
        return self._run(["shell", "cmd", "connectivity", "airplane-mode", "enable" if on else "disable"]).strip()

    def data_radio(self, enabled: bool) -> str:
        return self._run(["shell", "svc", "data", "enabled" if enabled else "disabled"]).strip()

    def at(self, command: str) -> str:
        """Raw AT passthrough (needs root on most devices). Returns raw modem reply."""
        return self._run(["shell", "at", command])

    # -- measured values --------------------------------------------------
    def sim_status(self) -> list[dict[str, str]]:
        out = self._run(["shell", "dumpsys", "isms"])
        slots: list[dict[str, str]] = []
        for m in re.finditer(r"SlotId:\s*(\d+)[^S]*?mSimState=(\w+)", out):
            slots.append({"slot": m.group(1), "state": m.group(2)})
        if not slots:  # fallback: single-slot devices print one block
            m = re.search(r"mSimState=(\w+)", out)
            if m:
                slots.append({"slot": "0", "state": m.group(1)})
        return slots

    def signal(self) -> dict[str, Any]:
        """Latest SignalStrength entry from telephony.registry (multi-RAT)."""
        out = self._run(["shell", "dumpsys", "telephony.registry"])
        best: dict[str, Any] = {}
        for body in _find_brace_blocks(out, "SignalStrength={"):
            entry: dict[str, Any] = {"raw": body}
            for key in ("nr", "lte", "wcdma", "gsm"):
                sub = _brace_after(body, key + "={")
                if sub is not None:
                    entry[key] = _parse_signal_block(sub)
            best = entry  # keep the most recent one
        return best

    def network_registration(self) -> str:
        out = self._run(["shell", "dumpsys", "telephony.registry"])
        m = re.search(r"(?:mNetworkRegistrationInfo|NetworkRegistrationInfo)[^\n]*", out)
        return m.group(0).strip() if m else ""


def _find_brace_blocks(text: str, prefix: str) -> list[str]:
    """Contents of every ``prefix{...}`` block (brace-matched, nesting-safe)."""
    blocks: list[str] = []
    i = 0
    while True:
        j = text.find(prefix, i)
        if j == -1:
            break
        k = j + len(prefix)
        depth = 1
        while k < len(text) and depth > 0:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        blocks.append(text[j + len(prefix):k - 1])
        i = k
    return blocks


def _brace_after(body: str, prefix: str) -> str | None:
    j = body.find(prefix)
    if j == -1:
        return None
    blocks = _find_brace_blocks(body[j:], prefix)
    return blocks[0] if blocks else None


def _parse_signal_block(body: str) -> dict[str, Any]:
    """Parse 'signalStrength=-47 rsrp=-85 ...' style blocks into numbers."""
    vals: dict[str, Any] = {}
    for kv in body.split():
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        try:
            vals[k] = int(v)
        except ValueError:
            vals[k] = v
    return vals


class AudioCtl:
    """Audio streams: volume get/set, mute, routing, device list."""

    STREAMS = ("voice", "system", "ring", "music", "alarm", "notification")

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    def volumes(self) -> dict[str, int]:
        """Current level per audio stream (tolerant of vendor output formats)."""
        out = self._run(["shell", "media", "volume"])
        vols: dict[str, int] = {}
        for m in re.finditer(r"(?i)stream\s+([a-z]+)[^0-9]*(\d+)\s*/\s*(\d+)", out):
            name = m.group(1).lower()
            if name in self.STREAMS:
                vols[name] = int(m.group(2))
        for m in re.finditer(r"(?i)([a-z]+)\s*\(.*?\)\s*:?\s*[Cc]urrent\s+(\d+)\s*/\s*(\d+)", out):
            name = m.group(1).lower()
            if name in self.STREAMS and name not in vols:
                vols[name] = int(m.group(2))
        return vols

    def set_volume(self, stream: str, level: int) -> str:
        if stream not in self.STREAMS:
            raise ValueError(f"stream must be one of {self.STREAMS}")
        return self._run(["shell", "media", "volume", "--stream", stream, "--set", str(int(level))]).strip()

    def mute(self, on: bool) -> str:
        return self._run(["shell", "cmd", "media", "audio", "mute" if on else "unmute"]).strip()

    def routing(self) -> list[str]:
        out = self._run(["shell", "dumpsys", "audio"])
        devs = re.findall(r"(?:Output|Input)\s+device[^\n]*?(Speaker|Earpiece|WiredHeadset|BluetoothSco|BtA2dp|USB)", out)
        return sorted(set(devs))

    def dump(self) -> str:
        return self._run(["shell", "dumpsys", "audio"])



class VibrationCtl:
    """Vibration motor control (best-effort across vendor ROMs)."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    def vibrate(self, ms: int = 300) -> str:
        """Trigger a vibration of ``ms`` milliseconds.

        Tries the helper APK broadcast first (reliable), then falls back to
        the shell command used by some ROMs. Returns which path succeeded.
        """
        if ms <= 0:
            raise ValueError("ms must be > 0")
        try:
            self._run(["shell", "am", "broadcast", "-a", "com.pyontrust.camera.VIBRATE", "--es", "ms", str(int(ms))])
            return "helper-broadcast"
        except RuntimeError:
            pass
        out = self._run(["shell", "input", "vibrate", str(int(ms))]).strip()
        return f"input-vibrate:{out}" if out else "input-vibrate"

    def stop(self) -> str:
        try:
            self._run(["shell", "am", "broadcast", "-a", "com.pyontrust.camera.VIBRATE_STOP"])
            return "helper-broadcast"
        except RuntimeError:
            pass
        return self._run(["shell", "input", "vibrate", "0"]).strip()


class CamerasCtl:
    """Camera-island enumeration + per-camera state (all physical cameras)."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    def list_cameras(self) -> list[dict[str, Any]]:
        out = self._run(["shell", "dumpsys", "media.camera"])
        cams: list[dict[str, Any]] = []
        seen: set[int] = set()
        for m in re.finditer(r"Camera\s+(\d+):[^C]*?Facing:\s*(\w+)", out):
            cid = int(m.group(1))
            if cid in seen:
                continue
            seen.add(cid)
            cams.append({"id": cid, "facing": m.group(2).lower()})
        if not cams:  # AOSP-style "Camera device N:" headers
            ids = sorted({int(m.group(1)) for m in re.finditer(r"Camera device (\d+):", out)})
            if ids:
                return [{"id": i, "facing": "unknown"} for i in ids]
        if not cams:  # fallback: count line "Number of cameras: N"
            n = re.search(r"[Nn]umber of cameras:\s*(\d+)", out)
            if n:
                cams = [{"id": i, "facing": "unknown"} for i in range(int(n.group(1)))]
        return cams

    def camera_state(self, camera_id: int = 0) -> dict[str, Any]:
        """Device state + active client info for one physical camera."""
        out = self._run(["shell", "dumpsys", "media.camera"])
        sec = re.search(rf"Camera\s+{camera_id}:.*?(?=Camera\s+\d+:|\Z)", out, re.S)
        block = sec.group(0) if sec else ""
        state_m = re.search(r"(?:Device|Camera)\s*state[:=]\s*(\w+)", block)
        client_m = re.search(r"Active clients?[:=]?(.*?)(?:\n\n|$)", block, re.S)
        return {
            "id": camera_id,
            "device_state": state_m.group(1).lower() if state_m else None,
            "active_clients": client_m.group(1).strip().splitlines()[:3] if client_m else [],
        }

    def resolutions(self) -> dict[int, list[str]]:
        """Supported JPEG sizes per camera (from CameraService capabilities)."""
        out = self._run(["shell", "dumpsys", "media.camera"])
        res: dict[int, list[str]] = {}
        for m in re.finditer(r"Camera\s+(\d+):.*?JPEG[^0-9]*([0-9x, ]{6,80})", out, re.S):
            cid = int(m.group(1))
            sizes = [s.strip() for s in re.findall(r"\d+x\d+", m.group(2))]
            if sizes:
                res[cid] = sorted(set(sizes), key=lambda s: -int(s.split("x")[0]))[:8]
        return res

    def dump(self) -> str:
        return self._run(["shell", "dumpsys", "media.camera"])



@dataclass(frozen=True)
class TouchEvent:
    """One raw input event from the touchscreen (getevent -l)."""

    device: str
    type_code: int      # e.g. 3 = EV_ABS, 1 = EV_KEY
    code: int           # e.g. 53 = ABS_MT_POSITION_X
    value: int


class TouchscreenCtl:
    """Touch injection (tap/swipe) + raw touch event capture for measurements."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    # -- control ---------------------------------------------------------
    def tap(self, x: int, y: int) -> str:
        return self._run(["shell", "input", "tap", str(int(x)), str(int(y))]).strip()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
        return self._run(["shell", "input", "swipe", str(int(x1)), str(int(y1)),
                          str(int(x2)), str(int(y2)), str(int(duration_ms))]).strip()

    # -- measured values --------------------------------------------------
    def input_devices(self) -> list[dict[str, str]]:
        out = self._run(["shell", "getevent", "-p"])
        devs: list[dict[str, str]] = []
        for m in re.finditer(r"add device\s+(\d+):\s*(/dev/input/event\d+)\s*\n\s*name:\s*'([^']+)'", out):
            devs.append({"index": m.group(1), "path": m.group(2), "name": m.group(3)})
        return devs

    def events(self, duration_s: float = 2.0) -> list[TouchEvent]:
        """Capture raw touch/input events for ``duration_s`` seconds."""
        if duration_s <= 0:
            raise ValueError("duration_s must be > 0")
        out = self._run(["shell", "timeout", f"{duration_s:.1f}", "getevent", "-l"])
        evs: list[TouchEvent] = []
        for m in re.finditer(
            r"(/dev/input/event\d+):[^E]*?EV_\w+\s*\((\d+)\)\s+(\S+)\s*\((\d+)\)\s+value\s+(-?\d+)", out
        ):
            evs.append(TouchEvent(device=m.group(1), type_code=int(m.group(2)),
                                 code=int(m.group(4)), value=int(m.group(5))))
        return evs


class PeripheralsCtl:
    """Battery, sensors, storage, network, USB and thermal — measured values."""

    def __init__(self, runner: Runner) -> None:
        self._run = runner

    def battery(self) -> dict[str, Any]:
        out = self._run(["shell", "dumpsys", "battery"])
        vals: dict[str, Any] = {}
        keys = ("level", "scale", "status", "health", "plugged", "voltage", "temperature", "technology")
        for m in re.finditer(r"^(?:\s*battery)?\s*(" + "|".join(keys) + r"):\s*(.+?)\s*$", out, re.M | re.I):
            key = m.group(1).lower()
            v = m.group(2).strip()
            try:
                vals[key] = int(v)
            except ValueError:
                vals[key] = v
        return vals

    def sensors_list(self) -> list[dict[str, str]]:
        out = self._run(["shell", "sensors.list"])
        devs: list[dict[str, str]] = []
        for m in re.finditer(r"^(\d+):\s*(.+?)\s*\(.*?\)\s*$", out, re.M):
            devs.append({"handle": m.group(1), "name": m.group(2).strip()})
        if not devs:  # vendor formats without a trailing (vendor) group
            for m in re.finditer(r"^(\d+):\s*(.+)$", out, re.M):
                name = m.group(2).split("(")[0].strip()
                if name:
                    devs.append({"handle": m.group(1), "name": name})
        return devs

    def sensor_read(self, handle: int | str) -> dict[str, Any]:
        out = self._run(["shell", "sensors.get", str(handle)])
        vals: dict[str, Any] = {}
        for kv in re.findall(r"([A-Za-z_]+):\s*([-+0-9.eE]+)", out):
            try:
                vals[kv[0]] = float(kv[1])
            except ValueError:
                vals[kv[0]] = kv[1]
        return vals

    def storage(self) -> dict[str, str]:
        out = self._run(["shell", "df", "/data"])
        m = re.search(r"/dev/[^\s]+\s+(\S+)\s+(\S+)\s+(\S+)\s+([0-9]+)%", out)
        if not m:
            return {"raw": out.strip()[:200]}
        return {"total": m.group(1), "used": m.group(2), "free": m.group(3), "used_pct": int(m.group(4))}

    def network(self) -> dict[str, Any]:
        out = self._run(["shell", "ip", "addr"])
        ifaces: dict[str, list[str]] = {}
        cur = ""
        for line in out.splitlines():
            im = re.match(r"\d+:\s+(\w+@)?(\w+):", line)
            if im:
                cur = im.group(2)
                continue
            am = re.search(r"inet\s+([0-9.]+)", line)
            if am and cur:
                ifaces.setdefault(cur, []).append(am.group(1))
        return {"interfaces": ifaces}

    def usb_state(self) -> str:
        return self._run(["shell", "getprop", "sys.usb.state"]).strip()

    def thermal_zones(self) -> list[dict[str, Any]]:
        """Temperatures of all thermal zones (millidegrees C from sysfs)."""
        listing = self._run(["shell", "ls", "/sys/class/thermal"])
        zones: list[dict[str, Any]] = []
        for name in listing.split():
            if not name.startswith("thermal_zone"):
                continue
            base = f"/sys/class/thermal/{name}"
            try:
                ztype = self._run(["shell", "cat", base + "/type"]).strip()
                raw = self._run(["shell", "cat", base + "/temp"]).strip()
            except RuntimeError:
                continue
            if not raw.lstrip("-").isdigit():
                continue
            zones.append({"zone": name, "type": ztype, "temp_c": int(raw) / 1000.0})
        return zones



class PhoneSubsystems:
    """One object for the whole phone: every subsystem controller on one runner.

    >>> ph = PhoneSubsystems()                    # first adb device
    >>> ph = PhoneSubsystems(serial="ABC123")     # pinned device
    >>> ph.info()                                 # model / brand / sdk / serial
    >>> ph.snapshot()                             # key measured values, all subsystems
    """

    def __init__(self, serial: str | None = None, runner: Runner | None = None) -> None:
        self.runner: Runner = runner or AdbShell(serial=serial)
        self.bluetooth = BluetoothCtl(self.runner)
        self.nfc = NfcCtl(self.runner)
        self.gsm = GsmCtl(self.runner)
        self.audio = AudioCtl(self.runner)
        self.vibration = VibrationCtl(self.runner)
        self.cameras = CamerasCtl(self.runner)
        self.touchscreen = TouchscreenCtl(self.runner)
        self.peripherals = PeripheralsCtl(self.runner)

    def info(self) -> dict[str, str]:
        out = {}
        for key, prop in (
            ("model", "ro.product.model"),
            ("brand", "ro.product.brand"),
            ("sdk", "ro.build.version.sdk"),
            ("android_version", "ro.build.version.release"),
        ):
            try:
                out[key] = self.runner(["shell", "getprop", prop]).strip()
            except RuntimeError:
                out[key] = ""
        return out

    def snapshot(self) -> dict[str, Any]:
        """Best-effort measured values from every subsystem (never raises)."""
        snap: dict[str, Any] = {}

        def _safe(name: str, fn):
            try:
                snap[name] = fn()
            except Exception as exc:  # noqa: BLE001 - snapshot must not abort
                logger.debug("snapshot[%s] failed: %s", name, exc)
                snap[name] = {"error": str(exc)}

        _safe("info", self.info)
        _safe("bluetooth_state", lambda: self.bluetooth.state())
        _safe("nfc_state", lambda: self.nfc.state())
        _safe("audio_volumes", self.audio.volumes)
        _safe("cameras", self.cameras.list_cameras)
        _safe("battery", self.peripherals.battery)
        _safe("thermal_zones", self.peripherals.thermal_zones)
        _safe("usb_state", self.peripherals.usb_state)
        return snap


__all__ = [
    "Runner",
    "AdbShell",
    "BluetoothCtl",
    "NfcCtl",
    "GsmCtl",
    "AudioCtl",
    "VibrationCtl",
    "CamerasCtl",
    "TouchEvent",
    "TouchscreenCtl",
    "PeripheralsCtl",
    "PhoneSubsystems",
]

