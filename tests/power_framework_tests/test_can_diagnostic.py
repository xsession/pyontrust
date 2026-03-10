"""Tests for the CAN diagnostic service, CANopen decoder, RE helpers, and blueprint.

All tests are designed to run **without** real CAN hardware — they exercise
the pure-logic functions (CANopen decode, counter/CRC detection, DBC
generation, etc.) and the service's internal data structures.  Where the
service's ``start()`` path is needed we fall back to
``interface="virtual"`` which only requires ``python-can`` to be installed.
"""
from __future__ import annotations

import json
import pathlib
import struct
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


# ═════════════════════════════════════════════════════════════════════
#  CANopen decoder tests
# ═════════════════════════════════════════════════════════════════════

from pyontrust.services.can_service import (  # noqa: E402
    CanDiagService,
    CanOpenInfo,
    MsgStats,
    compute_bit_transitions,
    decode_canopen,
    extract_signals_heuristic,
    find_counter_bytes,
    find_crc_bytes,
    generate_dbc_stub,
)


class TestCanOpenDecoder(unittest.TestCase):
    """Unit tests for ``decode_canopen()``."""

    def test_nmt_start(self):
        info = decode_canopen(0x000, bytes([0x01, 0x05]))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "NMT")
        self.assertEqual(info.node_id, 5)
        self.assertIn("Start", info.detail)

    def test_nmt_reset_node(self):
        info = decode_canopen(0x000, bytes([0x81, 0x0A]))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "NMT")
        self.assertEqual(info.node_id, 10)
        self.assertIn("Reset Node", info.detail)

    def test_sync(self):
        info = decode_canopen(0x080, b"")
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "SYNC")
        self.assertEqual(info.detail, "SYNC")

    def test_heartbeat_operational(self):
        info = decode_canopen(0x705, bytes([0x05]))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "HEARTBEAT")
        self.assertIn("Operational", info.detail)

    def test_heartbeat_bootup(self):
        info = decode_canopen(0x701, bytes([0x00]))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "HEARTBEAT")
        self.assertIn("Boot-up", info.detail)

    def test_heartbeat_preop(self):
        info = decode_canopen(0x703, bytes([0x7F]))
        self.assertIsNotNone(info)
        self.assertIn("Pre-operational", info.detail)

    def test_emcy(self):
        # EMCY: error code 0x1234, error register 0x01
        data = struct.pack("<H", 0x1234) + bytes([0x01, 0, 0, 0, 0, 0])
        info = decode_canopen(0x081, data)
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "EMCY")
        self.assertIn("0x1234", info.detail)

    def test_sdo_rx_initiate_download(self):
        # SDO RX (client → server): cs=1 (initiate download), index 0x6040, sub 0x00
        data = bytes([0x22]) + struct.pack("<H", 0x6040) + bytes([0x00, 0, 0, 0, 0])
        info = decode_canopen(0x600, data)
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "SDO_RX")
        self.assertIn("Initiate download", info.detail)
        self.assertIn("6040", info.detail)

    def test_sdo_tx_upload_response(self):
        # SDO TX (server → client): cs=2 (initiate upload)
        data = bytes([0x43]) + struct.pack("<H", 0x1018) + bytes([0x01, 0x00, 0x00, 0x00, 0x00])
        info = decode_canopen(0x580, data)
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "SDO_TX")
        self.assertIn("Initiate upload", info.detail)

    def test_pdo1_tx(self):
        data = bytes([0xAA, 0xBB, 0xCC, 0xDD])
        info = decode_canopen(0x181, data)
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "PDO1_TX")
        self.assertIn("PDO1_TX", info.detail)

    def test_pdo2_rx(self):
        info = decode_canopen(0x305, bytes(8))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "PDO2_RX")

    def test_pdo3_tx(self):
        info = decode_canopen(0x380, bytes(4))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "PDO3_TX")

    def test_pdo4_tx(self):
        info = decode_canopen(0x480, bytes(2))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "PDO4_TX")

    def test_timestamp(self):
        data = bytes(6)
        info = decode_canopen(0x100, data)
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "TIMESTAMP")
        self.assertIn("TIME", info.detail)

    def test_lss_tx(self):
        info = decode_canopen(0x7E4, bytes(8))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "LSS_TX")

    def test_lss_rx(self):
        info = decode_canopen(0x7E5, bytes(8))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "LSS_RX")

    def test_non_canopen_returns_none(self):
        # 0x7FF is not a standard CANopen COB-ID
        info = decode_canopen(0x7FF, bytes(8))
        self.assertIsNone(info)

    def test_standard_canopen_id_returns_none_for_high_id(self):
        info = decode_canopen(0x800, bytes(8))
        self.assertIsNone(info)

    def test_nmt_short_data(self):
        # NMT with only 1 byte — shouldn't crash
        info = decode_canopen(0x000, bytes([0x01]))
        self.assertIsNotNone(info)
        self.assertEqual(info.function, "NMT")


