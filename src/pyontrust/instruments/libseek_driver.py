"""Pure-Python driver for Seek Thermal cameras (Compact / CompactXR / CompactPRO).

Port of the OpenThermal/libseek-thermal C++ library to Python using ``pyusb``.
No C++ compilation required — communicates directly over USB using the same
vendor-specific control transfers and bulk endpoint reads as the reference
implementation.

Hardware:
    ┌───────────────────────┬────────┬───────────┬──────────────┬──────────────┐
    │ Camera                │ PID    │ Image     │ Raw buffer   │ Request size │
    ├───────────────────────┼────────┼───────────┼──────────────┼──────────────┤
    │ Compact / CompactXR   │ 0x0010 │ 207 × 154 │ 208 × 156    │ 16 224 bytes │
    │ CompactPRO            │ 0x0011 │ 320 × 240 │ 342 × 260    │ 13 680 bytes │
    └───────────────────────┴────────┴───────────┴──────────────┴──────────────┘

USB protocol:
    - Vendor ID:  0x289d
    - Config:     1
    - Interface:  0
    - Bulk IN EP: 0x81
    - Control transfers use vendor-specific request type to interface

Frame pipeline:
    1. ``START_GET_IMAGE_TRANSFER`` → bulk read raw uint16 buffer
    2. Check ``frame_id``: 4 = dead-pixel reference, 1 = FFC calibration, 3 = image
    3. Apply flat-field calibration (subtract FFC frame, add offset 0x4000)
    4. Filter dead pixels (replace with 4-neighbor mean)
    5. Crop ROI to exclude metadata rows/columns

Temperature note:
    The upstream library states "does not support absolute temperature readings".
    We provide an approximate linear mapping: ``T_C ≈ (raw - 6000) / 50`` which
    gives reasonable results for typical room-temperature scenes.  For precision
    you should calibrate against a blackbody reference.

Requires:
    ``pip install pyusb``
    On Windows: use Zadig to set the 'iAP Interface' driver to libusb-win32 or
    WinUSB for the Seek Thermal device.

References:
    https://github.com/OpenThermal/libseek-thermal
"""

from __future__ import annotations

import logging
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger("pyontrust.instruments.libseek_driver")

# ═══════════════════════════════════════════════════════════════════════
#  USB protocol constants  (from SeekDevice.h / SeekThermal.h / Pro.h)
# ═══════════════════════════════════════════════════════════════════════

SEEK_VENDOR_ID = 0x289D

# PIDs
PID_COMPACT = 0x0010  # Compact / CompactXR
PID_PRO = 0x0011  # CompactPRO

# Bulk endpoint
EP_DATA_IN = 0x81

# USB request type components
LIBUSB_ENDPOINT_OUT = 0x00
LIBUSB_ENDPOINT_IN = 0x80
LIBUSB_REQUEST_TYPE_VENDOR = 0x40
LIBUSB_RECIPIENT_INTERFACE = 0x01

REQUEST_TYPE_OUT = LIBUSB_ENDPOINT_OUT | LIBUSB_REQUEST_TYPE_VENDOR | LIBUSB_RECIPIENT_INTERFACE  # 0x41
REQUEST_TYPE_IN = LIBUSB_ENDPOINT_IN | LIBUSB_REQUEST_TYPE_VENDOR | LIBUSB_RECIPIENT_INTERFACE  # 0xC1


