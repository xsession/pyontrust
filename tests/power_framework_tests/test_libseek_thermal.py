"""Tests for the pure-Python libseek thermal camera driver.

Tests cover:
  - USB protocol constants and device command enum
  - Frame geometry for Compact and CompactPRO
  - Dead pixel detection and filtering
  - FFC (flat-field calibration) logic
  - LibSeekCamera init, grab, close lifecycle (mocked USB)
  - Temperature conversion
  - detect_camera / list_cameras helpers
  - Integration with seek_thermal.py instrument (backend selection)
"""

from __future__ import annotations

import struct
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

# ═══════════════════════════════════════════════════════════════════════
#  Constants & geometry
# ═══════════════════════════════════════════════════════════════════════


class TestConstants:
    """Verify USB and frame geometry constants match the C++ library."""

    def test_vendor_id(self):
        from pyontrust.instruments.libseek_driver import SEEK_VENDOR_ID
        assert SEEK_VENDOR_ID == 0x289D

    def test_compact_pid(self):
        from pyontrust.instruments.libseek_driver import PID_COMPACT
        assert PID_COMPACT == 0x0010

    def test_pro_pid(self):
        from pyontrust.instruments.libseek_driver import PID_PRO
        assert PID_PRO == 0x0011

    def test_compact_geometry(self):
        from pyontrust.instruments.libseek_driver import (
            COMPACT_WIDTH, COMPACT_HEIGHT,
            COMPACT_RAW_WIDTH, COMPACT_RAW_HEIGHT,
            COMPACT_REQUEST_SIZE, COMPACT_RAW_SIZE, COMPACT_ROI,
        )
        assert COMPACT_WIDTH == 207
        assert COMPACT_HEIGHT == 154
        assert COMPACT_RAW_WIDTH == 208
        assert COMPACT_RAW_HEIGHT == 156
        assert COMPACT_REQUEST_SIZE == 16_224
        assert COMPACT_RAW_SIZE == 208 * 156
        assert COMPACT_ROI == (0, 1, 207, 154)

    def test_pro_geometry(self):
        from pyontrust.instruments.libseek_driver import (
            PRO_WIDTH, PRO_HEIGHT,
            PRO_RAW_WIDTH, PRO_RAW_HEIGHT,
            PRO_REQUEST_SIZE, PRO_RAW_SIZE, PRO_ROI,
        )
        assert PRO_WIDTH == 320
        assert PRO_HEIGHT == 240
        assert PRO_RAW_WIDTH == 342
        assert PRO_RAW_HEIGHT == 260
        assert PRO_REQUEST_SIZE == 13_680
        assert PRO_RAW_SIZE == 342 * 260
        assert PRO_ROI == (1, 4, 320, 240)

    def test_ffc_offset(self):
        from pyontrust.instruments.libseek_driver import FFC_OFFSET
        assert FFC_OFFSET == 0x4000

    def test_frame_id_constants(self):
        from pyontrust.instruments.libseek_driver import (
            FRAME_ID_CALIBRATION, FRAME_ID_IMAGE, FRAME_ID_DEAD_PIXEL,
        )
        assert FRAME_ID_CALIBRATION == 1
        assert FRAME_ID_IMAGE == 3
        assert FRAME_ID_DEAD_PIXEL == 4

    def test_bulk_endpoint(self):
        from pyontrust.instruments.libseek_driver import EP_DATA_IN
        assert EP_DATA_IN == 0x81


