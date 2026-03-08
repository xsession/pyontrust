"""AOI Inspector — end-to-end orchestrator with database storage.

Ties together acquisition, processing, analysis, and storage into a
single inspection run.  Designed to be used standalone or integrated
into pyontrust test profiles via the ``"inspect"`` action.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from pyontrust.analysis.aoi.models import (
    AOIVerdict,
    Defect,
    InspectionResult,
)
from pyontrust.analysis.aoi.processing import (
    BoardAligner,
    DefectDetector,
    ImagePreprocessor,
    ResultAnnotator,
)

logger = logging.getLogger("pyontrust.analysis.aoi.inspector")


class AOIInspector:
    """Complete AOI inspection system.

    Orchestrates::

        Camera → Pre-process → Align → Detect → Analyse → Verdict → Store

    Usage::

        inspector = AOIInspector.from_config("aoi_config.json")
        inspector.open()
        result = inspector.inspect_board("SN-001")
        inspector.close()
    """

    def __init__(
        self,
        grabber: Any,
        preprocessor: ImagePreprocessor,
        aligner: BoardAligner | None,
        detector: DefectDetector | None,
        solder_analyzer: Any | None = None,
        alignment_checker: Any | None = None,
        via_inspector: Any | None = None,
        db_path: Path = Path("aoi_results.db"),
        image_archive: Path = Path("aoi_images"),
    ) -> None:
        self._grabber = grabber
        self._preprocessor = preprocessor
        self._aligner = aligner
        self._detector = detector
        self._solder = solder_analyzer
        self._alignment = alignment_checker
        self._via = via_inspector
        self._db_path = db_path
        self._archive = image_archive
        self._db: sqlite3.Connection | None = None

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: str | Path) -> AOIInspector:
        """Build a full AOI inspector from a JSON configuration file.

        Example ``aoi_config.json``::

            {
              "camera": {
                "mode": "simulated",
                "width": 640,
                "height": 480,
                "inject_defect": true
              },
              "reference_image": "golden/reference_board.png",
              "processing": {
                "denoise_strength": 5,
                "diff_threshold": 30,
                "min_defect_area": 50
              },
              "analysis": {
                "px_per_mm": 50.0,
                "alignment_tolerance_mm": 0.1,
                "via_fill_threshold": 0.75,
                "solder_min_area": 30,
                "solder_max_area": 5000
              },
              "storage": {
                "db_path": "aoi_results.db",
                "image_archive": "aoi_images"
              }
            }
        """
        from pyontrust.instruments.aoi_camera import create as create_camera

        config = json.loads(Path(config_path).read_text(encoding="utf-8"))

        cam_cfg = config.get("camera", {})
        proc_cfg = config.get("processing", {})
        analysis_cfg = config.get("analysis", {})
        store_cfg = config.get("storage", {})

        grabber = create_camera(cam_cfg)

        # Reference image (optional — needed for alignment + defect detection)
        ref_path = config.get("reference_image")
        reference: np.ndarray | None = None
        aligner: BoardAligner | None = None
        detector: DefectDetector | None = None

        if ref_path and Path(ref_path).exists():
            try:
                import cv2
                reference = cv2.imread(str(ref_path))
            except ImportError:
                logger.warning("OpenCV not available; skipping reference-based detection.")

        if reference is not None:
            aligner = BoardAligner(reference)
            detector = DefectDetector(
                reference=reference,
                diff_threshold=int(proc_cfg.get("diff_threshold", 30)),
                min_defect_area=int(proc_cfg.get("min_defect_area", 50)),
            )

        # Advanced analysers (optional)
        solder_analyzer = None
        alignment_checker = None
        via_inspector = None
        try:
            from pyontrust.analysis.aoi.advanced import (
                ComponentAlignmentChecker,
                SolderJointAnalyzer,
                ViaFillInspector,
            )
            solder_analyzer = SolderJointAnalyzer(
                min_joint_area=int(analysis_cfg.get("solder_min_area", 30)),
                max_joint_area=int(analysis_cfg.get("solder_max_area", 5000)),
            )
            alignment_checker = ComponentAlignmentChecker(
                px_per_mm=float(analysis_cfg.get("px_per_mm", 50.0)),
                tolerance_mm=float(analysis_cfg.get("alignment_tolerance_mm", 0.1)),
            )
            via_inspector = ViaFillInspector(
                fill_threshold=float(analysis_cfg.get("via_fill_threshold", 0.75)),
            )
        except ImportError:
            logger.info("scikit-image not available; advanced analysis disabled.")

        return cls(
            grabber=grabber,
            preprocessor=ImagePreprocessor(
                denoise_strength=int(proc_cfg.get("denoise_strength", 5)),
            ),
            aligner=aligner,
            detector=detector,
            solder_analyzer=solder_analyzer,
            alignment_checker=alignment_checker,
            via_inspector=via_inspector,
            db_path=Path(store_cfg.get("db_path", "aoi_results.db")),
            image_archive=Path(store_cfg.get("image_archive", "aoi_images")),
        )

    # ── Lifecycle ────────────────────────────────────────────────────

    def open(self) -> None:
        """Initialise camera and database."""
        self._grabber.open()
        self._archive.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info("AOI Inspector ready.")

    def close(self) -> None:
        """Release all resources."""
        self._grabber.close()
        if self._db:
            self._db.close()
            self._db = None
        logger.info("AOI Inspector closed.")

    # ── Main inspection ──────────────────────────────────────────────

    def inspect_board(self, board_id: str) -> InspectionResult:
        """Run full AOI inspection on one board.

        Pipeline stages:
            1. Grab frame from camera
            2. Pre-process (flat-field, denoise, CLAHE, sharpen)
            3. Align to golden reference (if available)
            4. Detect defects via OpenCV difference analysis
            5. Analyse solder joints via scikit-image (if available)
            6. Inspect via fill (if available)
            7. Aggregate verdict
            8. Annotate image + archive + store to DB
        """
        t0 = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Acquire
        raw_frame = self._grabber.grab_frame()
        t_acquire = time.perf_counter() - t0

        # 2. Pre-process
        try:
            processed = self._preprocessor.process(raw_frame)
        except ImportError:
            logger.warning("OpenCV not available; using raw frame.")
            processed = raw_frame
        t_preproc = time.perf_counter() - t0 - t_acquire

        # 3. Align
        aligned = processed
        if self._aligner is not None:
            try:
                aligned, _homography = self._aligner.align(processed)
            except RuntimeError as e:
                logger.error("Alignment failed for %s: %s", board_id, e)
                return InspectionResult(
                    board_id=board_id,
                    verdict=AOIVerdict.REVIEW,
                    metrics={"error": "alignment_failed", "timestamp": timestamp},
                )

        # 4. Defect detection
        defects: list[Defect] = []
        if self._detector is not None:
            defects = self._detector.detect(aligned)

        # 5. Solder joint analysis
        solder_results = []
        if self._solder is not None:
            try:
                solder_results = self._solder.analyze(aligned)
            except Exception as e:
                logger.warning("Solder analysis failed: %s", e)

        # 6. Via fill inspection
        via_results = []
        if self._via is not None:
            try:
                via_results = self._via.inspect(aligned)
            except Exception as e:
                logger.warning("Via fill inspection failed: %s", e)

        t_total = time.perf_counter() - t0

        # 7. Aggregate verdict
        solder_defects = [r for r in solder_results if r.grade != "GOOD"]
        via_defects = [r for r in via_results if r.grade not in ("FULL",)]
        total_defects = len(defects) + len(solder_defects) + len(via_defects)

        if total_defects == 0:
            verdict = AOIVerdict.PASS
        elif any(d.confidence > 0.8 for d in defects):
            verdict = AOIVerdict.FAIL
        elif total_defects <= 2:
            verdict = AOIVerdict.WARN
        else:
            verdict = AOIVerdict.FAIL

        result = InspectionResult(
            board_id=board_id,
            verdict=verdict,
            defects=defects,
            solder_results=solder_results,
            via_results=via_results,
            metrics={
                "total_defects": total_defects,
                "visual_defects": len(defects),
                "solder_defects": len(solder_defects),
                "via_defects": len(via_defects),
                "solder_joints_total": len(solder_results),
                "vias_total": len(via_results),
                "time_acquire_s": round(t_acquire, 4),
                "time_preprocess_s": round(t_preproc, 4),
                "time_total_s": round(t_total, 4),
                "timestamp": timestamp,
            },
        )

        # 8. Annotate + archive + store
        try:
            result.annotated_image = ResultAnnotator.annotate(aligned, result)
        except ImportError:
            pass

        self._archive_result(board_id, raw_frame, result)
        self._store_result(result)

        logger.info(
            "Board %s: %s — %d defects in %.3f s",
            board_id, verdict.value, total_defects, t_total,
        )
        return result

    def inspect_frame(self, frame: np.ndarray, board_id: str = "manual") -> InspectionResult:
        """Run inspection on a pre-captured frame (no camera needed).

        Useful for offline analysis, testing, or when the camera is
        managed externally.
        """
        # Temporarily swap grabber with a single-shot wrapper
        class _FrameWrapper:
            def __init__(self, f: np.ndarray) -> None:
                self._frame = f

            def open(self) -> None:
                pass

            def close(self) -> None:
                pass

            def grab_frame(self) -> np.ndarray:
                return self._frame.copy()

        original_grabber = self._grabber
        self._grabber = _FrameWrapper(frame)
        try:
            return self.inspect_board(board_id)
        finally:
            self._grabber = original_grabber

    # ── Database ─────────────────────────────────────────────────────

    def _init_database(self) -> None:
        self._db = sqlite3.connect(str(self._db_path))
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS aoi_inspections (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id      TEXT    NOT NULL,
                timestamp     TEXT    NOT NULL,
                verdict       TEXT    NOT NULL,
                defect_count  INTEGER,
                metrics       TEXT,
                image_path    TEXT
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS aoi_defects (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id   INTEGER REFERENCES aoi_inspections(id),
                defect_type     TEXT,
                x               INTEGER,
                y               INTEGER,
                width           INTEGER,
                height          INTEGER,
                confidence      REAL,
                description     TEXT
            )
        """)
        self._db.commit()

    def _store_result(self, result: InspectionResult) -> None:
        if not self._db:
            return

        cursor = self._db.execute(
            """INSERT INTO aoi_inspections
               (board_id, timestamp, verdict, defect_count, metrics, image_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result.board_id,
                result.metrics.get("timestamp", ""),
                result.verdict.value,
                result.total_defect_count,
                json.dumps(result.metrics, default=str),
                str(self._archive / f"{result.board_id}_annotated.png"),
            ),
        )
        inspection_id = cursor.lastrowid

        for defect in result.defects:
            self._db.execute(
                """INSERT INTO aoi_defects
                   (inspection_id, defect_type, x, y, width, height,
                    confidence, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    inspection_id,
                    defect.defect_type.value,
                    defect.x, defect.y,
                    defect.width, defect.height,
                    defect.confidence,
                    defect.description,
                ),
            )

        self._db.commit()

    def _archive_result(
        self,
        board_id: str,
        raw: np.ndarray,
        result: InspectionResult,
    ) -> None:
        """Save raw + annotated images and metrics JSON to archive."""
        try:
            import cv2
        except ImportError:
            return

        cv2.imwrite(str(self._archive / f"{board_id}_raw.png"), raw)
        if result.annotated_image is not None:
            cv2.imwrite(
                str(self._archive / f"{board_id}_annotated.png"),
                result.annotated_image,
            )

        metrics_path = self._archive / f"{board_id}_metrics.json"
        metrics_path.write_text(
            json.dumps(result.metrics, indent=2, default=str),
            encoding="utf-8",
        )

    # ── Query helpers ────────────────────────────────────────────────

    def get_inspection_history(
        self, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query recent inspection results from the database."""
        if not self._db:
            return []

        cursor = self._db.execute(
            "SELECT * FROM aoi_inspections ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_defects_for_board(self, board_id: str) -> list[dict[str, Any]]:
        """Query all defects for a given board ID."""
        if not self._db:
            return []

        cursor = self._db.execute(
            """SELECT d.* FROM aoi_defects d
               JOIN aoi_inspections i ON d.inspection_id = i.id
               WHERE i.board_id = ?
               ORDER BY d.id""",
            (board_id,),
        )
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