class DeviceCommand:
    """USB vendor command codes (from SeekDevice.h enum)."""
    BEGIN_MEMORY_WRITE = 82
    COMPLETE_MEMORY_WRITE = 81
    GET_BIT_DATA = 59
    GET_CURRENT_COMMAND_ARRAY = 68
    GET_DATA_PAGE = 65
    GET_DEFAULT_COMMAND_ARRAY = 71
    GET_ERROR_CODE = 53
    GET_FACTORY_SETTINGS = 88
    GET_FIRMWARE_INFO = 78
    GET_IMAGE_PROCESSING_MODE = 63
    GET_OPERATION_MODE = 61
    GET_RDAC_ARRAY = 77
    GET_SHUTTER_POLARITY = 57
    GET_VDAC_ARRAY = 74
    READ_CHIP_ID = 54
    RESET_DEVICE = 89
    SET_BIT_DATA_OFFSET = 58
    SET_CURRENT_COMMAND_ARRAY = 67
    SET_CURRENT_COMMAND_ARRAY_SIZE = 66
    SET_DATA_PAGE = 64
    SET_DEFAULT_COMMAND_ARRAY = 70
    SET_DEFAULT_COMMAND_ARRAY_SIZE = 69
    SET_FACTORY_SETTINGS = 87
    SET_FACTORY_SETTINGS_FEATURES = 86
    SET_FIRMWARE_INFO_FEATURES = 85
    SET_IMAGE_PROCESSING_MODE = 62
    SET_OPERATION_MODE = 60
    SET_RDAC_ARRAY = 76
    SET_RDAC_ARRAY_OFFSET_AND_ITEMS = 75
    SET_SHUTTER_POLARITY = 56
    SET_VDAC_ARRAY = 73
    SET_VDAC_ARRAY_OFFSET_AND_ITEMS = 72
    START_GET_IMAGE_TRANSFER = 83
    TARGET_PLATFORM = 84
    TOGGLE_SHUTTER = 55
    UPLOAD_FIRMWARE_ROW_SIZE = 79
    WRITE_MEMORY_DATA = 80


# ── Camera geometry ──────────────────────────────────────────────────

# Compact / CompactXR
COMPACT_WIDTH = 207
COMPACT_HEIGHT = 154
COMPACT_RAW_WIDTH = 208
COMPACT_RAW_HEIGHT = 156
COMPACT_REQUEST_SIZE = 16_224
COMPACT_RAW_SIZE = COMPACT_RAW_WIDTH * COMPACT_RAW_HEIGHT
# ROI: cv::Rect(0, 1, 207, 154)  →  x=0, y=1, w=207, h=154
COMPACT_ROI = (0, 1, COMPACT_WIDTH, COMPACT_HEIGHT)

# CompactPRO
PRO_WIDTH = 320
PRO_HEIGHT = 240
PRO_RAW_WIDTH = 342
PRO_RAW_HEIGHT = 260
PRO_REQUEST_SIZE = 13_680
PRO_RAW_SIZE = PRO_RAW_WIDTH * PRO_RAW_HEIGHT
# ROI: cv::Rect(1, 4, 320, 240)  →  x=1, y=4, w=320, h=240
PRO_ROI = (1, 4, PRO_WIDTH, PRO_HEIGHT)

# FFC calibration offset (C++ m_offset = 0x4000)
FFC_OFFSET = 0x4000

# Frame ID constants
FRAME_ID_CALIBRATION = 1   # FFC / flat-field calibration
FRAME_ID_IMAGE = 3         # Normal image data
FRAME_ID_DEAD_PIXEL = 4    # First frame — used for dead pixel detection

# Approximate raw → °C conversion
# Empirical linear mapping: adjust for your specific camera
RAW_TEMP_OFFSET = 6000.0
RAW_TEMP_SCALE = 50.0


# ═══════════════════════════════════════════════════════════════════════
#  USB device layer
# ═══════════════════════════════════════════════════════════════════════


