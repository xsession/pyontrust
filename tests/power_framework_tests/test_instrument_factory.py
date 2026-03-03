"""Tests for profiles.py instrument factory — verifies all instrument types can be created."""

from __future__ import annotations

import unittest

from pyontrust_packages.power_test_framework.profiles import _build_instruments, _create_instrument
from pyontrust_packages.power_test_framework.instruments.simulated import SimulatedPowerMeter


class TestBuildInstruments(unittest.TestCase):
    """Test the _build_instruments factory dispatches correctly."""

    def test_empty_config_gives_simulated(self):
        result = _build_instruments({})
        self.assertIn("power_meter", result)
        self.assertIsInstance(result["power_meter"], SimulatedPowerMeter)

    def test_simulated_explicit(self):
        cfg = {"power_meter": {"type": "simulated", "voltage_v": 5.0}}
        result = _build_instruments(cfg)
        meter = result["power_meter"]
        self.assertIsInstance(meter, SimulatedPowerMeter)
        self.assertEqual(meter.voltage_v, 5.0)

    def test_multiple_instruments(self):
        cfg = {
            "power_meter": {"type": "simulated"},
            "psu": {"type": "sk120", "port": "COM5"},
        }
        result = _build_instruments(cfg)
        self.assertIn("power_meter", result)
        self.assertIn("psu", result)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            _create_instrument("nonexistent_type", {})


class TestCreateInstrument(unittest.TestCase):
    """Test _create_instrument factory for each supported type."""

    def test_simulated(self):
        inst = _create_instrument("simulated", {"voltage_v": 3.3})
        self.assertIsInstance(inst, SimulatedPowerMeter)

    def test_ad3_dwf(self):
        from pyontrust_packages.power_test_framework.instruments.ad3_dwf import Ad3DwfPowerMeter

        inst = _create_instrument("ad3_dwf", {"sample_rate_hz": 5000, "device_index": 0})
        self.assertIsInstance(inst, Ad3DwfPowerMeter)
        self.assertEqual(inst.sample_rate_hz, 5000.0)

    def test_ad3_cluster(self):
        from pyontrust_packages.power_test_framework.instruments.ad3_cluster import Ad3ClusterPowerMeter

        inst = _create_instrument("ad3_cluster", {
            "devices": [
                {"device_index": 0, "role": "power"},
                {"device_index": 1, "role": "aux"},
            ],
            "buffer_size": 4096,
        })
        self.assertIsInstance(inst, Ad3ClusterPowerMeter)
        self.assertEqual(len(inst.devices), 2)
        self.assertEqual(inst.buffer_size, 4096)

    def test_ppk2(self):
        from pyontrust_packages.power_test_framework.instruments.ppk2 import Ppk2PowerMeter

        inst = _create_instrument("ppk2", {"serial_port": "auto", "mode": "source"})
        self.assertIsInstance(inst, Ppk2PowerMeter)
        self.assertEqual(inst.mode, "source")

    def test_sk120(self):
        from pyontrust_packages.power_test_framework.instruments.sk120_psu import Sk120PowerSupply

        inst = _create_instrument("sk120", {"port": "COM3", "voltage_v": 5.0})
        self.assertIsInstance(inst, Sk120PowerSupply)
        self.assertEqual(inst.voltage_v, 5.0)

    def test_jlink(self):
        from pyontrust_packages.power_test_framework.instruments.jlink_ctrl import JLinkController

        inst = _create_instrument("jlink", {"device": "nRF52840_xxAA"})
        self.assertIsInstance(inst, JLinkController)
        self.assertEqual(inst.device, "nRF52840_xxAA")

    def test_hackrf(self):
        from pyontrust_packages.power_test_framework.instruments.hackrf_instrument import HackRfInstrument

        inst = _create_instrument("hackrf", {"freq_hz": 915000000, "lna_gain_db": 24})
        self.assertIsInstance(inst, HackRfInstrument)
        self.assertEqual(inst.freq_hz, 915000000)

    def test_webcam(self):
        from pyontrust_packages.power_test_framework.instruments.webcam_instrument import WebcamInstrument

        inst = _create_instrument("webcam", {"input_device": "test cam"})
        self.assertIsInstance(inst, WebcamInstrument)
        self.assertEqual(inst.input_device, "test cam")


if __name__ == "__main__":
    unittest.main()
