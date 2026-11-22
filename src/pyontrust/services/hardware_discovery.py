"""Hardware discovery and diagnostic service.

Probes all physical interfaces (USB serial, ADB, webcam, DWF, Seek Thermal,
J-Link, HackRF, etc.) and reports what is connected and ready for use.

Each probe runs with a timeout and returns a standardised result dict::

    {
        "category": "android",
        "type": "android_sensors",
        "name": "Samsung Galaxy S23",
        "status": "ok" | "error" | "not_found",
        "icon": "📱",
        "details": { ... },
        "error": "...",         # only if status == "error"
        "test_result": None,    # filled by run_quick_test()
    }
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures._base import TimeoutError as FuturesTimeoutError
from typing import Any

logger = logging.getLogger("pyontrust.services.hardware_discovery")


# ═══════════════════════════════════════════════════════════════════════
#  Result builder
# ═══════════════════════════════════════════════════════════════════════

def _ok(category: str, hw_type: str, name: str, icon: str, details: dict) -> dict:
    return {"category": category, "type": hw_type, "name": name,
            "icon": icon, "status": "ok", "details": details,
            "error": None, "test_result": None}


def _err(category: str, hw_type: str, name: str, icon: str, error: str) -> dict:
    return {"category": category, "type": hw_type, "name": name,
            "icon": icon, "status": "error", "details": {},
            "error": error, "test_result": None}


def _not_found(category: str, hw_type: str, name: str, icon: str) -> dict:
    return {"category": category, "type": hw_type, "name": name,
            "icon": icon, "status": "not_found", "details": {},
            "error": None, "test_result": None}


_IS_WINDOWS = os.name == "nt"
_SYS_USB = "/sys/bus/usb/devices"
_SYS_NET = "/sys/class/net"


def _read_sys(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _usb_devices() -> list[dict]:
    """All USB devices from Linux sysfs (no device I/O, no permissions needed).

    Each entry: ``vid``, ``pid`` (int), ``manufacturer``, ``product``,
    ``serial``, ``path`` (USB port path, e.g. ``1-2.4``), ``node``
    (``/dev/bus/usb/BBB/DDD``) and ``writable`` (can this user open it).
    """
    out: list[dict] = []
    try:
        names = os.listdir(_SYS_USB)
    except OSError:
        return out
    for name in sorted(names):
        if ":" in name:                       # interfaces, not devices
            continue
        base = os.path.join(_SYS_USB, name)
        vid, pid = _read_sys(f"{base}/idVendor"), _read_sys(f"{base}/idProduct")
        if not vid or not pid:
            continue
        bus, dev = _read_sys(f"{base}/busnum"), _read_sys(f"{base}/devnum")
        node = f"/dev/bus/usb/{int(bus):03d}/{int(dev):03d}" if bus and dev else ""
        out.append({
            "vid": int(vid, 16), "pid": int(pid, 16), "path": name,
            "manufacturer": _read_sys(f"{base}/manufacturer"),
            "product": _read_sys(f"{base}/product"),
            "serial": _read_sys(f"{base}/serial"),
            "node": node,
            "writable": bool(node) and os.access(node, os.R_OK | os.W_OK),
        })
    return out


def _usb_find(vid: int, pids: set[int] | None = None) -> list[dict]:
    return [d for d in _usb_devices() if d["vid"] == vid and (pids is None or d["pid"] in pids)]


def _usb_details(d: dict) -> dict:
    """Card details for a sysfs USB device."""
    return {"vid_pid": f"{d['vid']:04X}:{d['pid']:04X}", "usb_path": d["path"],
            "manufacturer": d["manufacturer"], "product": d["product"],
            "serial": d["serial"], "node": d["node"], "usb_access": d["writable"]}


def _udev_hint(what: str, vid: int) -> str:
    return (f"no USB access to the {what} for this user — install its udev rule "
            f"(e.g. SUBSYSTEM==\"usb\", ATTR{{idVendor}}==\"{vid:04x}\", MODE=\"0660\", GROUP=\"plugdev\" "
            "in /etc/udev/rules.d/, then sudo udevadm control --reload && sudo udevadm trigger) and replug it")


def _probe_usb_vid_pid(
    vid: int, pids: set[int],
    category: str, hw_type: str, name: str, icon: str,
) -> list[dict]:
    """Check for USB devices by VID/PID via Windows WMI (Get-PnpDevice).

    Returns a list of ``_ok`` dicts for each matching device, or ``[]``.
    This is a Windows-only fallback for devices that don't expose a COM port.
    """
    import re as _re
    results: list[dict] = []
    if not _IS_WINDOWS:
        return results
    try:
        vid_hex = f"{vid:04X}"
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command",
             f"Get-PnpDevice -Status OK "
             f"| Where-Object {{ $_.InstanceId -match 'VID_{vid_hex}' }} "
             f"| Select-Object FriendlyName, InstanceId "
             f"| Format-List"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            out, _ = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return results

        # Parse each device block
        current: dict[str, str] = {}
        for line in out.splitlines():
            line = line.strip()
            if ":" in line:
                k, _, v = line.partition(":")
                current[k.strip()] = v.strip()
            elif not line and current:
                iid = current.get("InstanceId", "")
                m = _re.search(r"PID_([0-9A-Fa-f]{4})", iid)
                if m and int(m.group(1), 16) in pids:
                    friendly = current.get("FriendlyName", name)
                    results.append(_ok(
                        category, hw_type, friendly, icon,
                        {"instance_id": iid, "vid_pid": f"{vid_hex}:{m.group(1).upper()}"},
                    ))
                current = {}
        # Handle last block
        if current:
            iid = current.get("InstanceId", "")
            m = _re.search(r"PID_([0-9A-Fa-f]{4})", iid)
            if m and int(m.group(1), 16) in pids:
                friendly = current.get("FriendlyName", name)
                results.append(_ok(
                    category, hw_type, friendly, icon,
                    {"instance_id": iid, "vid_pid": f"{vid_hex}:{m.group(1).upper()}"},
                ))
    except Exception:
        pass
    return results


# ═══════════════════════════════════════════════════════════════════════
#  Individual hardware probes
# ═══════════════════════════════════════════════════════════════════════

def _probe_serial_ports() -> list[dict]:
    """Enumerate USB serial ports."""
    results = []
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            # Linux lists every legacy 8250 UART slot (/dev/ttyS0..31) — only real hardware counts
            if not _IS_WINDOWS and (p.hwid or "n/a") == "n/a":
                continue
            desc = p.description or p.device
            if desc == "n/a":
                desc = p.device
            elif p.device not in desc:
                desc = f"{desc} ({p.device})"
            vid_pid = ""
            if p.vid and p.pid:
                vid_pid = f"VID:{p.vid:04X} PID:{p.pid:04X}"
            results.append(_ok(
                "serial", "serial_port", desc, "🔌",
                {"device": p.device, "description": p.description,
                 "hwid": p.hwid, "vid_pid": vid_pid,
                 "manufacturer": p.manufacturer or "",
                 "product": p.product or "",
                 "serial_number": p.serial_number or ""},
            ))
    except ImportError:
        results.append(_err("serial", "serial_port", "Serial Ports", "🔌",
                            "pyserial not installed (pip install pyserial)"))
    except Exception as exc:
        results.append(_err("serial", "serial_port", "Serial Ports", "🔌", str(exc)))

    if not results:
        results.append(_not_found("serial", "serial_port", "No serial ports", "🔌"))
    return results


def _probe_adb_devices() -> list[dict]:
    """Enumerate ADB-connected Android devices.

    Detects devices in all states: authorized (``device``), unauthorized,
    and offline.  Unauthorized devices get an ``error`` status with a
    helpful message telling the user to accept the USB-debugging prompt.
    """
    results = []
    adb = os.environ.get("ADB_PATH", "adb")

    if not shutil.which(adb):
        return [_not_found("android", "android_sensors", "ADB not installed", "📱")]

    try:
        # First adb call may start the daemon — use Popen for reliable kill.
        proc = subprocess.Popen(
            [adb, "devices", "-l"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            out, _ = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return [_err("android", "android_sensors", "ADB devices",
                         "📱", "adb devices timed out (is ADB server hung?)")]

        # Match ALL device lines (device, unauthorized, offline, etc.)
        # ADB may use TAB or multiple SPACES to separate serial from state.
        _KNOWN_STATES = {"device", "unauthorized", "offline", "no", "authorizing",
                         "recovery", "sideload", "bootloader"}
        all_lines = []
        for l in out.splitlines():
            l = l.strip()
            if not l or l.startswith("List"):
                continue
            # A device line has ≥2 tokens and the 2nd token is a known state
            tokens = l.split()
            if len(tokens) >= 2 and tokens[1].lower() in _KNOWN_STATES:
                all_lines.append(l)

        if not all_lines:
            return [_not_found("android", "android_sensors", "No Android devices", "📱")]

        for line in all_lines:
            parts = line.split()
            serial = parts[0] if parts else "unknown"

            # Determine ADB state (second token, works with TABs or spaces)
            state_token = parts[1].lower() if len(parts) >= 2 else "unknown"
            adb_state = state_token if state_token in _KNOWN_STATES else "unknown"
            # "no permissions" shows as "no" — check full text
            if adb_state == "no" and "permissions" in line.lower():
                adb_state = "no_permissions"

            # --- Unauthorized / offline devices ---
            if adb_state != "device":
                hint = {
                    "unauthorized": (
                        "USB debugging not authorized. On the phone, "
                        "tap 'Allow USB debugging' in the popup dialog. "
                        "If no popup appears: Settings → Developer Options "
                        "→ Revoke USB debugging authorizations, then "
                        "reconnect the cable."
                    ),
                    "offline": (
                        "Device is offline. Try: unplug and replug USB, "
                        "or run 'adb kill-server' then 'adb start-server'."
                    ),
                    "no_permissions": (
                        "Insufficient USB permissions. On Linux, check "
                        "udev rules. On Windows, install the correct USB driver."
                    ),
                }.get(adb_state, f"Device state: {adb_state}")

                results.append(_err(
                    "android", "android_sensors",
                    f"Android ({serial[:16]})", "📱",
                    f"{adb_state.upper()}: {hint}",
                ))
                # Also attach details so the UI can show the serial
                results[-1]["details"] = {
                    "serial": serial, "adb_state": adb_state,
                    "raw_line": line,
                }
                continue

            # --- Authorized (device) ---
            # Extract model from "model:XXX"
            model = serial
            for p in parts:
                if p.startswith("model:"):
                    model = p.split(":", 1)[1]

            # Get detailed info — use a single shell call with multiple getprop
            details: dict = {"serial": serial, "adb_state": "device", "raw_line": line}
            try:
                # Batch getprop calls into one shell invocation
                props_cmd = (
                    "getprop ro.product.brand;"
                    "echo '|||';"
                    "getprop ro.product.model;"
                    "echo '|||';"
                    "getprop ro.build.version.release;"
                    "echo '|||';"
                    "getprop ro.build.version.sdk"
                )
                props_proc = subprocess.Popen(
                    [adb, "-s", serial, "shell", props_cmd],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    props_out, _ = props_proc.communicate(timeout=5)
                    prop_parts = props_out.split("|||")
                    if len(prop_parts) >= 4:
                        details["brand"] = prop_parts[0].strip()
                        details["model"] = prop_parts[1].strip()
                        details["android_version"] = prop_parts[2].strip()
                        details["sdk_version"] = prop_parts[3].strip()
                except subprocess.TimeoutExpired:
                    props_proc.kill()
                    props_proc.communicate()

                # Battery in a separate call
                bat_proc = subprocess.Popen(
                    [adb, "-s", serial, "shell", "dumpsys", "battery"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    bat_out, _ = bat_proc.communicate(timeout=5)
                    for bl in bat_out.splitlines():
                        bl = bl.strip()
                        if bl.startswith("level:"):
                            details["battery_pct"] = bl.split(":", 1)[1].strip()
                        elif bl.startswith("temperature:"):
                            try:
                                details["battery_temp_c"] = str(
                                    round(int(bl.split(":", 1)[1].strip()) / 10, 1))
                            except ValueError:
                                pass
                except subprocess.TimeoutExpired:
                    bat_proc.kill()
                    bat_proc.communicate()

                # Sensor list via dumpsys sensorservice
                details["sensors"] = _adb_list_sensors(adb, serial)

                display_name = f"{details.get('brand', '')} {details.get('model', model)}".strip()
            except Exception:
                display_name = model

            results.append(_ok("android", "android_sensors", display_name, "📱", details))
    except Exception as exc:
        results.append(_err("android", "android_sensors", "ADB probe", "📱", str(exc)))

    return results


def _adb_list_sensors(adb: str, serial: str) -> list[str]:
    """Query the Android sensor list via ``dumpsys sensorservice``.

    Returns a list of human-readable sensor names (e.g. ``"Accelerometer"``).
    The pyontrust phone app is asked first — it lists exactly the sensors that
    Live Data can read; ``dumpsys`` is the fallback.
    """
    sensors: list[str] = []
    try:
        from pyontrust.instruments import phone_camera
        return [s["type"] for s in phone_camera.sensors(serial)]
    except Exception:
        pass
    try:
        proc = subprocess.Popen(
            [adb, "-s", serial, "shell", "dumpsys", "sensorservice"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            out, _ = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return sensors

        # Parse sensor lines — they look like:
        #   0x00000001) {Accelerometer | vendor | ...}
        # or table rows with '|' separators
        seen: set[str] = set()
        for line in out.splitlines():
            line = line.strip()
            # Pattern 1: "{SensorName | ..."
            if "{" in line and "|" in line:
                name = line.split("{", 1)[1].split("|")[0].strip()
                if name and name not in seen and len(name) < 60:
                    seen.add(name)
                    sensors.append(name)
            # Pattern 2: table with "| SensorName |"
            elif line.startswith("|") and line.count("|") >= 2:
                parts = [p.strip() for p in line.split("|")]
                for p in parts:
                    if p and any(kw in p.lower() for kw in (
                        "accel", "gyro", "magnet", "light", "proxim",
                        "pressure", "barom", "gravity", "rotation",
                        "orient", "humid", "temp", "step", "heart",
                        "gps", "geomag",
                    )):
                        if p not in seen and len(p) < 60:
                            seen.add(p)
                            sensors.append(p)
    except Exception:
        pass
    return sensors[:30]  # cap to prevent huge payloads


def _v4l2_cameras() -> list[dict]:
    """Linux capture devices from sysfs: one entry per physical camera.

    UVC cameras register two nodes (image + metadata); the capture node is the
    one with ``index`` 0."""
    import glob
    import re as _re

    cams = []
    for d in glob.glob("/sys/class/video4linux/video*"):
        if _read_sys(f"{d}/index") not in ("0", ""):
            continue
        m = _re.search(r"(\d+)$", d)
        if not m:
            continue
        num = int(m.group(1))
        name = _read_sys(f"{d}/name").split(":")[0].strip() or f"video{num}"
        usb = os.path.basename(os.path.realpath(f"{d}/device")).split(":")[0]
        cams.append({"index": num, "device": f"/dev/video{num}", "name": name, "usb_path": usb})
    return sorted(cams, key=lambda c: c["index"])


def _open_capture(idx: int):
    """``cv2.VideoCapture`` with the native backend of this OS."""
    import cv2

    api = cv2.CAP_DSHOW if _IS_WINDOWS else getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
    return cv2.VideoCapture(idx, api)


def _probe_webcams() -> list[dict]:
    """Enumerate webcams.

    Linux: sysfs (instant, no device is opened — other tools may be streaming).
    Windows: ``cv2.VideoCapture`` with DSHOW; indices are contiguous so the
    scan stops at the first missing one (a missing index can block for seconds).
    """
    results = []
    if not _IS_WINDOWS:
        for cam in _v4l2_cameras():
            results.append(_ok("camera", "webcam", f"{cam['name']} ({cam['device']})", "📷", cam))
        if not results:
            results.append(_not_found("camera", "webcam", "No webcams found", "📷"))
        return results
    try:
        import cv2

        for idx in range(4):
            try:
                cap = _open_capture(idx)
                if not cap.isOpened():
                    cap.release()
                    break
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                bname = cap.getBackendName()
                cap.release()
                results.append(_ok(
                    "camera", "webcam", f"Camera #{idx}", "📷",
                    {"index": idx, "resolution": f"{w}x{h}",
                     "fps": round(fps, 1), "backend": bname},
                ))
            except Exception:
                break

    except ImportError:
        results.append(_err("camera", "webcam", "Webcams", "📷",
                            "opencv-python not installed"))
    except Exception as exc:
        results.append(_err("camera", "webcam", "Webcams", "📷", str(exc)))

    if not results:
        results.append(_not_found("camera", "webcam", "No webcams found", "📷"))
    return results


_DWF = None


def load_dwf():
    """The Digilent WaveForms runtime (``libdwf``) via ctypes, or raise OSError."""
    global _DWF
    if _DWF is not None:
        return _DWF
    import ctypes
    import sys

    try:
        from pyontrust.hal.dwf_loader import dwf  # type: ignore[import-not-found]
        _DWF = dwf
        return dwf
    except ImportError:
        pass
    if _IS_WINDOWS:
        names = ["dwf"]
    elif sys.platform == "darwin":
        names = ["/Library/Frameworks/dwf.framework/dwf"]
    else:
        names = ["libdwf.so", "/usr/lib/libdwf.so"]
    last: Exception | None = None
    for n in names:
        try:
            _DWF = ctypes.cdll.LoadLibrary(n) if _IS_WINDOWS else ctypes.CDLL(n)
            return _DWF
        except OSError as exc:
            last = exc
    raise OSError(f"Digilent WaveForms runtime (libdwf) not found: {last}")


def _probe_dwf_devices() -> list[dict]:
    """Enumerate Analog Discovery / WaveForms SDK devices."""
    import ctypes

    results = []
    try:
        try:
            dwf = load_dwf()
        except OSError:
            if _usb_find(0x1443):
                return [_err("instruments", "ad3_dwf", "Digilent device (USB)", "📟",
                             "Digilent device on USB but the WaveForms runtime (libdwf) is not installed")]
            return [_not_found("instruments", "ad3_dwf",
                               "Digilent WaveForms SDK not found", "📟")]

        c_count = ctypes.c_int(0)
        dwf.FDwfEnum(ctypes.c_int(0), ctypes.byref(c_count))
        count = c_count.value

        if count == 0:
            return [_not_found("instruments", "ad3_dwf",
                               "No Analog Discovery devices", "📟")]

        for i in range(count):
            name_buf = ctypes.create_string_buffer(64)
            serial_buf = ctypes.create_string_buffer(64)
            dev_id = ctypes.c_int(0)
            dev_rev = ctypes.c_int(0)
            in_use = ctypes.c_int(0)

            dwf.FDwfEnumDeviceType(ctypes.c_int(i),
                                   ctypes.byref(dev_id), ctypes.byref(dev_rev))
            try:
                dwf.FDwfEnumDeviceName(ctypes.c_int(i), name_buf)
                dwf.FDwfEnumSN(ctypes.c_int(i), serial_buf)
                dwf.FDwfEnumDeviceIsOpened(ctypes.c_int(i), ctypes.byref(in_use))
            except Exception:
                pass

            dev_name = name_buf.value.decode("utf-8", errors="replace").strip()
            dev_sn = serial_buf.value.decode("utf-8", errors="replace").strip().removeprefix("SN:")

            results.append(_ok(
                "instruments", "ad3_dwf",
                f"{dev_name or 'DWF device'} ({dev_sn})" if dev_sn else (dev_name or f"DWF Device #{i}"), "📟",
                {"index": i, "name": dev_name, "serial": dev_sn,
                 "device_id": dev_id.value, "revision": dev_rev.value,
                 "in_use": bool(in_use.value)},
            ))
    except Exception as exc:
        results.append(_err("instruments", "ad3_dwf", "DWF probe", "📟", f"{type(exc).__name__}: {exc}"))

    return results


def _probe_seek_thermal() -> list[dict]:
    """Check for Seek Thermal cameras."""
    results = []
    try:
        # ── libseek: pure-Python pyusb driver (preferred) ────────────
        try:
            from pyontrust.instruments.libseek_driver import list_cameras
            cams = list_cameras()
            if cams:
                for cam in cams:
                    results.append(_ok(
                        "thermal", "seek_thermal",
                        f"Seek Thermal {cam['type']} (libseek, {cam['resolution']})",
                        "🌡️",
                        {"sdk": "libseek", "camera_type": cam["camera_type"],
                         "vid_pid": f"{cam['vid']}:{cam['pid']}"},
                    ))
                return results
        except ImportError:
            pass

        # ── seekcamera SDK ───────────────────────────────────────────
        try:
            import seekcamera
            results.append(_ok("thermal", "seek_thermal",
                              "Seek Thermal (seekcamera SDK)", "🌡️",
                              {"sdk": "seekcamera"}))
            return results
        except ImportError:
            pass

        # ── seek_thermal community lib ───────────────────────────────
        try:
            from seek import SeekPro, SeekCompact
            results.append(_ok("thermal", "seek_thermal",
                              "Seek Thermal (community lib)", "🌡️",
                              {"sdk": "seek-thermal"}))
            return results
        except ImportError:
            pass

        # Check for USB device presence (Seek VID=289D) via serial ports
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                if p.vid and f"{p.vid:04X}" == "289D":
                    results.append(_ok("thermal", "seek_thermal",
                                      f"Seek Thermal USB ({p.device})", "🌡️",
                                      {"device": p.device, "vid_pid": f"{p.vid:04X}:{p.pid:04X}"}))
                    return results
        except ImportError:
            pass

        # Fallback: Windows WMI/PnP device scan (Seek cameras are USB bulk,
        # not serial — pyserial won't enumerate them)
        # Known PIDs: 0010=Compact, 0011=CompactPRO, 0012=CompactXR
        _SEEK_PID_NAMES = {0x0010: "Compact", 0x0011: "CompactPRO", 0x0012: "CompactXR"}
        try:
            _usb_results = _probe_usb_vid_pid(
                0x289D, set(_SEEK_PID_NAMES.keys()),
                "thermal", "seek_thermal", "Seek Thermal (USB)", "🌡️",
            )
            # Enrich friendly name with model from PID
            for r in _usb_results:
                vid_pid = r.get("details", {}).get("vid_pid", "")
                if ":" in vid_pid:
                    pid_val = int(vid_pid.split(":")[1], 16)
                    model = _SEEK_PID_NAMES.get(pid_val, "")
                    if model:
                        r["name"] = f"Seek Thermal {model}"
            if _usb_results:
                return _usb_results
        except Exception:
            pass

        return [_not_found("thermal", "seek_thermal", "No Seek Thermal camera", "🌡️")]
    except Exception as exc:
        return [_err("thermal", "seek_thermal", "Seek probe", "🌡️", str(exc))]


# ── Peak-CAN (PEAK-System Technik) ─────────────────────────────────

_PCAN_VID = 0x0C72  # PEAK-System Technik GmbH

_PCAN_PID_NAMES: dict[int, str] = {
    0x000C: "PCAN-USB",
    0x000D: "PCAN-USB Pro",
    0x0012: "PCAN-USB FD",
    0x0013: "PCAN-USB Pro FD",
    0x0014: "PCAN-USB X6",
    0x000F: "PCAN-PCI",
}


def _socketcan_pcan() -> list[dict]:
    """PEAK adapters bound to the Linux ``peak_usb`` driver show up as SocketCAN
    interfaces (``can0`` …)."""
    found = []
    base = _SYS_NET
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return found
    for name in names:
        drv = os.path.basename(os.path.realpath(f"{base}/{name}/device/driver"))
        if _read_sys(f"{base}/{name}/type") != "280" or drv not in ("peak_usb", "peak_pci", "peak_pciefd"):
            continue
        usb_path = os.path.basename(os.path.realpath(f"{base}/{name}/device")).split(":")[0]
        usb = next((d for d in _usb_devices() if d["path"] == usb_path), None)
        model = _PCAN_PID_NAMES.get(usb["pid"], "PCAN") if usb else "PCAN"
        state = _read_sys(f"{base}/{name}/operstate") or "unknown"
        found.append({"channel": name, "interface": "socketcan", "driver": drv, "model": model,
                      "state": state, "usb_path": usb_path,
                      "serial": (usb or {}).get("serial", "")})
    return found


def _probe_pcan() -> list[dict]:
    """Detect PEAK-CAN USB adapters.

    Strategy:
      1. Linux: SocketCAN interfaces of the ``peak_usb`` driver (``can0``).
      2. python-can detect_available_configs for the pcan interface (PCAN-Basic).
      3. USB VID 0x0C72 (sysfs on Linux, WMI on Windows).
    """
    try:
        results: list[dict] = []

        if not _IS_WINDOWS:
            for c in _socketcan_pcan():
                results.append(_ok("bus", "pcan", f"{c['model']} ({c['channel']}, {c['state']})", "🔌",
                                   {**c, "source": "socketcan"}))
            if results:
                return results

        try:
            import can  # type: ignore[import-untyped]
            configs = can.detect_available_configs(interfaces=["pcan"])
            for cfg in configs:
                ch = cfg.get("channel", "PCAN_USBBUS1")
                results.append(_ok("bus", "pcan",
                                   f"Peak-CAN ({ch})", "🔌",
                                   {"channel": ch, "interface": "pcan",
                                    "source": "python-can"}))
        except Exception:
            pass

        if results:
            return results

        for d in _usb_find(_PCAN_VID, set(_PCAN_PID_NAMES)):
            results.append(_err("bus", "pcan", f"{_PCAN_PID_NAMES[d['pid']]} (USB)", "🔌",
                                "adapter on USB but no CAN interface — load the driver: sudo modprobe peak_usb"))
            results[-1]["details"] = _usb_details(d)
        if results:
            return results

        try:
            usb_results = _probe_usb_vid_pid(
                _PCAN_VID, set(_PCAN_PID_NAMES.keys()),
                "bus", "pcan", "Peak-CAN (USB)", "🔌",
            )
            for r in usb_results:
                vid_pid = r.get("details", {}).get("vid_pid", "")
                if ":" in vid_pid:
                    pid_val = int(vid_pid.split(":")[1], 16)
                    model = _PCAN_PID_NAMES.get(pid_val, "")
                    if model:
                        r["name"] = model
            if usb_results:
                return usb_results
        except Exception:
            pass

        try:
            if _IS_WINDOWS:
                import ctypes
                try:
                    ctypes.windll.LoadLibrary("PCANBasic")  # type: ignore[attr-defined]
                    results.append(_ok("bus", "pcan",
                                       "Peak-CAN (driver installed)", "🔌",
                                       {"source": "PCANBasic.dll"}))
                    return results
                except OSError:
                    pass
        except Exception:
            pass

        return [_not_found("bus", "pcan", "No Peak-CAN adapters", "🔌")]
    except Exception as exc:
        return [_err("bus", "pcan", "PCAN probe", "🔌", str(exc))]


_SEGGER_VID = 0x1366
_HACKRF_VID = 0x1D50
_HACKRF_PIDS = {0x6089: "HackRF One", 0x604B: "HackRF Jawbreaker", 0xCC15: "rad1o"}


def _probe_jlink() -> list[dict]:
    """SEGGER J-Link probes: found on USB directly (VID 1366), no SEGGER software needed."""
    results = []
    for d in _usb_find(_SEGGER_VID):
        sn = d["serial"].lstrip("0") or d["serial"]
        results.append(_ok("debug", "jlink", f"{d['product'] or 'J-Link'} (SN {sn})", "🔧",
                           {**_usb_details(d), "serial": sn}))
    if results:
        return results

    jlink_exe = shutil.which("JLink") or shutil.which("JLinkExe")
    if jlink_exe:
        return [_ok("debug", "jlink", "SEGGER J-Link", "🔧",
                     {"path": jlink_exe})]

    try:
        import pylink
        jl = pylink.JLink()
        emus = jl.connected_emulators()
        for emu in emus:
            results.append(_ok("debug", "jlink",
                              f"J-Link SN:{emu}", "🔧",
                              {"serial": str(emu)}))
        if results:
            return results
    except Exception:
        pass

    if _IS_WINDOWS:
        results = _probe_usb_vid_pid(_SEGGER_VID, set(range(0x0101, 0x0110)) | {0x1015, 0x1051, 0x1061},
                                     "debug", "jlink", "SEGGER J-Link (USB)", "🔧")
        if results:
            return results
    return [_not_found("debug", "jlink", "No J-Link probes", "🔧")]


def _probe_hackrf() -> list[dict]:
    """HackRF SDR devices: found on USB directly (VID 1D50), no host tools needed."""
    results = []
    for d in _usb_find(_HACKRF_VID, set(_HACKRF_PIDS)):
        sn = d["serial"].lstrip("0") or d["serial"]
        details = {**_usb_details(d), "serial": d["serial"]}
        name = f"{_HACKRF_PIDS[d['pid']]} (…{sn[-8:]})" if sn else _HACKRF_PIDS[d["pid"]]
        if not d["writable"]:
            r = _err("sdr", "hackrf", name, "📡", _udev_hint("HackRF", _HACKRF_VID))
            r["details"] = details
            results.append(r)
        else:
            results.append(_ok("sdr", "hackrf", name, "📡", details))
    if results:
        return results

    hackrf_exe = shutil.which("hackrf_info")
    if hackrf_exe:
        try:
            out = subprocess.run(
                [hackrf_exe], capture_output=True, text=True, timeout=5,
            )
            if "Serial" in (out.stdout + out.stderr):
                serial_lines = [l for l in out.stdout.splitlines()
                                if "Serial" in l]
                serial = serial_lines[0].split(":", 1)[1].strip() if serial_lines else "?"
                return [_ok("sdr", "hackrf", f"HackRF One ({serial})", "📡",
                           {"serial": serial, "raw": out.stdout[:300]})]
        except Exception as exc:
            return [_err("sdr", "hackrf", "HackRF", "📡", str(exc))]

    try:
        _usb_results = _probe_usb_vid_pid(
            _HACKRF_VID, set(_HACKRF_PIDS),
            "sdr", "hackrf", "HackRF One (USB)", "📡",
        )
        if _usb_results:
            return _usb_results
    except Exception:
        pass

    return [_not_found("sdr", "hackrf", "No HackRF devices", "📡")]


# ─── Nordic CDC port classification ──────────────────────────────────
# PPK2 and nRF52840 dongles both use VID=1915 PID=C00A. The key
# differentiator is that PPK2 exposes **two** CDC interfaces on the
# same USB composite device (same serial number) whereas nRF52840
# dongles expose only one.  We group ports by serial number and
# classify accordingly.
# ──────────────────────────────────────────────────────────────────────

def _classify_nordic_cdc() -> tuple[list[dict], set[str]]:
    """Classify VID=1915 PID=C00A ports into PPK2 vs nRF52840.

    Returns
    -------
    ppk2_serials : set[str]
        Serial numbers that belong to PPK2 devices.
    port_groups : dict[str, list]
        ``{serial_number: [port_info, ...]}``
    """
    from collections import defaultdict

    ppk2_serials: set[str] = set()
    port_groups: dict[str, list] = defaultdict(list)

    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            if p.vid == 0x1915 and p.pid == 0xC00A and p.serial_number:
                port_groups[p.serial_number].append(p)
    except ImportError:
        return ppk2_serials, {}

    # Serials with 2+ ports on the same USB composite device → PPK2
    for sn, ports in port_groups.items():
        if len(ports) >= 2:
            ppk2_serials.add(sn)

    return ppk2_serials, dict(port_groups)


def _usb_iface(port: Any) -> int:
    import re as _re

    m = _re.search(r":\d+\.(\d+)$", getattr(port, "location", None) or "")
    return int(m.group(1)) if m else 99


def _probe_ppk2() -> list[dict]:
    """Check for Nordic PPK2 devices on serial ports or USB.

    PPK2 can appear with several VID/PID combos:
      - Nordic Semi VID=1915 PID=C00A (nRF Connect, shared with nRF dongles)
        → detected via multi-port heuristic (2+ CDC ports with same SN)
      - Nordic Semi VID=1915 PID=520F / C00B (PPK2-specific)
      - SEGGER VID=1366 PID=0105/1015/1051 (J-Link OB on PPK2)
    It may also show as "Power Profiler Kit" in description.
    """
    results = []
    _PPK2_PIDS_1366 = {0x0105, 0x1015, 0x1051}
    _PPK2_PIDS_1915 = {0x520F, 0xC00B}  # PPK2-specific Nordic PIDs

    try:
        import serial.tools.list_ports

        # --- Classify shared PID=C00A ports via multi-port heuristic ---
        ppk2_serials, port_groups = _classify_nordic_cdc()
        _seen_serials: set[str] = set()
        for sn in ppk2_serials:
            ports = port_groups[sn]
            # The data/command port is the CDC interface with the lower USB
            # interface number (…:1.1, not …:1.3) — not necessarily the lower tty number
            ports_sorted = sorted(ports, key=lambda p: (_usb_iface(p), p.device))
            data_port = ports_sorted[0]
            ctrl_port = ports_sorted[-1] if len(ports_sorted) > 1 else None
            details: dict[str, Any] = {
                "port": data_port.device,
                "description": data_port.description,
                "vid_pid": f"{data_port.vid:04X}:{data_port.pid:04X}",
                "serial_number": sn,
                "all_ports": [p.device for p in ports_sorted],
            }
            if ctrl_port and ctrl_port.device != data_port.device:
                details["control_port"] = ctrl_port.device
            results.append(_ok("instruments", "ppk2",
                              f"PPK2 ({data_port.device})", "⚡", details))
            _seen_serials.add(sn)

        # --- Check for PPK2-specific PIDs or keyword matches ---
        for p in serial.tools.list_ports.comports():
            sn = p.serial_number or ""
            if sn in _seen_serials:
                continue
            desc = (p.description or "").lower()
            prod = (p.product or "").lower()
            if ("ppk" in desc or "ppk" in prod
                    or "power profiler" in desc or "power profiler" in prod
                    or (p.vid == 0x1366 and p.pid in _PPK2_PIDS_1366)
                    or (p.vid == 0x1915 and p.pid in _PPK2_PIDS_1915)):
                results.append(_ok("instruments", "ppk2",
                                  f"PPK2 ({p.device})", "⚡",
                                  {"port": p.device, "description": p.description,
                                   "vid_pid": f"{p.vid:04X}:{p.pid:04X}" if p.vid else "",
                                   "serial_number": sn}))
                _seen_serials.add(sn)
    except ImportError:
        pass

    # USB-level fallback (Windows WMI)
    if not results:
        try:
            _usb = _probe_usb_vid_pid(
                0x1915, _PPK2_PIDS_1915,
                "instruments", "ppk2", "PPK2 (USB)", "⚡",
            )
            results.extend(_usb)
        except Exception:
            pass

    if not results:
        return [_not_found("instruments", "ppk2", "No PPK2 devices", "⚡")]
    return results


def _probe_nrf52840_dongle() -> list[dict]:
    """Check for nRF52840 USB dongles.

    Excludes serial numbers already claimed as PPK2 (multi-port CDC
    devices sharing VID=1915 PID=C00A).
    """
    results = []
    try:
        import serial.tools.list_ports

        # Get PPK2 serials so we don't double-count them
        ppk2_serials, _ = _classify_nordic_cdc()

        for p in serial.tools.list_ports.comports():
            sn = p.serial_number or ""
            # Skip ports that belong to PPK2
            if sn and sn in ppk2_serials:
                continue
            desc = (p.description or "").lower()
            prod = (p.product or "").lower()
            if ("nrf52840" in desc or "nrf52840" in prod or
                "nrf52" in desc or
                (p.vid == 0x1915 and p.pid in (0x521F, 0xCAFE, 0xC00A))):
                results.append(_ok("ble", "nrf52840_dongle",
                                  f"nRF52840 ({p.device})", "📶",
                                  {"port": p.device, "description": p.description,
                                   "serial_number": sn}))
    except ImportError:
        pass

    # A dongle without a serial port: Nordic bootloader / custom firmware (USB only)
    if not results and not _IS_WINDOWS:
        for d in _usb_find(0x1915, {0x521F, 0xCAFE, 0x520F}):
            results.append(_ok("ble", "nrf52840_dongle", f"{d['product'] or 'nRF52840'} (USB, no serial port)",
                               "📶", _usb_details(d)))

    if not results:
        return [_not_found("ble", "nrf52840_dongle", "No nRF52840 dongles", "📶")]
    return results


def _probe_network() -> list[dict]:
    """Quick check of local network / loopback."""
    import socket
    results = []
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
        results.append(_ok("network", "network", f"{hostname} ({ip})", "🌐",
                          {"hostname": hostname, "ip": ip}))
    except Exception:
        results.append(_ok("network", "network", hostname, "🌐",
                          {"hostname": hostname}))
    return results


# ═══════════════════════════════════════════════════════════════════════
#  Quick-test runners (per hardware category)
# ═══════════════════════════════════════════════════════════════════════

def _test_serial_port(hw: dict) -> dict:
    """Quick test: open + close serial port."""
    dev = hw["details"].get("device", "")
    if not dev:
        return {"passed": False, "message": "No device path"}
    try:
        import serial
        with serial.Serial(dev, 115200, timeout=1) as ser:
            return {"passed": True,
                    "message": f"Opened {dev} @ 115200 baud, DSR={ser.dsr}, CTS={ser.cts}"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_adb_device(hw: dict) -> dict:
    """Quick test: ADB shell round trip + the sensors the phone app can read."""
    dev_serial = hw["details"].get("serial", "")
    adb = os.environ.get("ADB_PATH", "adb")
    try:
        proc = subprocess.Popen(
            [adb, "-s", dev_serial, "shell", "echo", "pyontrust_ping"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return {"passed": False, "message": "ADB shell timed out"}
        if "pyontrust_ping" not in out:
            return {"passed": False, "message": f"ADB shell failed: {(err or out).strip()[:200]}"}

        try:
            from pyontrust.instruments import phone_camera
            sensors = phone_camera.sensors(dev_serial)
            names = [s["type"] for s in sensors]
            return {"passed": True,
                    "message": f"Shell OK, phone app OK — {len(names)} live sensors",
                    "sensors": names}
        except Exception as exc:
            names = _adb_list_sensors(adb, dev_serial)
            return {"passed": True,
                    "message": f"Shell OK; phone app not reachable ({exc}) — {len(names)} sensors via dumpsys",
                    "sensors": names[:20]}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def webcam_frame(index: int):
    """One frame from a webcam, through the camera pool the Microscopy and 3D
    pages use (so the device is shared, never opened twice)."""
    try:
        from pyontrust.services.camera_sources import _camera
    except ImportError:
        _camera = None
    if _camera is not None:
        return _camera.grab(int(index))
    cap = _open_capture(int(index))
    try:
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video device {index}")
        for _ in range(5):                     # first frames of some UVC cameras are empty
            ok, frame = cap.read()
            if ok and frame is not None:
                return frame
        raise RuntimeError(f"Video device {index} returned no frame")
    finally:
        cap.release()


def _test_webcam(hw: dict) -> dict:
    """Quick test: capture one frame from the webcam."""
    idx = hw["details"].get("index", 0)
    dev = hw["details"].get("device", f"#{idx}")
    try:
        frame = webcam_frame(int(idx))
        return {"passed": True,
                "message": f"Captured frame {frame.shape[1]}x{frame.shape[0]} from {dev}"}
    except Exception as exc:
        return {"passed": False, "message": f"{dev}: {exc}"}


def dwf_open(index: int):
    """Open a WaveForms device -> ``(dwf, handle)``; raises RuntimeError with the SDK's reason."""
    import ctypes

    dwf = load_dwf()
    count = ctypes.c_int()
    dwf.FDwfEnum(ctypes.c_int(0), ctypes.byref(count))
    if index >= count.value:
        raise RuntimeError(f"Analog Discovery #{index} is no longer connected")
    in_use = ctypes.c_int()
    dwf.FDwfEnumDeviceIsOpened(ctypes.c_int(index), ctypes.byref(in_use))
    if in_use.value:
        raise RuntimeError("device is open in another program (WaveForms, Lab Bench …)")
    hdwf = ctypes.c_int()
    dwf.FDwfDeviceOpen(ctypes.c_int(index), ctypes.byref(hdwf))
    if hdwf.value == 0:
        msg = ctypes.create_string_buffer(512)
        dwf.FDwfGetLastErrorMsg(msg)
        raise RuntimeError(f"FDwfDeviceOpen failed: {msg.value.decode(errors='replace').strip() or 'unknown error'}")
    return dwf, hdwf