class _SeekUSBDevice:
    """Low-level USB communication with Seek Thermal cameras via pyusb."""

    def __init__(self, vendor_id: int, product_id: int, timeout_ms: int = 1000):
        self._vid = vendor_id
        self._pid = product_id
        self._timeout = timeout_ms
        self._dev: Any = None
        self._is_opened = False

    @property
    def is_opened(self) -> bool:
        return self._is_opened

    def open(self) -> None:
        """Open the USB device, set configuration, claim interface."""
        import usb.core
        import usb.util

        self._dev = usb.core.find(idVendor=self._vid, idProduct=self._pid)
        if self._dev is None:
            raise RuntimeError(
                f"Seek Thermal device not found (VID=0x{self._vid:04X}, "
                f"PID=0x{self._pid:04X}).  Check USB connection and drivers "
                "(use Zadig on Windows to set libusb-win32 driver)."
            )

        # Detach kernel driver if necessary (Linux)
        if sys.platform != "win32":
            try:
                if self._dev.is_kernel_driver_active(0):
                    self._dev.detach_kernel_driver(0)
            except Exception:
                pass

        # Set configuration (if not already set)
        try:
            cfg = self._dev.get_active_configuration()
            if cfg is None or cfg.bConfigurationValue != 1:
                self._dev.set_configuration(1)
        except Exception:
            try:
                self._dev.set_configuration(1)
            except Exception:
                pass

        # Claim interface 0
        import usb.util
        try:
            usb.util.claim_interface(self._dev, 0)
        except Exception:
            pass

        self._is_opened = True
        logger.debug(
            "USB device opened: VID=0x%04X PID=0x%04X",
            self._vid, self._pid,
        )

    def close(self) -> None:
        """Release interface and dispose device."""
        if self._dev is not None:
            import usb.util
            try:
                usb.util.release_interface(self._dev, 0)
            except Exception:
                pass
            try:
                usb.util.dispose_resources(self._dev)
            except Exception:
                pass
            self._dev = None
        self._is_opened = False

    def request_set(self, command: int, data: bytes | bytearray) -> bool:
        """Vendor-specific SET request (host→device)."""
        if self._dev is None:
            return False
        try:
            self._dev.ctrl_transfer(
                REQUEST_TYPE_OUT, command, 0, 0,
                data, self._timeout,
            )
            return True
        except Exception as exc:
            logger.error("USB request_set(cmd=%d) failed: %s", command, exc)
            return False

    def request_get(self, command: int, length: int) -> bytes | None:
        """Vendor-specific GET request (device→host)."""
        if self._dev is None:
            return None
        try:
            data = self._dev.ctrl_transfer(
                REQUEST_TYPE_IN, command, 0, 0,
                length, self._timeout,
            )
            return bytes(data)
        except Exception as exc:
            logger.error("USB request_get(cmd=%d, len=%d) failed: %s",
                         command, length, exc)
            return None

    def fetch_frame(
        self,
        raw_size: int,
        request_size: int,
    ) -> np.ndarray | None:
        """Bulk-read a raw frame of ``raw_size`` uint16 words.

        Reads in chunks of ``request_size`` bytes from EP 0x81.
        Returns uint16 numpy array in host byte order.
        """
        if self._dev is None:
            return None

        total_bytes = raw_size * 2  # uint16 → 2 bytes each
        buf = bytearray(total_bytes)
        offset = 0

        while offset < total_bytes:
            chunk_size = min(request_size, total_bytes - offset)
            try:
                data = self._dev.read(EP_DATA_IN, chunk_size, self._timeout)
                n = len(data)
                buf[offset:offset + n] = bytes(data)
                offset += n
            except Exception as exc:
                logger.error("Bulk read failed at offset %d: %s", offset, exc)
                return None

        # Convert to uint16 array with correct endianness (little-endian on USB)
        arr = np.frombuffer(buf, dtype="<u2").astype(np.uint16)
        return arr


# ═══════════════════════════════════════════════════════════════════════
#  Camera init sequences (from SeekThermal.cpp / SeekThermalPro.cpp)
# ═══════════════════════════════════════════════════════════════════════


