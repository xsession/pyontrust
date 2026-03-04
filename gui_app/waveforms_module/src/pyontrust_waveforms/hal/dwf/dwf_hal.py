from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from ctypes import byref, c_double, c_int, c_ubyte

from ...errors import DeviceNotFound, UnsupportedCapability
from ...models import AwgConfig, Capabilities, ChannelConfig, DeviceInfo, ScopeConfig, TriggerConfig
from ..registry import register_hal
from .bindings_dwf import (
    DwfSafe,
    HDWF,
    DwfStateArmed,
    DwfStateDone,
    DwfStateReady,
    DwfStateTriggered,
    DwfTriggerSlopeFall,
    DwfTriggerSlopeRise,
    acqmodeRecord,
    acqmodeSingle,
    trigsrcDetectorAnalogIn,
)


class DwfHal:
    """WaveForms SDK (DWF) HAL.

    Notes:
    - This is intentionally a minimal v0.1 subset.
    - Device IDs are `dwf:{enum_index}`.
    """

    def __init__(self, config: dict[str, Any]):
        self._cfg = config
        self._dwf = DwfSafe()
        self._hdwf: Optional[HDWF] = None
        self._scope = ScopeConfig(sample_rate_hz=1_000_000.0, record_length=4096, mode="realtime")
        self._enabled_channels: set[int] = {0}
        self._last_lost = 0
        self._last_corrupt = 0

    def discover(self) -> list[DeviceInfo]:
        devices = self._dwf.enum_devices()
        out: list[DeviceInfo] = []
        for idx, name in devices:
            out.append(DeviceInfo(device_id=f"dwf:{idx}", display_name=name, transport="usb", vendor="digilent", product=name))
        return out

    def open(self, device_id: str) -> None:
        if not device_id.startswith("dwf:"):
            raise DeviceNotFound(f"Invalid DWF device id: {device_id}")
        idx = int(device_id.split(":", 1)[1])
        hdwf = HDWF()
        self._dwf._ok(self._dwf.f.DwfDeviceOpen(idx, byref(hdwf)), "DwfDeviceOpen")
        self._hdwf = hdwf

    def close(self) -> None:
        if self._hdwf is not None:
            try:
                self._dwf._ok(self._dwf.f.DwfDeviceClose(self._hdwf), "DwfDeviceClose")
            finally:
                self._hdwf = None

    def capabilities(self) -> Capabilities:
        # TODO: query real capabilities (device info API)
        return Capabilities(
            analog_in_channels=2,
            analog_out_channels=2,
            max_sample_rate_hz=100_000_000.0,
            has_hw_trigger=True,
            has_awg=True,
        )

    def configure_scope(self, cfg: ScopeConfig) -> None:
        self._scope = cfg
        if self._hdwf is None:
            return
        mode = acqmodeRecord if cfg.mode == "realtime" else acqmodeSingle
        self._dwf._ok(self._dwf.f.DwfAnalogInAcquisitionModeSet(self._hdwf, int(mode)), "DwfAnalogInAcquisitionModeSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInFrequencySet(self._hdwf, float(cfg.sample_rate_hz)), "DwfAnalogInFrequencySet")
        self._dwf._ok(self._dwf.f.DwfAnalogInBufferSizeSet(self._hdwf, int(cfg.record_length)), "DwfAnalogInBufferSizeSet")
        if cfg.mode == "realtime":
            # record length 0 => continuous (per DWF docs behavior)
            self._dwf._ok(self._dwf.f.DwfAnalogInRecordLengthSet(self._hdwf, 0.0), "DwfAnalogInRecordLengthSet")
        else:
            self._dwf._ok(
                self._dwf.f.DwfAnalogInRecordLengthSet(self._hdwf, float(cfg.record_length) / float(cfg.sample_rate_hz)),
                "DwfAnalogInRecordLengthSet",
            )

    def configure_trigger(self, cfg: TriggerConfig) -> None:
        if self._hdwf is None:
            return

        # Edge trigger on analog-in detector
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerSourceSet(self._hdwf, int(trigsrcDetectorAnalogIn)), "DwfAnalogInTriggerSourceSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerTypeSet(self._hdwf, 0), "DwfAnalogInTriggerTypeSet")  # trigtypeEdge

        trig_ch = 0
        if cfg.source.startswith("ch") and cfg.source[2:].isdigit():
            trig_ch = int(cfg.source[2:])
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerChannelSet(self._hdwf, int(trig_ch)), "DwfAnalogInTriggerChannelSet")

        # Pretrigger: negative position means keep pretrigger data before trigger.
        pre = float(cfg.pretrigger)
        pre = 0.0 if pre < 0.0 else (1.0 if pre > 0.95 else pre)
        sec = float(self._scope.record_length) / float(self._scope.sample_rate_hz)
        pos = -pre * sec
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerPositionSet(self._hdwf, float(pos)), "DwfAnalogInTriggerPositionSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerHoldOffSet(self._hdwf, float(cfg.holdoff)), "DwfAnalogInTriggerHoldOffSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerAutoTimeoutSet(self._hdwf, 0.0), "DwfAnalogInTriggerAutoTimeoutSet")

        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerLevelSet(self._hdwf, float(cfg.level)), "DwfAnalogInTriggerLevelSet")

        cond = DwfTriggerSlopeRise if cfg.edge == "rising" else DwfTriggerSlopeFall
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerConditionSet(self._hdwf, cond), "DwfAnalogInTriggerConditionSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInTriggerHysteresisSet(self._hdwf, float(cfg.hysteresis)), "DwfAnalogInTriggerHysteresisSet")

    def configure_channel(self, cfg: ChannelConfig) -> None:
        if cfg.enabled:
            self._enabled_channels.add(cfg.ch)
        else:
            self._enabled_channels.discard(cfg.ch)

        if self._hdwf is None:
            return
        self._dwf._ok(self._dwf.f.DwfAnalogInChannelEnableSet(self._hdwf, int(cfg.ch), 1 if cfg.enabled else 0), "DwfAnalogInChannelEnableSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInChannelRangeSet(self._hdwf, int(cfg.ch), float(cfg.range_v)), "DwfAnalogInChannelRangeSet")
        self._dwf._ok(self._dwf.f.DwfAnalogInChannelOffsetSet(self._hdwf, int(cfg.ch), float(cfg.offset_v)), "DwfAnalogInChannelOffsetSet")

    def configure_awg(self, cfg: AwgConfig) -> None:
        if self._hdwf is None:
            return
        if cfg.waveform not in {"sine", "square", "triangle", "ramp", "dc"}:
            raise UnsupportedCapability(f"Unsupported waveform: {cfg.waveform}")

        # funcRampUp = 4 (dwf.h)
        func_map = {"dc": 0, "sine": 1, "square": 2, "triangle": 3, "ramp": 4}
        func = func_map[cfg.waveform]
        self._dwf._ok(self._dwf.f.DwfAnalogOutEnableSet(self._hdwf, int(cfg.ch), 1), "DwfAnalogOutEnableSet")
        self._dwf._ok(self._dwf.f.DwfAnalogOutFunctionSet(self._hdwf, int(cfg.ch), int(func)), "DwfAnalogOutFunctionSet")
        self._dwf._ok(self._dwf.f.DwfAnalogOutFrequencySet(self._hdwf, int(cfg.ch), float(cfg.freq_hz)), "DwfAnalogOutFrequencySet")
        # DWF expects amplitude as peak (V). Our API takes Vpp.
        self._dwf._ok(self._dwf.f.DwfAnalogOutAmplitudeSet(self._hdwf, int(cfg.ch), float(cfg.amp_vpp) / 2.0), "DwfAnalogOutAmplitudeSet")
        self._dwf._ok(self._dwf.f.DwfAnalogOutOffsetSet(self._hdwf, int(cfg.ch), float(cfg.offset_v)), "DwfAnalogOutOffsetSet")
        self._dwf._ok(self._dwf.f.DwfAnalogOutConfigure(self._hdwf, int(cfg.ch), 1), "DwfAnalogOutConfigure")

    def start_streaming(self) -> None:
        if self._hdwf is None:
            return
        # First bool: reconfigure, second: start
        self._dwf._ok(self._dwf.f.DwfAnalogInConfigure(self._hdwf, 1, 1), "DwfAnalogInConfigure")

    def stop_streaming(self) -> None:
        if self._hdwf is None:
            return
        self._dwf._ok(self._dwf.f.DwfAnalogInConfigure(self._hdwf, 0, 0), "DwfAnalogInConfigure(stop)")

    def read_samples(self, max_n: int, timeout_s: float) -> dict[int, np.ndarray]:
        if self._hdwf is None:
            raise DeviceNotFound("DWF device not open")

        deadline = time.monotonic() + max(0.01, float(timeout_s))
        st = c_ubyte()
        n = int(max_n)

        while time.monotonic() < deadline:
            self._dwf._ok(self._dwf.f.DwfAnalogInStatus(self._hdwf, 1, byref(st)), "DwfAnalogInStatus")
            state = int(st.value)
            if self._scope.mode == "single":
                if state in (DwfStateDone, DwfStateTriggered):
                    break
            else:
                # record mode: ready/armed/triggered are acceptable; wait until we have some samples
                valid = c_int()
                self._dwf._ok(self._dwf.f.DwfAnalogInStatusSamplesValid(self._hdwf, byref(valid)), "DwfAnalogInStatusSamplesValid")
                if int(valid.value) >= n:
                    break
            time.sleep(0.001)

        # Detect loss/corruption (best-effort)
        avail = c_int()
        lost = c_int()
        corrupt = c_int()
        try:
            self._dwf._ok(self._dwf.f.DwfAnalogInStatusRecord(self._hdwf, byref(avail), byref(lost), byref(corrupt)), "DwfAnalogInStatusRecord")
            self._last_lost = int(lost.value)
            self._last_corrupt = int(corrupt.value)
        except Exception:
            pass

        # Read last n samples ending at current write index.
        idxw = c_int()
        self._dwf._ok(self._dwf.f.DwfAnalogInStatusIndexWrite(self._hdwf, byref(idxw)), "DwfAnalogInStatusIndexWrite")
        write = int(idxw.value)
        start = write - n
        if start < 0:
            start = 0

        out: dict[int, np.ndarray] = {}
        for ch in sorted(self._enabled_channels):
            buf = (c_double * n)()
            self._dwf._ok(self._dwf.f.DwfAnalogInStatusData2(self._hdwf, int(ch), buf, int(start), n), "DwfAnalogInStatusData2")
            out[ch] = np.frombuffer(buf, dtype=np.float64).astype(np.float32, copy=False)
        return out


register_hal("dwf", lambda cfg: DwfHal(cfg))
