"""AOI domain models — stdlib-only, no third-party dependencies.

Defines all value objects used across the AOI pipeline so that other
layers can reference them without pulling in OpenCV or scikit-image.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Defect taxonomy ──────────────────────────────────────────────────

class DefectType(enum.Enum):
    """Category of PCB defect detected by AOI."""

    MISSING_COMPONENT = "missing_component"
    SOLDER_BRIDGE = "solder_bridge"
    TOMBSTONE = "tombstone"
    MISALIGNMENT = "misalignment"
    WRONG_POLARITY = "wrong_polarity"
    EXCESS_SOLDER = "excess_solder"
    INSUFFICIENT_SOLDER = "insufficient_solder"
    CONTAMINATION = "contamination"
    CRACKED_COMPONENT = "cracked_component"
    VIA_VOID = "via_void"
    VIA_OVERFILL = "via_overfill"
    COLD_JOINT = "cold_joint"
    UNKNOWN = "unknown"


class AOIVerdict(enum.Enum):
    """Inspection outcome — mirrors ``pyontrust.core.limits.Verdict``."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    REVIEW = "REVIEW"


# ── Defect record ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Defect:
    """Single detected defect with bounding box and confidence."""

    defect_type: DefectType
    x: int
    y: int
    width: int
    height: int
    confidence: float  # 0.0 – 1.0
    description: str = ""
    severity: AOIVerdict = AOIVerdict.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_type": self.defect_type.value,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "description": self.description,
            "severity": self.severity.value,
        }


# ── Solder joint result ─────────────────────────────────────────────

@dataclass(frozen=True)
class SolderJointResult:
    """Analysis result for a single solder joint."""

    x: int
    y: int
    area_px: float
    circularity: float
    mean_intensity: float
    std_intensity: float
    wetting_angle_deg: float
    grade: str  # "GOOD", "COLD", "EXCESS", "INSUFFICIENT", "BRIDGE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "area_px": self.area_px,
            "circularity": self.circularity,
            "mean_intensity": self.mean_intensity,
            "std_intensity": self.std_intensity,
            "wetting_angle_deg": self.wetting_angle_deg,
            "grade": self.grade,
        }


# ── Component alignment result ──────────────────────────────────────

@dataclass(frozen=True)
class AlignmentResult:
    """Sub-pixel alignment measurement for a component."""

    component_id: str
    dx_mm: float
    dy_mm: float
    rotation_deg: float
    within_tolerance: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "dx_mm": self.dx_mm,
            "dy_mm": self.dy_mm,
            "rotation_deg": self.rotation_deg,
            "within_tolerance": self.within_tolerance,
        }


# ── Via fill result ──────────────────────────────────────────────────

@dataclass(frozen=True)
class ViaFillResult:
    """Via fill quality measurement."""

    via_id: int
    x: int
    y: int
    diameter_px: float
    fill_ratio: float  # 0.0 = empty, 1.0 = perfectly filled
    void_count: int
    grade: str  # "FULL", "PARTIAL", "VOID", "OVERFILL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "via_id": self.via_id,
            "x": self.x,
            "y": self.y,
            "diameter_px": self.diameter_px,
            "fill_ratio": self.fill_ratio,
            "void_count": self.void_count,
            "grade": self.grade,
        }


# ── Inspection result ────────────────────────────────────────────────

@dataclass
class InspectionResult:
    """Complete result from inspecting a single PCB board.

    This is the top-level object returned by ``AOIInspector.inspect_board()``.
    It aggregates defects from all pipeline stages and carries the final verdict.
    """

    board_id: str
    verdict: AOIVerdict
    defects: list[Defect] = field(default_factory=list)
    solder_results: list[SolderJointResult] = field(default_factory=list)
    alignment_results: list[AlignmentResult] = field(default_factory=list)
    via_results: list[ViaFillResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    annotated_image: Optional[Any] = None  # numpy.ndarray when available

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_id": self.board_id,
            "verdict": self.verdict.value,
            "defect_count": len(self.defects),
            "defects": [d.to_dict() for d in self.defects],
            "solder_joints": [s.to_dict() for s in self.solder_results],
            "alignment": [a.to_dict() for a in self.alignment_results],
            "via_fill": [v.to_dict() for v in self.via_results],
            "metrics": self.metrics,
        }

    @property
    def passed(self) -> bool:
        return self.verdict == AOIVerdict.PASS

    @property
    def total_defect_count(self) -> int:
        solder_defects = sum(1 for s in self.solder_results if s.grade != "GOOD")
        via_defects = sum(1 for v in self.via_results if v.grade not in ("FULL",))
        alignment_defects = sum(1 for a in self.alignment_results if not a.within_tolerance)
        return len(self.defects) + solder_defects + via_defects + alignment_defects