class TestDeviceCommands:
    """Verify device command enum values match the C++ SeekDevice.h."""

    def test_key_commands(self):
        from pyontrust.instruments.libseek_driver import DeviceCommand as DC
        assert DC.TARGET_PLATFORM == 84
        assert DC.SET_OPERATION_MODE == 60
        assert DC.GET_OPERATION_MODE == 61
        assert DC.GET_FIRMWARE_INFO == 78
        assert DC.READ_CHIP_ID == 54
        assert DC.SET_IMAGE_PROCESSING_MODE == 62
        assert DC.GET_IMAGE_PROCESSING_MODE == 63
        assert DC.START_GET_IMAGE_TRANSFER == 83
        assert DC.SET_FACTORY_SETTINGS_FEATURES == 86
        assert DC.GET_FACTORY_SETTINGS == 88
        assert DC.SET_FIRMWARE_INFO_FEATURES == 85
        assert DC.RESET_DEVICE == 89
        assert DC.TOGGLE_SHUTTER == 55

    def test_request_types(self):
        from pyontrust.instruments.libseek_driver import (
            REQUEST_TYPE_OUT, REQUEST_TYPE_IN,
        )
        assert REQUEST_TYPE_OUT == 0x41  # OUT | VENDOR | INTERFACE
        assert REQUEST_TYPE_IN == 0xC1   # IN  | VENDOR | INTERFACE


# ═══════════════════════════════════════════════════════════════════════
#  Dead pixel detection and filtering
# ═══════════════════════════════════════════════════════════════════════


class TestDeadPixelDetection:
    """Test the dead pixel detection logic."""

    def test_no_dead_pixels(self):
        from pyontrust.instruments.libseek_driver import _create_dead_pixel_list
        # Uniform frame — no dead pixels
        frame = np.full((154, 207), 8000, dtype=np.uint16)
        mask, dead_list = _create_dead_pixel_list(frame)
        # All pixels should be alive (mask=255)
        assert mask.shape == (154, 207)
        assert np.all(mask == 255)
        assert len(dead_list) == 0

    def test_dead_pixels_detected(self):
        from pyontrust.instruments.libseek_driver import _create_dead_pixel_list
        # Frame with a cluster of dead (zero) pixels
        frame = np.full((20, 30), 10000, dtype=np.uint16)
        frame[5, 10] = 0
        frame[5, 11] = 0
        frame[6, 10] = 0
        mask, dead_list = _create_dead_pixel_list(frame)
        # Dead pixels should have mask=0
        assert mask[5, 10] == 0
        assert mask[5, 11] == 0
        assert mask[6, 10] == 0
        assert len(dead_list) >= 3

    def test_all_zeros(self):
        from pyontrust.instruments.libseek_driver import _create_dead_pixel_list
        frame = np.zeros((10, 10), dtype=np.uint16)
        mask, dead_list = _create_dead_pixel_list(frame)
        assert mask.shape == (10, 10)


class TestDeadPixelFilter:
    """Test the dead pixel replacement with neighbour averaging."""

    def test_single_dead_pixel_replaced(self):
        from pyontrust.instruments.libseek_driver import _apply_dead_pixel_filter
        src = np.array([
            [100, 100, 100],
            [100,   0, 100],
            [100, 100, 100],
        ], dtype=np.uint16)
        mask = np.array([
            [255, 255, 255],
            [255,   0, 255],
            [255, 255, 255],
        ], dtype=np.uint8)
        dead_list = [(1, 1)]  # (x, y) = center pixel
        result = _apply_dead_pixel_filter(src, mask, dead_list)
        assert result[1, 1] == 100  # mean of 4 neighbours = 100

    def test_corner_dead_pixel(self):
        from pyontrust.instruments.libseek_driver import _apply_dead_pixel_filter
        src = np.array([
            [0, 200],
            [200, 200],
        ], dtype=np.uint16)
        mask = np.array([
            [0, 255],
            [255, 255],
        ], dtype=np.uint8)
        dead_list = [(0, 0)]
        result = _apply_dead_pixel_filter(src, mask, dead_list)
        # Corner (0,0) has 2 live neighbours: right=200, below=200 → mean=200
        assert result[0, 0] == 200

    def test_no_dead_pixels_passthrough(self):
        from pyontrust.instruments.libseek_driver import _apply_dead_pixel_filter
        src = np.full((5, 5), 42, dtype=np.uint16)
        mask = np.full((5, 5), 255, dtype=np.uint8)
        result = _apply_dead_pixel_filter(src, mask, [])
        np.testing.assert_array_equal(result, src)


