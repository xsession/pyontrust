"""Tests for AOI processing pipeline — requires OpenCV."""

from __future__ import annotations

import unittest

import numpy as np

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from pyontrust.analysis.aoi.models import AOIVerdict, DefectType, InspectionResult


@unittest.skipUnless(HAS_OPENCV, "OpenCV not installed")
class TestImagePreprocessor(unittest.TestCase):
    def setUp(self):
        from pyontrust.analysis.aoi.processing import ImagePreprocessor
        self.preprocessor = ImagePreprocessor(denoise_strength=3)

    def test_process_mono(self):
        frame = np.random.randint(50, 200, (100, 100), dtype=np.uint8)
        result = self.preprocessor.process(frame)
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_process_colour(self):
        frame = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        result = self.preprocessor.process(frame)
        self.assertEqual(result.shape, frame.shape)

    def test_process_with_flat_field(self):
        from pyontrust.analysis.aoi.processing import ImagePreprocessor
        flat = np.full((100, 100), 200, dtype=np.uint8)
        pp = ImagePreprocessor(flat_field=flat, denoise_strength=0)
        frame = np.full((100, 100), 150, dtype=np.uint8)
        result = pp.process(frame)
        self.assertEqual(result.shape, (100, 100))

    def test_process_preserves_shape(self):
        frame = np.zeros((64, 48), dtype=np.uint8)
        result = self.preprocessor.process(frame)
        self.assertEqual(result.shape, (64, 48))


@unittest.skipUnless(HAS_OPENCV, "OpenCV not installed")
class TestBoardAligner(unittest.TestCase):
    def setUp(self):
        from pyontrust.analysis.aoi.processing import BoardAligner
        # Create a reference with features (random pattern)
        rng = np.random.default_rng(42)
        self.reference = rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)
        self.aligner = BoardAligner(self.reference)

    def test_align_identical(self):
        """Aligning an identical image should return near-identity homography."""
        aligned, H = self.aligner.align(self.reference.copy())
        self.assertEqual(aligned.shape, self.reference.shape)
        # H should be close to identity
        identity = np.eye(3)
        np.testing.assert_allclose(H, identity, atol=0.5)

    def test_align_insufficient_features_raises(self):
        from pyontrust.analysis.aoi.processing import BoardAligner
        # Uniform image has no features
        uniform = np.full((200, 300, 3), 128, dtype=np.uint8)
        aligner = BoardAligner(uniform)
        with self.assertRaises(RuntimeError):
            aligner.align(uniform.copy())


@unittest.skipUnless(HAS_OPENCV, "OpenCV not installed")
class TestDefectDetector(unittest.TestCase):
    def setUp(self):
        from pyontrust.analysis.aoi.processing import DefectDetector
        self.reference = np.full((200, 300), 128, dtype=np.uint8)
        self.detector = DefectDetector(
            reference=self.reference,
            diff_threshold=20,
            min_defect_area=30,
        )

    def test_no_defects_on_identical(self):
        defects = self.detector.detect(self.reference.copy())
        self.assertEqual(len(defects), 0)

    def test_detects_bright_defect(self):
        """A bright rectangle should be detected as a defect."""
        captured = self.reference.copy()
        captured[50:80, 100:170] = 255  # Bright defect
        defects = self.detector.detect(captured)
        self.assertGreater(len(defects), 0)
        # Should have bounding box roughly matching the defect region
        d = defects[0]
        self.assertGreater(d.width, 10)
        self.assertGreater(d.height, 10)
        self.assertGreater(d.confidence, 0)

    def test_detects_dark_defect(self):
        """A dark rectangle (missing component) should be detected."""
        captured = self.reference.copy()
        captured[50:90, 100:160] = 0  # Dark region
        defects = self.detector.detect(captured)
        self.assertGreater(len(defects), 0)

    def test_small_defect_below_threshold_ignored(self):
        captured = self.reference.copy()
        captured[50:52, 100:102] = 255  # 2x2 pixels — below min area
        defects = self.detector.detect(captured)
        self.assertEqual(len(defects), 0)

    def test_defect_has_valid_type(self):
        captured = self.reference.copy()
        captured[50:80, 100:170] = 255
        defects = self.detector.detect(captured)
        for d in defects:
            self.assertIsInstance(d.defect_type, DefectType)


@unittest.skipUnless(HAS_OPENCV, "OpenCV not installed")
class TestResultAnnotator(unittest.TestCase):
    def test_annotate_mono(self):
        from pyontrust.analysis.aoi.processing import ResultAnnotator
        from pyontrust.analysis.aoi.models import Defect, DefectType
        img = np.full((100, 100), 128, dtype=np.uint8)
        result = InspectionResult(
            board_id="test",
            verdict=AOIVerdict.PASS,
            defects=[Defect(DefectType.CONTAMINATION, 10, 10, 20, 20, 0.5)],
        )
        annotated = ResultAnnotator.annotate(img, result)
        # Should be BGR
        self.assertEqual(len(annotated.shape), 3)
        self.assertEqual(annotated.shape[2], 3)

    def test_annotate_colour(self):
        from pyontrust.analysis.aoi.processing import ResultAnnotator
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = InspectionResult("test", AOIVerdict.FAIL)
        annotated = ResultAnnotator.annotate(img, result)
        self.assertEqual(annotated.shape, img.shape)


if __name__ == "__main__":
    unittest.main()
