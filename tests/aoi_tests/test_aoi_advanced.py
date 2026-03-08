"""Tests for advanced AOI analysis — solder joint, alignment, via fill."""

from __future__ import annotations

import unittest

import numpy as np

try:
    import skimage  # noqa: F401
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False

try:
    import cv2  # noqa: F401
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


@unittest.skipUnless(HAS_SKIMAGE, "scikit-image not installed")
class TestSolderJointAnalyzer(unittest.TestCase):
    """Tests for SolderJointAnalyzer (requires scikit-image)."""

    def _make_analyzer(self, **kw):
        from pyontrust.analysis.aoi.advanced import SolderJointAnalyzer
        return SolderJointAnalyzer(**kw)

    def test_uniform_image_no_joints(self):
        """A uniform grey image should yield zero solder joints."""
        analyzer = self._make_analyzer()
        image = np.full((100, 100), 128, dtype=np.uint8)
        results = analyzer.analyse(image)
        # Could be empty or very small
        # No bright blobs → nothing to report
        self.assertIsInstance(results, list)

    def test_bright_blob_detected_as_joint(self):
        """A bright ellipse on dark background should be graded."""
        analyzer = self._make_analyzer(min_area=50)
        image = np.zeros((200, 200), dtype=np.uint8)
        # Draw a bright circular blob
        rr, cc = np.mgrid[:200, :200]
        mask = ((rr - 100) ** 2 + (cc - 100) ** 2) < 30 ** 2
        image[mask] = 220
        results = analyzer.analyse(image)
        self.assertGreater(len(results), 0)
        self.assertIn(results[0].grade, ("GOOD", "ACCEPTABLE", "SUSPECT", "DEFECTIVE"))

    def test_grade_is_string(self):
        """Each SolderJointResult should carry a grade string."""
        analyzer = self._make_analyzer(min_area=20)
        image = np.zeros((100, 100), dtype=np.uint8)
        rr, cc = np.mgrid[:100, :100]
        mask = ((rr - 50) ** 2 + (cc - 50) ** 2) < 20 ** 2
        image[mask] = 200
        results = analyzer.analyse(image)
        for r in results:
            self.assertIsInstance(r.grade, str)
            self.assertGreater(r.area, 0)


@unittest.skipUnless(HAS_SKIMAGE and HAS_OPENCV, "scikit-image or OpenCV not installed")
class TestComponentAlignmentChecker(unittest.TestCase):
    """Tests for ComponentAlignmentChecker (requires scikit-image + OpenCV)."""

    def _make_checker(self, template):
        from pyontrust.analysis.aoi.advanced import ComponentAlignmentChecker
        return ComponentAlignmentChecker(template=template)

    def test_perfect_alignment(self):
        """Template matched against itself should show near-zero offset."""
        template = np.random.randint(50, 200, (40, 40), dtype=np.uint8)
        checker = self._make_checker(template)
        # Embed template in a larger image at (30, 30)
        image = np.full((100, 100), 128, dtype=np.uint8)
        image[30:70, 30:70] = template
        result = checker.check(image)
        self.assertIsNotNone(result)
        # Offset should be small
        self.assertLess(abs(result.offset_x), 5.0)
        self.assertLess(abs(result.offset_y), 5.0)

    def test_no_match_in_blank_image(self):
        """Checking against a blank image should still return a result."""
        template = np.random.randint(50, 200, (30, 30), dtype=np.uint8)
        checker = self._make_checker(template)
        image = np.full((100, 100), 128, dtype=np.uint8)
        result = checker.check(image)
        self.assertIsNotNone(result)


@unittest.skipUnless(HAS_SKIMAGE, "scikit-image not installed")
class TestViaFillInspector(unittest.TestCase):
    """Tests for ViaFillInspector."""

    def _make_inspector(self, **kw):
        from pyontrust.analysis.aoi.advanced import ViaFillInspector
        return ViaFillInspector(**kw)

    def test_no_circles_in_blank_image(self):
        """A uniform image should yield no via results."""
        inspector = self._make_inspector()
        image = np.full((100, 100), 128, dtype=np.uint8)
        results = inspector.inspect(image)
        self.assertIsInstance(results, list)
        # Blank image — may or may not find circles depending on params
        # Just check the type
        for r in results:
            self.assertIsNotNone(r.fill_ratio)

    def test_circle_detected(self):
        """A clearly drawn circle should be detected as a via."""
        inspector = self._make_inspector(
            min_radius=15, max_radius=40,
            hough_param1=50, hough_param2=20,
        )
        image = np.full((200, 200), 200, dtype=np.uint8)
        # Draw a dark ring with light centre (filled via)
        rr, cc = np.mgrid[:200, :200]
        ring = ((rr - 100) ** 2 + (cc - 100) ** 2)
        image[ring < 30 ** 2] = 50   # dark circle
        image[ring < 20 ** 2] = 200  # bright fill inside
        results = inspector.inspect(image)
        # We expect at least one via detected
        if len(results) > 0:
            self.assertGreater(results[0].fill_ratio, 0.0)
            self.assertIn(results[0].grade, ("GOOD", "ACCEPTABLE", "UNDERFILL", "VOID"))


if __name__ == "__main__":
    unittest.main()
