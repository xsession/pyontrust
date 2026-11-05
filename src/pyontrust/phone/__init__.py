"""Phone subsystem access layer (Bluetooth, GSM, NFC, audio, vibration, cameras, touchscreen, peripherals).

Everything runs over ADB shell against the connected device; no extra drivers.
See :mod:`pyontrust.phone.subsystems` for the per-subsystem controllers and
the :class:`~pyontrust.phone.subsystems.PhoneSubsystems` facade.
"""
from pyontrust.phone.fastlink import FastLink, FastLinkError  # noqa: F401
from pyontrust.phone.sonar import PhoneSonar, SonarPingResult, SonarError  # noqa: F401
from pyontrust.phone.subsystems import (  # noqa: F401
    AdbShell,
    AudioCtl,
    CamerasCtl,
    GsmCtl,
    NfcCtl,
    BluetoothCtl,
    PeripheralsCtl,
    PhoneSubsystems,
    TouchscreenCtl,
    VibrationCtl,
)

__all__ = [
    "AdbShell",
    "AudioCtl",
    "CamerasCtl",
    "GsmCtl",
    "NfcCtl",
    "BluetoothCtl",
    "PeripheralsCtl",
    "PhoneSubsystems",
    "TouchscreenCtl",
    "VibrationCtl",
    "FastLink",
    "FastLinkError",
    "PhoneSonar",
    "SonarPingResult",
    "SonarError",
]
