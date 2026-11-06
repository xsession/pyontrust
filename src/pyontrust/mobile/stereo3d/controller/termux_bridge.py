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
TERMUX_PKG = "com.termux"                      # package owning the binaries (run-as target)
TERMUX_BIN_DIR = f"/data/data/{TERMUX_PKG}/files/usr/bin"
TERMUX_SH = "/system/bin/sh"                    # universal shell, works under run-as


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
            listing = self._s("run-as", TERMUX_PKG, "ls", TERMUX_BIN_DIR)
            return ("termux-camera-photo" in listing and
                    "termux-microphone-record" in listing)
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
    def capture_still(self, index: int = 0, out_dir: str | Path = "/tmp/pyontrust.mobile.stereo3d",
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
            remote = f"/data/data/{TERMUX_PKG}/files/home/stereo3d/{local.name}"
            self._s("run-as", TERMUX_PKG, TERMUX_SH, "-c",
                    f"mkdir -p /data/data/{TERMUX_PKG}/files/home/stereo3d && "
                    f"{TERMUX_BIN_DIR}/termux-camera-photo {remote}", timeout=90)
            with open(local, "wb") as fh:
                subprocess.run(f'adb {"-s " + self.device.serial if self.device else ""} '
                               f'shell run-as {TERMUX_PKG} cat {remote}', shell=True, stdout=fh, timeout=60)

        if not local.exists() or local.stat().st_size == 0:
            raise RuntimeError(f"capture failed on {self.device.serial}")
        img = cv2.imread(str(local))
        if img is None:
            raise RuntimeError(f"unreadable JPEG from {self.device.serial}")
        return img

    # ── microphone (for the beamforming matrix) ──────────────────
    def record_audio(self, seconds: float = 5.0, out_dir: str | Path = "/tmp/pyontrust.mobile.stereo3d",
                     sample_rate: int = 48000) -> Path:
        """Record microphone audio via termux-microphone-record (Termux:API ≥ 0.5x).

        The v0.53+ client speaks the app's local-socket protocol and starts an
        *asynchronous* background recording, so we must start → wait → stop(-q)
        explicitly; cat-ing the file right after start would grab a partial file.
        Output is AAC-in-MP4 regardless of extension — when ffmpeg is available it
        is decoded to 16-bit PCM WAV for the beamforming pipeline (raw .m4a kept).
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        tag = self.device.serial if self.device else "dev"
        ts = int(time.time())
        raw_local = out / f"mic_{tag}_{ts}.m4a"
        remote_dir = f"/data/data/{TERMUX_PKG}/files/home/stereo3d"
        remote = f"{remote_dir}/{raw_local.name}"
        bin_rec = f"{TERMUX_BIN_DIR}/termux-microphone-record"

        self._s("run-as", TERMUX_PKG, "mkdir", "-p", remote_dir)
        # start — returns immediately; capture runs in the Termux:API service
        self._s("run-as", TERMUX_PKG, bin_rec, "-f", remote,
                "-l", str(max(1, int(seconds))), "-r", str(sample_rate), timeout=30)
        time.sleep(seconds + 1.5)          # let the service capture the full window
        self._s("run-as", TERMUX_PKG, bin_rec, "-q", timeout=30)   # stop & finalize

        with open(raw_local, "wb") as fh:
            subprocess.run(f'adb {"-s " + tag if self.device else ""} '
                           f'shell run-as {TERMUX_PKG} cat {remote}', shell=True, stdout=fh, timeout=60)
        if not raw_local.exists() or raw_local.stat().st_size == 0:
            raise RuntimeError(f"recording failed on {tag}")

        # decode AAC → PCM WAV when ffmpeg is present (pipeline expects linear PCM)
        wav = out / f"mic_{tag}_{ts}.wav"
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw_local),
                            "-acodec", "pcm_s16le", "-ar", str(sample_rate), str(wav)],
                           check=True, capture_output=True, timeout=60)
            if wav.exists() and wav.stat().st_size > 44:
                return wav
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        return raw_local


__all__ = ["TermuxBridge", "CameraConfig"]
