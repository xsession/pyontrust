# Seek Thermal Integration

Status: **working** — verified end-to-end on Linux (2026-11-03).

## Hardware

| Property | Value |
|---|---|
| Model | Seek Compact (PIR206) |
| USB ID | `289d:0010` |
| Sensor output | 207 × 154 uint16 radiometric frame (raw buffer 208 × 156) |
| Protocol | vendor-specific USB control + bulk transfers (**not** UVC) |

Because the Seek Compact presents **vendor-specific interfaces** (class `ff`),
the Linux `uvcvideo` driver does not bind and no `/dev/video*` node is
created. Capture must go through libusb — which is exactly what the bundled
driver does.

## Driver

`src/pyontrust/instruments/libseek_driver.py` is a pure-Python port of the
[OpenThermal/libseek-thermal](https://github.com/OpenThermal/libseek-thermal)
C++ reference (Compact + CompactPRO init sequences, FFC calibration, dead-pixel
filter). Dependencies: `pyusb`, `numpy`.

```python
from pyontrust.instruments.libseek_driver import detect_camera, LibSeekCamera

cam = LibSeekCamera(camera_type=detect_camera())   # "compact" | "pro"
cam.open()                                          # raises on failure
frame = cam.grab()                                  # (154, 207) uint16
cam.close()
```

## Linux USB permissions (required)

The kernel creates `/dev/bus/usb/<bus>/<addr>` with mode `640 root:root`, so
a normal user cannot open the device. Two-part fix:

**Immediate:**

```bash
sudo chmod 666 /dev/bus/usb/001/*
```

**Persistent (survives reconnects and reboots):**

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="289d", MODE="0666"' \
    | sudo tee /etc/udev/rules.d/99-seek.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

> ⚠️ **Gotcha:** when the camera disconnects and re-enumerates it gets a
> *new* device node, which resets to `640`. The udev rule above handles this;
> a one-off `chmod` does not.

## Driver bug fixed (2026-11-03)

The original `_init_compact()` sequence contained three commands **not present**
in the C++ reference `SeekThermal::init_cam()`:

1. early `SET_FACTORY_SETTINGS_FEATURES [0x06,0x00,0x08,…]` + 12-byte read
2. `SET_FIRMWARE_INFO_FEATURES [0x17,0x00]` ← caused **EPIPE** and crashed the
   camera off the USB bus
3. a 64-byte `GET_FIRMWARE_INFO` before the factory-settings block

All three were removed so the Python init matches the reference exactly:

```
TARGET_PLATFORM → SET_OPERATION_MODE(0) → GET_FIRMWARE_INFO(4) → READ_CHIP_ID
→ [SET_FACTORY_SETTINGS_FEATURES + GET_FACTORY_SETTINGS] × 4
→ SET_IMAGE_PROCESSING_MODE → GET_OPERATION_MODE
→ SET_IMAGE_PROCESSING_MODE → SET_OPERATION_MODE(1) → GET_OPERATION_MODE
```

## Verification (2026-11-03, Linux 6.8, pyusb via Python 3.12)

| Step | Result |
|---|---|
| `detect_camera()` | `"compact"` ✓ |
| `open()` | OK in ~2 s (one EPIPE on first `TARGET_PLATFORM`, recovered by built-in retry) |
| `grab()` | `(154, 207)` uint16, values 15628–15846 (uniform scene) ✓ |

## Spectroscope webcam identification (same session)

The USB spectroscope on this bench is the **Microdia Defender G-Lens 2577
HD720p** (`0c45:6341`), which enumerates as `/dev/video4` (MJPG, up to
1280×720). It is *not* the other Microdia device on the bench
(`0c45:636b`, a plain webcam at `/dev/video2`). Capture verified with OpenCV;
the spectroscopy pipeline entry point is `mobile_spectroscopy.SpectrometerPipeline`.

> Note: the 4-port hub feeding this bench has intermittent power failures
> (`Cannot enable. Maybe the USB cable is bad?` in kern.log). If a device
> drops off, re-check permissions on its new node and prefer a powered port.
