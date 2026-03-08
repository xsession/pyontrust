"""Analog Discovery 3 power meter via Digilent WaveForms (DWF).

Loads dwf.dll (Windows) or libdwf.so (Linux) via dwf_loader and
polls FDwfAnalogInStatusSample at sample_rate_hz.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from pyontrust.core.models import PowerSample
from pyontrust.instruments import dwf_loader


@dataclass
class Ad3DwfPowerMeter:
    """Poll AnalogIn channels and convert to current/voltage."""

    sample_rate_hz: float = 1000.0
    device_index: int = -1
    current_channel: int = 0
    voltage_channel: int = 1
    current_range_v: float = 5.0
    voltage_range_v: float = 5.0
    current_a_per_v: float = 1.0
    voltage_v_per_v: float = 1.0
    current_offset_v: float = 0.0
    voltage_offset_v: float = 0.0

    dwf: Any | None = None

    _hdwf: Any | None = field(default=None, init=False, repr=False)
    _t0: float | None = field(default=None, init=False, repr=False)

    def open(self) -> None:
        if self._hdwf is not None:
            return

        if self.dwf is None:
            self.dwf = dwf_loader.load_dwf()

        import ctypes

        self._set_ctypes_prototypes(self.dwf)

        hdwf = ctypes.c_int()
        ok = int(self.dwf.FDwfDeviceOpen(ctypes.c_int(int(self.device_index)), ctypes.byref(hdwf)))
        if ok == 0 or hdwf.value == 0:
            raise RuntimeError(self._dwf_last_error_msg(self.dwf) or "FDwfDeviceOpen failed")

        self._hdwf = hdwf

        self.dwf.FDwfAnalogInChannelEnableSet(hdwf, ctypes.c_int(int(self.current_channel)), ctypes.c_int(1))
        self.dwf.FDwfAnalogInChannelEnableSet(hdwf, ctypes.c_int(int(self.voltage_channel)), ctypes.c_int(1))
        self.dwf.FDwfAnalogInChannelRangeSet(
            hdwf, ctypes.c_int(int(self.current_channel)), ctypes.c_double(self.current_range_v)
        )
        self.dwf.FDwfAnalogInChannelRangeSet(
            hdwf, ctypes.c_int(int(self.voltage_channel)), ctypes.c_double(self.voltage_range_v)
        )
        self.dwf.FDwfAnalogInFrequencySet(hdwf, ctypes.c_double(float(self.sample_rate_hz)))
        self.dwf.FDwfAnalogInConfigure(hdwf, ctypes.c_int(1), ctypes.c_int(1))

        self._t0 = time.perf_counter()

    def close(self) -> None:
        if self._hdwf is None:
            return
        try:
            import ctypes

            self.dwf.FDwfDeviceClose(self._hdwf)
        finally:
            self._hdwf = None
            self._t0 = None

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        if self._hdwf is None or self._t0 is None:
            self.open()
        assert self._hdwf is not None
        assert self._t0 is not None

        import ctypes

        dt = 1.0 / float(self.sample_rate_hz)
        start = time.perf_counter()
        t = start

        v_i = ctypes.c_double()
        v_v = ctypes.c_double()

        while (t - start) < duration_s:
            self.dwf.FDwfAnalogInStatus(self._hdwf, ctypes.c_int(1), ctypes.c_int(0))
            self.dwf.FDwfAnalogInStatusSample(self._hdwf, ctypes.c_int(int(self.current_channel)), ctypes.byref(v_i))
            self.dwf.FDwfAnalogInStatusSample(self._hdwf, ctypes.c_int(int(self.voltage_channel)), ctypes.byref(v_v))

            now = time.perf_counter()
            current_a = (float(v_i.value) - float(self.current_offset_v)) * float(self.current_a_per_v)
            voltage_v = (float(v_v.value) - float(self.voltage_offset_v)) * float(self.voltage_v_per_v)
            yield PowerSample(t_s=(now - self._t0), current_a=current_a, voltage_v=voltage_v)

            time.sleep(max(0.0, dt))
            t = time.perf_counter()

    @staticmethod
    def _dwf_last_error_msg(dwf: Any) -> str:
        import ctypes

        buf = ctypes.create_string_buffer(512)
        try:
            dwf.FDwfGetLastErrorMsg(buf)
        except Exception:
            return ""
        try:
            return buf.value.decode("utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _set_ctypes_prototypes(dwf: Any) -> None:
        try:
            import ctypes

            dwf.FDwfGetLastErrorMsg.argtypes = [ctypes.c_char_p]
            dwf.FDwfDeviceOpen.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            dwf.FDwfDeviceOpen.restype = ctypes.c_int
            dwf.FDwfDeviceClose.argtypes = [ctypes.c_int]
            dwf.FDwfDeviceClose.restype = ctypes.c_int
            dwf.FDwfAnalogInChannelEnableSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInChannelRangeSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInFrequencySet.argtypes = [ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInConfigure.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInStatus.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInStatusSample.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
        except Exception:
            return


def create(config: dict[str, Any]) -> Ad3DwfPowerMeter:
    """Entry-point factory for AD3 DWF power meter."""
    return Ad3DwfPowerMeter(
        sample_rate_hz=float(config.get("sample_rate_hz", 1000.0)),
        device_index=int(config.get("device_index", -1)),
        current_channel=int(config.get("current_channel", 0)),
        voltage_channel=int(config.get("voltage_channel", 1)),
        current_range_v=float(config.get("current_range_v", 5.0)),
        voltage_range_v=float(config.get("voltage_range_v", 5.0)),
        current_a_per_v=float(config.get("current_a_per_v", 1.0)),
        voltage_v_per_v=float(config.get("voltage_v_per_v", 1.0)),
        current_offset_v=float(config.get("current_offset_v", 0.0)),
        voltage_offset_v=float(config.get("voltage_offset_v", 0.0)),
    )