def dwf_monitor(dwf, hdwf) -> dict[str, float]:
    """System monitor of an open WaveForms device (USB voltage/current, temperature …)."""
    import ctypes

    vals: dict[str, float] = {}
    dwf.FDwfAnalogIOStatus(hdwf)
    n_ch = ctypes.c_int()
    dwf.FDwfAnalogIOChannelCount(hdwf, ctypes.byref(n_ch))
    for ch in range(n_ch.value):
        name, label = ctypes.create_string_buffer(32), ctypes.create_string_buffer(16)
        dwf.FDwfAnalogIOChannelName(hdwf, ctypes.c_int(ch), name, label)
        if b"System" not in name.value and b"USB" not in name.value:
            continue
        n_node = ctypes.c_int()
        dwf.FDwfAnalogIOChannelInfo(hdwf, ctypes.c_int(ch), ctypes.byref(n_node))
        for node in range(n_node.value):
            nn, unit = ctypes.create_string_buffer(32), ctypes.create_string_buffer(16)
            dwf.FDwfAnalogIOChannelNodeName(hdwf, ctypes.c_int(ch), ctypes.c_int(node), nn, unit)
            v = ctypes.c_double()
            dwf.FDwfAnalogIOChannelNodeStatus(hdwf, ctypes.c_int(ch), ctypes.c_int(node), ctypes.byref(v))
            vals[nn.value.decode(errors="replace")] = v.value
    return vals


