"""Live data for the Hardware Diagnostic page — one reader per device type.

``CHANNELS[hw_type]`` lists what can be streamed for a device (the page builds
its sensor menu from it); ``open_reader(hw_type, channel, details)`` returns a
reader that is opened once per stream and polled with ``read()``:

=============  ==========  ==================================================
type           channel     values
=============  ==========  ==================================================
webcam         frame       brightness, mean R/G/B (shared Microscopy camera pool)
ad3_dwf        scope       scope inputs CH1/CH2 (V, ±25 V range)
ad3_dwf        system      USB voltage/current, device temperature
ppk2           current     mean/min/max current over the interval (ampere meter;
                           the DUT supply is never switched on)
seek_thermal   frame       min/mean/max °C (shared with the Thermal workspace)
jlink          vtarget     target voltage
pcan           bus         frames/s received/sent, error count (SocketCAN)
=============  ==========  ==================================================

Phones (``android_sensors``) are read by the diagnostic blueprint directly.
"""
from __future__ import annotations

import time
from typing import Any

CHANNELS: dict[str, list[dict[str, Any]]] = {
    "android_sensors": [
        {"id": "accelerometer", "label": "Accelerometer", "unit": "m/s²", "axes": ["x", "y", "z"]},
        {"id": "gyroscope", "label": "Gyroscope", "unit": "rad/s", "axes": ["x", "y", "z"]},
        {"id": "magnetometer", "label": "Magnetometer", "unit": "µT", "axes": ["x", "y", "z"]},
        {"id": "light", "label": "Light", "unit": "lux", "axes": ["lux"]},
        {"id": "proximity", "label": "Proximity", "unit": "cm", "axes": ["distance"]},
        {"id": "barometer", "label": "Barometer", "unit": "hPa", "axes": ["pressure"]},
        {"id": "gravity", "label": "Gravity", "unit": "m/s²", "axes": ["x", "y", "z"]},
        {"id": "linear_acceleration", "label": "Linear Accel", "unit": "m/s²", "axes": ["x", "y", "z"]},
        {"id": "rotation", "label": "Rotation Vec", "unit": "", "axes": ["x", "y", "z", "w"]},
        {"id": "battery", "label": "Battery", "unit": "", "axes": ["level_pct", "voltage_mv", "temperature_c"]},
        {"id": "gps", "label": "GPS", "unit": "", "axes": ["latitude", "longitude", "altitude_m"]},
    ],
    "webcam": [
        {"id": "frame", "label": "Image", "unit": "0–255", "axes": ["brightness", "mean_r", "mean_g", "mean_b"]},
    ],
    "ad3_dwf": [
        {"id": "scope", "label": "Scope inputs", "unit": "V", "axes": ["ch1_v", "ch2_v"]},
        {"id": "system", "label": "System monitor", "unit": "", "axes": ["usb_v", "usb_ma", "temp_c"]},
    ],
    "ppk2": [
        {"id": "current", "label": "Current (ampere meter)", "unit": "µA", "axes": ["mean_ua", "min_ua", "max_ua"]},
    ],
    "seek_thermal": [
        {"id": "frame", "label": "Temperature", "unit": "°C", "axes": ["min_c", "mean_c", "max_c"]},
    ],
    "jlink": [
        {"id": "vtarget", "label": "Target voltage", "unit": "V", "axes": ["vtarget_v"]},
    ],
    "pcan": [
        {"id": "bus", "label": "Bus traffic", "unit": "/s", "axes": ["rx_fps", "tx_fps", "errors"]},
    ],
}


class LiveError(RuntimeError):
    pass