def _init_compact(dev: _SeekUSBDevice) -> bool:
    """Initialisation sequence for Seek Compact / CompactXR (PID 0x0010).

    Translated from SeekThermal::init_cam() in SeekThermal.cpp.
    """
    DC = DeviceCommand

    # TARGET_PLATFORM
    if not dev.request_set(DC.TARGET_PLATFORM, bytes([0x01])):
        # Retry: deinit and try again (cam may not have been properly closed)
        dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00]))
        dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00]))
        dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00]))
        if not dev.request_set(DC.TARGET_PLATFORM, bytes([0x01])):
            return False

    # SET_OPERATION_MODE = 0
    if not dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00])):
        return False

    # GET_FIRMWARE_INFO (4 bytes)
    fw = dev.request_get(DC.GET_FIRMWARE_INFO, 4)
    if fw is None:
        return False
    logger.debug("Compact firmware: %s", fw.hex())

    # READ_CHIP_ID (12 bytes)
    chip = dev.request_get(DC.READ_CHIP_ID, 12)
    if chip is None:
        return False
    logger.debug("Compact chip ID: %s", chip.hex())

    # SET_FACTORY_SETTINGS_FEATURES / GET_FACTORY_SETTINGS — sequence of reads
    for set_data, get_len in [
        (bytes([0x06, 0x00, 0x08, 0x00, 0x00, 0x00]), 12),
        (bytes([0x17, 0x00]), 0),  # SET_FIRMWARE_INFO_FEATURES
    ]:
        cmd = DC.SET_FIRMWARE_INFO_FEATURES if get_len == 0 else DC.SET_FACTORY_SETTINGS_FEATURES
        if not dev.request_set(cmd, set_data):
            return False
        if get_len > 0:
            resp = dev.request_get(DC.GET_FACTORY_SETTINGS, get_len)
            if resp is None:
                return False

    # GET_FIRMWARE_INFO (64 bytes)
    fw64 = dev.request_get(DC.GET_FIRMWARE_INFO, 64)
    if fw64 is None:
        return False

    # Additional factory settings reads
    factory_reads = [
        (bytes([0x20, 0x00, 0x30, 0x00, 0x00, 0x00]), 64),
        (bytes([0x20, 0x00, 0x50, 0x00, 0x00, 0x00]), 64),
        (bytes([0x0C, 0x00, 0x70, 0x00, 0x00, 0x00]), 24),
        (bytes([0x06, 0x00, 0x08, 0x00, 0x00, 0x00]), 12),
    ]
    for set_data, get_len in factory_reads:
        if not dev.request_set(DC.SET_FACTORY_SETTINGS_FEATURES, set_data):
            return False
        resp = dev.request_get(DC.GET_FACTORY_SETTINGS, get_len)
        if resp is None:
            return False

    # SET_IMAGE_PROCESSING_MODE
    if not dev.request_set(DC.SET_IMAGE_PROCESSING_MODE, bytes([0x08, 0x00])):
        return False

    # GET_OPERATION_MODE
    dev.request_get(DC.GET_OPERATION_MODE, 2)

    # SET_IMAGE_PROCESSING_MODE (again)
    if not dev.request_set(DC.SET_IMAGE_PROCESSING_MODE, bytes([0x08, 0x00])):
        return False

    # SET_OPERATION_MODE = 1 (start)
    if not dev.request_set(DC.SET_OPERATION_MODE, bytes([0x01, 0x00])):
        return False

    # Final GET_OPERATION_MODE
    dev.request_get(DC.GET_OPERATION_MODE, 2)

    return True


def _init_pro(dev: _SeekUSBDevice) -> bool:
    """Initialisation sequence for Seek CompactPRO (PID 0x0011).

    Translated from SeekThermalPro::init_cam() in SeekThermalPro.cpp.
    """
    DC = DeviceCommand

    # TARGET_PLATFORM
    if not dev.request_set(DC.TARGET_PLATFORM, bytes([0x01])):
        dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00]))
        dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00]))
        dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00]))
        if not dev.request_set(DC.TARGET_PLATFORM, bytes([0x01])):
            return False

    # SET_OPERATION_MODE = 0
    if not dev.request_set(DC.SET_OPERATION_MODE, bytes([0x00, 0x00])):
        return False

    # GET_FIRMWARE_INFO (4 bytes)
    fw = dev.request_get(DC.GET_FIRMWARE_INFO, 4)
    if fw is None:
        return False

    # READ_CHIP_ID (12 bytes)
    chip = dev.request_get(DC.READ_CHIP_ID, 12)
    if chip is None:
        return False

    # Factory settings batch 1
    pro_factory_1 = [
        (bytes([0x06, 0x00, 0x08, 0x00, 0x00, 0x00]), 12),
        (bytes([0x17, 0x00]), -1),  # SET_FIRMWARE_INFO_FEATURES (no get)
    ]
    for set_data, get_len in pro_factory_1:
        if get_len == -1:
            if not dev.request_set(DC.SET_FIRMWARE_INFO_FEATURES, set_data):
                return False
        else:
            if not dev.request_set(DC.SET_FACTORY_SETTINGS_FEATURES, set_data):
                return False
            resp = dev.request_get(DC.GET_FACTORY_SETTINGS, get_len)
            if resp is None:
                return False

    # GET_FIRMWARE_INFO (64 bytes)
    fw64 = dev.request_get(DC.GET_FIRMWARE_INFO, 64)
    if fw64 is None:
        return False

    # Factory settings batch 2
    pro_factory_2 = [
        (bytes([0x01, 0x00, 0x00, 0x06, 0x00, 0x00]), 2),
        (bytes([0x01, 0x00, 0x01, 0x06, 0x00, 0x00]), 2),
    ]
    for set_data, get_len in pro_factory_2:
        if not dev.request_set(DC.SET_FACTORY_SETTINGS_FEATURES, set_data):
            return False
        resp = dev.request_get(DC.GET_FACTORY_SETTINGS, get_len)
        if resp is None:
            return False

    # Read factory settings in 32-address increments (0..2560)
    for addr in range(0, 2560, 32):
        addr_le = struct.pack("<H", addr)
        set_data = bytes([0x20, 0x00, addr_le[0], addr_le[1], 0x00, 0x00])
        if not dev.request_set(DC.SET_FACTORY_SETTINGS_FEATURES, set_data):
            return False
        resp = dev.request_get(DC.GET_FACTORY_SETTINGS, 64)
        if resp is None:
            return False

    # SET_FIRMWARE_INFO_FEATURES + GET_FIRMWARE_INFO
    if not dev.request_set(DC.SET_FIRMWARE_INFO_FEATURES, bytes([0x15, 0x00])):
        return False
    fw64b = dev.request_get(DC.GET_FIRMWARE_INFO, 64)
    if fw64b is None:
        return False

    # SET_IMAGE_PROCESSING_MODE
    if not dev.request_set(DC.SET_IMAGE_PROCESSING_MODE, bytes([0x08, 0x00])):
        return False

    # SET_OPERATION_MODE = 1 (start)
    if not dev.request_set(DC.SET_OPERATION_MODE, bytes([0x01, 0x00])):
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════
#  Frame processing helpers
# ═══════════════════════════════════════════════════════════════════════


