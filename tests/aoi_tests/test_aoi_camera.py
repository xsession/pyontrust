"""Tests for AOI instrument drivers — simulated camera + webcam."""

from __future__ import annotations

import unittest

from pyontrust.hal.industrial_camera import CameraInfo, IndustrialCamera
from pyontrust.instruments.aoi_camera import (
    HarvestersCamera,
    OpenCVWebcam,
    SimulatedAOICamera,
    create,
)


class TestSimulatedAOICamera(unittest.TestCase):
    """Test the simulated AOI camera instrument."""

    def setUp(self):
        self.cam = SimulatedAOICamera(width=64, height=48, channels=1)

    def test_open_close(self):
        self.cam.open()
        self.cam.close()

    def test_grab_frame_shape_mono(self):
        self.cam.open()
        frame = self.cam.grab_frame()
        self.assertEqual(frame.shape, (48, 64))
        self.cam.close()

    def test_grab_frame_shape_colour(self):
        cam = SimulatedAOICamera(width=64, height=48, channels=3)
        cam.open()
        frame = cam.grab_frame()
        self.assertEqual(frame.shape, (48, 64, 3))
        cam.close()

    def test_grab_frame_dtype(self):
        import numpy as np
        self.cam.open()
        frame = self.cam.grab_frame()
        self.assertEqual(frame.dtype, np.uint8)
        self.cam.close()

    def test_grab_frame_not_opened_raises(self):
        with self.assertRaises(RuntimeError):
            self.cam.grab_frame()

    def test_grab_sequence(self):
        self.cam.open()
        frames = self.cam.grab_sequence(3)
        self.assertEqual(len(frames), 3)
        for f in frames:
            self.assertEqual(f.shape, (48, 64))
        self.cam.close()

    def test_configure(self):
        self.cam.open()
        self.cam.configure(exposure_us=10000, gain_db=6.0)
        self.assertEqual(self.cam.exposure_us, 10000)
        self.assertEqual(self.cam.gain_db, 6.0)
        self.cam.close()

    def test_info(self):
        info = self.cam.info()
        self.assertIsInstance(info, CameraInfo)
        self.assertEqual(info.model, "SimulatedAOI")
        self.assertEqual(info.transport, "Simulated")

    def test_inject_defect(self):
        import numpy as np
        cam = SimulatedAOICamera(width=64, height=48, inject_defect=True)
        cam.open()
        frame = cam.grab_frame()
        # The defect region should have noticeably higher intensity
        # than a frame without defect
        cam2 = SimulatedAOICamera(width=64, height=48, inject_defect=False, noise_stddev=0)
        cam2.open()
        frame2 = cam2.grab_frame()
        self.assertGreater(frame.mean(), frame2.mean() - 5)  # Defect adds brightness
        cam.close()
        cam2.close()

    def test_protocol_compliance(self):
        """SimulatedAOICamera should satisfy the IndustrialCamera protocol."""
        self.assertTrue(isinstance(self.cam, IndustrialCamera))


class TestCreateFactory(unittest.TestCase):
    """Test the entry-point factory function."""

    def test_create_simulated_default(self):
        cam = create({})
        self.assertIsInstance(cam, SimulatedAOICamera)

    def test_create_simulated_explicit(self):
        cam = create({"mode": "simulated", "width": 320, "height": 240})
        self.assertIsInstance(cam, SimulatedAOICamera)
        self.assertEqual(cam.width, 320)
        self.assertEqual(cam.height, 240)

    def test_create_harvesters(self):
        cam = create({"mode": "harvesters", "cti_path": "/nonexistent/file.cti"})
        self.assertIsInstance(cam, HarvestersCamera)

    def test_create_webcam(self):
        cam = create({"mode": "webcam", "device_index": 2, "width": 640, "height": 480})
        self.assertIsInstance(cam, OpenCVWebcam)
        self.assertEqual(cam.device_index, 2)
        self.assertEqual(cam.width, 640)
        self.assertEqual(cam.height, 480)

    def test_create_with_exposure(self):
        cam = create({"exposure_us": 8000, "gain_db": 3.0})
        self.assertEqual(cam.exposure_us, 8000)
        self.assertEqual(cam.gain_db, 3.0)

    def test_create_with_inject_defect(self):
        cam = create({"inject_defect": True})
        self.assertIsInstance(cam, SimulatedAOICamera)
        self.assertTrue(cam.inject_defect)


class TestHarvestersCamera(unittest.TestCase):
    """Test HarvestersCamera configuration (without actual hardware)."""

    def test_info_without_open(self):
        cam = HarvestersCamera(cti_path="/nonexistent.cti")
        info = cam.info()
        self.assertEqual(info.model, "HarvestersCamera")
        self.assertEqual(info.transport, "GenTL")

    def test_configure_before_open_stores_values(self):
        cam = HarvestersCamera()
        cam.configure(12000.0, 4.5)
        self.assertEqual(cam.exposure_us, 12000.0)
        self.assertEqual(cam.gain_db, 4.5)

    def test_grab_frame_not_opened_raises(self):
        cam = HarvestersCamera()
        with self.assertRaises(RuntimeError):
            cam.grab_frame()

    def test_open_without_cti_raises(self):
        cam = HarvestersCamera(cti_path="")
        # Should raise either ImportError (no harvesters) or FileNotFoundError
        with self.assertRaises((ImportError, FileNotFoundError)):
            cam.open()


class TestOpenCVWebcam(unittest.TestCase):
    """Test OpenCVWebcam configuration (without actual camera hardware)."""

    def test_default_config(self):
        cam = OpenCVWebcam()
        self.assertEqual(cam.device_index, 0)
        self.assertEqual(cam.width, 1280)
        self.assertEqual(cam.height, 720)

    def test_info(self):
        cam = OpenCVWebcam(device_index=1)
        info = cam.info()
        self.assertIsInstance(info, CameraInfo)
        self.assertIn("Webcam", info.model)
        self.assertEqual(info.transport, "USB/UVC")

    def test_grab_frame_not_opened_raises(self):
        cam = OpenCVWebcam()
        with self.assertRaises(RuntimeError):
            cam.grab_frame()

    def test_configure_before_open(self):
        cam = OpenCVWebcam()
        cam.configure(exposure_us=10000, gain_db=3.0)
        self.assertEqual(cam.exposure_us, 10000)
        self.assertEqual(cam.gain_db, 3.0)


if __name__ == "__main__":
    unittest.main()