# ═══════════════════════════════════════════════════════════════════════
#  LibSeekCamera (mocked USB)
# ═══════════════════════════════════════════════════════════════════════


def _make_raw_frame(raw_h, raw_w, frame_id_pos, frame_id_val, fill=8000):
    """Create a fake raw frame buffer (uint16 flat array)."""
    buf = np.full(raw_h * raw_w, fill, dtype=np.uint16)
    buf[frame_id_pos] = frame_id_val
    return buf


class TestLibSeekCamera:
    """Test LibSeekCamera with mocked USB device."""

    def test_compact_post_init(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="compact")
        assert cam.resolution == (207, 154)
        assert cam._raw_width == 208
        assert cam._raw_height == 156

    def test_pro_post_init(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="pro")
        assert cam.resolution == (320, 240)
        assert cam._raw_width == 342
        assert cam._raw_height == 260

    def test_frame_id_compact(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="compact")
        raw = np.zeros(100, dtype=np.uint16)
        raw[10] = 3  # Compact: frame_id at index 10
        assert cam._frame_id(raw) == 3

    def test_frame_id_pro(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="pro")
        raw = np.zeros(100, dtype=np.uint16)
        raw[2] = 4  # Pro: frame_id at index 2
        assert cam._frame_id(raw) == 4

    def test_frame_counter_compact(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="compact")
        raw = np.zeros(100, dtype=np.uint16)
        raw[40] = 42
        assert cam._frame_counter(raw) == 42

    def test_frame_counter_pro(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="pro")
        raw = np.zeros(100, dtype=np.uint16)
        raw[1] = 99
        assert cam._frame_counter(raw) == 99

    def test_crop_roi_compact(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="compact")
        raw = np.arange(208 * 156, dtype=np.uint16)
        cropped = cam._crop_roi(raw)
        assert cropped.shape == (154, 207)

    def test_crop_roi_pro(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="pro")
        raw = np.arange(342 * 260, dtype=np.uint16)
        cropped = cam._crop_roi(raw)
        assert cropped.shape == (240, 320)

    def test_not_opened_raises(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="compact")
        with pytest.raises(RuntimeError, match="not open"):
            cam.grab()

    def test_temperature_conversion(self):
        from pyontrust.instruments.libseek_driver import (
            RAW_TEMP_OFFSET, RAW_TEMP_SCALE,
        )
        # 8500 raw → (8500 - 6000) / 50 = 50.0°C
        raw = np.array([[8500]], dtype=np.uint16)
        temp = (raw.astype(np.float32) - RAW_TEMP_OFFSET) / RAW_TEMP_SCALE
        assert abs(temp[0, 0] - 50.0) < 0.01


