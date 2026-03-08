"""Tests for ThermalRecorder — background capture during test profiles."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class _FakeArtifacts:
    """Stand-in for TestArtifacts with just the fields the recorder uses."""

    root_dir: Path
    recorders_dir: Path
    meta_path: Path = Path(".")
    markers_json_path: Path = Path(".")
    trace_csv_path: Path = Path(".")
    summary_json_path: Path = Path(".")
    report_md_path: Path = Path(".")


@dataclass
class _FakeContext:
    """Minimal TestContext for recorder tests."""

    artifacts: _FakeArtifacts
    instruments: dict[str, Any] = field(default_factory=dict)
    start_time_s: float = 0.0
    markers: list[dict[str, Any]] = field(default_factory=list)
    recorder_outputs: dict[str, Any] = field(default_factory=dict)


class TestThermalRecorderStartStop(unittest.TestCase):
    """Test recorder lifecycle with simulated camera."""

    def _make_ctx(self, tmp: str) -> _FakeContext:
        root = Path(tmp)
        rec_dir = root / "recorders"
        rec_dir.mkdir(parents=True, exist_ok=True)
        return _FakeContext(
            artifacts=_FakeArtifacts(root_dir=root, recorders_dir=rec_dir),
            start_time_s=time.perf_counter(),
        )

    def test_start_and_stop(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.5)
            rec.stop(ctx)

            self.assertIn("thermal", ctx.recorder_outputs)
            self.assertGreater(ctx.recorder_outputs["thermal"]["frames_captured"], 0)

    def test_peak_temperature_reported(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.3)
            rec.stop(ctx)

            outputs = ctx.recorder_outputs["thermal"]
            self.assertIn("peak_temperature_c", outputs)
            self.assertIsInstance(outputs["peak_temperature_c"], float)
            self.assertGreater(outputs["peak_temperature_c"], 0.0)

    def test_worst_verdict_in_outputs(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.3)
            rec.stop(ctx)

            outputs = ctx.recorder_outputs["thermal"]
            self.assertIn("worst_verdict", outputs)
            self.assertIn(outputs["worst_verdict"], {"NORMAL", "WARM", "HOT", "RUNAWAY"})


class TestThermalRecorderFiles(unittest.TestCase):
    """Test that the recorder writes the expected output files."""

    def _make_ctx(self, tmp: str) -> _FakeContext:
        root = Path(tmp)
        rec_dir = root / "recorders"
        rec_dir.mkdir(parents=True, exist_ok=True)
        return _FakeContext(
            artifacts=_FakeArtifacts(root_dir=root, recorders_dir=rec_dir),
            start_time_s=time.perf_counter(),
        )

    def test_writes_timeline_json(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.4)
            rec.stop(ctx)

            timeline_path = Path(tmp) / "recorders" / "thermal" / "thermal_timeline.json"
            self.assertTrue(timeline_path.exists())
            data = json.loads(timeline_path.read_text())
            self.assertIn("snapshots", data)
            self.assertGreater(len(data["snapshots"]), 0)

    def test_writes_summary_json(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.3)
            rec.stop(ctx)

            summary_path = Path(tmp) / "recorders" / "thermal" / "thermal_summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text())
            self.assertIn("peak_temperature_c", summary)
            self.assertIn("worst_verdict", summary)

    def test_thermal_frame_files_saved(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1, save_images=True)
            rec.start(ctx)
            time.sleep(0.4)
            rec.stop(ctx)

            thermal_dir = Path(tmp) / "recorders" / "thermal"
            # Either .png (if OpenCV) or .npy (fallback)
            frame_files = list(thermal_dir.glob("thermal_*"))
            self.assertGreater(len(frame_files), 0)

    def test_no_images_when_disabled(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(capture_interval_s=0.1, save_images=False)
            rec.start(ctx)
            time.sleep(0.3)
            rec.stop(ctx)

            thermal_dir = Path(tmp) / "recorders" / "thermal"
            frame_files = list(thermal_dir.glob("thermal_*.png")) + list(
                thermal_dir.glob("thermal_*.npy")
            )
            self.assertEqual(len(frame_files), 0)


class TestThermalRecorderWithZones(unittest.TestCase):
    """Test that zone-based analysis works end-to-end in the recorder."""

    def _make_ctx(self, tmp: str) -> _FakeContext:
        root = Path(tmp)
        rec_dir = root / "recorders"
        rec_dir.mkdir(parents=True, exist_ok=True)
        return _FakeContext(
            artifacts=_FakeArtifacts(root_dir=root, recorders_dir=rec_dir),
            start_time_s=time.perf_counter(),
        )

    def test_zones_in_timeline(self):
        from pyontrust.recorders.thermal import ThermalRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = ThermalRecorder(
                capture_interval_s=0.1,
                save_images=False,
                zones_config=[
                    {"name": "MCU", "x": 10, "y": 10, "width": 20, "height": 20},
                    {"name": "REGULATOR", "x": 50, "y": 50, "width": 15, "height": 15},
                ],
            )
            rec.start(ctx)
            time.sleep(0.3)
            rec.stop(ctx)

            timeline_path = Path(tmp) / "recorders" / "thermal" / "thermal_timeline.json"
            data = json.loads(timeline_path.read_text())
            self.assertIn("summary", data)
            self.assertIn("zones", data["summary"])
            zone_names = [z["name"] for z in data["summary"]["zones"]]
            self.assertIn("MCU", zone_names)
            self.assertIn("REGULATOR", zone_names)


class TestThermalRecorderFactory(unittest.TestCase):
    """Test the create() entry-point factory."""

    def test_create_defaults(self):
        from pyontrust.recorders.thermal import create

        rec = create({})
        self.assertEqual(rec.name, "thermal")
        self.assertAlmostEqual(rec.capture_interval_s, 1.0)
        self.assertTrue(rec.save_images)
        self.assertEqual(rec.colormap, "inferno")

    def test_create_with_config(self):
        from pyontrust.recorders.thermal import create

        rec = create({
            "name": "board_thermal",
            "capture_interval_s": 0.5,
            "save_images": False,
            "colormap": "jet",
            "camera": {"mode": "simulated", "base_temp_c": 30.0},
            "zones": [
                {"name": "CPU", "x": 10, "y": 10, "width": 20, "height": 20},
            ],
        })
        self.assertEqual(rec.name, "board_thermal")
        self.assertAlmostEqual(rec.capture_interval_s, 0.5)
        self.assertFalse(rec.save_images)
        self.assertEqual(rec.colormap, "jet")
        self.assertIsNotNone(rec.camera_config)
        self.assertEqual(len(rec.zones_config), 1)


if __name__ == "__main__":
    unittest.main()
