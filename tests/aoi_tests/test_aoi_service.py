"""Tests for AOIService — gateway façade."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from pyontrust.analysis.aoi.models import AOIVerdict
from pyontrust.services.aoi_service import AOIService


class TestAOIServiceLifecycle(unittest.TestCase):
    """Test service open/close lifecycle."""

    def test_default_constructor_opens_simulated(self):
        """Service with no config should create a simulated camera."""
        svc = AOIService()
        self.assertFalse(svc.ready)
        svc.open()
        self.assertTrue(svc.ready)
        svc.close()
        self.assertFalse(svc.ready)

    def test_inspect_before_open_raises(self):
        svc = AOIService()
        with self.assertRaises(RuntimeError):
            svc.inspect("SN-001")

    def test_inspect_frame_before_open_raises(self):
        svc = AOIService()
        frame = np.full((48, 64), 128, dtype=np.uint8)
        with self.assertRaises(RuntimeError):
            svc.inspect_frame(frame)


class TestAOIServiceInspection(unittest.TestCase):
    """Test inspection through the service layer (isolated temp DB per test)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        config = {
            "camera": {"mode": "simulated", "width": 64, "height": 48},
            "processing": {"denoise_strength": 0},
            "storage": {
                "db_path": str(Path(self._tmpdir.name) / "test.db"),
                "image_archive": str(Path(self._tmpdir.name) / "images"),
            },
        }
        self.svc = AOIService(config_dict=config)
        self.svc.open()

    def tearDown(self):
        self.svc.close()
        self._tmpdir.cleanup()

    def test_inspect_returns_result(self):
        result = self.svc.inspect("SN-001")
        self.assertEqual(result.board_id, "SN-001")
        self.assertEqual(result.verdict, AOIVerdict.PASS)

    def test_inspect_frame(self):
        frame = np.full((48, 64), 128, dtype=np.uint8)
        result = self.svc.inspect_frame(frame, "FRAME-001")
        self.assertEqual(result.board_id, "FRAME-001")

    def test_get_history_empty_then_populated(self):
        self.assertEqual(len(self.svc.get_history()), 0)
        self.svc.inspect("H-001")
        self.svc.inspect("H-002")
        history = self.svc.get_history()
        self.assertEqual(len(history), 2)

    def test_get_board_defects(self):
        self.svc.inspect("D-001")
        defects = self.svc.get_board_defects("D-001")
        self.assertIsInstance(defects, list)

    def test_get_stats(self):
        self.svc.inspect("S-001")
        self.svc.inspect("S-002")
        stats = self.svc.get_stats()
        self.assertEqual(stats["total_inspections"], 2)
        self.assertIn("passed", stats)
        self.assertIn("failed", stats)
        self.assertIn("pass_rate", stats)


class TestAOIServiceConfigDict(unittest.TestCase):
    """Test construction from a config dictionary."""

    def test_config_dict_constructor(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "camera": {"mode": "simulated", "width": 64, "height": 48},
                "processing": {"denoise_strength": 0},
                "storage": {
                    "db_path": str(Path(tmp) / "test.db"),
                    "image_archive": str(Path(tmp) / "images"),
                },
            }
            svc = AOIService(config_dict=config)
            svc.open()
            self.assertTrue(svc.ready)
            result = svc.inspect("CFG-001")
            self.assertEqual(result.verdict, AOIVerdict.PASS)
            svc.close()

    def test_history_empty_when_not_opened(self):
        svc = AOIService()
        self.assertEqual(svc.get_history(), [])
        self.assertEqual(svc.get_board_defects("NONE"), [])


if __name__ == "__main__":
    unittest.main()
