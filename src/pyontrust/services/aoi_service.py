"""AOI service — orchestrates inspection for the gateway and CLI.

Framework-agnostic façade (no Flask imports) that wraps the AOI inspector
for use from the gateway dashboard, CLI scripts, or test profiles.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any

from pyontrust.analysis.aoi.models import AOIVerdict, InspectionResult

logger = logging.getLogger("pyontrust.services.aoi_service")


class AOIService:
    """Service layer for AOI inspection.

    Manages the inspector lifecycle and exposes query methods
    for the gateway's ``/aoi/`` Blueprint.

    Usage::

        svc = AOIService("aoi_config.json")
        svc.open()
        result = svc.inspect("SN-001")
        history = svc.get_history()
        svc.close()
    """

    def __init__(
        self,
        config_path: str | pathlib.Path | None = None,
        config_dict: dict[str, Any] | None = None,
    ) -> None:
        self._config_path = config_path
        self._config_dict = config_dict
        self._inspector: Any = None  # AOIInspector (lazy)
        self._ready = False

    def open(self) -> None:
        """Initialise the AOI inspector."""
        from pyontrust.analysis.aoi.inspector import AOIInspector

        if self._config_path:
            self._inspector = AOIInspector.from_config(self._config_path)
        elif self._config_dict:
            # Build inline from dict — write to temp file
            import json
            import tempfile

            tmp = pathlib.Path(tempfile.mktemp(suffix=".json"))
            tmp.write_text(json.dumps(self._config_dict), encoding="utf-8")
            self._inspector = AOIInspector.from_config(tmp)
            tmp.unlink(missing_ok=True)
        else:
            # Default: simulated camera, no reference
            from pyontrust.analysis.aoi.processing import ImagePreprocessor
            from pyontrust.instruments.aoi_camera import SimulatedAOICamera

            self._inspector = AOIInspector(
                grabber=SimulatedAOICamera(),
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,
                detector=None,
            )

        self._inspector.open()
        self._ready = True
        logger.info("AOI service ready.")

    def close(self) -> None:
        if self._inspector:
            self._inspector.close()
            self._inspector = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def inspect(self, board_id: str) -> InspectionResult:
        """Run a full inspection and return the result."""
        if not self._ready:
            raise RuntimeError("AOI service not initialised. Call open() first.")
        return self._inspector.inspect_board(board_id)

    def inspect_frame(self, frame: Any, board_id: str = "manual") -> InspectionResult:
        """Run inspection on a pre-captured frame."""
        if not self._ready:
            raise RuntimeError("AOI service not initialised. Call open() first.")
        return self._inspector.inspect_frame(frame, board_id)

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Query recent inspection results."""
        if not self._inspector:
            return []
        return self._inspector.get_inspection_history(limit)

    def get_board_defects(self, board_id: str) -> list[dict[str, Any]]:
        """Query defects for a specific board."""
        if not self._inspector:
            return []
        return self._inspector.get_defects_for_board(board_id)

    def get_stats(self) -> dict[str, Any]:
        """Aggregate pass/fail statistics."""
        history = self.get_history(limit=1000)
        total = len(history)
        passed = sum(1 for r in history if r.get("verdict") == AOIVerdict.PASS.value)
        failed = sum(1 for r in history if r.get("verdict") == AOIVerdict.FAIL.value)
        warned = sum(1 for r in history if r.get("verdict") == AOIVerdict.WARN.value)

        return {
            "total_inspections": total,
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "pass_rate": (passed / total * 100) if total else 0.0,
        }
