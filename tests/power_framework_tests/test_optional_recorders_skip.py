import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

from power_test_framework.core import PowerTestRunner, TestStep, PowerTest  # noqa: E402
from power_test_framework.instruments.simulated import SimulatedPowerMeter  # noqa: E402
from power_test_framework.recorders.hackrf_iq import HackRfIqRecorder  # noqa: E402
from power_test_framework.recorders.ffmpeg_webcam import FfmpegWebcamRecorder  # noqa: E402


class TestOptionalRecordersSkip(unittest.TestCase):
    def test_hackrf_recorder_skips_when_missing(self):
        meter = SimulatedPowerMeter(sample_rate_hz=10.0, voltage_v=3.0)
        test = PowerTest(name="unit", description="", steps=[TestStep(name="s", duration_s=0.05, action=lambda ctx: None)])

        rec = HackRfIqRecorder(name="hackrf", tool_path="definitely_not_a_real_exe_123", skip_if_missing=True)

        with tempfile.TemporaryDirectory() as tmp:
            runner = PowerTestRunner(artifacts_root=tmp)
            artifacts = runner.run(test=test, instruments={"power_meter": meter}, recorders=[rec])
            meta = artifacts.meta_path.read_text(encoding="utf-8")
            self.assertIn('"hackrf"', meta)
            self.assertIn('"skipped": true', meta)

    def test_ffmpeg_recorder_skips_when_missing(self):
        meter = SimulatedPowerMeter(sample_rate_hz=10.0, voltage_v=3.0)
        test = PowerTest(name="unit", description="", steps=[TestStep(name="s", duration_s=0.05, action=lambda ctx: None)])

        rec = FfmpegWebcamRecorder(name="cam", ffmpeg_path="definitely_not_a_real_exe_456", skip_if_missing=True)

        with tempfile.TemporaryDirectory() as tmp:
            runner = PowerTestRunner(artifacts_root=tmp)
            artifacts = runner.run(test=test, instruments={"power_meter": meter}, recorders=[rec])
            meta = artifacts.meta_path.read_text(encoding="utf-8")
            self.assertIn('"cam"', meta)
            self.assertIn('"skipped": true', meta)


if __name__ == "__main__":
    unittest.main()
