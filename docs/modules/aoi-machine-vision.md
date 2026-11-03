# Automated Optical Inspection (AOI) — Machine Vision Pipeline

> **Version:** 1.0 · **Date:** 2026-03-08 · **Status:** Reference Architecture  
> **Audience:** Test engineers, vision system integrators, QA automation leads  
> **Scope:** End-to-end AOI pipeline for PCB & embedded hardware inspection

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [AOI Pipeline Architecture](#2-aoi-pipeline-architecture)
3. [Hardware Components](#3-hardware-components)
   - 3.1 [Camera Interface Comparison](#31-camera-interface-comparison-for-pcb-inspection)
   - 3.2 [Lighting Systems](#32-lighting-systems)
4. [Software Stack Architecture](#4-software-stack-architecture)
   - 4.1 [GenICam Standard](#41-genicam-standard)
   - 4.2 [Image Acquisition with Harvesters](#42-image-acquisition-with-harvesters)
   - 4.3 [Image Processing Pipeline (OpenCV)](#43-image-processing-pipeline-opencv)
   - 4.4 [Advanced Analysis (scikit-image)](#44-advanced-analysis-scikit-image)
   - 4.5 [Complete System Integration](#45-complete-system-integration)
5. [Hardware BOM Example](#5-hardware-bom-example)
6. [Verified References](#6-verified-references)

---

## 1  System Overview

Automated Optical Inspection (AOI) is a critical quality gate in electronics
manufacturing and embedded systems testing. An AOI system captures high-resolution
images of PCBs and assemblies, then applies machine vision algorithms to detect
defects such as:

- **Missing / misplaced components** — empty pads, tombstoned passives, rotated ICs
- **Solder defects** — bridges, cold joints, insufficient / excess solder
- **Via fill issues** — incomplete fills, voids, overfill
- **Silkscreen & marking errors** — wrong labels, misaligned print
- **Contamination / damage** — flux residue, scratches, cracked components

This document describes the full pipeline from photon capture to pass/fail
decision, with concrete Python code examples using industry-standard open-source
libraries.

---

## 2  AOI Pipeline Architecture

### Comprehensive Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         AOI SYSTEM — END-TO-END PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
  │  CAMERA  │────▶│ FRAME GRABBER│────▶│ IMAGE PROCESSING │────▶│DECISION ENGINE │
  │          │     │              │     │                  │     │                │
  │ GigE /   │     │ GenICam /    │     │ OpenCV +         │     │ Pass / Fail /  │
  │ USB3 /   │     │ Harvesters   │     │ scikit-image     │     │ Warn + Report  │
  │ CoaXPress│     │ GenTL        │     │                  │     │                │
  └──────────┘     └──────────────┘     └──────────────────┘     └────────────────┘
       │                  │                      │                        │
       ▼                  ▼                      ▼                        ▼
  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
  │ LIGHTING │     │ TRANSPORT    │     │ ANALYSIS STAGES  │     │   STORAGE      │
  │ CONTROL  │     │ LAYER        │     │                  │     │                │
  │          │     │              │     │ 1. Pre-process   │     │ • SQLite DB    │
  │ Ring     │     │ • GigE Vision│     │ 2. Alignment     │     │ • JSON reports │
  │ Dome     │     │ • USB3 Vision│     │ 3. Segmentation  │     │ • Image archive│
  │ Backlight│     │ • CoaXPress  │     │ 4. Feature extr. │     │ • CSV metrics  │
  │ Dark fld │     │ • Camera Link│     │ 5. Defect detect │     │ • Markdown log │
  │ Struct.  │     │              │     │ 6. Classification│     │                │
  └──────────┘     └──────────────┘     └──────────────────┘     └────────────────┘
```

### Detailed Data Flow

```
                        ┌────────────────────────────┐
                        │     ILLUMINATION STAGE      │
                        │                            │
                        │  Controller triggers LEDs  │
                        │  per inspection recipe     │
                        └─────────────┬──────────────┘
                                      │ photons
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           IMAGE ACQUISITION STAGE                           │
│                                                                              │
│  ┌─────────────┐    GenTL     ┌──────────────┐   NumPy    ┌──────────────┐  │
│  │   Camera    │─────────────▶│  Harvesters  │───────────▶│  Raw Frame   │  │
│  │  (sensor)   │   transport  │  (GenICam)   │   array    │  (H×W×C)    │  │
│  └─────────────┘              └──────────────┘            └──────┬───────┘  │
│                                                                  │          │
└──────────────────────────────────────────────────────────────────┼──────────┘
                                                                   │
                                                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         IMAGE PROCESSING STAGE                               │
│                                                                              │
│  ┌──────────┐   ┌───────────┐   ┌────────────┐   ┌───────────┐             │
│  │ Correct  │──▶│  Register │──▶│  Segment   │──▶│  Extract  │             │
│  │ & Denoise│   │  & Align  │   │  ROIs      │   │  Features │             │
│  └──────────┘   └───────────┘   └────────────┘   └─────┬─────┘             │
│       │               │               │                  │                   │
│  Flat-field     Template match    Threshold /       Contours,               │
│  White balance  Affine warp      Adaptive mask     Hu moments,              │
│  Gaussian blur  Sub-pixel reg.   Connected comp.   HOG descriptors          │
│                                                                              │
└──────────────────────────────────────────────────────────────────┼───────────┘
                                                                   │
                                                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DECISION ENGINE STAGE                               │
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                     │
│  │   Compare    │──▶│   Classify   │──▶│   Verdict    │                     │
│  │   vs Golden  │   │   Defect     │   │              │                     │
│  │   Reference  │   │   Type       │   │  PASS ✅     │                     │
│  └──────────────┘   └──────────────┘   │  FAIL ❌     │                     │
│                                         │  WARN ⚠️     │                     │
│  Tolerance bands     Categories:        │  REVIEW 🔍   │                     │
│  from limits.json    • Missing part     └──────┬───────┘                     │
│                      • Solder bridge            │                            │
│                      • Misalignment             │                            │
│                      • Tombstone                ▼                            │
│                      • Wrong polarity    ┌──────────────┐                    │
│                      • Via void          │  Report &    │                    │
│                                          │  Archive     │                    │
│                                          └──────────────┘                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3  Hardware Components

### 3.1  Camera Interface Comparison for PCB Inspection

| Feature | GigE Vision | USB3 Vision | CoaXPress (CXP) | Camera Link |
|---|---|---|---|---|
| **Bandwidth** | 1 Gbps (5/10/25 GbE) | 5 Gbps (USB 3.0) | 6.25 / 12.5 Gbps per lane | 255–850 MB/s |
| **Max Cable Length** | 100 m (copper), km (fiber) | 5 m (3 m reliable) | 40 m (coax) | 10 m |
| **Latency** | ~1 ms | ~0.5 ms | < 0.1 ms | < 0.1 ms |
| **Multi-Camera** | ✅ Native (switch/hub) | ⚠️ Hub needed, bandwidth shared | ✅ Multi-lane | ❌ Point-to-point |
| **Power over Cable** | PoE (15–90 W) | USB bus power (4.5 W) | PoCXP (13 W) | Separate supply |
| **GenICam Support** | ✅ Native | ✅ Native | ✅ Native | ⚠️ Via GenCP adapter |
| **Typical Resolution** | 1–150 MP | 1–30 MP | 5–150 MP | 1–25 MP |
| **Frame Rate (5 MP)** | 20–50 fps (1 GbE) | 30–80 fps | 100–300 fps | 50–150 fps |
| **Cost (camera body)** | $200–$2 000 | $100–$1 500 | $2 000–$15 000 | $500–$5 000 |
| **Frame Grabber** | NIC (standard or high-perf) | USB controller | Dedicated PCIe card | Dedicated PCIe card |
| **Best For** | General AOI, multi-cam setups | Desktop prototyping, short runs | High-speed line scan, 100% inspect | Legacy systems |
| **PCB Inspection Fit** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

**Recommendation for pyontrust AOI:**

| Use Case | Recommended Interface | Rationale |
|---|---|---|
| **Lab / prototype** | USB3 Vision | Lowest cost, simple cabling, good for single-board inspection |
| **Production line** | GigE Vision (5 GbE) | Long cables, multi-camera, PoE simplifies wiring |
| **High-speed 100% inspect** | CoaXPress | Maximum throughput for inline scanning at conveyor speed |

### 3.2  Lighting Systems

Proper illumination is the most critical factor in AOI image quality. The wrong
lighting makes even the best camera and software useless.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AOI LIGHTING CONFIGURATIONS                      │
└─────────────────────────────────────────────────────────────────────┘

  1. RING LIGHT                      2. DOME LIGHT (Diffuse)
     ┌─────────┐                        ╭───────────────╮
     │ ○ ○ ○ ○ │  ← LEDs               │ ░░░░░░░░░░░░░ │ ← Diffuse inner
     │ ○     ○ │     around             │ ░░░░░░░░░░░░░ │    coating
     │ ○ LENS ○ │     lens              │ ░░░ LENS ░░░░ │
     │ ○     ○ │                        │ ░░░░░░░░░░░░░ │
     │ ○ ○ ○ ○ │                        ╰───────────────╯
     └────┬────┘                             │
          │                                  │
     ═════╪═════ PCB                    ═════╪═════ PCB
     Highlights solder,                 Eliminates shadows,
     reveals topology                   uniform illumination

  3. DARK FIELD                      4. BACKLIGHT
     ┌───────────┐                      ┌─────────┐ LENS
     │   LENS    │                      └────┬────┘
     └─────┬─────┘                           │
           │                            ═════╪═════ PCB (translucent areas)
     ═════╪═════ PCB                         │
    ╱    │    ╲                         ┌────┴────┐
  ◀──    │    ──▶  LEDs at low         │░░░░░░░░░│ ← Uniform backlight
   angle to surface                     │░░░░░░░░░│    panel
   Reveals scratches,                   └─────────┘
   cracks, surface defects              Via fill, through-hole check

  5. STRUCTURED LIGHT
     ┌─────────┐ LENS
     └────┬────┘
          │
     ═════╪═════ PCB
    ╱╱╱╱╱ │ ╲╲╲╲╲   ← Projected stripe/grid pattern
   Stripe projector    3D height measurement
   (for coplanarity,   of solder joints
    warpage detection)
```

| Lighting Type | Principle | Best For | Limitations |
|---|---|---|---|
| **Ring Light** | Direct, angled LEDs around lens axis | Solder joint inspection, component presence, marking readability | Creates specular reflections on shiny surfaces |
| **Dome Light** | Diffuse hemisphere illumination | Uniform imaging of mixed-finish PCBs, BGA inspection | Lower contrast for topology features |
| **Dark Field** | Low-angle illumination, camera perpendicular | Scratch / crack detection, solder paste height, wire bond inspection | Requires precise angle control |
| **Backlight** | Transmitted illumination from below | Via fill measurement, through-hole component leads, PCB warpage | Only works for translucent / hole features |
| **Structured Light** | Projected pattern (stripes / grid) | 3D solder joint profiling, coplanarity, component height | Complex calibration, slower acquisition |

**Multi-Light Strategy:**  
Production AOI systems typically use **2–4 lighting channels** fired in sequence
(ring → dome → dark field → backlight) to capture different defect types in a
single inspection cycle. The images are then fused in software.

---

## 4  Software Stack Architecture

### 4.1  GenICam Standard

GenICam (Generic Interface for Cameras) is the EMVA standard that abstracts camera
hardware behind a uniform API. It is the foundation of all modern machine vision
systems.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        GenICam STANDARD ARCHITECTURE                             │
│                        (EMVA — European Machine Vision Association)              │
└──────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  USER APPLICATION                    │
│         (pyontrust AOI / Harvesters / etc.)          │
└────────────────────────┬────────────────────────────┘
                         │  GenApi (feature access)
                         ▼
┌─────────────────────────────────────────────────────┐
│                    GenApi Module                      │
│                                                      │
│  Camera features as a standardized node tree:        │
│  ├── Width          (IInteger)                       │
│  ├── Height         (IInteger)                       │
│  ├── ExposureTime   (IFloat, µs)                     │
│  ├── Gain           (IFloat, dB)                     │
│  ├── PixelFormat    (IEnumeration)                   │
│  ├── TriggerMode    (IEnumeration: On/Off)           │
│  ├── TriggerSource  (IEnumeration: Line0/Software)   │
│  └── AcquisitionFrameRate (IFloat, fps)              │
│                                                      │
│  Reads camera's XML description file to build tree   │
└────────────────────────┬────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   GenTL      │ │   GenTL      │ │   GenTL      │
│  Producer    │ │  Producer    │ │  Producer    │
│  (GigE)     │ │  (USB3)     │ │  (CXP)      │
│             │ │             │ │             │
│ .cti file   │ │ .cti file   │ │ .cti file   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  GigE Vision │ │  USB3 Vision │ │  CoaXPress   │
│  Camera      │ │  Camera      │ │  Camera      │
│  (physical)  │ │  (physical)  │ │  (physical)  │
└──────────────┘ └──────────────┘ └──────────────┘

          GenTL = GenICam Transport Layer
          .cti  = Compiled Transport Interface (vendor DLL/SO)
```

**Key GenICam Modules:**

| Module | Purpose |
|---|---|
| **GenApi** | Feature access (exposure, gain, ROI, trigger) via XML-described node tree |
| **GenTL** | Transport Layer — abstracts GigE, USB3, CXP, Camera Link behind one API |
| **GenCP** | Control Protocol — register-level access over any transport |
| **GenDC** | Data Container — standardized multi-part image payload format |
| **SFNC** | Standard Feature Naming Convention — ensures `Width` means the same on all cameras |

### 4.2  Image Acquisition with Harvesters

[Harvesters](https://pypi.org/project/harvesters/) is a Python library that speaks
GenTL natively. It works with any GenICam-compliant camera without vendor-specific
SDKs.

```python
"""
aoi/acquisition.py — Camera acquisition using Harvesters + GenICam

Requirements:
    pip install harvesters numpy opencv-python

You also need a GenTL Producer (.cti file) from your camera vendor:
    - Basler:   PYLON_GENICAM_GENTL64_CTI
    - FLIR:     FLIR_GENTL64_CTI
    - Baumer:   BAUMER_GAPI_SDK
    - IDS:      IDS_GENTL_PRODUCER
    - Aravis:   libaravis (open-source GigE/USB3 producer)
"""
from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Protocol, Optional

import numpy as np

logger = logging.getLogger(__name__)


class FrameGrabber(Protocol):
    """Protocol for camera frame grabbers (matches pyontrust HAL pattern)."""

    def open(self) -> None: ...
    def close(self) -> None: ...
    def configure(self, exposure_us: float, gain_db: float) -> None: ...
    def grab_frame(self) -> np.ndarray: ...
    def grab_sequence(self, count: int, interval_ms: float) -> list[np.ndarray]: ...


class HarvestersGrabber:
    """
    GenICam-compliant frame grabber using Harvesters library.

    Automatically discovers cameras via GenTL Producer (.cti file).
    Works with GigE Vision, USB3 Vision, and CoaXPress cameras.
    """

    def __init__(
        self,
        cti_path: str | Path | None = None,
        camera_index: int = 0,
        pixel_format: str = "Mono8",
    ):
        self._cti_path = self._resolve_cti(cti_path)
        self._camera_index = camera_index
        self._pixel_format = pixel_format
        self._harvester = None
        self._acquirer = None

    @staticmethod
    def _resolve_cti(cti_path: str | Path | None) -> str:
        """Resolve GenTL Producer path from argument or environment."""
        if cti_path:
            return str(cti_path)

        # Check common environment variables
        env_vars = [
            "GENTL_PRODUCER_PATH",
            "PYLON_GENICAM_GENTL64_CTI",
            "FLIR_GENTL64_CTI",
            "GENICAM_GENTL64_PATH",
        ]
        for var in env_vars:
            path = os.environ.get(var)
            if path and Path(path).exists():
                logger.info("Found GenTL producer via %s: %s", var, path)
                return path

        # Aravis open-source fallback (Linux)
        aravis_path = "/usr/lib/x86_64-linux-gnu/libaravis-0.8.so"
        if Path(aravis_path).exists():
            return aravis_path

        raise FileNotFoundError(
            "No GenTL Producer (.cti) found. Set GENTL_PRODUCER_PATH "
            "or install your camera vendor's SDK / Aravis."
        )

    def open(self) -> None:
        """Initialize Harvesters and connect to camera."""
        from harvesters.core import Harvester

        self._harvester = Harvester()
        self._harvester.add_file(self._cti_path)
        self._harvester.update()

        devices = self._harvester.device_info_list
        if not devices:
            raise RuntimeError("No GenICam cameras discovered.")

        logger.info(
            "Discovered %d camera(s): %s",
            len(devices),
            [d.model for d in devices],
        )

        self._acquirer = self._harvester.create(self._camera_index)

        # Configure pixel format via GenApi node
        node_map = self._acquirer.remote_device.node_map
        if hasattr(node_map, "PixelFormat"):
            node_map.PixelFormat.value = self._pixel_format

        self._acquirer.start()
        logger.info("Camera opened: %s", devices[self._camera_index].model)

    def configure(self, exposure_us: float, gain_db: float) -> None:
        """Set exposure and gain via GenApi feature nodes."""
        if not self._acquirer:
            raise RuntimeError("Camera not open. Call open() first.")

        node_map = self._acquirer.remote_device.node_map

        if hasattr(node_map, "ExposureTime"):
            node_map.ExposureTime.value = exposure_us
            logger.debug("ExposureTime set to %.1f µs", exposure_us)

        if hasattr(node_map, "Gain"):
            node_map.Gain.value = gain_db
            logger.debug("Gain set to %.1f dB", gain_db)

    def grab_frame(self) -> np.ndarray:
        """Grab a single frame and return as NumPy array."""
        if not self._acquirer:
            raise RuntimeError("Camera not open. Call open() first.")

        with self._acquirer.fetch() as buffer:
            component = buffer.payload.components[0]
            frame = component.data.reshape(
                component.height, component.width, -1
            ).squeeze()
            return frame.copy()  # Copy before buffer is released

    def grab_sequence(self, count: int, interval_ms: float = 0) -> list[np.ndarray]:
        """Grab multiple frames with optional inter-frame delay."""
        frames = []
        for i in range(count):
            frames.append(self.grab_frame())
            if interval_ms > 0 and i < count - 1:
                time.sleep(interval_ms / 1000.0)
        return frames

    def close(self) -> None:
        """Release camera and Harvesters resources."""
        if self._acquirer:
            self._acquirer.stop()
            self._acquirer.destroy()
            self._acquirer = None
        if self._harvester:
            self._harvester.reset()
            self._harvester = None
        logger.info("Camera closed.")
```

### 4.3  Image Processing Pipeline (OpenCV)

The OpenCV processing stage handles defect detection, alignment, and
classification on raw frames from the acquisition stage.

```python
"""
aoi/processing.py — OpenCV image processing pipeline for AOI

Requirements:
    pip install opencv-python numpy
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────────────

class DefectType(Enum):
    MISSING_COMPONENT = auto()
    SOLDER_BRIDGE = auto()
    TOMBSTONE = auto()
    MISALIGNMENT = auto()
    WRONG_POLARITY = auto()
    EXCESS_SOLDER = auto()
    INSUFFICIENT_SOLDER = auto()
    CONTAMINATION = auto()
    CRACKED_COMPONENT = auto()


class Verdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    REVIEW = "REVIEW"


@dataclass
class Defect:
    """Single detected defect."""
    defect_type: DefectType
    x: int
    y: int
    width: int
    height: int
    confidence: float  # 0.0 – 1.0
    description: str = ""
    severity: Verdict = Verdict.FAIL


@dataclass
class InspectionResult:
    """Result of inspecting one PCB."""
    board_id: str
    verdict: Verdict
    defects: list[Defect] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    annotated_image: Optional[np.ndarray] = None


# ── Pre-processing ───────────────────────────────────────────────────

class ImagePreprocessor:
    """Correct and normalise raw camera frames."""

    def __init__(
        self,
        flat_field: np.ndarray | None = None,
        denoise_strength: int = 5,
    ):
        self._flat_field = flat_field
        self._denoise_strength = denoise_strength

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply correction chain: flat-field → denoise → CLAHE → sharpen."""
        img = frame.copy()

        # 1. Flat-field correction (compensate uneven illumination)
        if self._flat_field is not None:
            img = cv2.divide(img, self._flat_field, scale=255)

        # 2. Denoise (non-local means for Gaussian noise)
        if len(img.shape) == 3:
            img = cv2.fastNlMeansDenoisingColored(
                img, None, self._denoise_strength, self._denoise_strength, 7, 21
            )
        else:
            img = cv2.fastNlMeansDenoising(
                img, None, self._denoise_strength, 7, 21
            )

        # 3. CLAHE (adaptive contrast enhancement)
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)

        # 4. Sharpen via unsharp mask
        blurred = cv2.GaussianBlur(img, (0, 0), 3)
        img = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

        return img


# ── Alignment ────────────────────────────────────────────────────────

class BoardAligner:
    """Register captured image to golden reference using fiducial marks."""

    def __init__(self, reference_image: np.ndarray, method: str = "orb"):
        self._reference = reference_image
        self._method = method

    def align(self, captured: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Align captured image to reference.

        Returns:
            (aligned_image, homography_matrix)
        """
        # Convert to grayscale for feature matching
        ref_gray = cv2.cvtColor(self._reference, cv2.COLOR_BGR2GRAY) \
            if len(self._reference.shape) == 3 else self._reference
        cap_gray = cv2.cvtColor(captured, cv2.COLOR_BGR2GRAY) \
            if len(captured.shape) == 3 else captured

        # Detect features
        if self._method == "orb":
            detector = cv2.ORB_create(nfeatures=5000)
        elif self._method == "sift":
            detector = cv2.SIFT_create(nfeatures=5000)
        else:
            raise ValueError(f"Unknown feature method: {self._method}")

        kp_ref, desc_ref = detector.detectAndCompute(ref_gray, None)
        kp_cap, desc_cap = detector.detectAndCompute(cap_gray, None)

        if desc_ref is None or desc_cap is None:
            raise RuntimeError("Feature detection failed — not enough features.")

        # Match features
        if self._method == "orb":
            matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        else:
            matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

        matches = matcher.knnMatch(desc_cap, desc_ref, k=2)

        # Lowe's ratio test
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]

        if len(good) < 10:
            raise RuntimeError(
                f"Only {len(good)} good matches found (need ≥10). "
                "Check lighting or camera position."
            )

        # Compute homography
        pts_cap = np.float32([kp_cap[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        pts_ref = np.float32([kp_ref[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        H, mask = cv2.findHomography(pts_cap, pts_ref, cv2.RANSAC, 5.0)
        h, w = ref_gray.shape[:2]
        aligned = cv2.warpPerspective(captured, H, (w, h))

        inliers = int(mask.sum()) if mask is not None else 0
        logger.info(
            "Alignment: %d/%d inliers, homography det=%.3f",
            inliers, len(good), np.linalg.det(H),
        )

        return aligned, H


# ── Defect Detection ─────────────────────────────────────────────────

class DefectDetector:
    """Detect PCB defects by comparing aligned image to golden reference."""

    def __init__(
        self,
        reference: np.ndarray,
        diff_threshold: int = 30,
        min_defect_area: int = 50,
        roi_regions: dict[str, tuple[int, int, int, int]] | None = None,
    ):
        """
        Args:
            reference: Golden reference image.
            diff_threshold: Pixel difference threshold (0–255).
            min_defect_area: Minimum contour area to count as defect (pixels²).
            roi_regions: Named ROIs as {name: (x, y, w, h)}.
        """
        self._reference = reference
        self._threshold = diff_threshold
        self._min_area = min_defect_area
        self._rois = roi_regions or {}

    def detect(self, aligned: np.ndarray) -> list[Defect]:
        """Run defect detection on an aligned image."""
        defects = []

        # Convert both to grayscale
        ref_gray = cv2.cvtColor(self._reference, cv2.COLOR_BGR2GRAY) \
            if len(self._reference.shape) == 3 else self._reference
        cap_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY) \
            if len(aligned.shape) == 3 else aligned

        # Absolute difference
        diff = cv2.absdiff(ref_gray, cap_gray)

        # Threshold
        _, binary = cv2.threshold(diff, self._threshold, 255, cv2.THRESH_BINARY)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self._min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Classify defect type based on shape and context
            defect_type = self._classify_defect(
                contour, ref_gray[y : y + h, x : x + w], cap_gray[y : y + h, x : x + w]
            )

            confidence = min(1.0, area / (self._min_area * 10))

            defects.append(
                Defect(
                    defect_type=defect_type,
                    x=x, y=y, width=w, height=h,
                    confidence=confidence,
                    description=f"Area={area:.0f}px², AR={w / max(h, 1):.2f}",
                )
            )

        logger.info("Found %d defect(s) above threshold.", len(defects))
        return defects

    def _classify_defect(
        self, contour: np.ndarray, ref_roi: np.ndarray, cap_roi: np.ndarray
    ) -> DefectType:
        """
        Heuristic defect classification based on contour geometry and intensity.
        """
        _, _, w, h = cv2.boundingRect(contour)
        aspect = w / max(h, 1)
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / max(perimeter ** 2, 1)

        ref_mean = ref_roi.mean() if ref_roi.size else 128
        cap_mean = cap_roi.mean() if cap_roi.size else 128

        # Captured much darker than reference → component missing
        if cap_mean < ref_mean - 40 and area > 500:
            return DefectType.MISSING_COMPONENT

        # Long thin defect → solder bridge
        if aspect > 3.0 or aspect < 0.33:
            return DefectType.SOLDER_BRIDGE

        # Captured brighter → excess solder
        if cap_mean > ref_mean + 30:
            return DefectType.EXCESS_SOLDER

        # High circularity, small area → solder blob
        if circularity > 0.7 and area < 300:
            return DefectType.INSUFFICIENT_SOLDER

        return DefectType.CONTAMINATION  # Fallback


# ── Annotator ────────────────────────────────────────────────────────

class ResultAnnotator:
    """Draw defect overlays on inspection images."""

    _COLORS = {
        Verdict.PASS: (0, 200, 0),       # Green
        Verdict.FAIL: (0, 0, 255),        # Red
        Verdict.WARN: (0, 180, 255),      # Orange
        Verdict.REVIEW: (255, 180, 0),    # Cyan
    }

    @classmethod
    def annotate(cls, image: np.ndarray, result: InspectionResult) -> np.ndarray:
        """Draw bounding boxes and labels for all defects."""
        annotated = image.copy()
        if len(annotated.shape) == 2:
            annotated = cv2.cvtColor(annotated, cv2.COLOR_GRAY2BGR)

        for defect in result.defects:
            color = cls._COLORS.get(defect.severity, (255, 255, 255))
            # Bounding box
            cv2.rectangle(
                annotated,
                (defect.x, defect.y),
                (defect.x + defect.width, defect.y + defect.height),
                color, 2,
            )
            # Label
            label = f"{defect.defect_type.name} ({defect.confidence:.0%})"
            cv2.putText(
                annotated, label,
                (defect.x, defect.y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
            )

        # Overall verdict banner
        verdict_color = cls._COLORS.get(result.verdict, (255, 255, 255))
        cv2.putText(
            annotated,
            f"VERDICT: {result.verdict.value}  |  {len(result.defects)} defect(s)",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, verdict_color, 2,
        )

        return annotated
```

### 4.4  Advanced Analysis (scikit-image)

For higher-fidelity inspection tasks — solder joint quality grading, sub-pixel
component alignment, and via fill measurement — we use
[scikit-image](https://scikit-image.org/) alongside OpenCV.

```python
"""
aoi/analysis.py — Advanced AOI analysis with scikit-image

Requirements:
    pip install scikit-image numpy opencv-python scipy
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage
from skimage import (
    feature,
    filters,
    measure,
    morphology,
    segmentation,
    transform,
)

logger = logging.getLogger(__name__)


# ── Solder Joint Detection & Grading ────────────────────────────────

@dataclass
class SolderJointResult:
    """Analysis result for a single solder joint."""
    x: int
    y: int
    area_px: float
    circularity: float
    mean_intensity: float
    std_intensity: float
    wetting_angle_deg: float  # Estimated from profile
    grade: str  # "GOOD", "COLD", "EXCESS", "INSUFFICIENT", "BRIDGE"


class SolderJointAnalyzer:
    """
    Detect and grade solder joints using scikit-image morphology
    and feature extraction.

    Methodology:
        1. Extract joint ROIs via adaptive thresholding
        2. Measure shape features (area, circularity, convexity)
        3. Estimate wetting angle from intensity profile
        4. Grade each joint against acceptance criteria
    """

    def __init__(
        self,
        min_joint_area: int = 30,
        max_joint_area: int = 5000,
        circularity_threshold: float = 0.4,
    ):
        self._min_area = min_joint_area
        self._max_area = max_joint_area
        self._circ_thresh = circularity_threshold

    def analyze(self, image: np.ndarray, mask: np.ndarray | None = None) -> list[SolderJointResult]:
        """
        Detect and grade solder joints in image.

        Args:
            image: Grayscale or BGR image of solder region.
            mask: Optional binary mask limiting analysis area.

        Returns:
            List of SolderJointResult for each detected joint.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Adaptive threshold to find bright solder regions
        thresh = filters.threshold_local(gray, block_size=51, method="gaussian", offset=-10)
        binary = gray > thresh

        if mask is not None:
            binary = binary & (mask > 0)

        # Clean up with morphological operations
        binary = morphology.remove_small_objects(binary, min_size=self._min_area)
        binary = morphology.remove_small_holes(binary, area_threshold=20)
        binary = morphology.binary_closing(binary, morphology.disk(2))

        # Label connected components
        labels = measure.label(binary)
        regions = measure.regionprops(labels, intensity_image=gray)

        results = []
        for region in regions:
            if not (self._min_area <= region.area <= self._max_area):
                continue

            circularity = (4 * np.pi * region.area) / max(region.perimeter ** 2, 1)
            y, x = region.centroid
            bbox = region.bbox  # (min_row, min_col, max_row, max_col)

            # Estimate wetting angle from radial intensity profile
            wetting = self._estimate_wetting_angle(gray, int(y), int(x), region.equivalent_diameter / 2)

            # Grade the joint
            grade = self._grade_joint(
                area=region.area,
                circularity=circularity,
                mean_intensity=region.mean_intensity,
                std_intensity=float(gray[labels == region.label].std()),
                wetting_angle=wetting,
            )

            results.append(SolderJointResult(
                x=int(x), y=int(y),
                area_px=region.area,
                circularity=circularity,
                mean_intensity=region.mean_intensity,
                std_intensity=float(gray[labels == region.label].std()),
                wetting_angle_deg=wetting,
                grade=grade,
            ))

        logger.info(
            "Solder analysis: %d joints found — %d GOOD, %d defective",
            len(results),
            sum(1 for r in results if r.grade == "GOOD"),
            sum(1 for r in results if r.grade != "GOOD"),
        )
        return results

    def _estimate_wetting_angle(
        self, gray: np.ndarray, cy: int, cx: int, radius: float
    ) -> float:
        """Estimate wetting angle from radial intensity gradient at joint edge."""
        r = max(int(radius), 3)
        # Sample intensity along radial profile
        angles = np.linspace(0, 2 * np.pi, 36)
        gradients = []
        for angle in angles:
            points = []
            for d in range(max(r - 3, 1), r + 3):
                py = int(cy + d * np.sin(angle))
                px = int(cx + d * np.cos(angle))
                if 0 <= py < gray.shape[0] and 0 <= px < gray.shape[1]:
                    points.append(float(gray[py, px]))
            if len(points) >= 3:
                gradients.append(abs(points[-1] - points[0]))

        if not gradients:
            return 45.0  # Default assumption

        # Map average edge gradient to approximate wetting angle
        avg_gradient = np.mean(gradients)
        # Steeper gradient → better wetting (lower angle)
        return max(10.0, min(80.0, 80.0 - avg_gradient * 0.5))

    def _grade_joint(
        self,
        area: float,
        circularity: float,
        mean_intensity: float,
        std_intensity: float,
        wetting_angle: float,
    ) -> str:
        """Grade solder joint based on measured features."""
        if circularity < 0.2:
            return "BRIDGE"  # Very elongated → likely bridge
        if wetting_angle > 60:
            return "COLD"  # Poor wetting
        if area > self._max_area * 0.8:
            return "EXCESS"
        if area < self._min_area * 2:
            return "INSUFFICIENT"
        if std_intensity > 50:
            return "COLD"  # Non-uniform appearance
        return "GOOD"


# ── Component Alignment Measurement ─────────────────────────────────

@dataclass
class AlignmentResult:
    """Sub-pixel alignment measurement for a component."""
    component_id: str
    dx_mm: float  # Offset in X (mm)
    dy_mm: float  # Offset in Y (mm)
    rotation_deg: float  # Rotation error (degrees)
    within_tolerance: bool


class ComponentAlignmentChecker:
    """
    Measure component placement accuracy using sub-pixel template matching
    and orientation detection.
    """

    def __init__(self, px_per_mm: float = 50.0, tolerance_mm: float = 0.1):
        """
        Args:
            px_per_mm: Camera calibration (pixels per millimetre).
            tolerance_mm: Maximum acceptable offset (mm).
        """
        self._px_per_mm = px_per_mm
        self._tolerance = tolerance_mm

    def check_alignment(
        self,
        image: np.ndarray,
        template: np.ndarray,
        expected_x: int,
        expected_y: int,
        component_id: str = "U1",
    ) -> AlignmentResult:
        """
        Measure placement offset of a component vs expected position.

        Uses phase correlation for sub-pixel accuracy.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template

        th, tw = tmpl.shape[:2]

        # Extract ROI around expected location (with margin)
        margin = max(th, tw)
        y1 = max(0, expected_y - margin)
        y2 = min(gray.shape[0], expected_y + th + margin)
        x1 = max(0, expected_x - margin)
        x2 = min(gray.shape[1], expected_x + tw + margin)
        roi = gray[y1:y2, x1:x2]

        # Template match with sub-pixel refinement
        result = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # Sub-pixel refinement via parabolic interpolation
        mx, my = max_loc
        if 0 < mx < result.shape[1] - 1 and 0 < my < result.shape[0] - 1:
            dx_sub = 0.5 * (result[my, mx + 1] - result[my, mx - 1]) / max(
                2 * result[my, mx] - result[my, mx + 1] - result[my, mx - 1], 1e-6
            )
            dy_sub = 0.5 * (result[my + 1, mx] - result[my - 1, mx]) / max(
                2 * result[my, mx] - result[my + 1, mx] - result[my - 1, mx], 1e-6
            )
        else:
            dx_sub, dy_sub = 0.0, 0.0

        # Actual position in full image coordinates
        actual_x = x1 + mx + dx_sub
        actual_y = y1 + my + dy_sub

        # Offset in mm
        dx_mm = (actual_x - expected_x) / self._px_per_mm
        dy_mm = (actual_y - expected_y) / self._px_per_mm

        # Rotation detection via moments
        rotation = self._detect_rotation(roi, tmpl, mx, my)

        offset_mm = np.sqrt(dx_mm ** 2 + dy_mm ** 2)

        return AlignmentResult(
            component_id=component_id,
            dx_mm=dx_mm,
            dy_mm=dy_mm,
            rotation_deg=rotation,
            within_tolerance=offset_mm <= self._tolerance,
        )

    def _detect_rotation(
        self, roi: np.ndarray, template: np.ndarray, mx: int, my: int
    ) -> float:
        """Detect rotation error using image moments."""
        th, tw = template.shape[:2]
        comp_roi = roi[my : my + th, mx : mx + tw]
        if comp_roi.shape != template.shape:
            return 0.0

        # Phase correlation to detect rotation
        f_comp = np.fft.fft2(comp_roi.astype(float))
        f_tmpl = np.fft.fft2(template.astype(float))

        # Log-polar transform for rotation detection
        try:
            comp_lp = transform.warp_polar(comp_roi.astype(float), radius=min(th, tw) // 2)
            tmpl_lp = transform.warp_polar(template.astype(float), radius=min(th, tw) // 2)

            shift, _, _ = feature.phase_cross_correlation(tmpl_lp, comp_lp)
            angle = shift[0] * (360.0 / comp_lp.shape[0])
            return angle
        except Exception:
            return 0.0


# ── Via Fill Inspection ──────────────────────────────────────────────

@dataclass
class ViaFillResult:
    """Via fill quality measurement."""
    via_id: int
    x: int
    y: int
    diameter_px: float
    fill_ratio: float  # 0.0 = empty, 1.0 = perfectly filled
    void_count: int
    grade: str  # "FULL", "PARTIAL", "VOID", "OVERFILL"


class ViaFillInspector:
    """
    Inspect via fill quality using backlight imaging.

    Methodology:
        1. Detect circular vias using Hough Circle Transform
        2. Analyze fill ratio from intensity within via boundary
        3. Detect voids using local thresholding
        4. Grade against IPC-6012 fill requirements
    """

    def __init__(
        self,
        min_radius_px: int = 5,
        max_radius_px: int = 50,
        fill_threshold: float = 0.75,  # IPC-6012 Class 2: ≥75% fill
    ):
        self._min_r = min_radius_px
        self._max_r = max_radius_px
        self._fill_thresh = fill_threshold

    def inspect(self, backlight_image: np.ndarray) -> list[ViaFillResult]:
        """
        Inspect via fill quality from a backlight image.

        Backlit vias: bright = unfilled (light passes through),
                      dark = filled (solder blocks light).
        """
        gray = cv2.cvtColor(backlight_image, cv2.COLOR_BGR2GRAY) \
            if len(backlight_image.shape) == 3 else backlight_image

        # Detect circles (vias)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=self._min_r * 3,
            param1=100,
            param2=30,
            minRadius=self._min_r,
            maxRadius=self._max_r,
        )

        if circles is None:
            logger.warning("No vias detected in backlight image.")
            return []

        results = []
        for i, (cx, cy, r) in enumerate(circles[0].astype(int)):
            # Create circular mask for this via
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)

            via_pixels = gray[mask > 0]
            if via_pixels.size == 0:
                continue

            # In backlight: bright pixels = unfilled, dark = filled
            # Normalize: fill_ratio = fraction of dark pixels
            median_bg = np.median(gray[mask == 0]) if np.any(mask == 0) else 200
            threshold = median_bg * 0.5
            filled_pixels = (via_pixels < threshold).sum()
            fill_ratio = filled_pixels / via_pixels.size

            # Detect voids (small bright spots within filled area)
            via_roi = gray[
                max(0, cy - r) : cy + r,
                max(0, cx - r) : cx + r,
            ]
            void_count = self._count_voids(via_roi, r)

            grade = self._grade_fill(fill_ratio, void_count)

            results.append(ViaFillResult(
                via_id=i,
                x=cx, y=cy,
                diameter_px=2 * r,
                fill_ratio=fill_ratio,
                void_count=void_count,
                grade=grade,
            ))

        logger.info(
            "Via fill: %d vias — %d FULL, %d defective",
            len(results),
            sum(1 for r in results if r.grade == "FULL"),
            sum(1 for r in results if r.grade != "FULL"),
        )
        return results

    def _count_voids(self, via_roi: np.ndarray, radius: int) -> int:
        """Count void regions within a via."""
        if via_roi.size == 0:
            return 0

        # Threshold for bright spots (potential voids)
        _, binary = cv2.threshold(via_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Label connected bright regions
        labeled, n_labels = ndimage.label(binary)
        return max(0, n_labels - 1)  # Subtract background

    def _grade_fill(self, fill_ratio: float, void_count: int) -> str:
        """Grade via fill per IPC-6012 criteria."""
        if fill_ratio > 1.05:
            return "OVERFILL"
        if fill_ratio >= self._fill_thresh and void_count == 0:
            return "FULL"
        if fill_ratio >= self._fill_thresh:
            return "PARTIAL"  # Filled but has voids
        return "VOID"
```

### 4.5  Complete System Integration

This section ties together acquisition, processing, analysis, and storage into a
single AOI inspection run.

```python
"""
aoi/inspector.py — Complete AOI system integration

Requirements:
    pip install harvesters opencv-python scikit-image numpy scipy

Usage:
    inspector = AOIInspector.from_config("aoi_config.json")
    inspector.open()
    result = inspector.inspect_board("SN-001")
    inspector.close()
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Local imports (from this package)
# from .acquisition import HarvestersGrabber
# from .processing import (
#     ImagePreprocessor, BoardAligner, DefectDetector,
#     ResultAnnotator, InspectionResult, Verdict,
# )
# from .analysis import SolderJointAnalyzer, ComponentAlignmentChecker, ViaFillInspector

logger = logging.getLogger(__name__)


class AOIInspector:
    """
    Complete AOI inspection system.

    Orchestrates the full pipeline:
        Camera → Pre-process → Align → Detect → Analyse → Decide → Store
    """

    def __init__(
        self,
        grabber,           # FrameGrabber protocol
        preprocessor,      # ImagePreprocessor
        aligner,           # BoardAligner
        detector,          # DefectDetector
        solder_analyzer,   # SolderJointAnalyzer
        alignment_checker, # ComponentAlignmentChecker
        via_inspector,     # ViaFillInspector
        db_path: Path = Path("aoi_results.db"),
        image_archive: Path = Path("aoi_images"),
    ):
        self._grabber = grabber
        self._preprocessor = preprocessor
        self._aligner = aligner
        self._detector = detector
        self._solder = solder_analyzer
        self._alignment = alignment_checker
        self._via = via_inspector
        self._db_path = db_path
        self._archive = image_archive
        self._db: sqlite3.Connection | None = None

    @classmethod
    def from_config(cls, config_path: str | Path) -> "AOIInspector":
        """
        Factory: build full AOI system from JSON configuration.

        Example config (aoi_config.json):
        {
            "camera": {
                "cti_path": "C:/Program Files/Basler/Runtime/ProducerU3V.cti",
                "camera_index": 0,
                "pixel_format": "BayerRG8",
                "exposure_us": 5000,
                "gain_db": 0
            },
            "reference_image": "golden/reference_board.png",
            "processing": {
                "denoise_strength": 5,
                "diff_threshold": 30,
                "min_defect_area": 50
            },
            "analysis": {
                "px_per_mm": 50.0,
                "alignment_tolerance_mm": 0.1,
                "via_fill_threshold": 0.75,
                "solder_min_area": 30,
                "solder_max_area": 5000
            },
            "storage": {
                "db_path": "aoi_results.db",
                "image_archive": "aoi_images"
            }
        }
        """
        config = json.loads(Path(config_path).read_text())

        cam_cfg = config["camera"]
        proc_cfg = config.get("processing", {})
        analysis_cfg = config.get("analysis", {})
        store_cfg = config.get("storage", {})

        # Load golden reference
        ref_path = config["reference_image"]
        reference = cv2.imread(ref_path)
        if reference is None:
            raise FileNotFoundError(f"Reference image not found: {ref_path}")

        grabber = HarvestersGrabber(
            cti_path=cam_cfg.get("cti_path"),
            camera_index=cam_cfg.get("camera_index", 0),
            pixel_format=cam_cfg.get("pixel_format", "Mono8"),
        )

        return cls(
            grabber=grabber,
            preprocessor=ImagePreprocessor(
                denoise_strength=proc_cfg.get("denoise_strength", 5),
            ),
            aligner=BoardAligner(reference),
            detector=DefectDetector(
                reference=reference,
                diff_threshold=proc_cfg.get("diff_threshold", 30),
                min_defect_area=proc_cfg.get("min_defect_area", 50),
            ),
            solder_analyzer=SolderJointAnalyzer(
                min_joint_area=analysis_cfg.get("solder_min_area", 30),
                max_joint_area=analysis_cfg.get("solder_max_area", 5000),
            ),
            alignment_checker=ComponentAlignmentChecker(
                px_per_mm=analysis_cfg.get("px_per_mm", 50.0),
                tolerance_mm=analysis_cfg.get("alignment_tolerance_mm", 0.1),
            ),
            via_inspector=ViaFillInspector(
                fill_threshold=analysis_cfg.get("via_fill_threshold", 0.75),
            ),
            db_path=Path(store_cfg.get("db_path", "aoi_results.db")),
            image_archive=Path(store_cfg.get("image_archive", "aoi_images")),
        )

    # ── Lifecycle ────────────────────────────────────────────────────

    def open(self) -> None:
        """Initialize camera and database."""
        self._grabber.open()
        self._archive.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info("AOI Inspector ready.")

    def close(self) -> None:
        """Release all resources."""
        self._grabber.close()
        if self._db:
            self._db.close()
            self._db = None
        logger.info("AOI Inspector closed.")

    # ── Main Inspection ──────────────────────────────────────────────

    def inspect_board(self, board_id: str) -> InspectionResult:
        """
        Run full AOI inspection on one board.

        Pipeline:
            1. Grab frame
            2. Pre-process (flat-field, denoise, CLAHE)
            3. Align to golden reference
            4. Detect defects (OpenCV difference analysis)
            5. Analyse solder joints (scikit-image)
            6. Check component alignment (sub-pixel template match)
            7. Inspect via fill (backlight analysis)
            8. Aggregate verdict
            9. Store results + archive images
        """
        t0 = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Acquire
        raw_frame = self._grabber.grab_frame()
        t_acquire = time.perf_counter() - t0

        # 2. Pre-process
        processed = self._preprocessor.process(raw_frame)
        t_preproc = time.perf_counter() - t0 - t_acquire

        # 3. Align
        try:
            aligned, homography = self._aligner.align(processed)
        except RuntimeError as e:
            logger.error("Alignment failed for %s: %s", board_id, e)
            return InspectionResult(
                board_id=board_id,
                verdict=Verdict.REVIEW,
                metrics={"error": "alignment_failed"},
            )
        t_align = time.perf_counter() - t0 - t_acquire - t_preproc

        # 4. Defect detection
        defects = self._detector.detect(aligned)

        # 5. Solder joint analysis
        solder_results = self._solder.analyze(aligned)
        solder_defects = [r for r in solder_results if r.grade != "GOOD"]

        # 6. Component alignment (example: check all ROI templates)
        # In production, iterate over component list from BOM
        alignment_results = []

        # 7. Via fill inspection
        via_results = self._via.inspect(aligned)
        via_defects = [r for r in via_results if r.grade not in ("FULL",)]

        # 8. Aggregate verdict
        total_defects = len(defects) + len(solder_defects) + len(via_defects)
        if total_defects == 0:
            verdict = Verdict.PASS
        elif any(d.confidence > 0.8 for d in defects):
            verdict = Verdict.FAIL
        elif total_defects <= 2:
            verdict = Verdict.WARN
        else:
            verdict = Verdict.FAIL

        t_total = time.perf_counter() - t0

        result = InspectionResult(
            board_id=board_id,
            verdict=verdict,
            defects=defects,
            metrics={
                "total_defects": total_defects,
                "solder_defects": len(solder_defects),
                "via_defects": len(via_defects),
                "solder_joints_total": len(solder_results),
                "vias_total": len(via_results),
                "time_acquire_s": t_acquire,
                "time_preprocess_s": t_preproc,
                "time_align_s": t_align,
                "time_total_s": t_total,
                "timestamp": timestamp,
            },
        )

        # 9. Annotate and archive
        result.annotated_image = ResultAnnotator.annotate(aligned, result)
        self._archive_result(board_id, raw_frame, result)
        self._store_result(result)

        logger.info(
            "Board %s: %s — %d defects in %.3f s",
            board_id, verdict.value, total_defects, t_total,
        )
        return result

    # ── Storage ──────────────────────────────────────────────────────

    def _init_database(self) -> None:
        """Create SQLite database and tables."""
        self._db = sqlite3.connect(str(self._db_path))
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id    TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                verdict     TEXT NOT NULL,
                defect_count INTEGER,
                metrics     TEXT,  -- JSON blob
                image_path  TEXT
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS defects (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id   INTEGER REFERENCES inspections(id),
                defect_type     TEXT,
                x               INTEGER,
                y               INTEGER,
                width           INTEGER,
                height          INTEGER,
                confidence      REAL,
                description     TEXT
            )
        """)
        self._db.commit()

    def _store_result(self, result: InspectionResult) -> None:
        """Persist inspection result to SQLite."""
        if not self._db:
            return

        cursor = self._db.execute(
            """INSERT INTO inspections (board_id, timestamp, verdict, defect_count, metrics, image_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result.board_id,
                result.metrics.get("timestamp", ""),
                result.verdict.value,
                len(result.defects),
                json.dumps(result.metrics, default=str),
                str(self._archive / f"{result.board_id}_annotated.png"),
            ),
        )
        inspection_id = cursor.lastrowid

        for defect in result.defects:
            self._db.execute(
                """INSERT INTO defects
                   (inspection_id, defect_type, x, y, width, height, confidence, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    inspection_id,
                    defect.defect_type.name,
                    defect.x, defect.y,
                    defect.width, defect.height,
                    defect.confidence,
                    defect.description,
                ),
            )

        self._db.commit()

    def _archive_result(
        self, board_id: str, raw: np.ndarray, result: InspectionResult
    ) -> None:
        """Save raw + annotated images to disk."""
        cv2.imwrite(str(self._archive / f"{board_id}_raw.png"), raw)
        if result.annotated_image is not None:
            cv2.imwrite(
                str(self._archive / f"{board_id}_annotated.png"),
                result.annotated_image,
            )

        # Save metrics as JSON sidecar
        metrics_path = self._archive / f"{board_id}_metrics.json"
        metrics_path.write_text(json.dumps(result.metrics, indent=2, default=str))
```

---

## 5  Hardware BOM Example

Estimated costs for a lab-grade AOI station suitable for PCB prototype inspection.

| # | Component | Example Model | Specification | Est. Cost (USD) |
|---|---|---|---|---|
| 1 | **Area Scan Camera** | Basler ace 2 a2A2448-75ucBAS | 5 MP, USB3, Sony IMX547, 75 fps | $350–$500 |
| 2 | **Lens** | Computar M0824-MPW2 | 8 mm, 2/3", 5 MP rated, C-mount | $80–$150 |
| 3 | **Ring Light** | Smart Vision Lights RM75-WHI | 75 mm ring, white LED, 24 V | $120–$200 |
| 4 | **Dome Light** | CCS LFV2-50SW | 50 mm dome, diffuse white | $200–$350 |
| 5 | **Backlight Panel** | Metaphase MB-BL4x4-W | 4×4″ uniform white LED backlight | $150–$250 |
| 6 | **Light Controller** | Gardasoft PP820 | 2-channel strobe, RS-232 / TTL | $300–$500 |
| 7 | **XY Stage** (optional) | Thorlabs MLS203-1 | 110×75 mm travel, 0.1 µm res. | $2 000–$4 000 |
| 8 | **Mounting Hardware** | Thorlabs posts + breadboard | Optical table or 80/20 frame | $200–$400 |
| 9 | **PC / GPU** | Any workstation | i7/Ryzen 7, 32 GB RAM, NVMe SSD | $800–$1 500 |
| 10 | **USB3 Hub / NIC** | StarTech 4-port USB 3.1 | Industrial grade, screw-lock | $50–$100 |
| | | | **Lab Setup Total** | **$4 250–$7 950** |

> **Note:** Production-grade AOI systems (GigE, multi-camera, conveyor integration)
> typically cost $15 000–$50 000+ depending on camera count and stage automation.

---

## 6  Verified References

| # | Library / Standard | Version | URL |
|---|---|---|---|
| 1 | **OpenCV** | 4.13.0+ | [pypi.org/project/opencv-python](https://pypi.org/project/opencv-python/) · [docs.opencv.org/4.x](https://docs.opencv.org/4.x/) |
| 2 | **Harvesters** | 1.4.3+ | [pypi.org/project/harvesters](https://pypi.org/project/harvesters/) |
| 3 | **Aravis** | 0.8.35+ | [github.com/AravisProject/aravis](https://github.com/AravisProject/aravis) |
| 4 | **GenICam / EMVA** | Standard | [emva.org/standards-technology/genicam](https://emva.org/standards-technology/genicam/) |
| 5 | **scikit-image** | 0.26.0+ | [scikit-image.org](https://scikit-image.org/) · [pypi.org/project/scikit-image](https://pypi.org/project/scikit-image/) |

---

## Appendix A — Integration with pyontrust

The AOI pipeline integrates into the existing pyontrust architecture via:

| Integration Point | How |
|---|---|
| **`FrameGrabber` Protocol** | Matches existing `PowerMeter` / `Recorder` protocol pattern in `pyontrust.hal` |
| **Instrument Factory** | Register `"aoi_camera"` type in lab bench JSON alongside `"webcam"`, `"ppk2"`, etc. |
| **Profile Runner** | Add `"inspect"` action type to test profiles for inline AOI during power tests |
| **Artifact System** | Annotated images + JSON metrics stored in standard `artifacts/` directory |
| **Limits / Verdicts** | Reuse existing `Verdict` system (PASS / FAIL / WARN) from `pyontrust.core.limits` |
| **Database** | SQLite results DB can be queried by the Flask gateway dashboard |

```json
{
  "name": "my_lab_bench",
  "instruments": {
    "power_meter": {"type": "ppk2", "serial_port": "auto"},
    "aoi_camera": {
      "type": "aoi",
      "cti_path": "C:/Program Files/Basler/Runtime/ProducerU3V.cti",
      "exposure_us": 5000,
      "gain_db": 0,
      "reference_image": "golden/reference_board.png"
    }
  }
}
```