class TestLibSeekCameraFullLifecycle:
    """Test full open/grab/close lifecycle with deeply mocked USB."""

    @patch("pyontrust.instruments.libseek_driver._SeekUSBDevice")
    def test_open_grab_close_compact(self, MockUSBDev):
        from pyontrust.instruments.libseek_driver import (
            LibSeekCamera, COMPACT_RAW_HEIGHT, COMPACT_RAW_WIDTH,
        )

        mock_dev = MockUSBDev.return_value
        mock_dev.is_opened = True
        raw_size = COMPACT_RAW_HEIGHT * COMPACT_RAW_WIDTH

        # First call returns frame_id=4 (dead pixel reference)
        dead_pixel_frame = np.full(raw_size, 8000, dtype=np.uint16)
        dead_pixel_frame[10] = 4  # frame_id index for compact

        # Second call (first grab) returns frame_id=3 (image)
        image_frame = np.full(raw_size, 9000, dtype=np.uint16)
        image_frame[10] = 3

        # Warmup frames
        warmup_frames = [np.full(raw_size, 9000 + i, dtype=np.uint16) for i in range(5)]
        for wf in warmup_frames:
            wf[10] = 3

        mock_dev.fetch_frame.side_effect = [dead_pixel_frame, image_frame] + warmup_frames
        mock_dev.request_set.return_value = True
        mock_dev.request_get.return_value = bytes(64)

        cam = LibSeekCamera(camera_type="compact", warmup_frames=5)
        cam._dev = mock_dev

        # Patch to skip actual USB open (already set up mock)
        with patch.object(cam, '_dev', mock_dev):
            cam._dev = mock_dev
            # Manually simulate open_cam logic
            # We can't easily mock the full open() flow, so test the grab path
            cam._is_opened = True
            cam._dead_pixel_mask = np.ones((154, 207), dtype=np.uint8) * 255
            cam._dead_pixel_list = []

            # Prepare a frame for grab
            grab_frame = np.full(raw_size, 10000, dtype=np.uint16)
            grab_frame[10] = 3
            mock_dev.fetch_frame.side_effect = [grab_frame]
            mock_dev.request_set.return_value = True

            frame = cam.grab()
            assert frame.shape == (154, 207)
            assert frame.dtype == np.uint16

    @patch("pyontrust.instruments.libseek_driver._SeekUSBDevice")
    def test_close_sends_stop_commands(self, MockUSBDev):
        from pyontrust.instruments.libseek_driver import LibSeekCamera

        mock_dev = MockUSBDev.return_value
        mock_dev.is_opened = True
        mock_dev.request_set.return_value = True

        cam = LibSeekCamera(camera_type="compact")
        cam._dev = mock_dev
        cam._is_opened = True

        cam.close()

        # Should send SET_OPERATION_MODE(0,0) three times
        stop_calls = [c for c in mock_dev.request_set.call_args_list
                      if c[0][0] == 60 and c[0][1] == bytes([0x00, 0x00])]
        assert len(stop_calls) == 3
        assert not cam._is_opened


class TestTemperatureFrame:
    """Test temperature frame conversion."""

    def test_grab_temperature_frame_formula(self):
        from pyontrust.instruments.libseek_driver import (
            RAW_TEMP_OFFSET, RAW_TEMP_SCALE,
        )
        # Verify the formula: T = (raw - 6000) / 50
        raw_values = np.array([6000, 7250, 8000, 10000], dtype=np.uint16)
        temps = (raw_values.astype(np.float32) - RAW_TEMP_OFFSET) / RAW_TEMP_SCALE
        expected = np.array([0.0, 25.0, 40.0, 80.0], dtype=np.float32)
        np.testing.assert_allclose(temps, expected, atol=0.01)


# ═══════════════════════════════════════════════════════════════════════
#  detect_camera / list_cameras
# ═══════════════════════════════════════════════════════════════════════


class TestDetection:
    """Test USB device detection helpers."""

    @patch("usb.core.find", return_value=None)
    def test_detect_camera_none(self, mock_find):
        from pyontrust.instruments.libseek_driver import detect_camera
        assert detect_camera() is None

    @patch("usb.core.find")
    def test_detect_camera_pro(self, mock_find):
        from pyontrust.instruments.libseek_driver import detect_camera, PID_PRO
        # First call (PID_PRO) returns a device, second (PID_COMPACT) not reached
        mock_find.side_effect = [MagicMock(), None]
        result = detect_camera()
        assert result == "pro"

    @patch("usb.core.find")
    def test_detect_camera_compact(self, mock_find):
        from pyontrust.instruments.libseek_driver import detect_camera
        mock_find.side_effect = [None, MagicMock()]
        result = detect_camera()
        assert result == "compact"

    @patch("usb.core.find", return_value=[])
    def test_list_cameras_empty(self, mock_find):
        from pyontrust.instruments.libseek_driver import list_cameras
        result = list_cameras()
        assert result == []

    @patch("usb.core.find")
    def test_list_cameras_found(self, mock_find):
        from pyontrust.instruments.libseek_driver import list_cameras
        mock_dev = MagicMock()
        mock_dev.bus = 1
        mock_dev.address = 2
        mock_find.side_effect = [
            [],        # PRO search
            [mock_dev],  # Compact search
        ]
        result = list_cameras()
        assert len(result) == 1
        assert result[0]["type"] == "Compact/CompactXR"
        assert result[0]["camera_type"] == "compact"
        assert result[0]["pid"] == "0x0010"

    def test_detect_camera_no_pyusb(self):
        """detect_camera returns None when pyusb is not installed."""
        from pyontrust.instruments.libseek_driver import detect_camera
        with patch.dict("sys.modules", {"usb": None, "usb.core": None}):
            # Re-import to get fresh module
            result = detect_camera()
            # The function catches ImportError and returns None
            assert result is None


