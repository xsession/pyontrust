"""Tests for thermal domain models (stdlib-only)."""

from __future__ import annotations

import unittest

from pyontrust.analysis.thermal.models import (
    ThermalSnapshot,
    ThermalTimeline,
    ThermalVerdict,
    ThermalZone,
    ZoneReading,
)


class TestThermalVerdict(unittest.TestCase):

    def test_values(self):
        self.assertEqual(ThermalVerdict.NORMAL.value, "NORMAL")
        self.assertEqual(ThermalVerdict.WARM.value, "WARM")
        self.assertEqual(ThermalVerdict.HOT.value, "HOT")
        self.assertEqual(ThermalVerdict.RUNAWAY.value, "RUNAWAY")


class TestThermalZone(unittest.TestCase):

    def test_defaults(self):
        z = ThermalZone(name="CPU", x=10, y=20, width=30, height=30)
        self.assertEqual(z.warn_temp_c, 60.0)
        self.assertEqual(z.max_temp_c, 85.0)
        self.assertEqual(z.max_rate_c_per_s, 5.0)

    def test_to_dict(self):
        z = ThermalZone(name="VREG", x=5, y=10, width=15, height=15, max_temp_c=105.0)
        d = z.to_dict()
        self.assertEqual(d["name"], "VREG")
        self.assertEqual(d["max_temp_c"], 105.0)
        self.assertIn("x", d)

    def test_frozen(self):
        z = ThermalZone(name="X", x=0, y=0, width=10, height=10)
        with self.assertRaises(AttributeError):
            z.name = "Y"  # type: ignore[misc]


class TestZoneReading(unittest.TestCase):

    def test_to_dict(self):
        r = ZoneReading(
            zone_name="CPU",
            mean_temp_c=42.5,
            max_temp_c=48.3,
            min_temp_c=38.1,
            std_temp_c=2.1,
            verdict=ThermalVerdict.NORMAL,
            rate_c_per_s=0.5,
        )
        d = r.to_dict()
        self.assertEqual(d["zone_name"], "CPU")
        self.assertEqual(d["verdict"], "NORMAL")
        self.assertAlmostEqual(d["rate_c_per_s"], 0.5, places=2)


class TestThermalSnapshot(unittest.TestCase):

    def test_to_dict(self):
        snap = ThermalSnapshot(
            timestamp_s=1.5,
            wall_time="2026-03-08T12:00:00Z",
            frame_index=1,
            global_min_c=20.0,
            global_max_c=55.0,
            global_mean_c=30.0,
            verdict=ThermalVerdict.NORMAL,
        )
        d = snap.to_dict()
        self.assertEqual(d["frame_index"], 1)
        self.assertEqual(d["verdict"], "NORMAL")
        self.assertIn("hotspot", d)


class TestThermalTimeline(unittest.TestCase):

    def test_empty_timeline(self):
        tl = ThermalTimeline(board_id="TEST-001")
        self.assertEqual(tl.duration_s, 0.0)
        self.assertEqual(tl.peak_temperature_c, 0.0)
        self.assertEqual(tl.worst_verdict, ThermalVerdict.NORMAL)

    def test_duration(self):
        tl = ThermalTimeline()
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=0.0, wall_time="", frame_index=0,
            global_min_c=20, global_max_c=30, global_mean_c=25,
        ))
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=5.0, wall_time="", frame_index=1,
            global_min_c=20, global_max_c=35, global_mean_c=28,
        ))
        self.assertAlmostEqual(tl.duration_s, 5.0)

    def test_peak_temperature(self):
        tl = ThermalTimeline()
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=0, wall_time="", frame_index=0,
            global_min_c=20, global_max_c=45, global_mean_c=30,
        ))
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=1, wall_time="", frame_index=1,
            global_min_c=20, global_max_c=80, global_mean_c=40,
        ))
        self.assertAlmostEqual(tl.peak_temperature_c, 80.0)

    def test_worst_verdict(self):
        tl = ThermalTimeline()
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=0, wall_time="", frame_index=0,
            global_min_c=20, global_max_c=30, global_mean_c=25,
            verdict=ThermalVerdict.NORMAL,
        ))
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=1, wall_time="", frame_index=1,
            global_min_c=20, global_max_c=90, global_mean_c=50,
            verdict=ThermalVerdict.HOT,
        ))
        self.assertEqual(tl.worst_verdict, ThermalVerdict.HOT)

    def test_violations(self):
        tl = ThermalTimeline()
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=0, wall_time="", frame_index=0,
            global_min_c=20, global_max_c=30, global_mean_c=25,
            verdict=ThermalVerdict.NORMAL,
        ))
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=1, wall_time="", frame_index=1,
            global_min_c=20, global_max_c=90, global_mean_c=50,
            verdict=ThermalVerdict.HOT,
        ))
        violations = tl.violations()
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["verdict"], "HOT")

    def test_zone_history(self):
        tl = ThermalTimeline()
        reading = ZoneReading(
            zone_name="CPU", mean_temp_c=40, max_temp_c=45,
            min_temp_c=35, std_temp_c=2.0, verdict=ThermalVerdict.NORMAL,
        )
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=0, wall_time="", frame_index=0,
            global_min_c=20, global_max_c=45, global_mean_c=30,
            zone_readings=[reading],
        ))
        hist = tl.zone_history("CPU")
        self.assertEqual(len(hist), 1)
        self.assertAlmostEqual(hist[0]["mean_c"], 40.0)

    def test_summary(self):
        tl = ThermalTimeline(board_id="SN-001")
        tl.snapshots.append(ThermalSnapshot(
            timestamp_s=0, wall_time="", frame_index=0,
            global_min_c=20, global_max_c=30, global_mean_c=25,
        ))
        s = tl.summary()
        self.assertEqual(s["board_id"], "SN-001")
        self.assertIn("peak_temperature_c", s)
        self.assertIn("worst_verdict", s)


if __name__ == "__main__":
    unittest.main()
