"""Android phone sensor instrument — ADB USB bridge + simulated driver.

Streams sensor data from an Android phone connected over USB via ADB.
Uses a lightweight helper (``termux-sensor`` or a custom sensor-bridge APK)
to read hardware sensors and forward the data over ``adb forward tcp``.

Supported sensors:
    - **Accelerometer** (TYPE_ACCELEROMETER) — 3-axis acceleration in m/s²
    - **Gyroscope** (TYPE_GYROSCOPE) — 3-axis angular velocity in rad/s
    - **Magnetometer** (TYPE_MAGNETIC_FIELD) — 3-axis magnetic field in µT
    - **Microphone** (raw PCM audio at configurable sample rate)
    - **Proximity** (distance in cm, typically binary near/far)
    - **Light** (ambient light in lux)
    - **Barometer** (atmospheric pressure in hPa)
    - **GPS** (latitude, longitude, altitude, speed)
    - **Battery** (voltage, temperature, level, status)
    - **Gravity** (TYPE_GRAVITY) — 3-axis gravity in m/s²
    - **Rotation Vector** (TYPE_ROTATION_VECTOR) — quaternion orientation

The bridge supports two connection modes:
    1. **ADB TCP forward** — ``adb forward tcp:LOCAL tcp:REMOTE`` then JSON over socket
    2. **ADB shell** — ``adb shell`` commands for Termux or dumpsys

All sensors share the ``create()`` factory for the pyontrust instrument registry.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import socket
import subprocess
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("pyontrust.instruments.android_sensors")

# ═══════════════════════════════════════════════════════════════════════
#  ADB helper utilities
# ═══════════════════════════════════════════════════════════════════════

_ADB = os.environ.get("ADB_PATH", "adb")


def _run_adb(*args: str, timeout: float = 10.0) -> str:
    """Run an ADB command and return stdout."""
    cmd = [_ADB] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(
            "adb not found. Install Android SDK Platform-Tools and ensure "
            "'adb' is on your PATH, or set ADB_PATH env var."
        )


def _adb_available() -> bool:
    """Check whether ADB is available and at least one device is connected."""
    try:
        out = _run_adb("devices", timeout=5.0)
        lines = [l.strip() for l in out.splitlines() if "\tdevice" in l]
        return len(lines) > 0
    except Exception:
        return False


def _adb_device_info() -> dict[str, str]:
    """Get basic device information via ADB."""
    try:
        model = _run_adb("shell", "getprop", "ro.product.model", timeout=5)
        brand = _run_adb("shell", "getprop", "ro.product.brand", timeout=5)
        sdk = _run_adb("shell", "getprop", "ro.build.version.sdk", timeout=5)
        serial = _run_adb("get-serialno", timeout=5)
        return {
            "model": model, "brand": brand, "sdk_version": sdk,
            "serial": serial,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _adb_get_battery() -> dict[str, Any]:
    """Read battery stats via ``adb shell dumpsys battery``."""
    try:
        out = _run_adb("shell", "dumpsys", "battery", timeout=5)
        info: dict[str, Any] = {}
        for line in out.splitlines():
            line = line.strip()
            if ":" in line:
                k, _, v = line.partition(":")
                k, v = k.strip().lower().replace(" ", "_"), v.strip()
                try:
                    info[k] = int(v) if v.isdigit() else v
                except ValueError:
                    info[k] = v
        return {
            "level_pct": info.get("level", 0),
            "voltage_mv": info.get("voltage", 0),
            "temperature_c": info.get("temperature", 0) / 10.0
            if isinstance(info.get("temperature"), (int, float)) else 0,
            "status": info.get("status", "unknown"),
            "health": info.get("health", "unknown"),
        }
    except Exception as exc:
        return {"error": str(exc)}


# ═══════════════════════════════════════════════════════════════════════
#  Sensor data types
# ═══════════════════════════════════════════════════════════════════════

SENSOR_TYPES = {
    "accelerometer": {"android_type": 1, "axes": ["x", "y", "z"], "unit": "m/s²"},
    "gyroscope":     {"android_type": 4, "axes": ["x", "y", "z"], "unit": "rad/s"},
    "magnetometer":  {"android_type": 2, "axes": ["x", "y", "z"], "unit": "µT"},
    "proximity":     {"android_type": 8, "axes": ["distance"], "unit": "cm"},
    "light":         {"android_type": 5, "axes": ["lux"], "unit": "lux"},
    "barometer":     {"android_type": 6, "axes": ["pressure"], "unit": "hPa"},
    "gravity":       {"android_type": 9, "axes": ["x", "y", "z"], "unit": "m/s²"},
    "rotation":      {"android_type": 11, "axes": ["x", "y", "z", "w"], "unit": ""},
}


# ═══════════════════════════════════════════════════════════════════════
#  ADB Sensor Bridge — JSON-over-TCP using Termux or custom APK
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_BRIDGE_PORT = 5210


@dataclass
class AdbSensorBridge:
    """Manage the ADB TCP bridge to the Android sensor server.

    The bridge works by forwarding a local TCP port to the phone's sensor
    server (either Termux-based or a custom APK).

    Protocol (JSON lines over TCP):
        → {"cmd": "start", "sensor": "accelerometer", "rate_ms": 20}
        ← {"sensor": "accelerometer", "t": 1234567890.123, "values": [0.1, 9.8, 0.3]}
        → {"cmd": "stop", "sensor": "accelerometer"}
        → {"cmd": "read_mic", "duration_s": 2, "sample_rate": 16000}
        ← {"sensor": "microphone", "samples": [...], "sample_rate": 16000}
    """

    local_port: int = _DEFAULT_BRIDGE_PORT
    remote_port: int = _DEFAULT_BRIDGE_PORT
    _socket: socket.socket | None = None
    _connected: bool = False

    def connect(self) -> None:
        """Set up ADB port forwarding and connect."""
        _run_adb("forward", f"tcp:{self.local_port}", f"tcp:{self.remote_port}")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        try:
            self._socket.connect(("127.0.0.1", self.local_port))
            self._connected = True
            logger.info("ADB sensor bridge connected on port %d", self.local_port)
        except ConnectionRefusedError:
            self._connected = False
            raise RuntimeError(
                "Could not connect to Android sensor server. "
                "Ensure the sensor bridge app is running on the phone.\n"
                "Options:\n"
                "  1. Install Termux + termux-api and run the sensor bridge script\n"
                "  2. Install the pyontrust sensor bridge APK\n"
                "  3. Use 'simulated' mode for testing without a phone"
            )

    def disconnect(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        self._socket = None
        self._connected = False
        try:
            _run_adb("forward", "--remove", f"tcp:{self.local_port}")
        except Exception:
            pass

    def send_cmd(self, cmd: dict) -> dict | None:
        """Send a JSON command and read one JSON response line."""
        if not self._connected or not self._socket:
            raise RuntimeError("Bridge not connected")
        self._socket.sendall((json.dumps(cmd) + "\n").encode())
        data = b""
        while b"\n" not in data:
            chunk = self._socket.recv(4096)
            if not chunk:
                return None
            data += chunk
        return json.loads(data.split(b"\n", 1)[0])

    def read_lines(self, timeout_s: float = 1.0) -> list[dict]:
        """Read available JSON lines within timeout."""
        if not self._socket:
            return []
        self._socket.settimeout(timeout_s)
        lines: list[dict] = []
        buf = b""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                chunk = self._socket.recv(8192)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            except socket.timeout:
                break
        return lines


# ═══════════════════════════════════════════════════════════════════════
#  Simulated Android sensors (CI / development — no phone required)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class SimulatedAndroidSensors:
    """Simulated Android sensor data for testing without a phone.

    Generates realistic-ish synthetic sensor readings so the full
    pipeline can be tested without hardware.
    """

    sample_rate_hz: float = 50.0
    base_temp_c: float = 25.0
    _opened: bool = False
    _t0: float = 0.0

    def open(self) -> None:
        self._opened = True
        self._t0 = time.time()
        logger.info("SimulatedAndroidSensors opened (%.0f Hz)", self.sample_rate_hz)

    def close(self) -> None:
        self._opened = False
        logger.info("SimulatedAndroidSensors closed")

    def info(self) -> dict[str, str]:
        return {
            "model": "Simulated Android",
            "brand": "pyontrust",
            "serial": "SIM-ANDROID-0000",
            "mode": "simulated",
        }

    def read_sensor(
        self, sensor_type: str, duration_s: float = 1.0,
    ) -> dict[str, Any]:
        """Read a sensor for a given duration, return aggregated data."""
        if not self._opened:
            raise RuntimeError("Sensors not open. Call open() first.")

        n = max(1, int(self.sample_rate_hz * duration_s))
        dt = duration_s / n
        t_base = time.time() - self._t0
        timestamps = [t_base + i * dt for i in range(n)]

        if sensor_type == "accelerometer":
            # Stationary phone: ~0, ~0, ~9.81 with noise
            data = {
                "x": [random.gauss(0.05, 0.02) for _ in range(n)],
                "y": [random.gauss(0.03, 0.02) for _ in range(n)],
                "z": [random.gauss(9.81, 0.05) for _ in range(n)],
            }
        elif sensor_type == "gyroscope":
            # Stationary: near zero
            data = {
                "x": [random.gauss(0, 0.005) for _ in range(n)],
                "y": [random.gauss(0, 0.005) for _ in range(n)],
                "z": [random.gauss(0, 0.005) for _ in range(n)],
            }
        elif sensor_type == "magnetometer":
            # Earth's field: ~25-65 µT total, with orientation components
            data = {
                "x": [random.gauss(20.0, 1.0) for _ in range(n)],
                "y": [random.gauss(-5.0, 1.0) for _ in range(n)],
                "z": [random.gauss(-40.0, 1.5) for _ in range(n)],
            }
        elif sensor_type == "proximity":
            data = {"distance": [random.choice([0.0, 5.0]) for _ in range(n)]}
        elif sensor_type == "light":
            data = {"lux": [random.gauss(300, 20) for _ in range(n)]}
        elif sensor_type == "barometer":
            data = {"pressure": [random.gauss(1013.25, 0.5) for _ in range(n)]}
        elif sensor_type == "gravity":
            data = {
                "x": [random.gauss(0, 0.01) for _ in range(n)],
                "y": [random.gauss(0, 0.01) for _ in range(n)],
                "z": [random.gauss(9.81, 0.01) for _ in range(n)],
            }
        elif sensor_type == "rotation":
            # Identity quaternion with slight noise
            data = {
                "x": [random.gauss(0, 0.01) for _ in range(n)],
                "y": [random.gauss(0, 0.01) for _ in range(n)],
                "z": [random.gauss(0, 0.01) for _ in range(n)],
                "w": [random.gauss(1, 0.01) for _ in range(n)],
            }
        else:
            data = {"value": [0.0] * n}

        info = SENSOR_TYPES.get(sensor_type, {})
        return {
            "sensor": sensor_type,
            "unit": info.get("unit", ""),
            "n_samples": n,
            "sample_rate_hz": self.sample_rate_hz,
            "duration_s": duration_s,
            "time_s": timestamps,
            **data,
        }

    def read_microphone(
        self, duration_s: float = 2.0, sample_rate: int = 16000,
    ) -> dict[str, Any]:
        """Simulate microphone audio capture (PCM samples [-1, 1])."""
        if not self._opened:
            raise RuntimeError("Sensors not open. Call open() first.")

        import numpy as np

        n = int(sample_rate * duration_s)
        t = np.linspace(0, duration_s, n)
        # Pink noise + a 440 Hz tone
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        noise = np.random.normal(0, 0.05, n)
        samples = np.clip(tone + noise, -1, 1)

        rms = float(np.sqrt(np.mean(samples ** 2)))
        db_spl = 20 * math.log10(rms + 1e-12) + 94  # approximate dB SPL

        return {
            "sensor": "microphone",
            "sample_rate_hz": sample_rate,
            "duration_s": duration_s,
            "n_samples": n,
            "samples": samples.tolist(),
            "rms": round(rms, 6),
            "db_spl": round(db_spl, 1),
            "peak": round(float(np.max(np.abs(samples))), 6),
        }

    def read_gps(self) -> dict[str, Any]:
        """Simulate GPS location reading."""
        return {
            "sensor": "gps",
            "latitude": 47.4979 + random.gauss(0, 0.0001),
            "longitude": 19.0402 + random.gauss(0, 0.0001),
            "altitude_m": 120.0 + random.gauss(0, 2),
            "accuracy_m": random.uniform(3, 15),
            "speed_ms": random.gauss(0.1, 0.05),
            "bearing_deg": random.uniform(0, 360),
            "timestamp": time.time(),
        }

    def read_battery(self) -> dict[str, Any]:
        """Simulate battery status."""
        return {
            "sensor": "battery",
            "level_pct": random.randint(20, 95),
            "voltage_mv": random.randint(3700, 4200),
            "temperature_c": round(self.base_temp_c + random.gauss(0, 1), 1),
            "status": "charging",
            "health": "good",
        }


# ═══════════════════════════════════════════════════════════════════════
#  Real ADB-connected Android sensor instrument
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class AdbAndroidSensors:
    """Read sensors from a real Android phone over ADB USB.

    Supports two backend strategies:
        - **bridge**: JSON-over-TCP via ADB port forwarding (preferred)
        - **termux**: Direct ``adb shell`` commands with termux-sensor

    For the bridge mode, the phone must be running the sensor server
    (either the pyontrust helper APK or a Termux script).
    """

    backend: str = "termux"  # "bridge" or "termux"
    local_port: int = _DEFAULT_BRIDGE_PORT
    _bridge: AdbSensorBridge | None = None
    _opened: bool = False
    _device_info: dict[str, str] = field(default_factory=dict)

    def open(self) -> None:
        if not _adb_available():
            raise RuntimeError(
                "No Android device found via ADB. Check:\n"
                "  1. USB cable is connected\n"
                "  2. USB debugging is enabled on the phone\n"
                "  3. 'adb devices' shows your device\n"
                "  4. ADB is installed (Android SDK Platform-Tools)"
            )
        self._device_info = _adb_device_info()
        logger.info(
            "ADB Android Sensors: %s %s (SDK %s)",
            self._device_info.get("brand", "?"),
            self._device_info.get("model", "?"),
            self._device_info.get("sdk_version", "?"),
        )

        if self.backend == "bridge":
            self._bridge = AdbSensorBridge(
                local_port=self.local_port,
                remote_port=self.local_port,
            )
            self._bridge.connect()

        self._opened = True

    def close(self) -> None:
        if self._bridge:
            self._bridge.disconnect()
            self._bridge = None
        self._opened = False

    def info(self) -> dict[str, str]:
        return {
            "model": self._device_info.get("model", "Unknown"),
            "brand": self._device_info.get("brand", "Unknown"),
            "serial": self._device_info.get("serial", ""),
            "mode": "adb",
            "backend": self.backend,
        }

    def read_sensor(
        self, sensor_type: str, duration_s: float = 1.0,
    ) -> dict[str, Any]:
        """Read a sensor via ADB for the given duration."""
        if not self._opened:
            raise RuntimeError("Sensors not open. Call open() first.")

        if self.backend == "bridge" and self._bridge:
            return self._read_sensor_bridge(sensor_type, duration_s)
        else:
            return self._read_sensor_termux(sensor_type, duration_s)

    def _read_sensor_bridge(
        self, sensor_type: str, duration_s: float,
    ) -> dict[str, Any]:
        """Read sensor via the TCP bridge."""
        assert self._bridge is not None
        rate_ms = max(10, int(1000 / 50))  # ~50 Hz
        self._bridge.send_cmd({
            "cmd": "start", "sensor": sensor_type, "rate_ms": rate_ms,
        })
        time.sleep(duration_s)
        self._bridge.send_cmd({"cmd": "stop", "sensor": sensor_type})
        lines = self._bridge.read_lines(timeout_s=0.5)

        # Parse accumulated readings
        readings = [l for l in lines if l.get("sensor") == sensor_type]
        if not readings:
            return {"sensor": sensor_type, "error": "no data received", "n_samples": 0}

        info = SENSOR_TYPES.get(sensor_type, {"axes": ["value"], "unit": ""})
        result: dict[str, Any] = {
            "sensor": sensor_type,
            "unit": info["unit"],
            "n_samples": len(readings),
            "sample_rate_hz": len(readings) / duration_s if duration_s > 0 else 0,
            "duration_s": duration_s,
            "time_s": [r.get("t", 0) for r in readings],
        }
        for axis in info["axes"]:
            idx = info["axes"].index(axis)
            result[axis] = [
                r["values"][idx] if idx < len(r.get("values", [])) else 0
                for r in readings
            ]
        return result

    def _read_sensor_termux(
        self, sensor_type: str, duration_s: float,
    ) -> dict[str, Any]:
        """Read sensor via ``adb shell`` + termux-sensor or dumpsys."""
        # Try termux-sensor first (requires Termux + termux-api package)
        try:
            n_samples = max(1, int(duration_s * 50))
            cmd = (
                f"termux-sensor -s {sensor_type} -n {n_samples} -d 20"
            )
            raw = _run_adb("shell", cmd, timeout=duration_s + 10)
            data = json.loads(raw)

            # termux-sensor returns: {"values": [[x,y,z], ...]}
            values = data.get("values", data.get(sensor_type, []))
            info = SENSOR_TYPES.get(sensor_type, {"axes": ["value"], "unit": ""})

            result: dict[str, Any] = {
                "sensor": sensor_type,
                "unit": info["unit"],
                "n_samples": len(values),
                "sample_rate_hz": len(values) / duration_s if duration_s > 0 else 0,
                "duration_s": duration_s,
            }

            if values and isinstance(values[0], list):
                for i, axis in enumerate(info["axes"]):
                    result[axis] = [v[i] if i < len(v) else 0 for v in values]
            else:
                result[info["axes"][0]] = values

            return result

        except Exception as exc:
            logger.warning("termux-sensor failed: %s — trying dumpsys", exc)

        # Fallback: dumpsys sensorservice (limited, single reading)
        try:
            raw = _run_adb("shell", "dumpsys", "sensorservice", timeout=5)
            # Parse is very device-specific — return raw dump
            return {
                "sensor": sensor_type,
                "raw_dump": raw[:2000],
                "n_samples": 0,
                "error": "dumpsys fallback — install Termux + termux-api for full sensor access",
            }
        except Exception as exc2:
            return {"sensor": sensor_type, "error": str(exc2), "n_samples": 0}

    def read_microphone(
        self, duration_s: float = 2.0, sample_rate: int = 16000,
    ) -> dict[str, Any]:
        """Record audio from Android microphone via ADB.

        Uses ``adb shell`` with ``termux-microphone-record`` or the bridge.
        """
        if not self._opened:
            raise RuntimeError("Sensors not open. Call open() first.")

        if self.backend == "bridge" and self._bridge:
            resp = self._bridge.send_cmd({
                "cmd": "read_mic",
                "duration_s": duration_s,
                "sample_rate": sample_rate,
            })
            return resp or {"error": "no response"}

        # Termux approach: record → pull → decode
        try:
            tmp_path = "/data/data/com.termux/files/home/mic_capture.wav"
            _run_adb(
                "shell",
                f"termux-microphone-record -f {tmp_path} "
                f"-r {sample_rate} -l {int(duration_s * 1000)} -e pcm_16bit",
                timeout=duration_s + 10,
            )
            time.sleep(duration_s + 0.5)
            _run_adb("shell", "termux-microphone-record -q", timeout=5)

            # Pull file
            local_tmp = "_android_mic_capture.wav"
            _run_adb("pull", tmp_path, local_tmp, timeout=10)
            _run_adb("shell", "rm", tmp_path, timeout=5)

            # Decode WAV
            import numpy as np
            import wave

            with wave.open(local_tmp, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            os.remove(local_tmp)

            rms = float(np.sqrt(np.mean(samples ** 2)))
            db_spl = 20 * math.log10(rms + 1e-12) + 94

            return {
                "sensor": "microphone",
                "sample_rate_hz": sample_rate,
                "duration_s": duration_s,
                "n_samples": len(samples),
                "samples": samples.tolist(),
                "rms": round(rms, 6),
                "db_spl": round(db_spl, 1),
                "peak": round(float(np.max(np.abs(samples))), 6),
            }

        except Exception as exc:
            return {
                "sensor": "microphone",
                "error": str(exc),
                "n_samples": 0,
                "hint": "Install Termux + termux-api on the phone",
            }

    def read_gps(self) -> dict[str, Any]:
        """Read GPS location via ``adb shell dumpsys location``."""
        if not self._opened:
            raise RuntimeError("Sensors not open. Call open() first.")

        # Try termux-location first
        try:
            raw = _run_adb("shell", "termux-location", timeout=15)
            data = json.loads(raw)
            return {
                "sensor": "gps",
                "latitude": data.get("latitude", 0),
                "longitude": data.get("longitude", 0),
                "altitude_m": data.get("altitude", 0),
                "accuracy_m": data.get("accuracy", 0),
                "speed_ms": data.get("speed", 0),
                "bearing_deg": data.get("bearing", 0),
                "timestamp": time.time(),
            }
        except Exception:
            pass

        # Fallback: dumpsys location
        try:
            raw = _run_adb("shell", "dumpsys", "location", timeout=10)
            # Extract last known location from dump
            for line in raw.splitlines():
                if "Location[" in line:
                    # Parse "Location[gps ... lat,long ...]"
                    return {
                        "sensor": "gps",
                        "raw": line.strip()[:300],
                        "timestamp": time.time(),
                    }
            return {"sensor": "gps", "error": "no GPS data in dumpsys"}
        except Exception as exc:
            return {"sensor": "gps", "error": str(exc)}

    def read_battery(self) -> dict[str, Any]:
        """Read battery status via ``adb shell dumpsys battery``."""
        return _adb_get_battery()


# ═══════════════════════════════════════════════════════════════════════
#  Unified Android sensor interface (wraps simulated or real)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class AndroidSensorInstrument:
    """Unified Android phone sensor instrument.

    Dispatches to either :class:`SimulatedAndroidSensors` or
    :class:`AdbAndroidSensors` based on the ``mode`` parameter.
    """

    mode: str = "simulated"  # "simulated", "adb", "adb_bridge"
    sample_rate_hz: float = 50.0
    adb_port: int = _DEFAULT_BRIDGE_PORT
    _impl: SimulatedAndroidSensors | AdbAndroidSensors | None = None

    def open(self) -> None:
        if self.mode == "simulated":
            self._impl = SimulatedAndroidSensors(
                sample_rate_hz=self.sample_rate_hz,
            )
        elif self.mode in ("adb", "adb_bridge"):
            self._impl = AdbAndroidSensors(
                backend="bridge" if self.mode == "adb_bridge" else "termux",
                local_port=self.adb_port,
            )
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
        self._impl.open()

    def close(self) -> None:
        if self._impl:
            self._impl.close()
            self._impl = None

    def info(self) -> dict[str, str]:
        if self._impl:
            return self._impl.info()
        return {"mode": self.mode, "status": "not opened"}

    def read_accelerometer(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("accelerometer", duration_s)

    def read_gyroscope(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("gyroscope", duration_s)

    def read_magnetometer(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("magnetometer", duration_s)

    def read_proximity(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("proximity", duration_s)

    def read_light(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("light", duration_s)

    def read_barometer(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("barometer", duration_s)

    def read_gravity(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("gravity", duration_s)

    def read_rotation(self, duration_s: float = 1.0) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_sensor("rotation", duration_s)

    def read_microphone(
        self, duration_s: float = 2.0, sample_rate: int = 16000,
    ) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_microphone(duration_s, sample_rate)

    def read_gps(self) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_gps()

    def read_battery(self) -> dict[str, Any]:
        assert self._impl is not None
        return self._impl.read_battery()


# ═══════════════════════════════════════════════════════════════════════
#  Factory (instrument registry entry point)
# ═══════════════════════════════════════════════════════════════════════


def create(config: dict[str, Any]) -> AndroidSensorInstrument:
    """Entry-point factory for the Android sensor instrument.

    Config keys:
        mode : str
            "simulated" (default), "adb", or "adb_bridge"
        sample_rate_hz : float
            Desired sensor sample rate (default 50)
        adb_port : int
            Port for ADB TCP forwarding (default 5210)
    """
    return AndroidSensorInstrument(
        mode=str(config.get("mode", "simulated")),
        sample_rate_hz=float(config.get("sample_rate_hz", 50)),
        adb_port=int(config.get("adb_port", _DEFAULT_BRIDGE_PORT)),
    )
