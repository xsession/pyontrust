"""Thermal analysis domain models — stdlib-only, no third-party dependencies.

Defines value objects for temperature monitoring across PCB zones.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class ThermalVerdict(enum.Enum):
    """Temperature assessment outcome."""

    NORMAL = "NORMAL"
    WARM = "WARM"       # Above warning threshold
    HOT = "HOT"         # Above critical threshold
    RUNAWAY = "RUNAWAY"  # Rate of rise exceeds safe limit


@dataclass(frozen=True)
class ThermalZone:
    """A named region of interest (ROI) on the board for temperature monitoring.

    Coordinates are in pixel space of the thermal camera frame.
    """

    name: str
    x: int
    y: int
    width: int
    height: int
    warn_temp_c: float = 60.0   # Above this → WARM
    max_temp_c: float = 85.0    # Above this → HOT
    max_rate_c_per_s: float = 5.0  # °C/s above this → RUNAWAY
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "warn_temp_c": self.warn_temp_c,
            "max_temp_c": self.max_temp_c,
            "max_rate_c_per_s": self.max_rate_c_per_s,
            "description": self.description,
        }


@dataclass(frozen=True)
class ZoneReading:
    """Temperature reading for a single zone at one point in time."""

    zone_name: str
    mean_temp_c: float
    max_temp_c: float
    min_temp_c: float
    std_temp_c: float
    verdict: ThermalVerdict
    rate_c_per_s: float = 0.0  # Rate of temperature change

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_name": self.zone_name,
            "mean_temp_c": round(self.mean_temp_c, 2),
            "max_temp_c": round(self.max_temp_c, 2),
            "min_temp_c": round(self.min_temp_c, 2),
            "std_temp_c": round(self.std_temp_c, 3),
            "verdict": self.verdict.value,
            "rate_c_per_s": round(self.rate_c_per_s, 3),
        }


@dataclass
class ThermalSnapshot:
    """One captured thermal frame with per-zone analysis.

    Represents a single point in time.
    """

    timestamp_s: float  # Monotonic seconds since recording start
    wall_time: str  # ISO 8601
    frame_index: int
    global_min_c: float
    global_max_c: float
    global_mean_c: float
    zone_readings: list[ZoneReading] = field(default_factory=list)
    verdict: ThermalVerdict = ThermalVerdict.NORMAL
    hotspot_x: int = 0
    hotspot_y: int = 0
    frame: Optional[Any] = None  # numpy.ndarray when kept in memory

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_s": round(self.timestamp_s, 4),
            "wall_time": self.wall_time,
            "frame_index": self.frame_index,
            "global_min_c": round(self.global_min_c, 2),
            "global_max_c": round(self.global_max_c, 2),
            "global_mean_c": round(self.global_mean_c, 2),
            "verdict": self.verdict.value,
            "hotspot": {"x": self.hotspot_x, "y": self.hotspot_y},
            "zones": [z.to_dict() for z in self.zone_readings],
        }


@dataclass
class ThermalTimeline:
    """Time-series of thermal snapshots — full test run thermal record.

    Supports querying peak temperatures, rate-of-rise events, and
    thermal limit violations across the entire run.
    """

    board_id: str = ""
    snapshots: list[ThermalSnapshot] = field(default_factory=list)
    zones: list[ThermalZone] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        if len(self.snapshots) < 2:
            return 0.0
        return self.snapshots[-1].timestamp_s - self.snapshots[0].timestamp_s

    @property
    def peak_temperature_c(self) -> float:
        if not self.snapshots:
            return 0.0
        return max(s.global_max_c for s in self.snapshots)

    @property
    def worst_verdict(self) -> ThermalVerdict:
        """Return the most severe verdict across all snapshots."""
        severity = {
            ThermalVerdict.NORMAL: 0,
            ThermalVerdict.WARM: 1,
            ThermalVerdict.HOT: 2,
            ThermalVerdict.RUNAWAY: 3,
        }
        if not self.snapshots:
            return ThermalVerdict.NORMAL
        return max(self.snapshots, key=lambda s: severity.get(s.verdict, 0)).verdict

    def violations(self) -> list[dict[str, Any]]:
        """Return all snapshots where temperature exceeded limits."""
        result = []
        for snap in self.snapshots:
            if snap.verdict not in (ThermalVerdict.NORMAL,):
                result.append({
                    "timestamp_s": snap.timestamp_s,
                    "verdict": snap.verdict.value,
                    "global_max_c": snap.global_max_c,
                    "zones": [
                        z.to_dict()
                        for z in snap.zone_readings
                        if z.verdict != ThermalVerdict.NORMAL
                    ],
                })
        return result

    def zone_history(self, zone_name: str) -> list[dict[str, float]]:
        """Extract temperature time-series for a specific zone."""
        result = []
        for snap in self.snapshots:
            for zr in snap.zone_readings:
                if zr.zone_name == zone_name:
                    result.append({
                        "t_s": snap.timestamp_s,
                        "mean_c": zr.mean_temp_c,
                        "max_c": zr.max_temp_c,
                        "rate_c_per_s": zr.rate_c_per_s,
                    })
        return result

    def summary(self) -> dict[str, Any]:
        """Generate a summary of the thermal timeline."""
        return {
            "board_id": self.board_id,
            "duration_s": round(self.duration_s, 2),
            "total_frames": len(self.snapshots),
            "peak_temperature_c": round(self.peak_temperature_c, 2),
            "worst_verdict": self.worst_verdict.value,
            "violations_count": len(self.violations()),
            "zones": [z.to_dict() for z in self.zones],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "snapshots": [s.to_dict() for s in self.snapshots],
        }
