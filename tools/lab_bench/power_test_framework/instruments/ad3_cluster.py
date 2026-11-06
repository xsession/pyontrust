"""Analog Discovery 3 cluster — coordinated multi-device power meter.

Coordinates two (or more) AD3 units for simultaneous acquisition across
up to 4 analog-in channels (2 per device). Uses DWF buffered acquisition
(``FDwfAnalogInStatusData``) instead of polling for reliable high-rate
sampling.

Typical wiring for power measurement on a DUT with 3.3 V rail::

    AD3-0 CH1  →  shunt resistor high side   (current sense)
    AD3-0 CH2  →  DUT Vdd rail               (voltage sense)
    AD3-1 CH1  →  second rail / GPIO toggle   (optional)
    AD3-1 CH2  →  external trigger / sync     (optional)

Usage in a test profile::

    "instruments": {
      "power_meter": {
        "type": "ad3_cluster",
        "devices": [
          {
            "device_index": 0,
            "role": "power",
            "current_channel": 0,
            "voltage_channel": 1,
            "current_a_per_v": 10.0,
            "sample_rate_hz": 100000
          },
          {
            "device_index": 1,
            "role": "aux",
            "current_channel": 0,
            "voltage_channel": 1,
            "sample_rate_hz": 100000
          }
        ],
        "buffer_size": 8192,
        "trigger_source": "none"
      }
    }
"""

from __future__ import annotations

import ctypes
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..core import PowerSample
from . import dwf_loader

logger = logging.getLogger("pyontrust.instruments.ad3_cluster")

# DWF acquisition states
_DwfStateReady = 0
_DwfStateConfig = 4
_DwfStateArmed = 1
_DwfStateDone = 2


@dataclass
class Ad3DeviceConfig:
    """Configuration for one AD3 in the cluster."""

    device_index: int = -1
    role: str = "power"  # "power" | "aux"
    current_channel: int = 0
    voltage_channel: int = 1
    current_range_v: float = 5.0
    voltage_range_v: float = 5.0
    current_a_per_v: float = 1.0
    voltage_v_per_v: float = 1.0
    current_offset_v: float = 0.0
    voltage_offset_v: float = 0.0
    sample_rate_hz: float = 100_000.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Ad3DeviceConfig:
        return Ad3DeviceConfig(**{k: v for k, v in d.items() if k != "type"})


@dataclass
class _OpenDevice:
    """Internal bookkeeping for an opened AD3."""

    config: Ad3DeviceConfig
    hdwf: Any = None  # ctypes c_int handle


