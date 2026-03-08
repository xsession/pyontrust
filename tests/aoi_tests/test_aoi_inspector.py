"""Tests for AOI inspector — end-to-end integration (simulated camera)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from pyontrust.analysis.aoi.models import AOIVerdict, InspectionResult
from pyontrust.instruments.aoi_camera import SimulatedAOICamera


class TestAOIInspectorSimulated(unittest.TestCase):
    """End-to-end AOI inspection with simulated camera (no OpenCV needed for basic path)."""

    def test_inspect_board_no_reference(self):
        """Inspection without reference image should pass (no defects detectable)."""
        from pyontrust.analysis.aoi.inspector import AOIInspector
        from pyontrust.analysis.aoi.processing import ImagePreprocessor

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            archive = Path(tmp) / "images"

            camera = SimulatedAOICamera(width=64, height=48, noise_stddev=0)
            inspector = AOIInspector(
                grabber=camera,
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,
                detector=None,
                db_path=db_path,
                image_archive=archive,
            )

            inspector.open()
            result = inspector.inspect_board("TEST-001")
            inspector.close()

            self.assertIsInstance(result, InspectionResult)
            self.assertEqual(result.board_id, "TEST-001")
            self.assertEqual(result.verdict, AOIVerdict.PASS)
            self.assertEqual(result.total_defect_count, 0)
            self.assertIn("time_total_s", result.metrics)
            self.assertIn("timestamp", result.metrics)

    def test_inspect_stores_to_database(self):
        """Results should be persisted to SQLite."""
        from pyontrust.analysis.aoi.inspector import AOIInspector
        from pyontrust.analysis.aoi.processing import ImagePreprocessor
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            archive = Path(tmp) / "images"

            camera = SimulatedAOICamera(width=64, height=48, noise_stddev=0)
            inspector = AOIInspector(
                grabber=camera,
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,
                detector=None,
                db_path=db_path,
                image_archive=archive,
            )

            inspector.open()
            inspector.inspect_board("DB-001")
            inspector.inspect_board("DB-002")
            inspector.close()

            # Verify database
            db = sqlite3.connect(str(db_path))
            rows = db.execute("SELECT COUNT(*) FROM aoi_inspections").fetchone()
            self.assertEqual(rows[0], 2)
            db.close()

    def test_get_inspection_history(self):
        from pyontrust.analysis.aoi.inspector import AOIInspector
        from pyontrust.analysis.aoi.processing import ImagePreprocessor

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            archive = Path(tmp) / "images"

            camera = SimulatedAOICamera(width=64, height=48, noise_stddev=0)
            inspector = AOIInspector(
                grabber=camera,
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,
                detector=None,
                db_path=db_path,
                image_archive=archive,
            )

            inspector.open()
            inspector.inspect_board("HIST-001")
            inspector.inspect_board("HIST-002")
            history = inspector.get_inspection_history(limit=10)
            inspector.close()

            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["board_id"], "HIST-002")  # Most recent first

    def test_inspect_frame_without_camera(self):
        """inspect_frame() should work on a pre-captured frame."""
        from pyontrust.analysis.aoi.inspector import AOIInspector
        from pyontrust.analysis.aoi.processing import ImagePreprocessor

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            archive = Path(tmp) / "images"

            camera = SimulatedAOICamera(width=64, height=48, noise_stddev=0)
            inspector = AOIInspector(
                grabber=camera,
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,
                detector=None,
                db_path=db_path,
                image_archive=archive,
            )

            inspector.open()
            frame = np.full((48, 64), 128, dtype=np.uint8)
            result = inspector.inspect_frame(frame, "FRAME-001")
            inspector.close()

            self.assertEqual(result.board_id, "FRAME-001")
            self.assertEqual(result.verdict, AOIVerdict.PASS)


@unittest.skipUnless(HAS_OPENCV, "OpenCV not installed")
class TestAOIInspectorWithOpenCV(unittest.TestCase):
    """Full pipeline test with OpenCV available."""

    def test_inspect_detects_defect(self):
        from pyontrust.analysis.aoi.inspector import AOIInspector
        from pyontrust.analysis.aoi.processing import (
            BoardAligner,
            DefectDetector,
            ImagePreprocessor,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            archive = Path(tmp) / "images"

            # Reference: uniform grey
            reference = np.full((100, 150, 3), 128, dtype=np.uint8)
            # Camera that produces a frame with a bright defect
            camera = SimulatedAOICamera(
                width=150, height=100, channels=3,
                inject_defect=True, noise_stddev=0,
            )

            inspector = AOIInspector(
                grabber=camera,
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,  # Skip alignment for this test
                detector=DefectDetector(
                    reference=reference,
                    diff_threshold=20,
                    min_defect_area=30,
                ),
                db_path=db_path,
                image_archive=archive,
            )

            inspector.open()
            result = inspector.inspect_board("DEFECT-001")
            inspector.close()

            self.assertIsInstance(result, InspectionResult)
            # Should detect at least one defect from the injected bright region
            self.assertGreater(len(result.defects), 0)
            self.assertIn(result.verdict, (AOIVerdict.FAIL, AOIVerdict.WARN))
            self.assertIsNotNone(result.annotated_image)

    def test_image_archival(self):
        from pyontrust.analysis.aoi.inspector import AOIInspector
        from pyontrust.analysis.aoi.processing import ImagePreprocessor

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            archive = Path(tmp) / "images"

            camera = SimulatedAOICamera(width=64, height=48, channels=3, noise_stddev=0)
            inspector = AOIInspector(
                grabber=camera,
                preprocessor=ImagePreprocessor(denoise_strength=0),
                aligner=None,
                detector=None,
                db_path=db_path,
                image_archive=archive,
            )

            inspector.open()
            inspector.inspect_board("ARCHIVE-001")
            inspector.close()

            # Check files were written
            self.assertTrue((archive / "ARCHIVE-001_raw.png").exists())
            self.assertTrue((archive / "ARCHIVE-001_metrics.json").exists())

            # Verify metrics JSON is valid
            metrics = json.loads((archive / "ARCHIVE-001_metrics.json").read_text())
            self.assertIn("time_total_s", metrics)


class TestAOIInspectorFromConfig(unittest.TestCase):
    """Test JSON config-driven factory."""

    def test_from_config_simulated(self):
        from pyontrust.analysis.aoi.inspector import AOIInspector

        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "camera": {"mode": "simulated", "width": 64, "height": 48},
                "processing": {"denoise_strength": 0},
                "storage": {
                    "db_path": str(Path(tmp) / "test.db"),
                    "image_archive": str(Path(tmp) / "images"),
                },
            }
            config_path = Path(tmp) / "aoi_config.json"
            config_path.write_text(json.dumps(config))

            inspector = AOIInspector.from_config(config_path)
            inspector.open()
            result = inspector.inspect_board("CFG-001")
            inspector.close()

            self.assertEqual(result.verdict, AOIVerdict.PASS)


if __name__ == "__main__":
    unittest.main()
