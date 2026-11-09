"""Digilent WaveForms (libdwf) oscilloscope + signal generator.

Instrument layer for the ``/waveforms`` web tab — a Digilent Waveforms clone:
scope capture, arbitrary-function generation, and spectrum analysis over the
DWF 3.x C API (verified against dwf.h 3.23.4 and the official Python samples).

API model (this SDK version):
- ``FDwfDeviceOpen(idx, &hdwf)`` — idx -1 = first device; handle is a plain int.
- Scope: channel/rate/record setup → ``FDwfAnalogInConfigure(h, fReconfigure, fStart)``
  → poll ``FDwfAnalogInStatus`` → read volts via ``FDwfAnalogInStatusData``.
- Generator: node setters (function/freq/amplitude/offset) →
  ``FDwfAnalogOutConfigure(h, ch, fStart)``.

All functions are wrapped with explicit ctypes prototypes; failures raise
:class:`DwfError` carrying the library's last error message.
"""
from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

# ── Constants (dwf.h / dwfconstants.py) ────────────────────────────────

DWF_STATE_NAMES = {
    0: "ready",      # DwfStateReady
    1: "armed",      # DwfStateArmed
    2: "done",       # DwfStateDone
    3: "running",    # DwfStateTriggered / Running
    4: "config",     # DwfStateConfig
    5: "prefill",    # DwfStatePrefill
    7: "wait",       # DwfStateWait
}

FUNC_VALUES = {
    "dc": 0, "sine": 1, "square": 2, "triangle": 3, "ramp_up": 4,
    "ramp_down": 5, "noise": 6, "pulse": 7, "trapezium": 8,
}

TRIGSRC_VALUES = {
    "none": 0, "pc": 1, "detector_analog_in": 2, "detector_digital_in": 3,
    "analog_in": 4, "digital_in": 5, "digital_out": 6, "analog_out1": 7,
}

ACQMODE_SINGLE = 0   # acqmodeSingle
ENUMFILTER_ALL = 0   # enumfilterAll


class DwfError(RuntimeError):
    """Raised when a libdwf call fails or no device is available."""


@dataclass(frozen=True)
class DwfDeviceInfo:
    index: int
    name: str
    serial: str
    user: str
    analog_in_channels: int
    analog_out_channels: int
    is_opened: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "serial": self.serial,
            "user": self.user,
            "analog_in_channels": self.analog_in_channels,
            "analog_out_channels": self.analog_out_channels,
            "is_opened": self.is_opened,
        }


# ── Library loading ────────────────────────────────────────────────────

def _candidate_paths() -> list[Path]:
    cands: list[Path] = []
    env = os.environ.get("DWF_LIB_PATH")
    if env:
        cands.append(Path(env))
    repo_root = Path(__file__).resolve().parents[3]
    vendored_dir = repo_root / "externals" / "WaveformSDK_linux" / "usr" / "lib"
    # The vendored libdwf.so/.so.3 may be flattened symlink stubs (16-byte text);
    # prefer the real versioned ELF when present, then the plain names.
    for name in ("libdwf.so.3.23.4", "libdwf.so", "libdwf.so.3"):
        cands.append(vendored_dir / name)
    cands += [Path("/usr/lib/libdwf.so"), Path("/usr/local/lib/libdwf.so")]
    return cands


