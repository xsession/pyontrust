"""Instrument drivers for the power test framework.

Core instruments are imported eagerly. Hardware-specific drivers that depend
on optional libraries (pyserial, ppk2-api, ctypes/DWF) are available for
import but not eagerly loaded here to keep the base package dependency-free.

Available drivers:
    - SimulatedPowerMeter — for CI / development
    - CsvFilePowerMeter, CsvProcessPowerMeter — replay from CSV
    - Ad3DwfPowerMeter — single Analog Discovery 3 (polling)
    - Ad3ClusterPowerMeter — multi-AD3 cluster (buffered)
    - Ppk2PowerMeter — Nordic PPK2
    - Sk120PowerSupply — SK120 / Korad programmable PSU
    - JLinkController — SEGGER J-Link flash / reset / RTT
    - HackRfInstrument — HackRF One spectrum / IQ
    - WebcamInstrument — webcam capture + vision analysis
"""

from .base import PowerMeter
from .simulated import SimulatedPowerMeter
from .csv_power_meter import CsvFilePowerMeter, CsvProcessPowerMeter
from .ad3_dwf import Ad3DwfPowerMeter