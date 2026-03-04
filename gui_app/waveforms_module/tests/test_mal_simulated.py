from __future__ import annotations

import tempfile
import time
import unittest

import numpy as np

from pyontrust_waveforms.config import WaveformsConfig
from pyontrust_waveforms.hal.file_replay import FileReplayHal
from pyontrust_waveforms.hal.simulated import SimulatedHal
from pyontrust_waveforms.mal.acquisition import AcquisitionManager
from pyontrust_waveforms.mal.recording import write_npz


class TestMalSimulated(unittest.TestCase):
    def test_acquisition_produces_ui_frame(self) -> None:
        cfg = WaveformsConfig()
        hal = SimulatedHal({})
        acq = AcquisitionManager(hal=hal, config=cfg)
        acq.connect("sim0")
        acq.start()
        deadline = time.monotonic() + 2.0
        uif = None
        while time.monotonic() < deadline:
            uif = acq.latest_ui_frame()
            if uif is not None:
                break
            time.sleep(0.05)
        acq.stop()

        self.assertIsNotNone(uif)
        assert uif is not None
        self.assertGreater(len(uif.env_min), 10)
        self.assertGreater(len(uif.fft_mag), 10)
        # Trigger index is best-effort; ensure field exists
        self.assertTrue(hasattr(uif, "trigger_index"))


class TestFileReplayHal(unittest.TestCase):
    def test_replay_reads(self) -> None:
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".npz")
            # Close immediately so NumPy can create the zip on Windows.
            import os

            os.close(fd)
            sr = 1_000_000.0
            ch0 = (0.5 * np.sin(2 * np.pi * 10_000.0 * np.arange(10_000) / sr)).astype(np.float32)
            np.savez(path, sample_rate_hz=sr, ch0=ch0)

            hal = FileReplayHal({"path": path})
            hal.open("replay0")
            hal.configure_scope(type("C", (), {"sample_rate_hz": sr, "record_length": 1024, "mode": "realtime"})())
            out = hal.read_samples(1024, timeout_s=0.01)
            self.assertIn(0, out)
            self.assertEqual(out[0].dtype, np.float32)
            self.assertEqual(len(out[0]), 1024)
        finally:
            if path:
                try:
                    import os

                    os.remove(path)
                except Exception:
                    pass


class TestRecordingSchema(unittest.TestCase):
    def test_write_npz_keys(self) -> None:
        import os
        import tempfile

        sr = 1_000_000.0
        frame = type(
            "F",
            (),
            {
                "t0_s": 123.0,
                "sample_rate_hz": sr,
                "channels": {0: np.zeros(128, np.float32)},
            },
        )()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cap.npz")
            write_npz(path, frame)
            with np.load(path) as npz:
                self.assertIn("schema_version", npz.files)
                self.assertIn("sample_rate_hz", npz.files)
                self.assertIn("t0_s", npz.files)
                self.assertIn("ch0", npz.files)


if __name__ == "__main__":
    unittest.main()
