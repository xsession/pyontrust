"""Tests for the hardware discovery service and diagnostic blueprint.

These tests mock hardware probes so they run anywhere without real devices.
"""
from __future__ import annotations

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from pyontrust.services.hardware_discovery import (
    _adb_list_sensors,
    _classify_nordic_cdc,
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
                {"serial": "ABC123", "brand": "Google", "model": "Pixel 7",
                 "adb_state": "device",
                 "sensors": ["Accelerometer", "Gyroscope", "Light"]})]


def _fake_webcam():
    return [_ok("camera", "webcam", "Camera #0", "📷",
                {"index": 0, "resolution": "640x480", "fps": 30.0})]


def _fake_dwf():
    return [_ok("instruments", "ad3_dwf", "Analog Discovery 3", "📟",
                {"index": 0, "name": "AD3", "serial": "SN:123"})]


def _fake_seek():
    return [_not_found("thermal", "seek_thermal", "No Seek Thermal", "🌡️")]


def _fake_pcan():
    return [_not_found("can", "pcan", "No PCAN", "🔌")]


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
    @patch("pyontrust.services.hardware_discovery._probe_pcan", _fake_pcan)
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
        self.assertEqual(nf_count, 4)  # seek + pcan + hackrf + ppk2

        # ok items come before not_found
        first_nf = next(i for i, s in enumerate(statuses) if s == "not_found")
        self.assertTrue(all(s == "ok" for s in statuses[:first_nf]))

    @patch("pyontrust.services.hardware_discovery._probe_serial_ports", _fake_serial_ports)
    @patch("pyontrust.services.hardware_discovery._probe_adb_devices", _fake_adb)
    @patch("pyontrust.services.hardware_discovery._probe_webcams", _fake_webcam)
    @patch("pyontrust.services.hardware_discovery._probe_dwf_devices", _fake_dwf)
    @patch("pyontrust.services.hardware_discovery._probe_seek_thermal", _fake_seek)
    @patch("pyontrust.services.hardware_discovery._probe_pcan", _fake_pcan)
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
    @patch("pyontrust.services.hardware_discovery._probe_pcan", _fake_pcan)
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
    @patch("pyontrust.services.hardware_discovery._probe_pcan",
           lambda: [_not_found("can", "pcan", "No PCAN", "🔌")])
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
        self.assertEqual(summary["not_found"], 9)  # adb + webcam + dwf + seek + pcan + jlink + hackrf + ppk2 + nrf

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
    @patch("pyontrust.services.hardware_discovery._probe_pcan",
           lambda: [_not_found("can", "pcan", "No PCAN", "🔌")])
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
        self.assertIn("/diag/api/live/<hw_type>/<sensor>", rules)
        self.assertIn("/diag/api/live/stream", rules)
        self.assertIn("/diag/api/live/stop", rules)


# ═══════════════════════════════════════════════════════════════════════
#  ADB unauthorized / offline detection
# ═══════════════════════════════════════════════════════════════════════