# ═════════════════════════════════════════════════════════════════════
#  Reverse-engineering helper tests
# ═════════════════════════════════════════════════════════════════════

class TestFindCounterBytes(unittest.TestCase):
    def test_identifies_monotonic_counter(self):
        # Byte 0 increments by 1 each frame, byte 1 is static
        history = [bytes([i & 0xFF, 0x42, 0x00]) for i in range(50)]
        result = find_counter_bytes(history)
        self.assertIn(0, result)
        self.assertNotIn(1, result)
        self.assertNotIn(2, result)

    def test_wrapping_counter(self):
        # Counter wraps around 255→0
        history = [bytes([(200 + i) & 0xFF, 0x10]) for i in range(100)]
        result = find_counter_bytes(history)
        self.assertIn(0, result)

    def test_no_counters_in_static_data(self):
        history = [bytes([0x42, 0x42, 0x42]) for _ in range(50)]
        result = find_counter_bytes(history)
        self.assertEqual(result, [])

    def test_requires_minimum_samples(self):
        history = [bytes([i, 0]) for i in range(5)]
        result = find_counter_bytes(history)
        self.assertEqual(result, [])

    def test_counter_in_later_byte(self):
        history = [bytes([0xFF, 0xFF, i & 0xFF]) for i in range(50)]
        result = find_counter_bytes(history)
        self.assertIn(2, result)


class TestFindCrcBytes(unittest.TestCase):
    def test_identifies_high_entropy_byte(self):
        import random
        random.seed(42)
        # Byte 0 is a counter, byte 1 is random (high entropy), byte 2 is static
        history = []
        for i in range(60):
            history.append(bytes([i & 0xFF, random.randint(0, 255), 0xAA]))
        result = find_crc_bytes(history)
        self.assertIn(1, result)
        self.assertNotIn(0, result)  # counter, not CRC
        self.assertNotIn(2, result)  # static

    def test_no_crcs_in_static_data(self):
        history = [bytes([0x00, 0x00, 0x00]) for _ in range(50)]
        result = find_crc_bytes(history)
        self.assertEqual(result, [])


class TestComputeBitTransitions(unittest.TestCase):
    def test_static_byte_has_zero_transitions(self):
        history = [bytes([0xFF, 0x00]) for _ in range(20)]
        trans = compute_bit_transitions(history)
        self.assertEqual(len(trans), 2)
        self.assertEqual(trans[0], [0] * 8)
        self.assertEqual(trans[1], [0] * 8)

    def test_toggling_bit(self):
        # Bit 0 of byte 0 toggles every frame
        history = [bytes([i & 1, 0]) for i in range(20)]
        trans = compute_bit_transitions(history)
        self.assertEqual(trans[0][0], 19)  # 19 transitions for 20 frames
        self.assertEqual(trans[0][1], 0)   # higher bits never change
        self.assertEqual(trans[1][0], 0)   # second byte never changes

    def test_empty_history(self):
        result = compute_bit_transitions([])
        self.assertEqual(result, [])

    def test_single_frame(self):
        result = compute_bit_transitions([bytes([0x42])])
        self.assertEqual(result, [])


