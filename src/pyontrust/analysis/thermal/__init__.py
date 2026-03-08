"""Thermal analysis package — board temperature monitoring and anomaly detection.

Provides analysis functions for thermal imaging data:

- **models** — ThermalZone, ThermalSnapshot, ThermalTimeline data classes
- **analyzer** — ROI-based temperature tracking, hotspot detection, thermal limits
"""

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
    ThermalZone,
)

__all__ = [
    "ThermalSnapshot",
    "ThermalTimeline",
    "ThermalVerdict",
    "ThermalZone",
]