def _is_elf(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def load_dwf_library() -> ctypes.CDLL:
    """Load libdwf, skipping non-ELF stub files. Raises DwfError if none works."""
    tried: list[str] = []
    for path in _candidate_paths():
        if not path.exists() or not _is_elf(path):
            continue
        try:
            parent = str(path.parent)
            cur = os.environ.get("LD_LIBRARY_PATH", "")
            if cur and parent not in cur.split(":"):
                os.environ["LD_LIBRARY_PATH"] = f"{parent}:{cur}"
            elif not cur:
                os.environ["LD_LIBRARY_PATH"] = parent
            return ctypes.CDLL(str(path))
        except OSError as exc:  # keep trying other candidates
            tried.append(f"{path}: {exc}")
    raise DwfError(
        "Could not load libdwf (Digilent WaveForms SDK). Tried: "
        + ("; ".join(tried) if tried else "no candidate files found")
        + ". Set DWF_LIB_PATH to a valid libdwf.so."
    )


# ── ctypes prototypes ──────────────────────────────────────────────────

def _set_prototypes(dwf: ctypes.CDLL) -> None:
    c_int, c_double = ctypes.c_int, ctypes.c_double
    p_int, p_double = ctypes.POINTER(c_int), ctypes.POINTER(c_double)

    def proto(name: str, argtypes: list, restype: Any = c_int) -> None:
        fn = getattr(dwf, name, None)
        if fn is None:  # optional symbol absent in this SDK build — skip
            return
        fn.argtypes = argtypes
        fn.restype = restype

    proto("FDwfEnum", [c_int, p_int])
    proto("FDwfEnumDeviceName", [c_int, ctypes.c_char_p])
    proto("FDwfEnumSN", [c_int, ctypes.c_char_p])
    proto("FDwfEnumUserName", [c_int, ctypes.c_char_p])
    proto("FDwfEnumAnalogInChannels", [c_int, p_int])
    proto("FDwfEnumAnalogOutChannels", [c_int, p_int])
    proto("FDwfEnumDeviceIsOpened", [c_int, p_int])
    proto("FDwfDeviceOpen", [c_int, p_int])
    proto("FDwfDeviceClose", [c_int])
    proto("FDwfGetLastErrorMsg", [ctypes.c_char_p], restype=None)
    proto("FDwfDeviceAutoConfigureSet", [c_int, c_int])

    # Scope (AnalogIn)
    proto("FDwfAnalogInChannelEnableSet", [c_int, c_int, c_int])
    proto("FDwfAnalogInChannelRangeSet", [c_int, c_int, c_double])
    proto("FDwfAnalogInFrequencySet", [c_int, c_double])
    proto("FDwfAnalogInRecordLengthSet", [c_int, c_double])
    proto("FDwfAnalogInAcquisitionModeSet", [c_int, c_int])
    proto("FDwfAnalogInConfigure", [c_int, c_int, c_int])
    proto("FDwfAnalogInStatus", [c_int, c_int, ctypes.POINTER(ctypes.c_byte)])
    proto("FDwfAnalogInStatusData", [c_int, c_int, p_double, c_int])
    proto("FDwfAnalogInStatusSamplesLeft", [c_int, p_int])
    proto("FDwfAnalogInTriggerSourceSet", [c_int, c_int])
    proto("FDwfAnalogInTriggerLevelSet", [c_int, c_double])

    # Generator (AnalogOut) — node-based API used by the official samples
    proto("FDwfAnalogOutNodeEnableSet", [c_int, c_int, c_int, c_int])
    proto("FDwfAnalogOutNodeFunctionSet", [c_int, c_int, c_int, c_int])
    proto("FDwfAnalogOutNodeFrequencySet", [c_int, c_int, c_int, c_double])
    proto("FDwfAnalogOutNodeAmplitudeSet", [c_int, c_int, c_int, c_double])
    proto("FDwfAnalogOutNodeOffsetSet", [c_int, c_int, c_int, c_double])
    proto("FDwfAnalogOutConfigure", [c_int, c_int, c_int])

    # Optional (guarded at call sites)
    for name in ("FDwfAnalogInTriggerAutoTimeoutSet",):
        if hasattr(dwf, name):
            proto(name, [c_int, c_double])

    # Fail fast if a core symbol is missing from this SDK build.
    for required in (
        "FDwfEnum", "FDwfDeviceOpen", "FDwfDeviceClose",
        "FDwfAnalogInConfigure", "FDwfAnalogInStatusData",
    ):
        if not hasattr(dwf, required):
            raise DwfError(f"libdwf is missing required symbol {required}")


# ── Enumeration ────────────────────────────────────────────────────────

def enumerate_devices() -> list[DwfDeviceInfo]:
    """List all DWF devices visible to the SDK (USB + network)."""
    dwf = load_dwf_library()
    _set_prototypes(dwf)
    count = ctypes.c_int(0)
    dwf.FDwfEnum(ENUMFILTER_ALL, ctypes.byref(count))
    n = max(0, int(count.value))

    def cstr(idx: int, fn_name: str) -> str:
        buf = ctypes.create_string_buffer(64)
        fn = getattr(dwf, fn_name, None)
        if fn is not None and fn(idx, buf):
            return buf.value.decode("utf-8", errors="replace")
        return ""

    def cint(idx: int, fn_name: str) -> int:
        val = ctypes.c_int(0)
        fn = getattr(dwf, fn_name, None)
        if fn is not None:
            fn(idx, ctypes.byref(val))
        return int(val.value)

    devices: list[DwfDeviceInfo] = []
    for idx in range(n):
        opened = cint(idx, "FDwfEnumDeviceIsOpened")
        devices.append(DwfDeviceInfo(
            index=idx,
            name=cstr(idx, "FDwfEnumDeviceName"),
            serial=cstr(idx, "FDwfEnumSN"),
            user=cstr(idx, "FDwfEnumUserName"),
            analog_in_channels=cint(idx, "FDwfEnumAnalogInChannels"),
            analog_out_channels=cint(idx, "FDwfEnumAnalogOutChannels"),
            is_opened=bool(opened),
        ))
    return devices


# ── Open device: scope + generator ─────────────────────────────────────

class WaveformDevice:
    """One open DWF device with oscilloscope and signal-generator access.

    Usage::

        dev = WaveformDevice(index=-1)   # -1 → first device
        dev.open()
        dev.scope_configure(channels=(0,), rate_hz=250e3, record_s=0.04)
        dev.scope_start()
        if dev.scope_wait_done(timeout_s=5):
            volts = dev.scope_read(channel=0, count=1000)
        dev.close()
    """

    def __init__(self, index: int = -1) -> None:
        self.index = index
        self._dwf: Optional[ctypes.CDLL] = None
        self._hdwf = 0

    # -- lifecycle -------------------------------------------------------

    @property
    def handle(self) -> int:
        if not self._hdwf:
            raise DwfError("Device is not open — call .open() first")
        return self._hdwf

    def _last_error(self, context: str) -> str:
        buf = ctypes.create_string_buffer(512)
        try:
            if self._dwf is not None:
                self._dwf.FDwfGetLastErrorMsg(buf)
        except Exception:  # noqa: BLE001 - error reporting must never raise
            pass
        msg = buf.value.decode("utf-8", errors="replace").strip()
        return f"{context}: {msg}" if msg else context

    def open(self) -> None:
        dwf = load_dwf_library()
        _set_prototypes(dwf)
        self._dwf = dwf
        hdwf = ctypes.c_int(0)
        ret = dwf.FDwfDeviceOpen(ctypes.c_int(self.index), ctypes.byref(hdwf))
        if not ret or hdwf.value == 0:
            raise DwfError(self._last_error(f"FDwfDeviceOpen(index={self.index}) failed"))
        self._hdwf = int(hdwf.value)
        # Manual configure mode: setters must not auto-start the device.
        dwf.FDwfDeviceAutoConfigureSet(self._hdwf, 0)

    def close(self) -> None:
        if self._dwf is not None and self._hdwf:
            try:
                self._dwf.FDwfDeviceClose(self._hdwf)
            except Exception:  # noqa: BLE001
                pass
        self._hdwf = 0

    def __enter__(self) -> "WaveformDevice":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- oscilloscope ----------------------------------------------------

    def scope_configure(
        self,
        channels: Sequence[int] = (0,),
        rate_hz: float = 250_000.0,
        record_s: Optional[float] = 0.04,
        range_v: Optional[dict[int, float]] = None,
        trigger_source: str = "none",
        trigger_level_v: float = 0.0,
        auto_timeout_ms: Optional[float] = 250.0,
    ) -> None:
        """Arm the scope (reconfigure=1, start=0). Call scope_start() to run."""
        if self._dwf is None:
            raise DwfError("device not open")
        dwf = self._dwf
        h = self.handle
        for ch in channels:
            dwf.FDwfAnalogInChannelEnableSet(h, ch, 1)
            if range_v and ch in range_v:
                dwf.FDwfAnalogInChannelRangeSet(h, ch, float(range_v[ch]))
        dwf.FDwfAnalogInAcquisitionModeSet(h, ACQMODE_SINGLE)
        dwf.FDwfAnalogInFrequencySet(h, float(rate_hz))
        if record_s is not None:
            dwf.FDwfAnalogInRecordLengthSet(h, float(record_s))

        trig = TRIGSRC_VALUES.get(trigger_source.lower())
        if trig is None:
            raise DwfError(f"Unknown trigger source '{trigger_source}' "
                           f"(expected one of {sorted(TRIGSRC_VALUES)})")
        dwf.FDwfAnalogInTriggerSourceSet(h, trig)
        if trig != 0:
            dwf.FDwfAnalogInTriggerLevelSet(h, float(trigger_level_v))
        elif auto_timeout_ms is not None and hasattr(dwf, "FDwfAnalogInTriggerAutoTimeoutSet"):
            # Auto-trigger after this many ms so captures never hang.
            dwf.FDwfAnalogInTriggerAutoTimeoutSet(h, float(auto_timeout_ms) / 1000.0)

        ret = dwf.FDwfAnalogInConfigure(h, 1, 0)  # reconfigure=1, start=0
        if not ret:
            raise DwfError(self._last_error("FDwfAnalogInConfigure(reconfigure) failed"))

    def scope_start(self) -> None:
        dwf = self._dwf
        assert dwf is not None
        ret = dwf.FDwfAnalogInConfigure(self.handle, 0, 1)  # reconfigure=0, start=1
        if not ret:
            raise DwfError(self._last_error("FDwfAnalogInConfigure(start) failed"))

    def scope_state(self) -> str:
        dwf = self._dwf
        assert dwf is not None
        sts = ctypes.c_byte(0)
        dwf.FDwfAnalogInStatus(self.handle, 1, ctypes.byref(sts))
        return DWF_STATE_NAMES.get(int(sts.value), f"unknown({sts.value})")

    def scope_wait_done(self, timeout_s: float = 5.0, poll_s: float = 0.02) -> bool:
        """Poll until the capture finishes (state done/running→done). True on success."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self.scope_state()
            if state == "done":
                return True
            if state in ("config", "prefill", "armed", "wait"):
                time.sleep(poll_s)
                continue
            # running with a finite record will reach done; give it the full window
            time.sleep(poll_s)
        return self.scope_state() == "done"

    def scope_read(self, channel: int = 0, count: Optional[int] = None) -> list[float]:
        """Read captured samples (volts) for one channel."""
        dwf = self._dwf
        assert dwf is not None
        if count is None:
            # Prefer SamplesValid (buffer size after a single-shot capture);
            # SamplesLeft reports 0 once the buffer is fully written on some builds.
            valid = ctypes.c_int(0)
            fn_valid = getattr(dwf, "FDwfAnalogInStatusSamplesValid", None)
            if fn_valid is not None:
                fn_valid(self.handle, ctypes.byref(valid))
            else:
                dwf.FDwfAnalogInStatusSamplesLeft(self.handle, ctypes.byref(valid))
            count = max(int(valid.value), 1)
        buf = (ctypes.c_double * count)()
        ret = dwf.FDwfAnalogInStatusData(self.handle, channel, buf, count)
        if not ret:
            raise DwfError(self._last_error(f"FDwfAnalogInStatusData(ch={channel}) failed"))
        return [float(buf[i]) for i in range(count)]

    def scope_samples_left(self) -> int:
        dwf = self._dwf
        assert dwf is not None
        left = ctypes.c_int(0)
        dwf.FDwfAnalogInStatusSamplesLeft(self.handle, ctypes.byref(left))
        return max(int(left.value), 0)

    # -- signal generator --------------------------------------------------

    def gen_set(
        self,
        channel: int = 0,
        function: str = "sine",
        freq_hz: float = 1_000.0,
        amplitude_v: float = 1.41,
        offset_v: float = 0.0,
    ) -> None:
        """Configure the carrier node of one output channel (not started yet)."""
        dwf = self._dwf
        assert dwf is not None
        h = self.handle
        func = FUNC_VALUES.get(function.lower())
        if func is None:
            raise DwfError(f"Unknown function '{function}' "
                           f"(expected one of {sorted(FUNC_VALUES)})")
        carrier = 0  # AnalogOutNodeCarrier
        dwf.FDwfAnalogOutNodeEnableSet(h, channel, carrier, 1)
        dwf.FDwfAnalogOutNodeFunctionSet(h, channel, carrier, func)
        dwf.FDwfAnalogOutNodeFrequencySet(h, channel, carrier, float(freq_hz))
        dwf.FDwfAnalogOutNodeAmplitudeSet(h, channel, carrier, float(amplitude_v))
        dwf.FDwfAnalogOutNodeOffsetSet(h, channel, carrier, float(offset_v))

    def gen_start(self, channels: Sequence[int] = (0,)) -> None:
        dwf = self._dwf
        assert dwf is not None
        for ch in channels:
            ret = dwf.FDwfAnalogOutConfigure(self.handle, ch, 1)
            if not ret:
                raise DwfError(self._last_error(f"FDwfAnalogOutConfigure(ch={ch}, start) failed"))

    def gen_stop(self, channels: Sequence[int] = (0,)) -> None:
        dwf = self._dwf
        assert dwf is not None
        for ch in channels:
            dwf.FDwfAnalogOutConfigure(self.handle, ch, 0)


# ── Convenience one-shot capture ───────────────────────────────────────

def quick_capture(
    device_index: int = -1,
    channel: int = 0,
    rate_hz: float = 250_000.0,
    record_s: float = 0.04,
) -> dict[str, Any]:
    """Open → configure → capture → read → close; returns stats + samples."""
    dev = WaveformDevice(device_index)
    try:
        dev.open()
        dev.scope_configure(channels=(channel,), rate_hz=rate_hz, record_s=record_s)
        time.sleep(0.25)  # let the front-end offset settle (per official sample)
        dev.scope_start()
        done = dev.scope_wait_done(timeout_s=max(3.0, record_s * 4))
        if not done:
            return {"ok": False, "error": f"capture did not finish (state={dev.scope_state()})"}
        samples = dev.scope_read(channel=channel)
    finally:
        dev.close()
    if not samples:
        return {"ok": False, "error": "no samples returned by device"}
    return {
        "ok": True,
        "state": "done",
        "samples": len(samples),
        "min_v": min(samples),
        "max_v": max(samples),
        "mean_v": sum(samples) / len(samples),
        "rate_hz": rate_hz,
        "record_s": record_s,
    }
