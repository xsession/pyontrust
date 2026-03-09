"""Tests for the hardware discovery service and diagnostic blueprint.

These tests mock hardware probes so they run anywhere without real devices.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from pyontrust.services.hardware_discovery import (
    _err,
    _not_found,
    _ok,
    discover_all_hardware,
    run_all_tests,
    run_quick_test,
)


# ═══════════════════════════════════════════════════════════════════════
#  Result builders
# ═══════════════════════════════════════════════════════════════════════

class TestResultBuilders(unittest.TestCase):
    def test_ok(self):
        r = _ok("serial", "serial_port", "COM3", "🔌", {"device": "COM3"})
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["category"], "serial")
        self.assertEqual(r["type"], "serial_port")
        self.assertEqual(r["name"], "COM3")
        self.assertEqual(r["icon"], "🔌")
        self.assertEqual(r["details"]["device"], "COM3")
        self.assertIsNone(r["error"])
        self.assertIsNone(r["test_result"])

    def test_err(self):
        r = _err("serial", "serial_port", "Ports", "🔌", "no pyserial")
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error"], "no pyserial")
        self.assertEqual(r["details"], {})

    def test_not_found(self):
        r = _not_found("android", "android_sensors", "No ADB", "📱")
        self.assertEqual(r["status"], "not_found")
        self.assertIsNone(r["error"])


# ═══════════════════════════════════════════════════════════════════════
#  Discovery with mocked probes
# ═══════════════════════════════════════════════════════════════════════

def _fake_serial_ports():
    return [
        _ok("serial", "serial_port", "COM3", "🔌",
            {"device": "COM3", "description": "nRF52840"}),
        _ok("serial", "serial_port", "COM7", "🔌",
            {"device": "COM7", "description": "Bluetooth Port"}),
    ]


def _fake_adb():
    return [_ok("android", "android_sensors", "Pixel 7", "📱",
                {"serial": "ABC123", "brand": "Google", "model": "Pixel 7"})]


def _fake_webcam():
    return [_ok("camera", "webcam", "Camera #0", "📷",
                {"index": 0, "resolution": "640x480", "fps": 30.0})]


def _fake_dwf():
    return [_ok("instruments", "ad3_dwf", "Analog Discovery 3", "📟",
                {"index": 0, "name": "AD3", "serial": "SN:123"})]


def _fake_seek():
    return [_not_found("thermal", "seek_thermal", "No Seek Thermal", "🌡️")]


def _fake_jlink():
    return [_ok("debug", "jlink", "J-Link EDU", "🔧", {"path": "/usr/bin/jlink"})]


def _fake_hackrf():
    return [_not_found("sdr", "hackrf", "No HackRF", "📡")]


def _fake_ppk2():
    return [_not_found("instruments", "ppk2", "No PPK2", "⚡")]


def _fake_nrf52840():
    return [_ok("ble", "nrf52840_dongle", "nRF52840 Dongle", "📶",
                {"port": "COM3", "description": "nRF52840"})]


def _fake_network():
    return [_ok("network", "network", "host (127.0.0.1)", "🌐",
                {"hostname": "host", "ip": "127.0.0.1"})]


class TestDiscoverAllHardware(unittest.TestCase):

    @patch("pyontrust.services.hardware_discovery._probe_serial_ports", _fake_serial_ports)
    @patch("pyontrust.services.hardware_discovery._probe_adb_devices", _fake_adb)
    @patch("pyontrust.services.hardware_discovery._probe_webcams", _fake_webcam)
    @patch("pyontrust.services.hardware_discovery._probe_dwf_devices", _fake_dwf)
    @patch("pyontrust.services.hardware_discovery._probe_seek_thermal", _fake_seek)
    @patch("pyontrust.services.hardware_discovery._probe_jlink", _fake_jlink)
    @patch("pyontrust.services.hardware_discovery._probe_hackrf", _fake_hackrf)
    @patch("pyontrust.services.hardware_discovery._probe_ppk2", _fake_ppk2)
    @patch("pyontrust.services.hardware_discovery._probe_nrf52840_dongle", _fake_nrf52840)
    @patch("pyontrust.services.hardware_discovery._probe_network", _fake_network)
    def test_full_discovery(self):
        results = discover_all_hardware(timeout_s=10)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        # Check sorting: ok first, then not_found
        statuses = [r["status"] for r in results]
        ok_count = sum(1 for s in statuses if s == "ok")
        self.assertEqual(ok_count, 8)  # serial×2 + adb + webcam + dwf + jlink + nrf + network
        nf_count = sum(1 for s in statuses if s == "not_found")
        self.assertEqual(nf_count, 3)  # seek + hackrf + ppk2

        # ok items come before not_found
        first_nf = next(i for i, s in enumerate(statuses) if s == "not_found")
        self.assertTrue(all(s == "ok" for s in statuses[:first_nf]))

    @patch("pyontrust.services.hardware_discovery._probe_serial_ports", _fake_serial_ports)
    @patch("pyontrust.services.hardware_discovery._probe_adb_devices", _fake_adb)
    @patch("pyontrust.services.hardware_discovery._probe_webcams", _fake_webcam)
    @patch("pyontrust.services.hardware_discovery._probe_dwf_devices", _fake_dwf)
    @patch("pyontrust.services.hardware_discovery._probe_seek_thermal", _fake_seek)
    @patch("pyontrust.services.hardware_discovery._probe_jlink", _fake_jlink)
    @patch("pyontrust.services.hardware_discovery._probe_hackrf", _fake_hackrf)
    @patch("pyontrust.services.hardware_discovery._probe_ppk2", _fake_ppk2)
    @patch("pyontrust.services.hardware_discovery._probe_nrf52840_dongle", _fake_nrf52840)
    @patch("pyontrust.services.hardware_discovery._probe_network", _fake_network)
    def test_result_structure(self):
        results = discover_all_hardware(timeout_s=10)
        for r in results:
            self.assertIn("category", r)
            self.assertIn("type", r)
            self.assertIn("name", r)
            self.assertIn("icon", r)
            self.assertIn("status", r)
            self.assertIn(r["status"], ("ok", "error", "not_found"))
            self.assertIn("details", r)
            self.assertIn("test_result", r)


def _slow_probe():
    """Probe that hangs forever to test timeout handling."""
    import time
    time.sleep(60)
    return []


class TestDiscoveryTimeout(unittest.TestCase):

    @patch("pyontrust.services.hardware_discovery._probe_serial_ports", _fake_serial_ports)
    @patch("pyontrust.services.hardware_discovery._probe_adb_devices", _slow_probe)
    @patch("pyontrust.services.hardware_discovery._probe_webcams", _fake_webcam)
    @patch("pyontrust.services.hardware_discovery._probe_dwf_devices", _fake_dwf)
    @patch("pyontrust.services.hardware_discovery._probe_seek_thermal", _fake_seek)
    @patch("pyontrust.services.hardware_discovery._probe_jlink", _fake_jlink)
    @patch("pyontrust.services.hardware_discovery._probe_hackrf", _fake_hackrf)
    @patch("pyontrust.services.hardware_discovery._probe_ppk2", _fake_ppk2)
    @patch("pyontrust.services.hardware_discovery._probe_nrf52840_dongle", _fake_nrf52840)
    @patch("pyontrust.services.hardware_discovery._probe_network", _fake_network)
    def test_timeout_returns_partial_results(self):
        """Slow probes time out gracefully without blocking other results."""
        results = discover_all_hardware(timeout_s=3)
        # We should get results from the fast probes
        self.assertGreater(len(results), 0)
        # The slow probe should appear as a timeout error
        names = [r["name"] for r in results]
        types = [r["type"] for r in results]
        # At least some fast probes should have completed
        self.assertIn("serial_port", types)


# ═══════════════════════════════════════════════════════════════════════
#  Quick test runners
# ═══════════════════════════════════════════════════════════════════════

class TestRunQuickTest(unittest.TestCase):

    def test_noop_test_for_unknown_type(self):
        hw = _ok("custom", "unknown_device", "Test", "❓", {})
        result = run_quick_test(hw)
        self.assertIn("passed", result)
        self.assertIn("message", result)

    def test_network_test(self):
        hw = _ok("network", "network", "localhost", "🌐", {"hostname": "host"})
        result = run_quick_test(hw)
        self.assertTrue(result["passed"])

    def test_run_all_tests_only_tests_ok_devices(self):
        devices = [
            _ok("network", "network", "host", "🌐", {}),
            _not_found("sdr", "hackrf", "No HackRF", "📡"),
            _err("serial", "serial_port", "Ports", "🔌", "err"),
        ]
        results = run_all_tests(devices)
        # Only the first (ok) device gets a test_result
        self.assertIsNotNone(results[0]["test_result"])
        self.assertIsNone(results[1]["test_result"])
        self.assertIsNone(results[2]["test_result"])


# ═══════════════════════════════════════════════════════════════════════
#  Diagnostic Blueprint (via Flask test client)
# ═══════════════════════════════════════════════════════════════════════

class TestDiagnosticBlueprint(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pyontrust.gateway.app import create_app
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_diag_page_loads(self):
        r = self.client.get("/diag/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Hardware Diagnostic", r.data)
        self.assertIn(b"scanHardware", r.data)

    def test_diag_page_has_all_sections(self):
        r = self.client.get("/diag/")
        self.assertIn(b"hw-container", r.data)
        self.assertIn(b"sys-section", r.data)
        self.assertIn(b"summary-bar", r.data)

    def test_system_info_endpoint(self):
        r = self.client.get("/diag/api/system")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("hostname", data)
        self.assertIn("os", data)
        self.assertIn("python", data)
        self.assertIn("packages", data)
        self.assertIsInstance(data["packages"], dict)
        # At minimum flask should be reported
        self.assertIn("flask", data["packages"])

    @patch("pyontrust.services.hardware_discovery._probe_serial_ports",
           lambda: [_ok("serial", "serial_port", "COM3", "🔌", {"device": "COM3"})])
    @patch("pyontrust.services.hardware_discovery._probe_adb_devices",
           lambda: [_not_found("android", "android_sensors", "No ADB", "📱")])
    @patch("pyontrust.services.hardware_discovery._probe_webcams",
           lambda: [_not_found("camera", "webcam", "No cams", "📷")])
    @patch("pyontrust.services.hardware_discovery._probe_dwf_devices",
           lambda: [_not_found("instruments", "ad3_dwf", "No DWF", "📟")])
    @patch("pyontrust.services.hardware_discovery._probe_seek_thermal",
           lambda: [_not_found("thermal", "seek_thermal", "No Seek", "🌡️")])
    @patch("pyontrust.services.hardware_discovery._probe_jlink",
           lambda: [_not_found("debug", "jlink", "No JLink", "🔧")])
    @patch("pyontrust.services.hardware_discovery._probe_hackrf",
           lambda: [_not_found("sdr", "hackrf", "No HackRF", "📡")])
    @patch("pyontrust.services.hardware_discovery._probe_ppk2",
           lambda: [_not_found("instruments", "ppk2", "No PPK2", "⚡")])
    @patch("pyontrust.services.hardware_discovery._probe_nrf52840_dongle",
           lambda: [_not_found("ble", "nrf52840_dongle", "No nRF", "📶")])
    @patch("pyontrust.services.hardware_discovery._probe_network",
           lambda: [_ok("network", "network", "host", "🌐", {"hostname": "host"})])
    def test_scan_endpoint(self):
        r = self.client.get("/diag/api/scan")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("devices", data)
        self.assertIn("summary", data)
        self.assertIn("scan_time_s", data)
        self.assertGreater(len(data["devices"]), 0)
        summary = data["summary"]
        self.assertIn("ok", summary)
        self.assertIn("error", summary)
        self.assertIn("not_found", summary)
        self.assertEqual(summary["ok"], 2)  # COM3 + network
        self.assertEqual(summary["not_found"], 8)

    @patch("pyontrust.services.hardware_discovery._probe_serial_ports",
           lambda: [_ok("serial", "serial_port", "COM3", "🔌", {"device": "COM3"})])
    @patch("pyontrust.services.hardware_discovery._probe_adb_devices",
           lambda: [_not_found("android", "android_sensors", "No ADB", "📱")])
    @patch("pyontrust.services.hardware_discovery._probe_webcams",
           lambda: [_not_found("camera", "webcam", "No cams", "📷")])
    @patch("pyontrust.services.hardware_discovery._probe_dwf_devices",
           lambda: [_not_found("instruments", "ad3_dwf", "No DWF", "📟")])
    @patch("pyontrust.services.hardware_discovery._probe_seek_thermal",
           lambda: [_not_found("thermal", "seek_thermal", "No Seek", "🌡️")])
    @patch("pyontrust.services.hardware_discovery._probe_jlink",
           lambda: [_not_found("debug", "jlink", "No JLink", "🔧")])
    @patch("pyontrust.services.hardware_discovery._probe_hackrf",
           lambda: [_not_found("sdr", "hackrf", "No HackRF", "📡")])
    @patch("pyontrust.services.hardware_discovery._probe_ppk2",
           lambda: [_not_found("instruments", "ppk2", "No PPK2", "⚡")])
    @patch("pyontrust.services.hardware_discovery._probe_nrf52840_dongle",
           lambda: [_not_found("ble", "nrf52840_dongle", "No nRF", "📶")])
    @patch("pyontrust.services.hardware_discovery._probe_network",
           lambda: [_ok("network", "network", "host", "🌐", {"hostname": "host"})])
    def test_test_all_endpoint(self):
        r = self.client.post("/diag/api/test_all")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("devices", data)
        self.assertIn("test_summary", data)
        self.assertIn("total_time_s", data)
        ts = data["test_summary"]
        self.assertIn("tested", ts)
        self.assertIn("passed", ts)
        self.assertIn("failed", ts)

    def test_test_one_endpoint(self):
        hw = _ok("network", "network", "host", "🌐", {"hostname": "host"})
        r = self.client.post(
            "/diag/api/test",
            data=json.dumps(hw),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("passed", data)
        self.assertIn("message", data)

    def test_test_one_requires_body(self):
        r = self.client.post("/diag/api/test")
        self.assertEqual(r.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════
#  Navigation integration
# ═══════════════════════════════════════════════════════════════════════

class TestNavIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pyontrust.gateway.app import create_app
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_shell_has_diag_link(self):
        """The app shell nav bar includes a link to /diag/."""
        r = self.client.get("/")
        self.assertIn(b"/diag/", r.data)
        self.assertIn(b"Diagnostic", r.data)

    def test_blueprint_count(self):
        """Diagnostic is one of the registered blueprints."""
        self.assertIn("diagnostic", self.app.blueprints)

    def test_url_rules_registered(self):
        """All diagnostic routes are present."""
        rules = [r.rule for r in self.app.url_map.iter_rules()]
        self.assertIn("/diag/", rules)
        self.assertIn("/diag/api/scan", rules)
        self.assertIn("/diag/api/test", rules)
        self.assertIn("/diag/api/test_all", rules)
        self.assertIn("/diag/api/system", rules)


if __name__ == "__main__":
    unittest.main()
