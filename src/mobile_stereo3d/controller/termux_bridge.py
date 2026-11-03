"""Termux bridge — per-device camera & microphone control from the PC.

Two capture backends (auto-selected):

* ``helper``  — com.pyontrust.camera APK: manual focus distance / AF mode per
  frame, still JPEGs written to the app's external files dir (true different-
  focus capture on HALs that honour LENS_FOCUS_DISTANCE).
* ``termux``  — stock termux-api tools (termux-camera-photo,
  termux-microphone-record): no manual focus, but zero extra installs.

Focus/exposure are locked per the design notes: phones must not re-focus or
re-gain between stereo frames or calibration drifts.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import cv2  # optional at import time; required for image backends
except ImportError:  # pragma: no cover
    cv2 = None

from .adb_manager import ADBManager, DeviceInfo

HELPER_PKG = "com.pyontrust.camera"
HELPER_CAPDIR = f"/sdcard/Android/data/{HELPER_PKG}/files/captures"
TERMUX_BIN_DIR = "/data/data/com.termux/files/usr/bin"


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) required for image capture — pip install opencv-python")


@dataclass
class CameraConfig:
    """Locked imaging parameters for a bridge (design note #2)."""

    auto_focus: bool = False
    focus_diopter: float | None = None   # manual LENS_FOCUS_DISTANCE when auto_focus=False
    af_mode: str | None = None           # "auto" | "macro" | "continuous"
    iso: int | None = None               # advisory (HAL-dependent)
    exposure_us: int | None = None       # advisory (HAL-dependent)

    def to_extras(self, index: int) -> dict[str, Any]:
        """Map to helper-APK broadcast extras for capture frame ``index``."""
        ex: dict[str, Any] = {"req_id": index}
        if self.af_mode:
            ex["af_mode"] = self.af_mode
        elif not self.auto_focus and self.focus_diopter is not None:
            ex["focus"] = float(self.focus_diopter)
        return ex


class TermuxBridge:
    """One phone's camera (and microphone) as a PC-side instrument.

    >>> adb = ADBManager()
    >>> cam = TermuxBridge(adb, device=adb.get_device(0), port=8081)
    >>> frame = cam.capture_still(index=3)          # BGR numpy array
    """

    def __init__(self, adb: ADBManager | None = None,
                 device: DeviceInfo | str | None = None,
                 port: int = 8081, camera_id: int = 0,
                 config: CameraConfig | None = None) -> None:
        self.adb = adb or ADBManager()
        if isinstance(device, str):
            device = DeviceInfo(serial=device, transport="usb", state="device")
        self.device = device
        self.port = port
        self.camera_id = camera_id
        self.config = config or CameraConfig()
        self._helper_present: bool | None = None

    # ── capability probing ───────────────────────────────────────
    def _s(self, *cmd: str, timeout: int = 30) -> str:
        return self.adb.shell(*cmd, serial=self.device.serial if self.device else None, timeout=timeout)

    def helper_available(self) -> bool:
        if self._helper_present is None:
            try:
                out = self._s("pm", "list", "packages")
                self._helper_present = HELPER_PKG in out
            except Exception:
                self._helper_present = False
        return self._helper_present

    def termux_available(self) -> bool:
        try:
            return os.path.basename(TERMUX_BIN_DIR + "/termux-camera-photo") in self._s(
                "run-as", "com.termux.api", "ls", TERMUX_BIN_DIR)
        except Exception:
            return False

    def backend(self, prefer: str = "auto") -> str:
        if prefer == "helper" and not self.helper_available():
            raise RuntimeError(f"{HELPER_PKG} not installed on {self.device.serial}")
        if prefer == "termux" and not self.termux_available():
            raise RuntimeError("Termux + Termux:API not available on device")
        return "helper" if self.helper_available() else "termux"

    # ── camera control (design note #2: lock focus/exposure) ─────
    def configure_camera(self, auto_focus: bool = False, ISO: int | None = None,
                         exposure_us: int | None = None,
                         focus_diopter: float | None = None,
                         af_mode: str | None = None) -> CameraConfig:
        """Store locked imaging parameters applied to every subsequent capture."""
        self.config = CameraConfig(
            auto_focus=auto_focus, focus_diopter=focus_diopter, af_mode=af_mode,
            iso=ISO, exposure_us=exposure_us)
        return self.config

    # ── still capture ────────────────────────────────────────────
    def capture_still(self, index: int = 0, out_dir: str | Path = "/tmp/mobile_stereo3d",
                      backend: str = "auto") -> Any:
        """Capture one JPEG still from this phone's camera → BGR numpy array."""
        _require_cv2()
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        local = out / f"cam{self.camera_id}_{index:03d}.jpg"
        be = self.backend(backend)

        if be == "helper":
            extras = self.config.to_extras(index)
            args = ["am", "broadcast", "-n", f"{HELPER_PKG}/.CaptureReceiver",
                    "-a", "com.pyontrust.camera.CAPTURE"]
            for k, v in extras.items():
                if isinstance(v, float):
                    args += ["--ef", str(k), str(v)]
                elif isinstance(v, int) and not isinstance(v, bool):
                    args += ["--ei", str(k), str(v)]
                else:
                    args += ["--el", str(k), "0"]  # --ez broken on some am builds; unused here
            remote = f"{HELPER_CAPDIR}/{local.name}"
            self._s(*args, "-d", f"file:///{remote}", timeout=45)
            time.sleep(8)  # async capture on device (~1-3 s typical)
            with open(local, "wb") as fh:
                subprocess.run(f'adb {"-s " + self.device.serial if self.device else ""} '
                               f'shell cat {remote}', shell=True, stdout=fh, timeout=60)
        else:
            remote = f"/data/data/com.termux/files/home/stereo3d/{local.name}"
            self._s("run-as", "com.termux.api", "sh", "-c",
                    f"mkdir -p /data/data/com.termux/files/home/stereo3d && "
                    f"{TERMUX_BIN_DIR}/termux-camera-photo {remote}", timeout=90)
            with open(local, "wb") as fh:
                subprocess.run(f'adb {"-s " + self.device.serial if self.device else ""} '
                               f'shell run-as com.termux.api cat {remote}', shell=True, stdout=fh, timeout=60)

        if not local.exists() or local.stat().st_size == 0:
            raise RuntimeError(f"capture failed on {self.device.serial}")
        img = cv2.imread(str(local))
        if img is None:
            raise RuntimeError(f"unreadable JPEG from {self.device.serial}")
        return img

    # ── microphone (for the beamforming matrix) ──────────────────
    def record_audio(self, seconds: float = 5.0, out_dir: str | Path = "/tmp/mobile_stereo3d",
                     sample_rate: int = 48000) -> Path:
        """Record raw microphone audio via termux-microphone-record (WAV)."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        local = out / f"mic_{self.device.serial if self.device else 'dev'}_{int(time.time())}.wav"
        remote = f"/data/data/com.termux/files/home/stereo3d/{local.name}"
        self._s("run-as", "com.termux.api", "sh", "-c",
                f"mkdir -p /data/data/com.termux/files/home/stereo3d && "
                f"{TERMUX_BIN_DIR}/termux-microphone-record {remote}", timeout=int(seconds * 1000) + 20000)
        with open(local, "wb") as fh:
            subprocess.run(f'adb {"-s " + self.device.serial if self.device else ""} '
                           f'shell run-as com.termux.api cat {remote}', shell=True, stdout=fh, timeout=60)
        return local


__all__ = ["TermuxBridge", "CameraConfig"]