class TestExtractSignalsHeuristic(unittest.TestCase):
    def test_finds_multi_bit_signal(self):
        # Create a pattern where bits 0-7 (byte 0) change together
        history = [bytes([i & 0xFF, 0x00, 0x00]) for i in range(50)]
        signals = extract_signals_heuristic(history)
        # Should find at least one signal
        self.assertGreater(len(signals), 0)
        self.assertIn("start_byte", signals[0])
        self.assertIn("length_bits", signals[0])

    def test_insufficient_data(self):
        history = [bytes([i]) for i in range(5)]
        signals = extract_signals_heuristic(history)
        self.assertEqual(signals, [])


class TestGenerateDbcStub(unittest.TestCase):
    def test_generates_valid_dbc(self):
        stats = {
            0x100: MsgStats(arb_id=0x100, count=50, dlc=8),
            0x200: MsgStats(arb_id=0x200, count=30, dlc=4),
        }
        history = {
            0x100: [bytes([i & 0xFF, 0, 0, 0, 0, 0, 0, 0]) for i in range(50)],
            0x200: [bytes([0, 0, 0, 0]) for _ in range(30)],
        }
        dbc = generate_dbc_stub(stats, history)
        self.assertIn('VERSION ""', dbc)
        self.assertIn("BO_ 256 MSG_0x100", dbc)
        self.assertIn("BO_ 512 MSG_0x200", dbc)

    def test_empty_traffic(self):
        dbc = generate_dbc_stub({}, {})
        self.assertIn('VERSION ""', dbc)


# ═════════════════════════════════════════════════════════════════════
#  CAN Diagnostic Service tests (no hardware)
# ═════════════════════════════════════════════════════════════════════

class TestCanDiagServiceNoHardware(unittest.TestCase):
    """Tests that exercise the service without starting a real bus."""

    def setUp(self):
        self.svc = CanDiagService()

    def test_initial_state(self):
        self.assertFalse(self.svc.is_running)
        snap = self.svc.get_snapshot()
        self.assertFalse(snap["running"])
        self.assertEqual(snap["total_frames"], 0)
        self.assertEqual(snap["unique_ids"], 0)

    def test_stop_without_start(self):
        result = self.svc.stop()
        self.assertTrue(result["ok"])

    def test_clear(self):
        self.svc.clear()
        snap = self.svc.get_snapshot()
        self.assertEqual(snap["total_frames"], 0)

    def test_send_frame_without_bus(self):
        result = self.svc.send_frame(0x100, bytes(8))
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    def test_set_id_filter(self):
        self.svc.set_id_filter([0x100, 0x200])
        self.assertEqual(self.svc._id_filter, {0x100, 0x200})

    def test_set_id_filter_none(self):
        self.svc.set_id_filter(None)
        self.assertIsNone(self.svc._id_filter)

    def test_set_mask_filter(self):
        self.svc.set_mask_filter(0x100, 0x7F0)
        self.assertEqual(self.svc._id_mask_filter, (0x100, 0x7F0))

    def test_clear_filters(self):
        self.svc.set_id_filter([0x100])
        self.svc.set_mask_filter(0x100, 0x7F0)
        self.svc.clear_filters()
        self.assertIsNone(self.svc._id_filter)
        self.assertIsNone(self.svc._id_mask_filter)

    def test_get_stats_table_empty(self):
        rows = self.svc.get_stats_table()
        self.assertEqual(rows, [])

    def test_analyze_nonexistent_id(self):
        result = self.svc.analyze_message(0x999)
        self.assertIn("error", result)

    def test_generate_dbc_empty(self):
        dbc = self.svc.generate_dbc()
        self.assertIn('VERSION ""', dbc)

    def test_export_csv_empty(self):
        csv_str = self.svc.export_log("csv")
        self.assertIn("timestamp,id,dlc,data,canopen", csv_str)

    def test_export_asc_empty(self):
        asc = self.svc.export_log("asc")
        self.assertIn("base hex", asc)

    def test_double_stop(self):
        result1 = self.svc.stop()
        result2 = self.svc.stop()
        self.assertTrue(result1["ok"])
        self.assertTrue(result2["ok"])


