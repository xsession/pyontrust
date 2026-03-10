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
            desc = p.description or p.device
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
    """
    sensors: list[str] = []
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


def _probe_webcams() -> list[dict]:
    """Enumerate available webcams via OpenCV.

    On Windows with DSHOW, ``cv2.VideoCapture(idx)`` for a non-existent
    index can block for many seconds.  We only probe index 0 quickly;
    if it works we try 1–3 as well.
    """
    results = []
    try:
        import cv2

        for idx in range(4):
            try:
                # Use CAP_DSHOW on Windows for device-name support
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap.release()
                    break  # Stop at first missing index — they are contiguous
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


def _probe_dwf_devices() -> list[dict]:
    """Enumerate Analog Discovery / WaveForms SDK devices."""
    results = []
    try:
        # Try loading the DWF library
        try:
            from pyontrust.hal.dwf_loader import dwf
        except ImportError:
            try:
                import ctypes
                dwf = ctypes.cdll.dwf  # type: ignore[attr-defined]
            except OSError:
                return [_not_found("instruments", "ad3_dwf",
                                   "Digilent WaveForms SDK not found", "📟")]

        import ctypes
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

            dwf.FDwfEnumDeviceType(ctypes.c_int(i),
                                   ctypes.byref(dev_id), ctypes.byref(dev_rev))
            try:
                dwf.FDwfEnumDeviceName(ctypes.c_int(i), name_buf)
                dwf.FDwfEnumSN(ctypes.c_int(i), serial_buf)
            except Exception:
                pass

            dev_name = name_buf.value.decode("utf-8", errors="replace").strip()
            dev_sn = serial_buf.value.decode("utf-8", errors="replace").strip()

            results.append(_ok(
                "instruments", "ad3_dwf",
                dev_name or f"DWF Device #{i}", "📟",
                {"index": i, "name": dev_name, "serial": dev_sn,
                 "device_id": dev_id.value, "revision": dev_rev.value},
            ))
    except Exception as exc:
        results.append(_err("instruments", "ad3_dwf", "DWF probe", "📟", str(exc)))

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


def _probe_pcan() -> list[dict]:
    """Detect PEAK-CAN USB adapters.

    Strategy:
      1. Try python-can detect_available_configs for pcan interface.
      2. Fall back to USB VID/PID scanning (VID 0x0C72).
    """
    try:
        results: list[dict] = []

        # Strategy 1: python-can detection
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

        # Strategy 2: USB VID/PID enumeration
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

        # Strategy 3: check if PCAN driver DLL is installed (Windows)
        try:
            import platform
            if platform.system() == "Windows":
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


def _probe_jlink() -> list[dict]:
    """Check for SEGGER J-Link probes."""
    jlink_exe = shutil.which("JLink") or shutil.which("JLinkExe")
    if jlink_exe:
        return [_ok("debug", "jlink", "SEGGER J-Link", "🔧",
                     {"path": jlink_exe})]

    # Try pylink
    try:
        import pylink
        jl = pylink.JLink()
        if jl.connected_emulators():
            emus = jl.connected_emulators()
            results = []
            for emu in emus:
                results.append(_ok("debug", "jlink",
                                  f"J-Link SN:{emu}", "🔧",
                                  {"serial": str(emu)}))
            return results
    except Exception:
        pass

    return [_not_found("debug", "jlink", "No J-Link probes", "🔧")]


def _probe_hackrf() -> list[dict]:
    """Check for HackRF SDR devices."""
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

    # Try SoapySDR
    try:
        import SoapySDR
        devs = SoapySDR.Device.enumerate("driver=hackrf")
        if devs:
            return [_ok("sdr", "hackrf", "HackRF via SoapySDR", "📡",
                        {"devices": len(devs)})]
    except Exception:
        pass

    # Fallback: check USB VID/PID (HackRF VID=1D50, PID=6089/604B/CC15)
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            if p.vid == 0x1D50 and p.pid in (0x6089, 0x604B, 0xCC15):
                return [_ok("sdr", "hackrf",
                            f"HackRF One ({p.device})", "📡",
                            {"port": p.device,
                             "vid_pid": f"{p.vid:04X}:{p.pid:04X}",
                             "serial_number": p.serial_number or ""})]
    except ImportError:
        pass

    # Fallback: check all USB devices via WMI (Windows) for VID 1D50
    try:
        _usb_results = _probe_usb_vid_pid(
            0x1D50, {0x6089, 0x604B, 0xCC15},
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
            # Pick the lowest-numbered COM port as the "data" port
            ports_sorted = sorted(ports, key=lambda p: p.device)
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
    """Quick test: read sensors list from Android device."""
    dev_serial = hw["details"].get("serial", "")
    adb = os.environ.get("ADB_PATH", "adb")
    try:
        # Test basic shell access with Popen for reliable kill
        proc = subprocess.Popen(
            [adb, "-s", dev_serial, "shell", "echo", "pyontrust_ping"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return {"passed": False, "message": "ADB shell timed out"}

        if "pyontrust_ping" not in out:
            return {"passed": False, "message": "Shell echo failed"}

        # Get sensor list
        proc2 = subprocess.Popen(
            [adb, "-s", dev_serial, "shell", "dumpsys", "sensorservice"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            sensors_out, _ = proc2.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc2.kill()
            proc2.communicate()
            return {"passed": True, "message": "Shell OK, sensor query timed out"}
        sensor_count = sum(1 for l in sensors_out.splitlines()
                          if "| " in l and "handle" in l.lower())

        # Get available sensors summary
        sensor_names = []
        for line in sensors_out.splitlines():
            if "| " in line and ("Accel" in line or "Gyro" in line or
                                  "Magnet" in line or "Proximity" in line or
                                  "Light" in line or "Pressure" in line or
                                  "Gravity" in line or "Rotation" in line):
                name = line.split("|")[1].strip() if "|" in line else line.strip()
                if name:
                    sensor_names.append(name[:50])

        return {"passed": True,
                "message": f"Shell OK, ~{sensor_count} sensors detected",
                "sensors": sensor_names[:20]}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_webcam(hw: dict) -> dict:
    """Quick test: capture one frame from webcam."""
    idx = hw["details"].get("index", 0)
    try:
        import cv2
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return {"passed": False, "message": f"Cannot open camera #{idx}"}
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            return {"passed": True,
                    "message": f"Captured frame: {frame.shape[1]}x{frame.shape[0]} "
                               f"({frame.dtype})"}
        return {"passed": False, "message": "read() returned empty frame"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_dwf_device(hw: dict) -> dict:
    """Quick test: open + close DWF device."""
    idx = hw["details"].get("index", 0)
    try:
        import ctypes
        try:
            from pyontrust.hal.dwf_loader import dwf
        except ImportError:
            dwf = ctypes.cdll.dwf  # type: ignore[attr-defined]

        hdwf = ctypes.c_int()
        ok = dwf.FDwfDeviceOpen(ctypes.c_int(idx), ctypes.byref(hdwf))
        if ok and hdwf.value != 0:
            # Read supply voltage as a simple health check
            v_pos = ctypes.c_double()
            v_neg = ctypes.c_double()
            dwf.FDwfAnalogIOChannelNodeStatus(
                hdwf, ctypes.c_int(0), ctypes.c_int(0), ctypes.byref(v_pos))
            dwf.FDwfDeviceClose(hdwf)
            return {"passed": True,
                    "message": f"Opened device #{idx}, USB voltage ≈ {v_pos.value:.2f}V"}
        return {"passed": False, "message": "FDwfDeviceOpen failed"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_seek_thermal(hw: dict) -> dict:
    """Quick test: try simulated grab."""
    try:
        from pyontrust.instruments.seek_thermal import create
        cam = create({"mode": "simulated"})
        cam.open()
        try:
            frame = cam.grab_temperature_frame()
            import numpy as np
            return {"passed": True,
                    "message": f"Simulated OK: shape={frame.shape}, "
                               f"mean={float(np.mean(frame)):.1f}°C"}
        finally:
            cam.close()
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


def _test_pcan(hw: dict) -> dict:
    """Quick test: try opening a PCAN channel in loopback / virtual mode."""
    try:
        import can  # type: ignore[import-untyped]
        channel = hw.get("details", {}).get("channel", "PCAN_USBBUS1")
        bus = can.Bus(interface="pcan", channel=channel, bitrate=500000)
        bus.shutdown()
        return {"passed": True, "message": f"Opened {channel} OK"}
    except Exception as exc:
        return {"passed": False, "message": str(exc)}


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
    "jlink": _test_noop,
    "hackrf": _test_noop,
    "ppk2": _test_noop,
    "nrf52840_dongle": _test_noop,
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