def _test_dwf_device(hw: dict) -> dict:
    """Quick test: open the device, read its system monitor, close."""
    idx = int(hw["details"].get("index", 0))
    try:
        dwf, hdwf = dwf_open(idx)
        try:
            mon = dwf_monitor(dwf, hdwf)
        finally:
            dwf.FDwfDeviceClose(hdwf)
        parts = []
        if "VUSB" in mon:
            parts.append(f"USB {mon['VUSB']:.2f} V")
        if "IUSB" in mon:
            parts.append(f"{mon['IUSB'] * 1000:.0f} mA")
        if "Temp" in mon:
            parts.append(f"{mon['Temp']:.1f} °C")
        return {"passed": True, "message": f"Opened device #{idx}" + (": " + ", ".join(parts) if parts else "")}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def thermal_frame():
    """One °C frame from the real Seek camera, shared with the Thermal workspace."""
    try:
        from pyontrust.gateway.blueprints.thermal_measurement import _arbiter
        from pyontrust.services.thermal_live import FrameError
    except ImportError:
        _arbiter = None
    if _arbiter is not None:
        try:
            return _arbiter.display_frame("seek")[0]
        except FrameError as exc:
            raise RuntimeError(exc.message) from exc
    from pyontrust.instruments.seek_thermal import create
    cam = create({"mode": "seek"})
    cam.open()
    try:
        return cam.grab_temperature_frame()
    finally:
        cam.close()


