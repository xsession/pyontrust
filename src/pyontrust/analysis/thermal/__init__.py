"""Thermal analysis package — board temperature monitoring and anomaly detection.

Provides analysis functions for thermal imaging data:

- **models** — ThermalZone, ThermalSnapshot, ThermalTimeline data classes
- **analyzer** — ROI-based temperature tracking, hotspot detection, thermal limits
- **measurement** — production-grade thermal measurement modes (continuous, soak, delta, gradient)
"""

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
    ThermalZone,
)
from pyontrust.analysis.thermal.measurement import (
    ThermalMeasurementConfig,
    ThermalMeasurementResult,
    ZoneStatistics,
    GradientResult,
    run_thermal_measurement,
    generate_thermal_report,
)

__all__ = [
    "ThermalSnapshot",
    "ThermalTimeline",
    "ThermalVerdict",
    "ThermalZone",
    "ThermalMeasurementConfig",
    "ThermalMeasurementResult",
    "ZoneStatistics",
    "GradientResult",
    "run_thermal_measurement",
    "generate_thermal_report",
]
