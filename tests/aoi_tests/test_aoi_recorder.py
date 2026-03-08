"""Tests for AOI recorder — background capture during test profiles."""

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
    # Required by TestArtifacts but unused in recorder:
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


class TestAOIRecorderStartStop(unittest.TestCase):
    """Test recorder lifecycle."""

    def _make_ctx(self, tmp: str) -> _FakeContext:
        root = Path(tmp)
        rec_dir = root / "recorders"
        rec_dir.mkdir(parents=True, exist_ok=True)
        return _FakeContext(
            artifacts=_FakeArtifacts(root_dir=root, recorders_dir=rec_dir),
            start_time_s=time.perf_counter(),
        )

    def test_start_and_stop(self):
        from pyontrust.recorders.aoi import AOIRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = AOIRecorder(capture_interval_s=0.1)
            rec.start(ctx)

            # Let it capture a few frames
            time.sleep(0.5)

            rec.stop(ctx)
            self.assertIn("aoi", ctx.recorder_outputs)
            self.assertGreater(ctx.recorder_outputs["aoi"]["frames_captured"], 0)

    def test_writes_summary_json(self):
        from pyontrust.recorders.aoi import AOIRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = AOIRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.3)
            rec.stop(ctx)

            summary_path = Path(tmp) / "recorders" / "aoi" / "aoi_recorder_summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text())
            self.assertIn("frames_captured", summary)
            self.assertGreater(summary["frames_captured"], 0)

    def test_frames_saved_to_disk(self):
        from pyontrust.recorders.aoi import AOIRecorder

        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._make_ctx(tmp)
            rec = AOIRecorder(capture_interval_s=0.1)
            rec.start(ctx)
            time.sleep(0.4)
            rec.stop(ctx)

            aoi_dir = Path(tmp) / "recorders" / "aoi"
            frame_files = list(aoi_dir.glob("frame_*"))
            self.assertGreater(len(frame_files), 0)


class TestAOIRecorderFactory(unittest.TestCase):
    """Test the create() entry-point factory."""

    def test_create_defaults(self):
        from pyontrust.recorders.aoi import create

        rec = create({})
        self.assertEqual(rec.name, "aoi")
        self.assertAlmostEqual(rec.capture_interval_s, 2.0)
        self.assertFalse(rec.live_inspect)

    def test_create_with_config(self):
        from pyontrust.recorders.aoi import create

        rec = create({
            "name": "aoi_custom",
            "capture_interval_s": 0.5,
            "live_inspect": True,
            "camera": {"mode": "simulated", "width": 32, "height": 24},
        })
        self.assertEqual(rec.name, "aoi_custom")
        self.assertAlmostEqual(rec.capture_interval_s, 0.5)
        self.assertTrue(rec.live_inspect)


if __name__ == "__main__":
    unittest.main()
