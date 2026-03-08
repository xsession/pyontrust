"""AOI (Automated Optical Inspection) analysis package.

Provides the full machine-vision pipeline for PCB inspection:

- **models** — data classes for defects, verdicts, inspection results
- **processing** — OpenCV pre-processing, alignment, defect detection
- **analysis** — scikit-image solder joint, component alignment, via fill
- **inspector** — end-to-end orchestrator with database storage

All heavy dependencies (OpenCV, scikit-image, scipy) are lazy-imported so
the package can be imported in stdlib-only environments without error.
"""

from pyontrust.analysis.aoi.models import (
    AOIVerdict,
    Defect,
    DefectType,
    InspectionResult,
)

__all__ = [
    "AOIVerdict",
    "Defect",
    "DefectType",
    "InspectionResult",
]