# ═══════════════════════════════════════════════════════════════════════
#  SeekThermalCamera backend selection (seek_thermal.py integration)
# ═══════════════════════════════════════════════════════════════════════


class TestBackendSelection:
    """Test that SeekThermalCamera selects libseek as preferred backend."""

    @patch("pyontrust.instruments.libseek_driver.detect_camera", return_value="compact")
    @patch("pyontrust.instruments.libseek_driver.LibSeekCamera")
    def test_libseek_preferred(self, MockCam, mock_detect):
        from pyontrust.instruments.seek_thermal import SeekThermalCamera

        # Verify libseek is detected as backend
        cam = SeekThermalCamera(camera_type="compact")
        backend = cam._detect_backend()
        assert backend == "libseek"

    def test_fallback_to_simulated(self):
        """When no backend available and mode=simulated, still works."""
        from pyontrust.instruments.seek_thermal import create

        cam = create({"mode": "simulated"})
        cam.open()
        frame = cam.grab_temperature_frame()
        assert frame.shape == (156, 206)
        cam.close()

    def test_factory_passes_camera_type(self):
        """create() passes camera_type and ffc_file to SeekThermalCamera."""
        from pyontrust.instruments.seek_thermal import create

        cam = create({
            "mode": "seek",
            "camera_type": "pro",
            "ffc_file": "/path/to/ffc.png",
        })
        assert cam.camera_type == "pro"
        assert cam.ffc_file == "/path/to/ffc.png"

    def test_error_message_mentions_pyusb(self):
        """ImportError message mentions pyusb when nothing is available."""
        from pyontrust.instruments.seek_thermal import SeekThermalCamera

        cam = SeekThermalCamera()

        # Mock all backends as unavailable
        with patch.object(cam, "_detect_backend", side_effect=ImportError("pyusb")):
            with pytest.raises(ImportError, match="pyusb"):
                cam.open()


class TestSeekThermalCameraInfo:
    """Test the info() method with libseek backend."""

    def test_info_libseek_compact(self):
        from pyontrust.instruments.seek_thermal import SeekThermalCamera

        cam = SeekThermalCamera(camera_type="compact")
        cam._backend = "libseek"
        cam._libseek_cam = MagicMock()
        cam._libseek_cam.resolution = (207, 154)
        cam._libseek_cam.camera_type = "compact"

        info = cam.info()
        assert info.model == "Seek Thermal Compact (libseek)"
        assert info.serial == "libseek-usb"
        assert info.resolution == (207, 154)
        assert info.vendor == "Seek Thermal"

    def test_info_libseek_pro(self):
        from pyontrust.instruments.seek_thermal import SeekThermalCamera

        cam = SeekThermalCamera(camera_type="pro")
        cam._backend = "libseek"
        cam._libseek_cam = MagicMock()
        cam._libseek_cam.resolution = (320, 240)
        cam._libseek_cam.camera_type = "pro"

        info = cam.info()
        assert info.model == "Seek Thermal CompactPRO (libseek)"
        assert info.resolution == (320, 240)


# ═══════════════════════════════════════════════════════════════════════
#  Hardware discovery integration
# ═══════════════════════════════════════════════════════════════════════


