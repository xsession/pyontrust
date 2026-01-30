from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    device_id: str
    display_name: str
    transport: Literal["usb", "network", "unknown"] = "unknown"
    vendor: str = "digilent"
    product: str = "unknown"


@dataclass(frozen=True, slots=True)
class Capabilities:
    analog_in_channels: int
    analog_out_channels: int
    max_sample_rate_hz: float
    has_hw_trigger: bool
    has_awg: bool


@dataclass(frozen=True, slots=True)
class ScopeConfig:
    sample_rate_hz: float
    record_length: int
    mode: Literal["realtime", "single"] = "realtime"


@dataclass(frozen=True, slots=True)
class TriggerConfig:
    source: str
    level: float
    edge: Literal["rising", "falling"]
    pretrigger: float
    holdoff: float
    hysteresis: float


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    ch: int
    enabled: bool
    coupling: Literal["dc", "ac"] = "dc"
    range_v: float = 5.0
    offset_v: float = 0.0
    bandwidth_hz: Optional[float] = None


@dataclass(frozen=True, slots=True)
class AwgConfig:
    ch: int
    waveform: Literal["sine", "square", "triangle", "ramp", "dc"]
    freq_hz: float
    amp_vpp: float
    offset_v: float
    duty: float = 0.5
    symmetry: float = 0.5
