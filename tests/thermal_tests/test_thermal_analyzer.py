"""Tests for ThermalAnalyzer — frame analysis and zone tracking."""

from __future__ import annotations

import unittest

import numpy as np

from pyontrust.analysis.thermal.analyzer import ThermalAnalyzer
from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalVerdict,
    ThermalZone,
)


class TestThermalAnalyzerNoZones(unittest.TestCase):
    """Analyze frames without any ROI zones defined."""

    def test_analyse_uniform_frame(self):
        analyzer = ThermalAnalyzer()
        frame = np.full((100, 100), 25.0, dtype=np.float32)
        snap = analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        self.assertIsInstance(snap, ThermalSnapshot)
        self.assertAlmostEqual(snap.global_mean_c, 25.0, places=1)
        self.assertAlmostEqual(snap.global_max_c, 25.0, places=1)
        self.assertEqual(snap.verdict, ThermalVerdict.NORMAL)

    def test_hot_frame_triggers_hot_verdict(self):
        analyzer = ThermalAnalyzer()
        frame = np.full((100, 100), 90.0, dtype=np.float32)
        snap = analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        self.assertEqual(snap.verdict, ThermalVerdict.HOT)

    def test_warm_frame_triggers_warm_verdict(self):
        analyzer = ThermalAnalyzer()
        frame = np.full((100, 100), 70.0, dtype=np.float32)
        snap = analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        self.assertEqual(snap.verdict, ThermalVerdict.WARM)

    def test_hotspot_detection(self):
        analyzer = ThermalAnalyzer()
        frame = np.full((100, 100), 25.0, dtype=np.float32)
        frame[30, 50] = 55.0  # Hotspot
        snap = analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        self.assertEqual(snap.hotspot_x, 50)
        self.assertEqual(snap.hotspot_y, 30)

    def test_timeline_accumulation(self):
        analyzer = ThermalAnalyzer()
        for i in range(5):
            frame = np.full((50, 50), 25.0 + i, dtype=np.float32)
            analyzer.analyse_frame(frame, frame_index=i, timestamp_s=float(i))
        tl = analyzer.timeline
        self.assertEqual(len(tl.snapshots), 5)
        self.assertAlmostEqual(tl.duration_s, 4.0)


class TestThermalAnalyzerWithZones(unittest.TestCase):
    """Analyze frames with ROI zones."""

    def setUp(self):
        self.zones = [
            ThermalZone(
                name="CPU", x=10, y=10, width=20, height=20,
                warn_temp_c=60.0, max_temp_c=85.0,
            ),
            ThermalZone(
                name="VREG", x=50, y=50, width=15, height=15,
                warn_temp_c=80.0, max_temp_c=110.0,
            ),
        ]
        self.analyzer = ThermalAnalyzer(zones=self.zones)

    def test_zone_readings_populated(self):
        frame = np.full((100, 100), 30.0, dtype=np.float32)
        snap = self.analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        self.assertEqual(len(snap.zone_readings), 2)
        self.assertEqual(snap.zone_readings[0].zone_name, "CPU")
        self.assertEqual(snap.zone_readings[1].zone_name, "VREG")

    def test_zone_hot_verdict(self):
        frame = np.full((100, 100), 30.0, dtype=np.float32)
        # Make CPU zone hot
        frame[10:30, 10:30] = 90.0
        snap = self.analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        cpu_reading = snap.zone_readings[0]
        self.assertEqual(cpu_reading.verdict, ThermalVerdict.HOT)
        self.assertGreater(cpu_reading.max_temp_c, 85.0)

    def test_zone_warm_verdict(self):
        frame = np.full((100, 100), 30.0, dtype=np.float32)
        frame[10:30, 10:30] = 70.0  # Above warn, below max
        snap = self.analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        cpu_reading = snap.zone_readings[0]
        self.assertEqual(cpu_reading.verdict, ThermalVerdict.WARM)

    def test_rate_of_rise(self):
        """Two frames with rapid temperature increase should detect RUNAWAY."""
        zones = [
            ThermalZone(
                name="CPU", x=10, y=10, width=20, height=20,
                max_rate_c_per_s=2.0, warn_temp_c=80.0, max_temp_c=120.0,
            ),
        ]
        analyzer = ThermalAnalyzer(zones=zones)

        frame1 = np.full((50, 50), 30.0, dtype=np.float32)
        analyzer.analyse_frame(frame1, frame_index=0, timestamp_s=0.0)

        frame2 = np.full((50, 50), 40.0, dtype=np.float32)  # +10°C in 1s → rate=10°C/s
        snap2 = analyzer.analyse_frame(frame2, frame_index=1, timestamp_s=1.0)
        cpu_reading = snap2.zone_readings[0]
        self.assertEqual(cpu_reading.verdict, ThermalVerdict.RUNAWAY)
        self.assertGreater(abs(cpu_reading.rate_c_per_s), 2.0)


class TestThermalAnalyzerReset(unittest.TestCase):

    def test_reset_clears_history(self):
        analyzer = ThermalAnalyzer()
        frame = np.full((50, 50), 25.0, dtype=np.float32)
        analyzer.analyse_frame(frame, frame_index=0, timestamp_s=0.0)
        self.assertEqual(len(analyzer.timeline.snapshots), 1)
        analyzer.reset()
        self.assertEqual(len(analyzer.timeline.snapshots), 0)


class TestThermalAnalyzerColorise(unittest.TestCase):

    def test_colorise_returns_bgr(self):
        analyzer = ThermalAnalyzer()
        frame = np.full((50, 50), 30.0, dtype=np.float32)
        colour = analyzer.colorise_frame(frame)
        self.assertEqual(colour.ndim, 3)
        self.assertEqual(colour.shape[2], 3)  # BGR
        self.assertEqual(colour.shape[:2], (50, 50))


if __name__ == "__main__":
    unittest.main()
