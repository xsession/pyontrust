"""Tests for lab_bench.py — LabBench configuration, serialization, round-trip."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from pyontrust_packages.power_test_framework.lab_bench import (
    CalibrationData,
    InstrumentConfig,
    LabBench,
)


class TestCalibrationData(unittest.TestCase):
    def test_defaults(self):
        c = CalibrationData()
        self.assertEqual(c.current_offset_a, 0.0)
        self.assertEqual(c.voltage_offset_v, 0.0)
        self.assertEqual(c.gain_correction, 1.0)
        self.assertIsNone(c.last_cal_date)
        self.assertEqual(c.notes, "")

    def test_round_trip_dict(self):
        c = CalibrationData(current_offset_a=0.01, gain_correction=1.02, last_cal_date="2025-01-15")
        d = c.__dict__
        c2 = CalibrationData(**d)
        self.assertEqual(c, c2)


class TestInstrumentConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = InstrumentConfig(name="test", type="simulated")
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.params, {})
        # Default calibration is a CalibrationData() instance, not None
        self.assertIsInstance(cfg.calibration, CalibrationData)
        self.assertEqual(cfg.calibration.current_offset_a, 0.0)

    def test_with_calibration(self):
        cal = CalibrationData(current_offset_a=0.005)
        cfg = InstrumentConfig(name="ppk2", type="ppk2", params={"serial_port": "auto"}, calibration=cal)
        self.assertEqual(cfg.calibration.current_offset_a, 0.005)

    def test_disabled(self):
        cfg = InstrumentConfig(name="hackrf", type="hackrf", enabled=False)
        self.assertFalse(cfg.enabled)

    def test_get_param(self):
        cfg = InstrumentConfig(name="psu", type="sk120", params={"port": "COM5", "voltage_v": 3.3})
        self.assertEqual(cfg.get("port"), "COM5")
        self.assertIsNone(cfg.get("nonexistent"))
        self.assertEqual(cfg.get("nonexistent", 42), 42)


class TestLabBench(unittest.TestCase):
    def _make_bench(self) -> LabBench:
        return LabBench(
            name="test_bench",
            instruments={
                "ppk2": InstrumentConfig(name="ppk2", type="ppk2", params={"serial_port": "auto"}),
                "psu": InstrumentConfig(name="psu", type="sk120", params={"port": "COM5"}),
                "jlink": InstrumentConfig(name="jlink", type="jlink", enabled=False),
            },
        )

    def test_enabled_instruments(self):
        bench = self._make_bench()
        enabled = bench.enabled_instruments()
        self.assertIn("ppk2", enabled)
        self.assertIn("psu", enabled)
        self.assertNotIn("jlink", enabled)

    def test_get_instrument(self):
        bench = self._make_bench()
        cfg = bench.get_instrument("ppk2")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.type, "ppk2")

    def test_get_instrument_missing_raises(self):
        bench = self._make_bench()
        with self.assertRaises(KeyError):
            bench.get_instrument("nonexistent")

    def test_to_dict_round_trip(self):
        bench = self._make_bench()
        d = bench.to_dict()
        bench2 = LabBench.from_dict(d)
        self.assertEqual(bench.name, bench2.name)
        self.assertEqual(set(bench.instruments.keys()), set(bench2.instruments.keys()))

    def test_save_load_round_trip(self):
        bench = self._make_bench()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bench.json")
            bench.save(path)
            bench2 = LabBench.load(path)
        self.assertEqual(bench.name, bench2.name)
        self.assertEqual(len(bench.instruments), len(bench2.instruments))
        # Verify disabled instrument survived
        self.assertFalse(bench2.instruments["jlink"].enabled)

    def test_save_creates_valid_json(self):
        bench = self._make_bench()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bench.json")
            bench.save(path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertIn("name", data)
        self.assertIn("instruments", data)
        self.assertIsInstance(data["instruments"], dict)

    def test_empty_bench(self):
        bench = LabBench(name="empty")
        self.assertEqual(bench.enabled_instruments(), {})
        d = bench.to_dict()
        bench2 = LabBench.from_dict(d)
        self.assertEqual(bench2.name, "empty")

    def test_from_dict_with_calibration(self):
        raw = {
            "name": "cal_bench",
            "instruments": {
                "meter": {"type": "ad3_dwf", "sample_rate_hz": 1000}
            },
            "calibration": {
                "meter": {
                    "current_offset_a": 0.001,
                    "voltage_offset_v": 0.002,
                    "gain_correction": 1.01,
                    "last_cal_date": "2025-06-01",
                }
            },
        }
        bench = LabBench.from_dict(raw)
        meter = bench.get_instrument("meter")
        self.assertEqual(meter.calibration.current_offset_a, 0.001)
        self.assertEqual(meter.calibration.last_cal_date, "2025-06-01")


if __name__ == "__main__":
    unittest.main()