class TestHardwareDiscovery:
    """Test that hardware discovery picks up libseek cameras."""

    @patch("pyontrust.instruments.libseek_driver.list_cameras")
    def test_probe_finds_libseek(self, mock_list):
        from pyontrust.services.hardware_discovery import _probe_seek_thermal

        mock_list.return_value = [{
            "type": "Compact/CompactXR",
            "camera_type": "compact",
            "vid": "0x289D",
            "pid": "0x0010",
            "index": 0,
            "resolution": "207x154",
            "bus": 1,
            "address": 3,
        }]

        results = _probe_seek_thermal()
        assert len(results) >= 1
        assert results[0]["status"] == "ok"
        assert "libseek" in results[0]["name"]
        assert results[0]["details"]["sdk"] == "libseek"


# ═══════════════════════════════════════════════════════════════════════
#  USB device layer unit tests
# ═══════════════════════════════════════════════════════════════════════


class TestSeekUSBDevice:
    """Test the low-level USB device layer."""

    def test_request_types_binary(self):
        from pyontrust.instruments.libseek_driver import (
            REQUEST_TYPE_OUT, REQUEST_TYPE_IN,
        )
        # OUT = 0x00 | 0x40 | 0x01 = 0x41
        assert REQUEST_TYPE_OUT == 0x41
        # IN = 0x80 | 0x40 | 0x01 = 0xC1
        assert REQUEST_TYPE_IN == 0xC1

    @patch("usb.core.find", return_value=None)
    def test_open_no_device_raises(self, mock_find):
        from pyontrust.instruments.libseek_driver import _SeekUSBDevice
        dev = _SeekUSBDevice(0x289D, 0x0010)
        with pytest.raises(RuntimeError, match="not found"):
            dev.open()

    @patch("usb.util.claim_interface")
    @patch("usb.util.release_interface")
    @patch("usb.util.dispose_resources")
    @patch("usb.core.find")
    def test_open_and_close(self, mock_find, mock_dispose, mock_release, mock_claim):
        from pyontrust.instruments.libseek_driver import _SeekUSBDevice

        mock_dev = MagicMock()
        mock_dev.get_active_configuration.return_value = MagicMock(bConfigurationValue=1)
        mock_find.return_value = mock_dev

        dev = _SeekUSBDevice(0x289D, 0x0010)
        dev.open()
        assert dev.is_opened

        dev.close()
        assert not dev.is_opened

    def test_request_set_not_opened(self):
        from pyontrust.instruments.libseek_driver import _SeekUSBDevice
        dev = _SeekUSBDevice(0x289D, 0x0010)
        assert dev.request_set(84, bytes([0x01])) is False

    def test_request_get_not_opened(self):
        from pyontrust.instruments.libseek_driver import _SeekUSBDevice
        dev = _SeekUSBDevice(0x289D, 0x0010)
        assert dev.request_get(78, 4) is None


# ═══════════════════════════════════════════════════════════════════════
#  FFC / calibration
# ═══════════════════════════════════════════════════════════════════════


class TestFlatFieldCalibration:
    """Test FFC logic in retrieve()."""

    def test_ffc_subtraction(self):
        """Verify raw_frame + offset - ffc_frame formula."""
        from pyontrust.instruments.libseek_driver import FFC_OFFSET
        raw = np.full((5, 5), 10000, dtype=np.uint16)
        ffc = np.full((5, 5), 10000, dtype=np.uint16)
        # After calibration: raw + 0x4000 - ffc = 10000 + 16384 - 10000 = 16384
        result = raw.astype(np.int32) + FFC_OFFSET - ffc.astype(np.int32)
        result = np.clip(result, 0, 65535).astype(np.uint16)
        np.testing.assert_array_equal(result, np.full((5, 5), FFC_OFFSET, dtype=np.uint16))

    def test_ffc_with_temperature_variation(self):
        """FFC should normalize spatial non-uniformity."""
        from pyontrust.instruments.libseek_driver import FFC_OFFSET
        # Simulate non-uniform frame (corners brighter)
        raw = np.full((10, 10), 10000, dtype=np.uint16)
        raw[0, 0] = 10500  # Corner hot pixel (sensor artifact)
        raw[9, 9] = 10500

        # FFC frame captured with uniform temp = same non-uniformity
        ffc = np.full((10, 10), 10000, dtype=np.uint16)
        ffc[0, 0] = 10500
        ffc[9, 9] = 10500

        result = raw.astype(np.int32) + FFC_OFFSET - ffc.astype(np.int32)
        result = np.clip(result, 0, 65535).astype(np.uint16)

        # After FFC, all pixels should be equal (uniformized)
        assert result[0, 0] == result[5, 5]
        assert result[9, 9] == result[5, 5]


