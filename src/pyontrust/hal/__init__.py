"""Hardware Abstraction Layer — Protocol definitions.

All hardware interfaces are defined as ``typing.Protocol`` classes.
Implementations register via entry points. This layer has ZERO
third-party dependencies (stdlib only).
"""

from pyontrust.hal.power_meter import PowerMeter, StreamingPowerMeter
from pyontrust.hal.recorder import Recorder, RecorderOutput
from pyontrust.hal.sdr import SdrHal, RxConfig, DeviceInfo
from pyontrust.hal.debug_probe import DebugProbe, FlashableProbe
from pyontrust.hal.psu import PowerSupply
from pyontrust.hal.can_bus import CanBusInterface, CanFrame
from pyontrust.hal.camera import Camera, StreamingCamera
from pyontrust.hal.industrial_camera import IndustrialCamera, CameraInfo
from pyontrust.hal.thermal_camera import ThermalCamera, ThermalCameraInfo
from pyontrust.hal.signal_gen import SignalGenerator

__all__ = [
    "PowerMeter",
    "StreamingPowerMeter",
    "Recorder",
    "RecorderOutput",
    "SdrHal",
    "RxConfig",
    "DeviceInfo",
    "DebugProbe",
    "FlashableProbe",
    "PowerSupply",
    "CanBusInterface",
    "CanFrame",
    "Camera",
    "StreamingCamera",
    "IndustrialCamera",
    "CameraInfo",
    "ThermalCamera",
    "ThermalCameraInfo",
    "SignalGenerator",
]