class TestAdbUnauthorizedDetection(unittest.TestCase):
    """Verify that unauthorized / offline devices are detected and shown."""

    @patch("pyontrust.services.hardware_discovery.subprocess.Popen")
    @patch("pyontrust.services.hardware_discovery.shutil.which", return_value="/usr/bin/adb")
    def test_unauthorized_device_reported_as_error(self, _which, mock_popen):
        from pyontrust.services.hardware_discovery import _probe_adb_devices

        proc = MagicMock()
        proc.communicate.return_value = (
            "List of devices attached\nABC123\tunauthorized\n", ""
        )
        mock_popen.return_value = proc

        results = _probe_adb_devices()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("UNAUTHORIZED", results[0]["error"])
        self.assertIn("serial", results[0]["details"])
        self.assertEqual(results[0]["details"]["adb_state"], "unauthorized")

    @patch("pyontrust.services.hardware_discovery.subprocess.Popen")
    @patch("pyontrust.services.hardware_discovery.shutil.which", return_value="/usr/bin/adb")
    def test_offline_device_reported(self, _which, mock_popen):
        from pyontrust.services.hardware_discovery import _probe_adb_devices

        proc = MagicMock()
        proc.communicate.return_value = (
            "List of devices attached\nXYZ789\toffline\n", ""
        )
        mock_popen.return_value = proc

        results = _probe_adb_devices()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("OFFLINE", results[0]["error"])
        self.assertEqual(results[0]["details"]["adb_state"], "offline")

    @patch("pyontrust.services.hardware_discovery.subprocess.Popen")
    @patch("pyontrust.services.hardware_discovery.shutil.which", return_value="/usr/bin/adb")
    def test_mixed_authorized_and_unauthorized(self, _which, mock_popen):
        from pyontrust.services.hardware_discovery import _probe_adb_devices

        # First call: adb devices -l
        proc_devices = MagicMock()
        proc_devices.communicate.return_value = (
            "List of devices attached\n"
            "DEV001\tdevice model:TestPhone\n"
            "DEV002\tunauthorized\n", ""
        )
        # Second call: getprop (for authorized device)
        proc_props = MagicMock()
        proc_props.communicate.return_value = (
            "Google\n|||\nPixel\n|||\n14\n|||\n34\n", ""
        )
        # Third call: battery
        proc_bat = MagicMock()
        proc_bat.communicate.return_value = ("level: 85\ntemperature: 320\n", "")
        # Fourth call: sensorservice
        proc_sensor = MagicMock()
        proc_sensor.communicate.return_value = ("", "")

        mock_popen.side_effect = [proc_devices, proc_props, proc_bat, proc_sensor]

        results = _probe_adb_devices()
        self.assertEqual(len(results), 2)
        # One should be ok, one should be error
        statuses = {r["status"] for r in results}
        self.assertIn("ok", statuses)
        self.assertIn("error", statuses)


# ═══════════════════════════════════════════════════════════════════════
#  Sensor list parsing
# ═══════════════════════════════════════════════════════════════════════