class TestCanDiagServiceUpdateStats(unittest.TestCase):
    """Test internal _update_stats() by calling it directly."""

    def setUp(self):
        self.svc = CanDiagService()

    def test_first_message_creates_stats(self):
        with self.svc._lock:
            self.svc._update_stats(0x100, bytes(8), 1.0, 8, False)
        self.assertIn(0x100, self.svc._stats)
        self.assertEqual(self.svc._stats[0x100].count, 1)
        self.assertEqual(self.svc._stats[0x100].dlc, 8)

    def test_period_tracking(self):
        with self.svc._lock:
            self.svc._update_stats(0x100, bytes(8), 1.0, 8, False)
            self.svc._update_stats(0x100, bytes(8), 1.01, 8, False)
            self.svc._update_stats(0x100, bytes(8), 1.02, 8, False)
        st = self.svc._stats[0x100]
        self.assertGreater(st.period_s, 0)
        self.assertEqual(st.count, 3)

    def test_byte_change_mask(self):
        with self.svc._lock:
            self.svc._update_stats(0x100, bytes([0x00, 0x00]), 1.0, 2, False)
            self.svc._update_stats(0x100, bytes([0x01, 0x00]), 1.01, 2, False)
        st = self.svc._stats[0x100]
        # Byte 0 changed, byte 1 didn't
        self.assertEqual(st.byte_change_mask & 0x01, 1)
        self.assertEqual(st.byte_change_mask & 0x02, 0)

    def test_history_accumulation(self):
        with self.svc._lock:
            for i in range(10):
                self.svc._update_stats(0x200, bytes([i]), float(i), 1, False)
        self.assertEqual(len(self.svc._history[0x200]), 10)

    def test_history_cap(self):
        from pyontrust.services.can_service import _MAX_HISTORY
        with self.svc._lock:
            for i in range(250):
                self.svc._update_stats(0x300, bytes([i & 0xFF]), float(i), 1, False)
        self.assertLessEqual(len(self.svc._history[0x300]), _MAX_HISTORY)

    def test_jitter_computation(self):
        with self.svc._lock:
            self.svc._update_stats(0x100, bytes(8), 1.0, 8, False)
            self.svc._update_stats(0x100, bytes(8), 1.010, 8, False)
            self.svc._update_stats(0x100, bytes(8), 1.025, 8, False)
        st = self.svc._stats[0x100]
        self.assertGreater(st.jitter_s, 0)
        self.assertAlmostEqual(st.min_period_s, 0.010, places=3)
        self.assertAlmostEqual(st.max_period_s, 0.015, places=3)


class TestCanDiagServiceAnalyze(unittest.TestCase):
    """Test analyze_message() with synthetic data."""

    def test_analyze_with_counter(self):
        svc = CanDiagService()
        with svc._lock:
            for i in range(60):
                data = bytes([i & 0xFF, 0x42, 0x00, 0x00])
                svc._update_stats(0x100, data, float(i) * 0.01, 4, False)
        analysis = svc.analyze_message(0x100)
        self.assertEqual(analysis["arb_id"], 0x100)
        self.assertIn(0, analysis["counter_bytes"])  # byte 0 is counter
        self.assertGreater(analysis["sample_count"], 0)
        self.assertIn("byte_ranges", analysis)
        self.assertIn("bit_transitions", analysis)
        self.assertIn("signals", analysis)

    def test_analyze_byte_ranges(self):
        svc = CanDiagService()
        with svc._lock:
            for i in range(30):
                data = bytes([i, 0xFF, 0x00])
                svc._update_stats(0x200, data, float(i) * 0.01, 3, False)
        analysis = svc.analyze_message(0x200)
        ranges = analysis["byte_ranges"]
        self.assertEqual(len(ranges), 3)
        # byte 0: min=0 max=29
        self.assertEqual(ranges[0]["min"], 0)
        self.assertEqual(ranges[0]["max"], 29)
        self.assertFalse(ranges[0]["is_static"])
        # byte 1: always 0xFF
        self.assertTrue(ranges[1]["is_static"])
        # byte 2: always 0x00
        self.assertTrue(ranges[2]["is_static"])