def _test_seek_thermal(hw: dict) -> dict:
    """Quick test: grab one real thermal frame."""
    try:
        import numpy as np

        frame = thermal_frame()
        return {"passed": True,
                "message": f"Frame {frame.shape[1]}x{frame.shape[0]}: "
                           f"{float(np.min(frame)):.1f} … {float(np.max(frame)):.1f} °C, "
                           f"mean {float(np.mean(frame)):.1f} °C"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_pcan(hw: dict) -> dict:
    """Quick test: SocketCAN interface state (Linux) or open a PCAN-Basic channel."""
    d = hw.get("details", {})
    if d.get("interface") == "socketcan":
        ch = d.get("channel", "can0")
        state = _read_sys(f"{_SYS_NET}/{ch}/operstate") or "gone"
        if state == "gone":
            return {"passed": False, "message": f"{ch} disappeared — adapter unplugged?"}
        if state != "up":
            return {"passed": True,
                    "message": f"{d.get('model', 'PCAN')} ready on {ch} (driver {d.get('driver')}); the bus is "
                               f"{state} — to use it: sudo ip link set {ch} up type can bitrate 500000"}
        try:
            import can  # type: ignore[import-untyped]
            bus = can.Bus(interface="socketcan", channel=ch)
            bus.shutdown()
            return {"passed": True, "message": f"{ch} is up and opened OK"}
        except Exception as exc:
            return {"passed": False, "message": f"{ch} is up but cannot be opened: {exc}"}
    try:
        import can  # type: ignore[import-untyped]
        channel = d.get("channel", "PCAN_USBBUS1")
        bus = can.Bus(interface="pcan", channel=channel, bitrate=500000)
        bus.shutdown()
        return {"passed": True, "message": f"Opened {channel} OK"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_jlink(hw: dict) -> dict:
    """Quick test: firmware version and target voltage over USB (read-only)."""
    if not hw.get("details", {}).get("vid_pid"):
        return _test_noop(hw)
    try:
        from pyontrust.instruments.jlink_usb import JLinkUsb

        with JLinkUsb(hw["details"].get("serial", "")) as jl:
            fw, st = jl.firmware(), jl.hw_status()
        target = (f"target {st['vtarget_v']:.2f} V" if st["vtarget_v"] > 0.3
                  else "no target voltage (target unpowered or not connected)")
        return {"passed": True, "message": f"{fw}; {target}"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_hackrf(hw: dict) -> dict:
    """Quick test: board id + firmware version via USB vendor requests (read-only)."""
    d = hw.get("details", {})
    if not d.get("vid_pid"):
        return _test_noop(hw)
    if not d.get("usb_access", True):
        return {"passed": False, "message": _udev_hint("HackRF", _HACKRF_VID)}
    try:
        import usb.core

        dev = usb.core.find(idVendor=_HACKRF_VID,
                            custom_match=lambda x: not d.get("serial") or x.serial_number == d["serial"])
        if dev is None:
            return {"passed": False, "message": "HackRF not found on USB"}
        try:
            board = bytes(dev.ctrl_transfer(0xC0, 14, 0, 0, 1))[0]
            version = bytes(dev.ctrl_transfer(0xC0, 15, 0, 0, 255)).decode(errors="replace").strip("\0 ")
        finally:
            usb.util.dispose_resources(dev)
        boards = {0: "Jellybean", 1: "Jawbreaker", 2: "HackRF One", 3: "rad1o", 4: "HackRF One r9"}
        return {"passed": True, "message": f"{boards.get(board, f'board id {board}')}, firmware {version}"}
    except Exception as exc:
        if "Access denied" in str(exc) or "langid" in str(exc):
            return {"passed": False, "message": _udev_hint("HackRF", _HACKRF_VID)}
        return {"passed": False, "message": str(exc)}


def _test_ppk2(hw: dict) -> dict:
    """Quick test: open the PPK2 and read its calibration (no measurement, DUT power untouched)."""
    port = hw.get("details", {}).get("port", "")
    if not port:
        return {"passed": False, "message": "No PPK2 port"}
    try:
        try:
            from ppk2_api import PPK2_API
        except ImportError:
            from ppk2_api.ppk2_api import PPK2_API
    except ImportError:
        return {"passed": False, "message": "ppk2-api is not installed (pip install ppk2-api)"}
    try:
        ppk = PPK2_API(port, timeout=1)
    except Exception as exc:
        if "Permission denied" in str(exc):
            return {"passed": False, "message": f"{port}: permission denied — add the user to the 'dialout' group"}
        return {"passed": False, "message": f"{port}: {exc}"}
    try:
        ppk.stop_measuring()
        old, ppk.ser.timeout = ppk.ser.timeout, 0.3
        end = time.time() + 3
        while time.time() < end and ppk.ser.read(65536):   # drain samples still in flight
            pass
        ppk.ser.timeout = old
        if not ppk.get_modifiers():
            return {"passed": False, "message": f"{port} opened but the PPK2 sent no calibration data"}
        return {"passed": True, "message": f"Opened {port}, calibration read OK (DUT power untouched)"}
    except Exception as exc:
        return {"passed": False, "message": f"{port}: {exc}"}
    finally:
        try:
            ppk.ser.close()
        except Exception:
            pass


def _test_nordic_serial(hw: dict) -> dict:
    d = hw.get("details", {})
    if not d.get("port"):
        return _test_noop(hw)
    return _test_serial_port({"details": {"device": d["port"]}})


def _test_noop(hw: dict) -> dict:
    """No-op test for hardware we can't easily probe further."""
    return {"passed": True, "message": "Detected (no quick test available)"}


_TEST_RUNNERS: dict[str, Any] = {
    "serial_port": _test_serial_port,
    "android_sensors": _test_adb_device,
    "webcam": _test_webcam,
    "ad3_dwf": _test_dwf_device,
    "seek_thermal": _test_seek_thermal,
    "pcan": _test_pcan,
    "jlink": _test_jlink,
    "hackrf": _test_hackrf,
    "ppk2": _test_ppk2,
    "nrf52840_dongle": _test_nordic_serial,
    "network": _test_noop,
}


# ═══════════════════════════════════════════════════════════════════════
#  Main discovery and diagnostic API
# ═══════════════════════════════════════════════════════════════════════

def discover_all_hardware(*, timeout_s: float = 30.0) -> list[dict]:
    """Run all hardware probes in parallel and return results.

    Each probe runs in a thread with a timeout so one slow probe
    doesn't block the others.  If the global timeout expires we
    still return whatever partial results were collected.
    """
    probes = [
        ("serial", _probe_serial_ports),
        ("adb", _probe_adb_devices),
        ("webcam", _probe_webcams),
        ("dwf", _probe_dwf_devices),
        ("seek", _probe_seek_thermal),
        ("pcan", _probe_pcan),
        ("jlink", _probe_jlink),
        ("hackrf", _probe_hackrf),
        ("ppk2", _probe_ppk2),
        ("nrf52840", _probe_nrf52840_dongle),
        ("network", _probe_network),
    ]

    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(probes)) as executor:
        future_map = {
            executor.submit(fn): name
            for name, fn in probes
        }
        try:
            for future in as_completed(future_map, timeout=timeout_s):
                name = future_map[future]
                try:
                    items = future.result(timeout=5)
                    all_results.extend(items)
                except Exception as exc:
                    all_results.append(
                        _err("system", name, f"{name} probe", "⚠️", str(exc)))
        except FuturesTimeoutError:
            # Collect whatever finished, mark the rest as timed-out
            for future, name in future_map.items():
                if not future.done():
                    all_results.append(
                        _err("system", name, f"{name} probe", "⏱️",
                             "Probe timed out"))
                    future.cancel()

    # Sort: ok first, then error, then not_found
    order = {"ok": 0, "error": 1, "not_found": 2}
    all_results.sort(key=lambda r: (order.get(r["status"], 3), r["category"]))
    return all_results


def run_quick_test(hw_item: dict) -> dict:
    """Run a quick test on a discovered hardware item.

    Returns the test result dict with ``passed`` and ``message``.
    """
    hw_type = hw_item.get("type", "")
    runner = _TEST_RUNNERS.get(hw_type, _test_noop)
    try:
        return runner(hw_item)
    except Exception as exc:
        return {"passed": False, "message": f"Test error: {exc}"}


def run_all_tests(hw_list: list[dict]) -> list[dict]:
    """Run quick tests on all 'ok' hardware items."""
    results = []
    for hw in hw_list:
        if hw["status"] == "ok":
            hw["test_result"] = run_quick_test(hw)
        results.append(hw)
    return results