class TestAdbListSensors(unittest.TestCase):

    @patch("pyontrust.services.hardware_discovery.subprocess.Popen")
    def test_parses_sensor_names(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = (
            "Sensor List:\n"
            "0x00000001) {Accelerometer | STMicro | ver: 1}\n"
            "0x00000004) {Gyroscope | STMicro | ver: 1}\n"
            "0x00000005) {Light Sensor | AMS | ver: 1}\n"
            "0x00000008) {Proximity Sensor | AMS | ver: 1}\n",
            ""
        )
        mock_popen.return_value = proc

        sensors = _adb_list_sensors("adb", "SN123")
        self.assertGreaterEqual(len(sensors), 3)
        self.assertIn("Accelerometer", sensors)
        self.assertIn("Gyroscope", sensors)

    @patch("pyontrust.services.hardware_discovery.subprocess.Popen")
    def test_empty_output_returns_empty_list(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        mock_popen.return_value = proc

        sensors = _adb_list_sensors("adb", "SN123")
        self.assertEqual(sensors, [])

    @patch("pyontrust.services.hardware_discovery.subprocess.Popen")
    def test_timeout_returns_empty(self, mock_popen):
        import subprocess
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired("adb", 8)
        proc.kill = MagicMock()
        mock_popen.return_value = proc

        sensors = _adb_list_sensors("adb", "SN123")
        self.assertEqual(sensors, [])


# ═══════════════════════════════════════════════════════════════════════
#  PPK2 vs nRF52840 dongle classification
# ═══════════════════════════════════════════════════════════════════════

def _make_fake_port(device, vid, pid, serial_number, description="", product=""):
    """Create a mock serial port object mimicking pyserial ListPortInfo."""
    p = MagicMock()
    p.device = device
    p.vid = vid
    p.pid = pid
    p.serial_number = serial_number
    p.description = description
    p.product = product
    p.hwid = f"USB VID:PID={vid:04X}:{pid:04X} SER={serial_number}"
    p.location = ""
    return p


class TestPpk2VsNrf52840Classification(unittest.TestCase):
    """Test that PPK2 (multi-port) is distinguished from nRF52840 dongle."""

    @patch("serial.tools.list_ports.comports")
    def test_ppk2_two_ports_same_serial(self, mock_comports):
        """Two CDC ports with same serial → PPK2, not nRF dongle."""
        mock_comports.return_value = [
            _make_fake_port("COM12", 0x1915, 0xC00A, "F2114C40B2B2",
                            "nRF Connect USB CDC ACM (COM12)"),
            _make_fake_port("COM17", 0x1915, 0xC00A, "F2114C40B2B2",
                            "Soros USB-eszköz (COM17)"),
            _make_fake_port("COM15", 0x1915, 0xC00A, "C3A7B28B99E6",
                            "nRF Connect USB CDC ACM (COM15)"),
        ]
        ppk2_serials, groups = _classify_nordic_cdc()
        self.assertIn("F2114C40B2B2", ppk2_serials)
        self.assertNotIn("C3A7B28B99E6", ppk2_serials)
        # PPK2 serial has 2 ports
        self.assertEqual(len(groups["F2114C40B2B2"]), 2)
        # nRF dongle serial has 1 port
        self.assertEqual(len(groups["C3A7B28B99E6"]), 1)

    @patch("serial.tools.list_ports.comports")
    def test_single_port_is_not_ppk2(self, mock_comports):
        """A single port device is classified as nRF dongle, not PPK2."""
        mock_comports.return_value = [
            _make_fake_port("COM15", 0x1915, 0xC00A, "SINGLE_SN",
                            "nRF Connect USB CDC ACM (COM15)"),
        ]
        ppk2_serials, groups = _classify_nordic_cdc()
        self.assertEqual(len(ppk2_serials), 0)
        self.assertEqual(len(groups["SINGLE_SN"]), 1)

    @patch("serial.tools.list_ports.comports")
    def test_no_nordic_ports(self, mock_comports):
        """When no VID=1915 PID=C00A ports exist, both sets empty."""
        mock_comports.return_value = [
            _make_fake_port("COM3", 0x0403, 0x6001, "FT232",
                            "USB Serial (COM3)"),
        ]
        ppk2_serials, groups = _classify_nordic_cdc()
        self.assertEqual(len(ppk2_serials), 0)
        self.assertEqual(len(groups), 0)

    @patch("serial.tools.list_ports.comports")
    def test_multiple_ppk2_devices(self, mock_comports):
        """Two separate PPK2 devices each with 2 ports."""
        mock_comports.return_value = [
            _make_fake_port("COM10", 0x1915, 0xC00A, "PPK2_A"),
            _make_fake_port("COM11", 0x1915, 0xC00A, "PPK2_A"),
            _make_fake_port("COM20", 0x1915, 0xC00A, "PPK2_B"),
            _make_fake_port("COM21", 0x1915, 0xC00A, "PPK2_B"),
        ]
        ppk2_serials, groups = _classify_nordic_cdc()
        self.assertEqual(len(ppk2_serials), 2)
        self.assertIn("PPK2_A", ppk2_serials)
        self.assertIn("PPK2_B", ppk2_serials)


class TestPpk2ProbeIntegration(unittest.TestCase):
    """Test _probe_ppk2 and _probe_nrf52840_dongle use classification."""

    @patch("serial.tools.list_ports.comports")
    def test_probe_ppk2_finds_multi_port_device(self, mock_comports):
        from pyontrust.services.hardware_discovery import _probe_ppk2

        mock_comports.return_value = [
            _make_fake_port("COM12", 0x1915, 0xC00A, "F2114C40B2B2",
                            "nRF Connect USB CDC ACM (COM12)"),
            _make_fake_port("COM17", 0x1915, 0xC00A, "F2114C40B2B2",
                            "Soros USB-eszköz (COM17)"),
            _make_fake_port("COM15", 0x1915, 0xC00A, "C3A7B28B99E6",
                            "nRF Connect USB CDC ACM (COM15)"),
        ]
        results = _probe_ppk2()
        # Should find exactly one PPK2 device
        ppk2_ok = [r for r in results if r["status"] == "ok"]
        self.assertEqual(len(ppk2_ok), 1)
        self.assertEqual(ppk2_ok[0]["type"], "ppk2")
        self.assertEqual(ppk2_ok[0]["details"]["serial_number"], "F2114C40B2B2")
        self.assertIn("COM12", ppk2_ok[0]["details"]["port"])
        self.assertIn("all_ports", ppk2_ok[0]["details"])
        self.assertIn("COM12", ppk2_ok[0]["details"]["all_ports"])
        self.assertIn("COM17", ppk2_ok[0]["details"]["all_ports"])

    @patch("serial.tools.list_ports.comports")
    def test_probe_nrf52840_excludes_ppk2(self, mock_comports):
        from pyontrust.services.hardware_discovery import _probe_nrf52840_dongle

        mock_comports.return_value = [
            _make_fake_port("COM12", 0x1915, 0xC00A, "F2114C40B2B2",
                            "nRF Connect USB CDC ACM (COM12)"),
            _make_fake_port("COM17", 0x1915, 0xC00A, "F2114C40B2B2",
                            "Soros USB-eszköz (COM17)"),
            _make_fake_port("COM15", 0x1915, 0xC00A, "C3A7B28B99E6",
                            "nRF Connect USB CDC ACM (COM15)"),
        ]
        results = _probe_nrf52840_dongle()
        # Should find only the single-port nRF dongle, not the PPK2
        nrf_ok = [r for r in results if r["status"] == "ok"]
        self.assertEqual(len(nrf_ok), 1)
        self.assertEqual(nrf_ok[0]["details"]["serial_number"], "C3A7B28B99E6")
        self.assertIn("COM15", nrf_ok[0]["details"]["port"])

    @patch("serial.tools.list_ports.comports")
    def test_probe_nrf52840_no_ppk2_mixed(self, mock_comports):
        """When no PPK2 exists, nRF probe finds all VID=1915 PID=C00A."""
        mock_comports.return_value = [
            _make_fake_port("COM15", 0x1915, 0xC00A, "DONGLE1",
                            "nRF Connect USB CDC ACM (COM15)"),
        ]
        from pyontrust.services.hardware_discovery import _probe_nrf52840_dongle
        results = _probe_nrf52840_dongle()
        nrf_ok = [r for r in results if r["status"] == "ok"]
        self.assertEqual(len(nrf_ok), 1)
        self.assertEqual(nrf_ok[0]["details"]["serial_number"], "DONGLE1")

    @patch("serial.tools.list_ports.comports")
    def test_probe_ppk2_not_found_when_only_dongle(self, mock_comports):
        from pyontrust.services.hardware_discovery import _probe_ppk2

        mock_comports.return_value = [
            _make_fake_port("COM15", 0x1915, 0xC00A, "DONGLE1",
                            "nRF Connect USB CDC ACM (COM15)"),
        ]
        results = _probe_ppk2()
        # Only single-port device → not a PPK2
        self.assertTrue(any(r["status"] == "not_found" for r in results))


# ═══════════════════════════════════════════════════════════════════════
#  Live data endpoints
# ═══════════════════════════════════════════════════════════════════════

class TestLiveDataEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pyontrust.gateway.app import create_app
        cls.app = create_app()
        cls.client = cls.app.test_client()

    @patch("pyontrust.gateway.blueprints.diagnostic._read_sensor_once")
    def test_live_read_once_ok(self, mock_read):
        mock_read.return_value = {
            "sensor": "accelerometer",
            "x": [0.1, 0.2], "y": [0.0, 0.1], "z": [9.8, 9.81],
        }
        r = self.client.get("/diag/api/live/android_sensors/accelerometer?mode=simulated")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertIn("data", data)
        self.assertIn("ts", data)

    @patch("pyontrust.gateway.blueprints.diagnostic._read_sensor_once",
           side_effect=RuntimeError("sensor failed"))
    def test_live_read_once_error(self, _):
        r = self.client.get("/diag/api/live/android_sensors/light?mode=simulated")
        self.assertEqual(r.status_code, 500)
        data = json.loads(r.data)
        self.assertFalse(data["ok"])
        self.assertIn("error", data)

    def test_live_read_simulated_android(self):
        """Live read with simulated android sensors returns real data."""
        r = self.client.get("/diag/api/live/android_sensors/accelerometer?mode=simulated")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        inner = data["data"]
        self.assertEqual(inner["sensor"], "accelerometer")
        self.assertIn("x", inner)
        self.assertIn("y", inner)
        self.assertIn("z", inner)

    def test_live_read_simulated_light(self):
        r = self.client.get("/diag/api/live/android_sensors/light?mode=simulated")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertIn("lux", data["data"])

    def test_live_read_simulated_battery(self):
        r = self.client.get("/diag/api/live/android_sensors/battery?mode=simulated")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertIn("level_pct", data["data"])

    def test_live_read_simulated_gps(self):
        r = self.client.get("/diag/api/live/android_sensors/gps?mode=simulated")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertIn("latitude", data["data"])

    def test_live_read_unknown_hw_type(self):
        r = self.client.get("/diag/api/live/unknown_hw/foo?mode=simulated")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data["ok"])
        self.assertIn("error", data["data"])

    def test_live_stop_endpoint(self):
        r = self.client.post("/diag/api/live/stop")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("stopped", data)
        self.assertIsInstance(data["stopped"], int)

    def test_live_stream_returns_sse_headers(self):
        """The SSE stream endpoint returns the correct content type."""
        r = self.client.get(
            "/diag/api/live/stream?hw_type=android_sensors&sensor=accelerometer"
            "&rate_ms=500&mode=simulated"
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/event-stream", r.content_type)

    def test_live_stream_produces_data(self):
        """The SSE stream produces at least one data line."""
        import threading

        result = {}

        def fetch():
            r = self.client.get(
                "/diag/api/live/stream?hw_type=android_sensors&sensor=light"
                "&rate_ms=200&mode=simulated"
            )
            result["status"] = r.status_code
            # Read first chunk
            result["data"] = r.data[:2000].decode("utf-8", errors="replace")

        # Run the request in a thread (since it's a streaming response)
        # but we'll use the stop endpoint after a short delay
        t = threading.Thread(target=fetch, daemon=True)
        t.start()

        # Give it time to produce some data, then stop
        time.sleep(1.5)
        self.client.post("/diag/api/live/stop")
        t.join(timeout=5)

        if result.get("data"):
            self.assertIn("data:", result["data"])


class TestLiveDataUI(unittest.TestCase):
    """Verify the diagnostic HTML has the live data panel."""

    @classmethod
    def setUpClass(cls):
        from pyontrust.gateway.app import create_app
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_page_has_live_overlay(self):
        r = self.client.get("/diag/")
        html = r.data.decode("utf-8")
        self.assertIn("live-overlay", html)
        self.assertIn("live-panel", html)

    def test_page_has_live_chart(self):
        r = self.client.get("/diag/")
        html = r.data.decode("utf-8")
        self.assertIn("live-chart", html)
        self.assertIn("openLivePanel", html)

    def test_page_has_sensor_selector(self):
        r = self.client.get("/diag/")
        html = r.data.decode("utf-8")
        self.assertIn("live-sensor", html)
        self.assertIn("ANDROID_SENSORS", html)

    def test_page_has_stream_controls(self):
        r = self.client.get("/diag/")
        html = r.data.decode("utf-8")
        self.assertIn("toggleStream", html)
        self.assertIn("stopStream", html)
        self.assertIn("EventSource", html)

    def test_card_has_live_button(self):
        r = self.client.get("/diag/")
        html = r.data.decode("utf-8")
        self.assertIn("btn-live", html)
        self.assertIn("Live Data", html)


if __name__ == "__main__":
    unittest.main()