class TestCanDiagServiceExport(unittest.TestCase):
    """Test export functions with synthetic ring buffer data."""

    def setUp(self):
        self.svc = CanDiagService()
        # Manually populate ring buffer
        for i in range(5):
            self.svc._ring.append({
                "ts": 1000.0 + i * 0.01,
                "id": 0x100,
                "hex_id": "0x100",
                "dlc": 4,
                "data": "DE AD BE EF",
                "ext": False,
                "canopen": "PDO1_TX",
                "canopen_detail": "PDO1_TX Node 0: DE AD BE EF",
            })

    def test_csv_export(self):
        csv_str = self.svc.export_log("csv")
        lines = csv_str.strip().split("\n")
        self.assertEqual(len(lines), 6)  # header + 5 data
        self.assertIn("timestamp,id,dlc,data,canopen", lines[0])
        self.assertIn("0x100", lines[1])

    def test_asc_export(self):
        asc = self.svc.export_log("asc")
        self.assertIn("base hex", asc)
        self.assertIn("0x100", asc)

    def test_generate_dbc_with_data(self):
        with self.svc._lock:
            for i in range(50):
                self.svc._update_stats(0x100, bytes([i & 0xFF, 0, 0, 0]),
                                       float(i) * 0.01, 4, False)
        dbc = self.svc.generate_dbc()
        self.assertIn("BO_ 256 MSG_0x100", dbc)


# ═════════════════════════════════════════════════════════════════════
#  CAN Diagnostic Service with virtual bus
# ═════════════════════════════════════════════════════════════════════

class TestCanDiagServiceVirtualBus(unittest.TestCase):
    """Tests using python-can's virtual interface (no hardware needed)."""

    def _has_python_can(self) -> bool:
        try:
            import can  # noqa: F401
            return True
        except ImportError:
            return False

    def test_start_stop_virtual(self):
        if not self._has_python_can():
            self.skipTest("python-can not installed")
        svc = CanDiagService()
        result = svc.start(interface="virtual", channel="vtest0", bitrate=500000)
        self.assertTrue(result["ok"], result)
        self.assertTrue(svc.is_running)
        result = svc.stop()
        self.assertTrue(result["ok"])
        self.assertFalse(svc.is_running)

    def test_start_already_running(self):
        if not self._has_python_can():
            self.skipTest("python-can not installed")
        svc = CanDiagService()
        svc.start(interface="virtual", channel="vtest1", bitrate=500000)
        result = svc.start(interface="virtual", channel="vtest1", bitrate=500000)
        self.assertFalse(result["ok"])
        self.assertIn("Already running", result["error"])
        svc.stop()

    def test_send_and_receive_virtual(self):
        if not self._has_python_can():
            self.skipTest("python-can not installed")
        import can

        svc = CanDiagService()
        svc.start(interface="virtual", channel="vloopback0", bitrate=500000)
        time.sleep(0.1)

        # Send a frame from a separate bus on the same virtual channel
        sender = can.Bus(interface="virtual", channel="vloopback0")
        sender.send(can.Message(arbitration_id=0x123, data=bytes([0xDE, 0xAD])))
        sender.send(can.Message(arbitration_id=0x456, data=bytes([0xBE, 0xEF])))
        time.sleep(0.3)

        snap = svc.get_snapshot()
        self.assertGreaterEqual(snap["total_frames"], 2)
        self.assertGreaterEqual(snap["unique_ids"], 2)

        stats = svc.get_stats_table()
        ids = {r["arb_id"] for r in stats}
        self.assertIn(0x123, ids)
        self.assertIn(0x456, ids)

        sender.shutdown()
        svc.stop()

    def test_id_filter_virtual(self):
        if not self._has_python_can():
            self.skipTest("python-can not installed")
        import can

        svc = CanDiagService()
        svc.start(interface="virtual", channel="vfilt0", bitrate=500000)
        svc.set_id_filter([0x100])
        time.sleep(0.1)

        sender = can.Bus(interface="virtual", channel="vfilt0")
        sender.send(can.Message(arbitration_id=0x100, data=bytes(4)))
        sender.send(can.Message(arbitration_id=0x200, data=bytes(4)))
        time.sleep(0.3)

        snap = svc.get_snapshot()
        ids = {m["id"] for m in snap["messages"]}
        self.assertIn(0x100, ids)
        self.assertNotIn(0x200, ids)

        sender.shutdown()
        svc.stop()


# ═════════════════════════════════════════════════════════════════════
#  Blueprint API tests
# ═════════════════════════════════════════════════════════════════════

