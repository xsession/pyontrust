"""Tests for ThermalService — gateway façade."""

from __future__ import annotations

import unittest

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
)
from pyontrust.services.thermal_service import ThermalService


class TestThermalServiceLifecycle(unittest.TestCase):

    def test_default_opens_simulated(self):
        svc = ThermalService()
        self.assertFalse(svc.ready)
        svc.open()
        self.assertTrue(svc.ready)
        svc.close()
        self.assertFalse(svc.ready)

    def test_capture_before_open_raises(self):
        svc = ThermalService()
        with self.assertRaises(RuntimeError):
            svc.capture()


class TestThermalServiceCapture(unittest.TestCase):

    def setUp(self):
        self.svc = ThermalService(config_dict={
            "camera": {"mode": "simulated", "base_temp_c": 25.0, "noise_stddev_c": 0.1},
            "zones": [
                {"name": "CPU", "x": 10, "y": 10, "width": 20, "height": 20},
            ],
        })
        self.svc.open()

    def tearDown(self):
        self.svc.close()

    def test_capture_returns_snapshot(self):
        snap = self.svc.capture()
        self.assertIsInstance(snap, ThermalSnapshot)
        self.assertAlmostEqual(snap.global_mean_c, 25.0, delta=5.0)

    def test_capture_accumulates_timeline(self):
        self.svc.capture()
        self.svc.capture()
        self.svc.capture()
        tl = self.svc.get_timeline()
        self.assertIsInstance(tl, ThermalTimeline)
        self.assertEqual(len(tl.snapshots), 3)

    def test_spot_temperature(self):
        temp = self.svc.spot_temperature(20, 20)
        self.assertIsInstance(temp, float)
        self.assertAlmostEqual(temp, 25.0, delta=10.0)

    def test_get_summary(self):
        self.svc.capture()
        s = self.svc.get_summary()
        self.assertIn("peak_temperature_c", s)
        self.assertIn("worst_verdict", s)

    def test_get_camera_info(self):
        info = self.svc.get_camera_info()
        self.assertEqual(info["model"], "SimulatedThermal")
        self.assertEqual(info["vendor"], "pyontrust")

    def test_get_zone_history(self):
        self.svc.capture()
        self.svc.capture()
        hist = self.svc.get_zone_history("CPU")
        self.assertEqual(len(hist), 2)
        self.assertIn("mean_c", hist[0])


class TestThermalServiceHotspot(unittest.TestCase):
    """Test with injected hotspot."""

    def test_hotspot_detection(self):
        svc = ThermalService(config_dict={
            "camera": {
                "mode": "simulated",
                "inject_hotspot": True,
                "hotspot_temp_c": 90.0,
                "noise_stddev_c": 0.1,
            },
            "zones": [
                {"name": "HOT_ZONE", "x": 10, "y": 10, "width": 30, "height": 30,
                 "warn_temp_c": 60.0, "max_temp_c": 85.0},
            ],
        })
        svc.open()
        snap = svc.capture()
        svc.close()

        # Global max should reflect the hotspot
        self.assertGreater(snap.global_max_c, 70.0)


class TestThermalServiceNotInitialised(unittest.TestCase):

    def test_summary_before_open(self):
        svc = ThermalService()
        s = svc.get_summary()
        self.assertEqual(s["status"], "not_initialised")

    def test_violations_before_open(self):
        svc = ThermalService()
        self.assertEqual(svc.get_violations(), [])

    def test_zone_history_before_open(self):
        svc = ThermalService()
        self.assertEqual(svc.get_zone_history("CPU"), [])

    def test_camera_info_before_open(self):
        svc = ThermalService()
        self.assertEqual(svc.get_camera_info(), {})


if __name__ == "__main__":
    unittest.main()