def _create_dead_pixel_list(
    frame: np.ndarray,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Detect dead pixels and return (mask, ordered_pixel_list).

    Mimics SeekCam::create_dead_pixel_list from SeekCam.cpp.
    Dead pixels are those with values significantly below the histogram peak.
    """
    f32 = frame.astype(np.float32)
    max_val = f32.max()
    if max_val <= 0:
        return np.ones(frame.shape, dtype=np.uint8) * 255, []

    # Histogram with 0x4000 bins
    hist, edges = np.histogram(f32.ravel(), bins=0x4000, range=(0, 0x4000))
    hist[0] = 0  # suppress 0th bin

    peak_bin = int(np.argmax(hist))
    threshold = peak_bin - (max_val - peak_bin)
    if threshold < 0:
        threshold = 0

    # Dead pixel mask: pixels at or above threshold are alive (255), below are dead (0)
    mask = np.where(f32 >= threshold, np.uint8(255), np.uint8(0))

    # Build ordered dead pixel list (simple approach)
    dead_ys, dead_xs = np.where(mask == 0)
    dead_pixel_list = list(zip(dead_xs.tolist(), dead_ys.tolist()))

    return mask, dead_pixel_list


def _apply_dead_pixel_filter(
    src: np.ndarray,
    mask: np.ndarray,
    dead_pixel_list: list[tuple[int, int]],
) -> np.ndarray:
    """Replace dead pixel values with mean of their live neighbours.

    Mimics SeekCam::apply_dead_pixel_filter from SeekCam.cpp.
    """
    DEAD_MARKER = 0xFFFF
    dst = np.full_like(src, DEAD_MARKER, dtype=np.uint16)
    # Copy only alive pixels
    dst[mask > 0] = src[mask > 0]

    rows, cols = dst.shape
    for (x, y) in dead_pixel_list:
        total = 0
        count = 0
        # 4-connected neighbours
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows:
                val = dst[ny, nx]
                if val != DEAD_MARKER:
                    total += int(val)
                    count += 1
        if count > 0:
            dst[y, x] = total // count

    return dst


# ═══════════════════════════════════════════════════════════════════════
#  Main camera class
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class LibSeekCamera:
    """Pure-Python Seek Thermal camera driver using pyusb.

    Port of the OpenThermal/libseek-thermal C++ library.

    Parameters
    ----------
    camera_type : str
        ``"compact"`` for Compact/CompactXR (PID 0x0010) or
        ``"pro"`` for CompactPRO (PID 0x0011).  Default: ``"compact"``.
    ffc_file : str | None
        Path to a pre-computed flat-field calibration image (uint16 PNG).
        If provided, it is subtracted during ``retrieve()`` to reduce
        corner glow.  See the libseek-thermal ``seek_create_flat_field``
        utility for how to create one.
    warmup_frames : int
        Number of frames to discard before providing data (sensor
        stabilisation).  Default: 5.
    """

    camera_type: str = "compact"
    ffc_file: str | None = None
    warmup_frames: int = 5

    # ── private state ────────────────────────────────────────────────
    _dev: _SeekUSBDevice = field(default=None, repr=False, init=False)  # type: ignore[assignment]
    _is_opened: bool = field(default=False, repr=False, init=False)
    _raw_width: int = field(default=0, repr=False, init=False)
    _raw_height: int = field(default=0, repr=False, init=False)
    _width: int = field(default=0, repr=False, init=False)
    _height: int = field(default=0, repr=False, init=False)
    _raw_size: int = field(default=0, repr=False, init=False)
    _request_size: int = field(default=0, repr=False, init=False)
    _roi: tuple[int, int, int, int] = field(default=(0, 0, 0, 0), repr=False, init=False)
    _dead_pixel_mask: np.ndarray | None = field(default=None, repr=False, init=False)
    _dead_pixel_list: list[tuple[int, int]] = field(default_factory=list, repr=False, init=False)
    _ffc_frame: np.ndarray | None = field(default=None, repr=False, init=False)
    _additional_ffc: np.ndarray | None = field(default=None, repr=False, init=False)
    _chip_id: bytes = field(default=b"", repr=False, init=False)
    _firmware_info: bytes = field(default=b"", repr=False, init=False)

    def __post_init__(self) -> None:
        is_pro = self.camera_type.lower() in ("pro", "compactpro", "compact_pro")
        if is_pro:
            self._raw_width = PRO_RAW_WIDTH
            self._raw_height = PRO_RAW_HEIGHT
            self._width = PRO_WIDTH
            self._height = PRO_HEIGHT
            self._raw_size = PRO_RAW_SIZE
            self._request_size = PRO_REQUEST_SIZE
            self._roi = PRO_ROI
        else:
            self._raw_width = COMPACT_RAW_WIDTH
            self._raw_height = COMPACT_RAW_HEIGHT
            self._width = COMPACT_WIDTH
            self._height = COMPACT_HEIGHT
            self._raw_size = COMPACT_RAW_SIZE
            self._request_size = COMPACT_REQUEST_SIZE
            self._roi = COMPACT_ROI

    # ── frame_id extraction (camera-specific) ────────────────────────

    def _frame_id(self, raw_data: np.ndarray) -> int:
        """Extract frame type ID from raw buffer.

        Compact:  raw_data[10]
        Pro:      raw_data[2]
        """
        is_pro = self.camera_type.lower() in ("pro", "compactpro", "compact_pro")
        idx = 2 if is_pro else 10
        if idx < len(raw_data):
            return int(raw_data[idx])
        return -1

    def _frame_counter(self, raw_data: np.ndarray) -> int:
        """Extract frame counter from raw buffer."""
        is_pro = self.camera_type.lower() in ("pro", "compactpro", "compact_pro")
        idx = 1 if is_pro else 40
        if idx < len(raw_data):
            return int(raw_data[idx])
        return -1

    # ── public API ───────────────────────────────────────────────────

    @property
    def is_opened(self) -> bool:
        return self._is_opened

    @property
    def resolution(self) -> tuple[int, int]:
        """(width, height) of the output image (ROI-cropped)."""
        return (self._width, self._height)

    def open(self) -> None:
        """Open USB device, initialise camera, build dead-pixel map."""
        if self._is_opened:
            return

        is_pro = self.camera_type.lower() in ("pro", "compactpro", "compact_pro")
        pid = PID_PRO if is_pro else PID_COMPACT
        self._dev = _SeekUSBDevice(SEEK_VENDOR_ID, pid)
        self._dev.open()

        # Load additional FFC image if provided
        if self.ffc_file:
            try:
                import cv2
                ffc = cv2.imread(self.ffc_file, cv2.IMREAD_UNCHANGED)
                if ffc is not None and ffc.dtype == np.uint16:
                    # Crop to ROI dimensions
                    rx, ry, rw, rh = self._roi
                    if ffc.shape == (self._raw_height, self._raw_width):
                        ffc = ffc[ry:ry + rh, rx:rx + rw]
                    if ffc.shape == (self._height, self._width):
                        self._additional_ffc = ffc
                        logger.info("Loaded additional FFC from %s", self.ffc_file)
                    else:
                        logger.warning(
                            "FFC image size mismatch: expected (%d,%d), got %s",
                            self._height, self._width, ffc.shape,
                        )
            except ImportError:
                # No OpenCV — try with PIL or skip
                logger.warning("cv2 not available for FFC loading, skipping")
            except Exception as exc:
                logger.warning("Could not load FFC file %s: %s", self.ffc_file, exc)

        # Init camera (with retry, matching C++ open_cam logic)
        for attempt in range(3):
            # Camera-specific init
            if is_pro:
                ok = _init_pro(self._dev)
            else:
                ok = _init_compact(self._dev)

            if not ok:
                raise RuntimeError("Camera init_cam() failed")

            # Get first frame (should be frame_id=4 → dead pixel reference)
            raw_data = self._get_frame()
            if raw_data is None:
                logger.warning("First frame acquisition failed, retry %d", attempt + 1)
                continue

            fid = self._frame_id(raw_data)
            if fid != FRAME_ID_DEAD_PIXEL:
                raise RuntimeError(
                    f"Expected first frame id=4 (dead pixel), got {fid}"
                )

            # Build dead pixel list from the first frame
            raw_frame = self._crop_roi(raw_data)
            self._dead_pixel_mask, self._dead_pixel_list = _create_dead_pixel_list(raw_frame)

            # First grab (calibration capture)
            ok = self._do_grab()
            if not ok:
                raise RuntimeError("First grab() failed after init")

            self._is_opened = True

            # Warm up: discard initial frames for sensor stabilisation
            for _ in range(self.warmup_frames):
                try:
                    self.grab()
                except Exception:
                    pass

            logger.info(
                "LibSeekCamera opened: type=%s, resolution=%dx%d",
                self.camera_type, self._width, self._height,
            )
            return

        raise RuntimeError("Failed to initialise camera after 3 attempts")

    def close(self) -> None:
        """Shut down camera and release USB device."""
        if self._dev is not None and self._dev.is_opened:
            # Send stop sequence (3× SET_OPERATION_MODE=0, like C++ close)
            for _ in range(3):
                self._dev.request_set(
                    DeviceCommand.SET_OPERATION_MODE, bytes([0x00, 0x00])
                )
            self._dev.close()
        self._dev = None  # type: ignore[assignment]
        self._is_opened = False
        self._ffc_frame = None
        self._dead_pixel_mask = None
        self._dead_pixel_list = []
        logger.info("LibSeekCamera closed")

    def grab(self) -> np.ndarray:
        """Grab, calibrate, and return a single uint16 thermal frame.

        Equivalent to the C++ ``read()`` call: grab() → retrieve().
        The returned frame has dead pixel filtering and flat-field
        calibration applied.

        Returns
        -------
        np.ndarray
            uint16 array of shape ``(height, width)`` with calibrated
            14-bit thermal data.
        """
        if not self._is_opened:
            raise RuntimeError("Camera not open. Call open() first.")

        if not self._do_grab():
            raise RuntimeError("Frame acquisition failed")

        return self._retrieve()

    def grab_raw(self) -> np.ndarray:
        """Grab a raw, uncalibrated frame (uint16, ROI-cropped).

        Useful for diagnostics and custom processing pipelines.
        """
        if not self._is_opened:
            raise RuntimeError("Camera not open. Call open() first.")

        if not self._do_grab():
            raise RuntimeError("Frame acquisition failed")

        # Return just the ROI-cropped raw data without calibration
        raw = self._get_frame()
        if raw is None:
            raise RuntimeError("Frame acquisition failed")
        return self._crop_roi(raw)

    def grab_temperature_frame(self) -> np.ndarray:
        """Grab a frame and convert to approximate temperatures (°C).

        Uses a linear approximation.  For precision, calibrate against
        a known blackbody source and adjust ``RAW_TEMP_OFFSET`` and
        ``RAW_TEMP_SCALE``.

        Returns
        -------
        np.ndarray
            float32 array of shape ``(height, width)`` with approximate
            temperatures in degrees Celsius.
        """
        raw = self.grab()
        return (raw.astype(np.float32) - RAW_TEMP_OFFSET) / RAW_TEMP_SCALE

    # ── private helpers ──────────────────────────────────────────────

    def _crop_roi(self, raw_data: np.ndarray) -> np.ndarray:
        """Reshape flat raw_data to 2D and extract the ROI."""
        frame_2d = raw_data.reshape(self._raw_height, self._raw_width)
        rx, ry, rw, rh = self._roi
        return frame_2d[ry:ry + rh, rx:rx + rw].copy()

    def _get_frame(self) -> np.ndarray | None:
        """Issue START_GET_IMAGE_TRANSFER and read raw frame data."""
        size_bytes = struct.pack("<I", self._raw_size)
        if not self._dev.request_set(
            DeviceCommand.START_GET_IMAGE_TRANSFER, size_bytes
        ):
            return None

        arr = self._dev.fetch_frame(self._raw_size, self._request_size)
        return arr

    def _do_grab(self) -> bool:
        """Grab frames until we get an image frame (id=3).

        FFC calibration frames (id=1) are captured for flat-field correction.
        Tries up to 40 times (matching C++ logic).
        """
        for _ in range(40):
            raw_data = self._get_frame()
            if raw_data is None:
                return False

            fid = self._frame_id(raw_data)

            if fid == FRAME_ID_IMAGE:
                # Store cropped raw for retrieve()
                self._last_raw = self._crop_roi(raw_data)
                return True

            if fid == FRAME_ID_CALIBRATION:
                # Update flat-field calibration
                self._ffc_frame = self._crop_roi(raw_data)

        return False

    def _retrieve(self) -> np.ndarray:
        """Apply calibration and dead-pixel filter to the last grabbed frame.

        Mimics SeekCam::retrieve():
            raw_frame += offset - flat_field_calibration_frame
            apply_dead_pixel_filter()
            if additional_ffc: dst += offset - additional_ffc
        """
        frame = self._last_raw.astype(np.int32)

        # Flat-field calibration
        if self._ffc_frame is not None:
            frame = frame + FFC_OFFSET - self._ffc_frame.astype(np.int32)

        frame = np.clip(frame, 0, 65535).astype(np.uint16)

        # Dead pixel filter
        if self._dead_pixel_mask is not None:
            frame = _apply_dead_pixel_filter(
                frame, self._dead_pixel_mask, self._dead_pixel_list
            )

        # Additional FFC (user-provided flat-field for corner gradient removal)
        if self._additional_ffc is not None:
            f32 = frame.astype(np.int32) + FFC_OFFSET - self._additional_ffc.astype(np.int32)
            frame = np.clip(f32, 0, 65535).astype(np.uint16)

        return frame

    # ── context manager ──────────────────────────────────────────────

    def __enter__(self) -> "LibSeekCamera":
        self.open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ═══════════════════════════════════════════════════════════════════════
#  Convenience / detection
# ═══════════════════════════════════════════════════════════════════════


def detect_camera() -> str | None:
    """Detect which Seek Thermal camera model is connected via USB.

    Returns ``"compact"``, ``"pro"``, or ``None`` if nothing found.
    """
    try:
        import usb.core
    except ImportError:
        return None

    for pid, name in [(PID_PRO, "pro"), (PID_COMPACT, "compact")]:
        dev = usb.core.find(idVendor=SEEK_VENDOR_ID, idProduct=pid)
        if dev is not None:
            return name
    return None


def list_cameras() -> list[dict[str, Any]]:
    """Return a list of all detected Seek Thermal USB cameras."""
    results: list[dict[str, Any]] = []
    try:
        import usb.core
    except ImportError:
        return results

    for pid, name, w, h in [
        (PID_PRO, "CompactPRO", PRO_WIDTH, PRO_HEIGHT),
        (PID_COMPACT, "Compact/CompactXR", COMPACT_WIDTH, COMPACT_HEIGHT),
    ]:
        devs = list(usb.core.find(
            idVendor=SEEK_VENDOR_ID, idProduct=pid, find_all=True,
        ))
        for i, d in enumerate(devs):
            results.append({
                "type": name,
                "camera_type": "pro" if pid == PID_PRO else "compact",
                "vid": f"0x{SEEK_VENDOR_ID:04X}",
                "pid": f"0x{pid:04X}",
                "index": i,
                "resolution": f"{w}x{h}",
                "bus": getattr(d, "bus", None),
                "address": getattr(d, "address", None),
            })

    return results
