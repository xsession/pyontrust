"""Tests for Seek Thermal instrument drivers — simulated camera."""

from __future__ import annotations

import unittest

import numpy as np

from pyontrust.hal.thermal_camera import ThermalCamera, ThermalCameraInfo
from pyontrust.instruments.seek_thermal import (
    SeekThermalCamera,
    SimulatedThermalCamera,
    create,
)


class TestSimulatedThermalCamera(unittest.TestCase):
    """Test the simulated thermal camera."""

    def setUp(self):
        self.cam = SimulatedThermalCamera(width=64, height=48)

    def test_open_close(self):
        self.cam.open()
        self.cam.close()

    def test_grab_frame_shape(self):
        self.cam.open()
        frame = self.cam.grab_frame()
        self.assertEqual(frame.shape, (48, 64))
        self.assertEqual(frame.dtype, np.uint16)
        self.cam.close()

    def test_grab_temperature_frame_shape(self):
        self.cam.open()
        frame = self.cam.grab_temperature_frame()
        self.assertEqual(frame.shape, (48, 64))
        self.assertEqual(frame.dtype, np.float32)
        self.cam.close()

    def test_temperature_range(self):
        """Simulated temps should be around base_temp_c."""
        self.cam.open()
        frame = self.cam.grab_temperature_frame()
        mean = float(np.mean(frame))
        self.assertAlmostEqual(mean, 25.0, delta=5.0)
        self.cam.close()

    def test_hotspot_injection(self):
        cam = SimulatedThermalCamera(
            width=64, height=48,
            inject_hotspot=True, hotspot_temp_c=85.0, noise_stddev_c=0.1,
        )
        cam.open()
        frame = cam.grab_temperature_frame()
        self.assertGreater(float(np.max(frame)), 70.0)  # Hotspot visible
        cam.close()

    def test_grab_frame_not_opened_raises(self):
        with self.assertRaises(RuntimeError):
            self.cam.grab_frame()

    def test_grab_temperature_frame_not_opened_raises(self):
        with self.assertRaises(RuntimeError):
            self.cam.grab_temperature_frame()

    def test_configure(self):
        self.cam.open()
        self.cam.configure(emissivity=0.90, reflected_temp_c=20.0)
        self.assertAlmostEqual(self.cam.emissivity, 0.90)
        self.assertAlmostEqual(self.cam.reflected_temp_c, 20.0)
        self.cam.close()

    def test_spot_temperature(self):
        self.cam.open()
        temp = self.cam.spot_temperature(32, 24)
        self.assertIsInstance(temp, float)
        self.assertAlmostEqual(temp, 25.0, delta=10.0)
        self.cam.close()

    def test_info(self):
        info = self.cam.info()
        self.assertIsInstance(info, ThermalCameraInfo)
        self.assertEqual(info.model, "SimulatedThermal")
        self.assertEqual(info.vendor, "pyontrust")
        self.assertEqual(info.resolution, (64, 48))

    def test_protocol_compliance(self):
        """SimulatedThermalCamera should satisfy the ThermalCamera protocol."""
        self.assertTrue(isinstance(self.cam, ThermalCamera))


class TestCreateFactory(unittest.TestCase):
    """Test the entry-point factory function."""

    def test_create_simulated_default(self):
        cam = create({})
        self.assertIsInstance(cam, SimulatedThermalCamera)

    def test_create_simulated_explicit(self):
        cam = create({"mode": "simulated", "base_temp_c": 30.0})
        self.assertIsInstance(cam, SimulatedThermalCamera)
        self.assertAlmostEqual(cam.base_temp_c, 30.0)

    def test_create_seek_mode(self):
        cam = create({"mode": "seek", "device_index": 0})
        self.assertIsInstance(cam, SeekThermalCamera)

    def test_create_with_emissivity(self):
        cam = create({"emissivity": 0.80})
        self.assertAlmostEqual(cam.emissivity, 0.80)

    def test_create_with_hotspot(self):
        cam = create({"inject_hotspot": True, "hotspot_temp_c": 100.0})
        self.assertIsInstance(cam, SimulatedThermalCamera)
        self.assertTrue(cam.inject_hotspot)
        self.assertAlmostEqual(cam.hotspot_temp_c, 100.0)


class TestSeekThermalCamera(unittest.TestCase):
    """Test SeekThermalCamera (without hardware)."""

    def test_default_emissivity(self):
        cam = SeekThermalCamera()
        self.assertAlmostEqual(cam.emissivity, 0.95)

    def test_open_without_library_raises(self):
        cam = SeekThermalCamera()
        # Should raise ImportError if neither seekcamera nor seek_thermal installed
        with self.assertRaises(ImportError):
            cam.open()


if __name__ == "__main__":
    unittest.main()