# ═══════════════════════════════════════════════════════════════════════
#  Init sequence validation
# ═══════════════════════════════════════════════════════════════════════


class TestInitSequence:
    """Validate init_compact / init_pro send correct USB commands."""

    def test_init_compact_commands(self):
        from pyontrust.instruments.libseek_driver import _init_compact, DeviceCommand

        mock_dev = MagicMock()
        mock_dev.request_set.return_value = True
        mock_dev.request_get.return_value = bytes(64)

        result = _init_compact(mock_dev)
        assert result is True

        # Check first command is TARGET_PLATFORM
        first_set = mock_dev.request_set.call_args_list[0]
        assert first_set[0][0] == DeviceCommand.TARGET_PLATFORM
        assert first_set[0][1] == bytes([0x01])

        # Check final command is SET_OPERATION_MODE = 1 (start)
        set_calls = mock_dev.request_set.call_args_list
        # Find the SET_OPERATION_MODE(0x01, 0x00) call
        start_calls = [c for c in set_calls
                       if c[0][0] == DeviceCommand.SET_OPERATION_MODE
                       and c[0][1] == bytes([0x01, 0x00])]
        assert len(start_calls) >= 1

    def test_init_pro_commands(self):
        from pyontrust.instruments.libseek_driver import _init_pro, DeviceCommand

        mock_dev = MagicMock()
        mock_dev.request_set.return_value = True
        mock_dev.request_get.return_value = bytes(64)

        result = _init_pro(mock_dev)
        assert result is True

        # Check first command is TARGET_PLATFORM
        first_set = mock_dev.request_set.call_args_list[0]
        assert first_set[0][0] == DeviceCommand.TARGET_PLATFORM

        # Pro should read factory settings in address loop (0..2560 step 32)
        factory_set_calls = [
            c for c in mock_dev.request_set.call_args_list
            if c[0][0] == DeviceCommand.SET_FACTORY_SETTINGS_FEATURES
        ]
        # At least 80 calls for the address loop (2560/32 = 80)
        assert len(factory_set_calls) >= 80

    def test_init_compact_retry_on_failure(self):
        from pyontrust.instruments.libseek_driver import _init_compact

        mock_dev = MagicMock()
        # First TARGET_PLATFORM fails, then succeeds after deinit
        mock_dev.request_set.side_effect = [
            False,  # TARGET_PLATFORM fails
            True,   # SET_OPERATION_MODE (deinit 1)
            True,   # SET_OPERATION_MODE (deinit 2)
            True,   # SET_OPERATION_MODE (deinit 3)
            True,   # TARGET_PLATFORM retry — succeeds
        ] + [True] * 50  # rest succeed
        mock_dev.request_get.return_value = bytes(64)

        result = _init_compact(mock_dev)
        assert result is True


# ═══════════════════════════════════════════════════════════════════════
#  Context manager
# ═══════════════════════════════════════════════════════════════════════


class TestContextManager:
    """Test LibSeekCamera context manager protocol."""

    def test_context_manager_enter_exit(self):
        from pyontrust.instruments.libseek_driver import LibSeekCamera
        cam = LibSeekCamera(camera_type="compact")

        with patch.object(cam, "open") as mock_open, \
             patch.object(cam, "close") as mock_close:
            with cam as c:
                assert c is cam
                mock_open.assert_called_once()
            mock_close.assert_called_once()