class TestCanDiagBlueprint(unittest.TestCase):
    """Test the Flask blueprint routes."""

    @classmethod
    def setUpClass(cls):
        try:
            from pyontrust.gateway.blueprints.can_diag import bp
            from flask import Flask
            cls.app = Flask(__name__)
            cls.app.register_blueprint(bp, url_prefix="/can")
            cls.client = cls.app.test_client()
            cls._available = True
        except ImportError:
            cls._available = False

    def _skip_if_no_flask(self):
        if not self._available:
            self.skipTest("Flask or can_diag blueprint not importable")

    def test_index_serves_html(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/")
        self.assertIn(resp.status_code, (200, 304))

    def test_status_endpoint(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("running", data)

    def test_stop_without_start(self):
        self._skip_if_no_flask()
        resp = self.client.post("/can/api/stop")
        self.assertEqual(resp.status_code, 200)

    def test_clear(self):
        self._skip_if_no_flask()
        resp = self.client.post("/can/api/clear")
        self.assertEqual(resp.status_code, 200)

    def test_snapshot(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/snapshot")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("messages", data)

    def test_stats(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("stats", data)
        self.assertIsInstance(data["stats"], list)

    def test_dbc(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/dbc")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("VERSION", resp.get_data(as_text=True))

    def test_export_csv(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/export/csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("timestamp", resp.get_data(as_text=True))

    def test_export_asc(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/export/asc")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("base hex", resp.get_data(as_text=True))

    def test_analyze_no_data(self):
        self._skip_if_no_flask()
        resp = self.client.get("/can/api/analyze/0x999")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_send_without_bus(self):
        self._skip_if_no_flask()
        resp = self.client.post("/can/api/send",
                                data=json.dumps({"arb_id": "0x100", "data": "DEADBEEF"}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Will fail because bus isn't started
        self.assertFalse(data.get("ok", True))

    def test_filter_set(self):
        self._skip_if_no_flask()
        resp = self.client.post("/can/api/filter",
                                data=json.dumps({"ids": [256, 512]}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)

    def test_filter_clear(self):
        self._skip_if_no_flask()
        resp = self.client.post("/can/api/filter",
                                data=json.dumps({"clear": True}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)


# ═════════════════════════════════════════════════════════════════════
#  FlowLab CAN block registration test
# ═════════════════════════════════════════════════════════════════════

class TestFlowLabCanBlocks(unittest.TestCase):
    def test_can_blocks_registered(self):
        from pyontrust.gateway.flowlab_engine import FlowLabEngine
        engine = FlowLabEngine()
        for btype in ["can_send", "can_receive", "can_decode",
                      "can_analyze", "can_replay"]:
            self.assertIn(btype, engine.block_registry,
                          f"{btype} not in FlowLabEngine.block_registry")


# ═════════════════════════════════════════════════════════════════════
#  Hardware discovery PCAN tests
# ═════════════════════════════════════════════════════════════════════

class TestPcanDiscovery(unittest.TestCase):
    def test_probe_pcan_returns_list(self):
        from pyontrust.services.hardware_discovery import _probe_pcan
        results = _probe_pcan()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Every item should have "status" key
        for r in results:
            self.assertIn("status", r)

    def test_pcan_in_test_runners(self):
        from pyontrust.services.hardware_discovery import _TEST_RUNNERS
        self.assertIn("pcan", _TEST_RUNNERS)

    def test_pcan_in_probes_list(self):
        """Verify discover_all_hardware includes the pcan probe."""
        import inspect
        from pyontrust.services.hardware_discovery import discover_all_hardware
        src = inspect.getsource(discover_all_hardware)
        self.assertIn("_probe_pcan", src)


# ═════════════════════════════════════════════════════════════════════
#  Blueprint registration test
# ═════════════════════════════════════════════════════════════════════

class TestBlueprintRegistration(unittest.TestCase):
    def test_can_blueprint_registered_in_app(self):
        try:
            from pyontrust.gateway.app import create_app
            app = create_app()
            bp_names = list(app.blueprints.keys())
            self.assertIn("can_diag", bp_names)
        except ImportError:
            self.skipTest("Flask app not importable")


if __name__ == "__main__":
    unittest.main()