class _Reader:
    def read(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass


# ── webcam ──────────────────────────────────────────────────────────────
class _Webcam(_Reader):
    def __init__(self, d: dict[str, Any]) -> None:
        self.index = int(d.get("index", 0))

    def read(self) -> dict[str, Any]:
        import numpy as np

        from pyontrust.services.hardware_discovery import webcam_frame

        f = webcam_frame(self.index)
        b, g, r = (float(np.mean(f[:, :, i])) for i in range(3))
        return {"width": f.shape[1], "height": f.shape[0],
                "brightness": round(0.114 * b + 0.587 * g + 0.299 * r, 2),
                "mean_r": round(r, 2), "mean_g": round(g, 2), "mean_b": round(b, 2)}


# ── Analog Discovery (WaveForms) ────────────────────────────────────────
class _Dwf(_Reader):
    def __init__(self, d: dict[str, Any], channel: str) -> None:
        import ctypes

        from pyontrust.services.hardware_discovery import dwf_open

        self.c = ctypes
        self.channel = channel
        try:
            self.dwf, self.h = dwf_open(int(d.get("index", 0)))
        except Exception as exc:
            raise LiveError(str(exc)) from exc
        if channel == "scope":
            # both inputs, ±25 V range, single-sample mode (no acquisition buffer)
            self.dwf.FDwfAnalogInChannelEnableSet(self.h, ctypes.c_int(-1), ctypes.c_int(1))
            self.dwf.FDwfAnalogInChannelRangeSet(self.h, ctypes.c_int(-1), ctypes.c_double(50.0))
            self.dwf.FDwfAnalogInConfigure(self.h, ctypes.c_int(0), ctypes.c_int(0))
            time.sleep(0.1)

    def read(self) -> dict[str, Any]:
        c = self.c
        if self.channel == "system":
            from pyontrust.services.hardware_discovery import dwf_monitor

            m = dwf_monitor(self.dwf, self.h)
            return {"usb_v": round(m.get("VUSB", float("nan")), 3),
                    "usb_ma": round(m.get("IUSB", float("nan")) * 1000, 1),
                    "temp_c": round(m.get("Temp", float("nan")), 2)}
        st = c.c_byte()
        self.dwf.FDwfAnalogInStatus(self.h, c.c_int(0), c.byref(st))
        out = {}
        for i in range(2):
            v = c.c_double()
            self.dwf.FDwfAnalogInStatusSample(self.h, c.c_int(i), c.byref(v))
            out[f"ch{i + 1}_v"] = round(v.value, 4)
        return out

    def close(self) -> None:
        try:
            self.dwf.FDwfDeviceClose(self.h)
        except Exception:
            pass


# ── PPK2 (ampere meter only) ────────────────────────────────────────────
class _Ppk2(_Reader):
    def __init__(self, d: dict[str, Any]) -> None:
        port = d.get("port", "")
        if not port:
            raise LiveError("no PPK2 port")
        try:
            try:
                from ppk2_api import PPK2_API
            except ImportError:
                from ppk2_api.ppk2_api import PPK2_API
        except ImportError as exc:
            raise LiveError("ppk2-api is not installed (pip install ppk2-api)") from exc
        try:
            self.ppk = PPK2_API(port, timeout=1)
        except Exception as exc:
            if "Permission denied" in str(exc):
                raise LiveError(f"{port}: permission denied — add the user to the 'dialout' group") from exc
            raise LiveError(f"{port}: {exc}") from exc
        try:
            self._drain()
            if not self.ppk.get_modifiers():
                raise LiveError(f"{port}: the PPK2 sent no calibration data")
            self.ppk.use_ampere_meter()           # in-line meter; DUT power is never switched on
            self.ppk.set_source_voltage(3300)     # ppk2-api needs a reference voltage to start
            self.ppk.start_measuring()
        except Exception:
            self.close()
            raise
        import threading

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._acc = self._empty()
        self._err: str | None = None
        self._last = time.time()
        # 100 k samples/s ≈ 400 kB/s: read continuously so the tty buffer never overflows
        self._thread = threading.Thread(target=self._pump, name="ppk2-live", daemon=True)
        self._thread.start()

    @staticmethod
    def _empty() -> dict[str, float]:
        return {"n": 0, "sum": 0.0, "min": float("inf"), "max": float("-inf")}

    def _pump(self) -> None:
        import numpy as np

        while not self._stop.is_set():
            try:
                raw = self.ppk.get_data()
                if not raw:
                    time.sleep(0.002)
                    continue
                s = self.ppk.get_samples(raw)
                s = s[0] if isinstance(s, tuple) else s
                if not s:
                    continue
                a = np.asarray(s, dtype=float)
                with self._lock:
                    acc = self._acc
                    acc["n"] += a.size
                    acc["sum"] += float(a.sum())
                    acc["min"] = min(acc["min"], float(a.min()))
                    acc["max"] = max(acc["max"], float(a.max()))
            except Exception as exc:       # port closed / unplugged
                self._err = str(exc)
                return

    def _drain(self) -> None:
        self.ppk.stop_measuring()
        old, self.ppk.ser.timeout = self.ppk.ser.timeout, 0.3
        end = time.time() + 3
        while time.time() < end and self.ppk.ser.read(65536):
            pass
        self.ppk.ser.timeout = old

    def read(self) -> dict[str, Any]:
        if self._err:
            raise LiveError(f"PPK2: {self._err}")
        end = time.time() + 1.0
        while True:                         # first call right after start: wait for data
            with self._lock:
                if self._acc["n"] or time.time() > end:
                    acc, self._acc = self._acc, self._empty()
                    break
            time.sleep(0.01)
        now = time.time()
        window, self._last = now - self._last, now
        if not acc["n"]:
            return {"error": "no samples from the PPK2"}
        return {"mean_ua": round(acc["sum"] / acc["n"], 3), "min_ua": round(acc["min"], 3),
                "max_ua": round(acc["max"], 3), "n_samples": int(acc["n"]), "window_s": round(window, 3)}

    def close(self) -> None:
        stop = getattr(self, "_stop", None)
        if stop is not None:
            stop.set()
            self._thread.join(2)
        try:
            self._drain()
        except Exception:
            pass
        try:
            self.ppk.ser.close()
        except Exception:
            pass


# ── Seek thermal ────────────────────────────────────────────────────────
class _Seek(_Reader):
    def read(self) -> dict[str, Any]:
        import numpy as np

        from pyontrust.services.hardware_discovery import thermal_frame

        f = thermal_frame()
        return {"min_c": round(float(np.min(f)), 2), "mean_c": round(float(np.mean(f)), 2),
                "max_c": round(float(np.max(f)), 2)}


# ── J-Link ──────────────────────────────────────────────────────────────
class _JLink(_Reader):
    def __init__(self, d: dict[str, Any]) -> None:
        from pyontrust.instruments.jlink_usb import JLinkUsb, JLinkUsbError

        try:
            self.jl = JLinkUsb(d.get("serial", "")).open()
        except JLinkUsbError as exc:
            raise LiveError(str(exc)) from exc

    def read(self) -> dict[str, Any]:
        return {"vtarget_v": round(self.jl.hw_status()["vtarget_v"], 3)}

    def close(self) -> None:
        self.jl.close()


# ── PCAN via SocketCAN statistics ───────────────────────────────────────
class _Pcan(_Reader):
    def __init__(self, d: dict[str, Any]) -> None:
        if d.get("interface") != "socketcan":
            raise LiveError("live bus statistics need the Linux SocketCAN driver (peak_usb)")
        self.ch = d.get("channel", "can0")
        self._prev = self._stats()
        self._t = time.time()

    def _stats(self) -> dict[str, int]:
        from pyontrust.services import hardware_discovery as hd

        base = f"{hd._SYS_NET}/{self.ch}"
        _read_sys = hd._read_sys
        if not _read_sys(f"{base}/operstate"):
            raise LiveError(f"{self.ch} is gone — adapter unplugged?")
        return {k: int(_read_sys(f"{base}/statistics/{k}") or 0)
                for k in ("rx_packets", "tx_packets", "rx_errors", "tx_errors")}

    def read(self) -> dict[str, Any]:
        from pyontrust.services import hardware_discovery as hd

        now, cur = time.time(), self._stats()
        dt = max(1e-3, now - self._t)
        prev, self._prev, self._t = self._prev, cur, now
        state = hd._read_sys(f"{hd._SYS_NET}/{self.ch}/operstate")
        out = {"rx_fps": round((cur["rx_packets"] - prev["rx_packets"]) / dt, 1),
               "tx_fps": round((cur["tx_packets"] - prev["tx_packets"]) / dt, 1),
               "errors": cur["rx_errors"] + cur["tx_errors"], "state": state}
        if state != "up":
            out["note"] = f"{self.ch} is {state} — sudo ip link set {self.ch} up type can bitrate 500000"
        return out


def open_reader(hw_type: str, channel: str, details: dict[str, Any]) -> _Reader:
    """Reader for one device/channel; raises :class:`LiveError` with a readable reason."""
    chans = {c["id"] for c in CHANNELS.get(hw_type, [])}
    if hw_type == "android_sensors" or not chans:
        raise LiveError(f"no live data for {hw_type}")
    if channel not in chans:
        channel = next(iter(c["id"] for c in CHANNELS[hw_type]))
    if hw_type == "webcam":
        return _Webcam(details)
    if hw_type == "ad3_dwf":
        return _Dwf(details, channel)
    if hw_type == "ppk2":
        return _Ppk2(details)
    if hw_type == "seek_thermal":
        return _Seek()
    if hw_type == "jlink":
        return _JLink(details)
    if hw_type == "pcan":
        return _Pcan(details)
    raise LiveError(f"no live data for {hw_type}")


def read_once(hw_type: str, channel: str, details: dict[str, Any]) -> dict[str, Any]:
    r = open_reader(hw_type, channel, details)
    try:
        return r.read()
    finally:
        r.close()