@dataclass
class Ad3ClusterPowerMeter:
    """Multi-device AD3 cluster with buffered acquisition.

    Only the *first* device with ``role="power"`` contributes to the
    ``PowerSample`` stream.  Auxiliary devices are acquired in sync and
    their data is stored in ``aux_buffers`` for post-processing.
    """

    devices: list[Ad3DeviceConfig] = field(default_factory=list)
    buffer_size: int = 8192
    trigger_source: str = "none"  # "none" | "ext_rise" | "ext_fall"

    # For unit tests: inject a fake DWF object.
    dwf: Any | None = None

    _open_devs: list[_OpenDevice] = field(default_factory=list, init=False, repr=False)
    _t0: float = field(default=0.0, init=False, repr=False)
    aux_buffers: dict[int, list[tuple[float, float]]] = field(default_factory=dict, init=False, repr=False)

    # ---- Lifecycle -------------------------------------------------------

    def open(self) -> None:
        if self._open_devs:
            return
        if not self.devices:
            raise ValueError("No devices configured for AD3 cluster")

        if self.dwf is None:
            self.dwf = dwf_loader.load_dwf()

        self._set_prototypes(self.dwf)

        for cfg in self.devices:
            hdwf = ctypes.c_int()
            ok = int(self.dwf.FDwfDeviceOpen(ctypes.c_int(cfg.device_index), ctypes.byref(hdwf)))
            if ok == 0 or hdwf.value == 0:
                raise RuntimeError(f"FDwfDeviceOpen({cfg.device_index}) failed")

            dev = _OpenDevice(config=cfg, hdwf=hdwf)
            self._open_devs.append(dev)
            self._configure_device(dev)
            logger.info("AD3 cluster: opened device_index=%d (role=%s)", cfg.device_index, cfg.role)

        self._t0 = time.perf_counter()

    def close(self) -> None:
        for dev in reversed(self._open_devs):
            try:
                self.dwf.FDwfDeviceClose(dev.hdwf)
            except Exception:
                pass
        self._open_devs.clear()
        self.aux_buffers.clear()

    # ---- PowerMeter Protocol: capture ------------------------------------

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        """Buffered acquisition from all cluster devices.

        Yields ``PowerSample`` from the primary (role=power) device.
        Auxiliary channel data is accumulated in ``self.aux_buffers``.
        """
        if not self._open_devs:
            self.open()

        primary = self._primary()
        if primary is None:
            raise RuntimeError("No device with role='power' in cluster")

        # Start all devices
        for dev in self._open_devs:
            self.dwf.FDwfAnalogInConfigure(dev.hdwf, ctypes.c_int(1), ctypes.c_int(1))

        elapsed = 0.0
        while elapsed < duration_s:
            for dev in self._open_devs:
                samples_i, samples_v = self._read_buffer(dev)
                if not samples_i:
                    continue

                cfg = dev.config
                n = len(samples_i)
                dt = 1.0 / cfg.sample_rate_hz

                for k in range(n):
                    t = time.perf_counter() - self._t0
                    raw_i = samples_i[k] - cfg.current_offset_v
                    raw_v = samples_v[k] - cfg.voltage_offset_v
                    current_a = raw_i * cfg.current_a_per_v
                    voltage_v = raw_v * cfg.voltage_v_per_v

                    if dev is primary:
                        yield PowerSample(t_s=t, current_a=current_a, voltage_v=voltage_v)
                    else:
                        self.aux_buffers.setdefault(cfg.device_index, []).append(
                            (current_a, voltage_v)
                        )

            # Small sleep to avoid busy-wait; actual timing is DWF buffer driven
            time.sleep(min(0.01, duration_s - elapsed))
            elapsed = time.perf_counter() - self._t0 - (self._t0 - self._t0)
            elapsed = time.perf_counter() - self._t0  # fix: track wall clock

        # Final drain
        for dev in self._open_devs:
            remaining_i, remaining_v = self._read_buffer(dev)
            if dev is primary and remaining_i:
                cfg = dev.config
                for k in range(len(remaining_i)):
                    t = time.perf_counter() - self._t0
                    current_a = (remaining_i[k] - cfg.current_offset_v) * cfg.current_a_per_v
                    voltage_v = (remaining_v[k] - cfg.voltage_offset_v) * cfg.voltage_v_per_v
                    yield PowerSample(t_s=t, current_a=current_a, voltage_v=voltage_v)

    # ---- Internal --------------------------------------------------------

    def _primary(self) -> _OpenDevice | None:
        for dev in self._open_devs:
            if dev.config.role == "power":
                return dev
        return None

    def _configure_device(self, dev: _OpenDevice) -> None:
        """Configure AnalogIn channels and acquisition mode."""
        cfg = dev.config
        h = dev.hdwf
        dwf = self.dwf

        # Enable channels
        dwf.FDwfAnalogInChannelEnableSet(h, ctypes.c_int(cfg.current_channel), ctypes.c_int(1))
        dwf.FDwfAnalogInChannelEnableSet(h, ctypes.c_int(cfg.voltage_channel), ctypes.c_int(1))

        # Range
        dwf.FDwfAnalogInChannelRangeSet(h, ctypes.c_int(cfg.current_channel), ctypes.c_double(cfg.current_range_v))
        dwf.FDwfAnalogInChannelRangeSet(h, ctypes.c_int(cfg.voltage_channel), ctypes.c_double(cfg.voltage_range_v))

        # Sample rate and buffer
        dwf.FDwfAnalogInFrequencySet(h, ctypes.c_double(cfg.sample_rate_hz))
        dwf.FDwfAnalogInBufferSizeSet(h, ctypes.c_int(self.buffer_size))

        # Acquisition mode: record (continuous streaming)
        # acqmodeRecord = 1
        dwf.FDwfAnalogInAcquisitionModeSet(h, ctypes.c_int(1))

        # Trigger
        if self.trigger_source == "none":
            # auto-trigger (immediate)
            dwf.FDwfAnalogInTriggerSourceSet(h, ctypes.c_int(0))  # trigsrcNone
        elif self.trigger_source in ("ext_rise", "ext_fall"):
            dwf.FDwfAnalogInTriggerSourceSet(h, ctypes.c_int(11))  # trigsrcExternal1
            edge = 0 if self.trigger_source == "ext_rise" else 1
            try:
                dwf.FDwfAnalogInTriggerTypeSet(h, ctypes.c_int(edge))
            except Exception:
                pass  # not all FW versions support this

    def _read_buffer(self, dev: _OpenDevice) -> tuple[list[float], list[float]]:
        """Non-blocking read of available buffered samples."""
        sts = ctypes.c_int()
        self.dwf.FDwfAnalogInStatus(dev.hdwf, ctypes.c_int(1), ctypes.byref(sts))

        avail = ctypes.c_int()
        lost = ctypes.c_int()
        corrupt = ctypes.c_int()
        self.dwf.FDwfAnalogInStatusRecord(
            dev.hdwf, ctypes.byref(avail), ctypes.byref(lost), ctypes.byref(corrupt)
        )

        n = avail.value
        if n <= 0:
            return [], []

        buf_i = (ctypes.c_double * n)()
        buf_v = (ctypes.c_double * n)()
        self.dwf.FDwfAnalogInStatusData(
            dev.hdwf, ctypes.c_int(dev.config.current_channel), buf_i, ctypes.c_int(n)
        )
        self.dwf.FDwfAnalogInStatusData(
            dev.hdwf, ctypes.c_int(dev.config.voltage_channel), buf_v, ctypes.c_int(n)
        )

        if lost.value > 0:
            logger.warning("AD3 dev%d: %d samples lost", dev.config.device_index, lost.value)
        if corrupt.value > 0:
            logger.warning("AD3 dev%d: %d samples corrupt", dev.config.device_index, corrupt.value)

        return list(buf_i), list(buf_v)

    @staticmethod
    def _set_prototypes(dwf: Any) -> None:
        """Best-effort ctypes prototypes."""
        try:
            dwf.FDwfDeviceOpen.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            dwf.FDwfDeviceOpen.restype = ctypes.c_int
            dwf.FDwfDeviceClose.argtypes = [ctypes.c_int]
            dwf.FDwfDeviceClose.restype = ctypes.c_int

            dwf.FDwfAnalogInChannelEnableSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInChannelRangeSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInFrequencySet.argtypes = [ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInBufferSizeSet.argtypes = [ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInAcquisitionModeSet.argtypes = [ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInTriggerSourceSet.argtypes = [ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInConfigure.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInStatus.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            dwf.FDwfAnalogInStatusRecord.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ]
            dwf.FDwfAnalogInStatusData.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_double),
                ctypes.c_int,
            ]
        except Exception:
            return
