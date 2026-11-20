"""Android phone cameras over ADB (Termux:API) — any camera, any phone.

Uses ``termux-camera-info`` to enumerate a phone's cameras (id, facing,
focal length, JPEG sizes) and ``termux-camera-photo -c <id>`` to take a
full-resolution still from a specific camera — e.g. any of the back cameras
on multi-camera phones.  Images are pulled with ``adb exec-out`` (binary
safe) and decoded in memory; nothing is left on the phone.

Requirements on each phone: USB debugging authorised, Termux + Termux:API
installed (Termux:API needs the CAMERA permission, granted on first use).
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger("pyontrust.instruments.phone_camera")

TERMUX = "com.termux"
TERMUX_API = "com.termux.api"
_BIN = f"/data/data/{TERMUX}/files/usr/bin"
_HOME = f"/data/data/{TERMUX}/files/home"

_LOCKS: dict[str, threading.Lock] = {}          # one capture per phone at a time
_LOCKS_GUARD = threading.Lock()
_CAMERA_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


class PhoneCameraError(RuntimeError):
    """Actionable error (message is shown to the user as-is)."""


def _adb(*args: str, timeout: float = 30, binary: bool = False) -> Any:
    exe = shutil.which("adb")
    if exe is None:
        raise PhoneCameraError("adb not found — install Android platform-tools")
    r = subprocess.run([exe, *args], capture_output=True, timeout=timeout)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).decode(errors="replace").strip()
        raise PhoneCameraError(msg or f"adb {' '.join(args[:3])} failed")
    return r.stdout if binary else r.stdout.decode(errors="replace")


def _lock(serial: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(serial, threading.Lock())


@dataclass
class Phone:
    serial: str
    state: str                       # "device" | "unauthorized" | "offline" | …
    model: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.state == "device"

    @property
    def label(self) -> str:
        return (self.model or self.serial).replace("_", " ")

    @property
    def hint(self) -> str:
        if self.state == "unauthorized":
            return "Unlock the phone and tap “Allow USB debugging”"
        if self.state == "offline":
            return "Phone is offline — reconnect the USB cable"
        return ""


def list_phones() -> list[Phone]:
    """All phones ADB sees (including ones not yet authorised)."""
    try:
        out = _adb("devices", "-l", timeout=10)
    except (PhoneCameraError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("adb devices failed: %s", exc)
        return []
    phones = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        extra = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        phones.append(Phone(serial=parts[0], state=parts[1], model=extra.get("model", ""), extra=extra))
    return phones


def cameras(serial: str, max_age_s: float = 60.0) -> list[dict[str, Any]]:
    """Cameras of one phone: ``[{id, facing, focal_mm, max_size: [w, h]}]`` (cached)."""
    cached = _CAMERA_CACHE.get(serial)
    if cached and time.time() - cached[0] < max_age_s:
        return cached[1]
    packages = _adb("-s", serial, "shell", "pm", "list", "packages", TERMUX_API, timeout=15)
    if f"package:{TERMUX_API}" not in packages:
        raise PhoneCameraError("Termux:API is not installed on the phone (install Termux and Termux:API)")
    raw = _adb("-s", serial, "shell", "run-as", TERMUX, f"{_BIN}/termux-camera-info", timeout=30)
    try:
        info = json.loads(raw)
    except ValueError:
        raise PhoneCameraError(f"Unexpected termux-camera-info output: {raw.strip()[:120]}") from None
    cams = []
    for c in info:
        sizes = c.get("jpeg_output_sizes") or []
        best = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0), default={})
        focal = (c.get("focal_lengths") or [None])[0]
        cams.append({"id": str(c.get("id")), "facing": str(c.get("facing", "unknown")),
                     "focal_mm": focal, "max_size": [best.get("width"), best.get("height")]})
    _CAMERA_CACHE[serial] = (time.time(), cams)
    return cams


def capture(serial: str, camera_id: str = "0", timeout_s: float = 30.0) -> np.ndarray:
    """One full-resolution still (BGR) from ``camera_id`` on phone ``serial``."""
    import cv2

    remote = f"{_HOME}/pyontrust_{uuid.uuid4().hex[:8]}.jpg"
    with _lock(serial):
        try:
            _adb("-s", serial, "shell", "run-as", TERMUX, f"{_BIN}/termux-camera-photo",
                 "-c", str(camera_id), remote, timeout=timeout_s)
            data = b""
            deadline = time.time() + timeout_s
            # termux-camera-photo may return before the JPEG is fully written:
            # wait for a complete file (JPEG end-of-image marker).
            while time.time() < deadline:
                try:
                    data = _adb("-s", serial, "exec-out", "run-as", TERMUX, "cat", remote,
                                timeout=timeout_s, binary=True)
                except PhoneCameraError:
                    data = b""
                if len(data) > 1000 and data.rstrip(b"\0").endswith(b"\xff\xd9"):
                    break
                time.sleep(0.3)
        finally:
            try:
                _adb("-s", serial, "shell", "run-as", TERMUX, "rm", "-f", remote, timeout=10)
            except Exception:  # pragma: no cover - best effort cleanup
                pass
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
    if img is None:
        raise PhoneCameraError(
            f"No image from camera {camera_id} — is the phone unlocked and Termux:API allowed to use the camera?")
    return img
