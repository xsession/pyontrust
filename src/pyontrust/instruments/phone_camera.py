"""Android phone cameras over USB — live MJPEG video, full-res stills, focus.

Each phone runs the **pyontrust camera** app (``android-camera/``, built with
``android-camera/build.sh``).  It serves the phone's cameras on the phone's
own loopback (127.0.0.1:8090); the PC reaches it through ``adb forward``, so
nothing is exposed on Wi-Fi.

* :func:`list_phones`          — every phone ADB sees (incl. unauthorised)
* :func:`cameras`              — per-camera facing / focal length / sizes / min focus
* :func:`stream`               — shared live reader: newest JPEG + fps per camera
* :func:`capture`              — full-resolution still (BGR)
* :func:`set_focus`            — continuous AF, one-shot AF, or a fixed distance

One reader thread per (phone, camera) keeps only the newest frame; any
number of viewers share it.  Readers stop after ``IDLE_S`` without viewers.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("pyontrust.instruments.phone_camera")

APP_PACKAGE = "com.pyontrust.cam"
APP_ACTIVITY = f"{APP_PACKAGE}/.MainActivity"
DEVICE_PORT = 8090
IDLE_S = 20.0
_APK = Path(__file__).resolve().parents[3] / "android-camera" / "build" / "pyontrust-camera.apk"


class PhoneCameraError(RuntimeError):
    """Actionable error (shown to the user as-is)."""


# ── adb ─────────────────────────────────────────────────────────────────

def _adb(*args: str, timeout: float = 30) -> str:
    exe = shutil.which("adb")
    if exe is None:
        raise PhoneCameraError("adb not found — install Android platform-tools")
    r = subprocess.run([exe, *args], capture_output=True, timeout=timeout)
    out = (r.stdout or b"").decode(errors="replace")
    if r.returncode != 0:
        raise PhoneCameraError(((r.stderr or b"").decode(errors="replace") or out).strip()
                               or f"adb {' '.join(args[:3])} failed")
    return out


@dataclass
class Phone:
    serial: str
    state: str
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
    try:
        out = _adb("devices", "-l", timeout=10)
    except (PhoneCameraError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("adb devices failed: %s", exc)
        return []
    phones = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            extra = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
            phones.append(Phone(parts[0], parts[1], extra.get("model", ""), extra))
    return phones


# ── per-phone connection (app + port forward) ───────────────────────────

class _Link:
    def __init__(self, serial: str) -> None:
        self.serial = serial
        self.port: int | None = None
        self.lock = threading.Lock()

    def url(self, path: str) -> str:
        with self.lock:
            if self.port is None or not self._alive():
                self._connect()
            return f"http://127.0.0.1:{self.port}{path}"

    def _alive(self) -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/status", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def _connect(self) -> None:
        installed = APP_PACKAGE in _adb("-s", self.serial, "shell", "pm", "list", "packages", APP_PACKAGE, timeout=15)
        if not installed:
            if not _APK.is_file():
                raise PhoneCameraError("pyontrust camera app not installed on the phone — "
                                       "build it with android-camera/build.sh")
            logger.info("Installing pyontrust camera app on %s", self.serial)
            _adb("-s", self.serial, "install", "-r", "-g", str(_APK), timeout=120)
        port = _adb("-s", self.serial, "forward", "tcp:0", f"tcp:{DEVICE_PORT}", timeout=10).strip()
        self.port = int(port)
        for attempt in range(2):
            if self._alive():
                return
            # (re)start the app: the activity checks permissions and starts the service
            _adb("-s", self.serial, "shell", "am", "start", "-n", APP_ACTIVITY, timeout=15)
            deadline = time.time() + 6
            while time.time() < deadline:
                if self._alive():
                    return
                time.sleep(0.3)
        raise PhoneCameraError("pyontrust camera app did not start — unlock the phone and allow the camera permission")


_LINKS: dict[str, _Link] = {}
_LINKS_GUARD = threading.Lock()


def _link(serial: str) -> _Link:
    with _LINKS_GUARD:
        return _LINKS.setdefault(serial, _Link(serial))


def _get(serial: str, path: str, timeout: float = 15) -> bytes:
    try:
        with urllib.request.urlopen(_link(serial).url(path), timeout=timeout) as r:
            return r.read()
    except PhoneCameraError:
        raise
    except Exception as exc:
        raise PhoneCameraError(f"phone {serial}: {exc}") from None


# ── public API ──────────────────────────────────────────────────────────

_CAMERA_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def cameras(serial: str, max_age_s: float = 120.0) -> list[dict[str, Any]]:
    cached = _CAMERA_CACHE.get(serial)
    if cached and time.time() - cached[0] < max_age_s:
        return cached[1]
    data = json.loads(_get(serial, "/cameras"))
    if not data.get("ok"):
        raise PhoneCameraError(data.get("error", "camera list failed"))
    cams = data["cameras"]
    _CAMERA_CACHE[serial] = (time.time(), cams)
    return cams


def capture(serial: str, camera_id: str = "0", timeout_s: float = 20.0) -> np.ndarray:
    """Full-resolution still (BGR)."""
    import cv2

    data = _get(serial, f"/photo?camera={camera_id}", timeout=timeout_s)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise PhoneCameraError(f"phone {serial}: still capture returned no image")
    return img


def set_focus(serial: str, mode: str = "continuous", diopters: float | None = None) -> dict[str, Any]:
    """``mode``: continuous | auto | manual (``diopters`` = 1 / distance in m)."""
    q = f"/focus?mode={mode}" + (f"&d={float(diopters):.4f}" if diopters is not None else "")
    return json.loads(_get(serial, q))


def status(serial: str) -> dict[str, Any]:
    return json.loads(_get(serial, "/status"))


# ── shared live streams ─────────────────────────────────────────────────

class PhoneStream:
    """Reads one camera's MJPEG stream; keeps the newest JPEG for all viewers."""

    def __init__(self, serial: str, camera_id: str, width: int = 1280, height: int = 720, quality: int = 70):
        self.serial, self.camera_id = serial, str(camera_id)
        self.size, self.quality = (width, height), quality
        self._cond = threading.Condition()
        self.jpeg: bytes | None = None
        self.seq = 0
        self.ts_ns = 0
        self.fps = 0.0
        self.error = ""
        self._last_use = time.time()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def touch(self) -> None:
        self._last_use = time.time()
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name=f"phone-{self.serial}-{self.camera_id}", daemon=True)
            self._thread.start()

    def wait(self, after_seq: int, timeout: float = 5.0) -> tuple[int, bytes] | None:
        """Block until a frame newer than ``after_seq`` arrives."""
        self.touch()
        with self._cond:
            if not self._cond.wait_for(lambda: self.seq > after_seq or self._stop.is_set(), timeout):
                return None
            return (self.seq, self.jpeg) if self.jpeg else None

    def latest_bgr(self, timeout: float = 5.0) -> np.ndarray:
        import cv2

        got = self.wait(self.seq - 1 if self.seq else 0, timeout)
        if not got:
            raise PhoneCameraError(self.error or f"no live frame from {self.serial} camera {self.camera_id}")
        img = cv2.imdecode(np.frombuffer(got[1], np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise PhoneCameraError("undecodable frame")
        return img

    def stop(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()

    def _run(self) -> None:
        n, t_fps = 0, time.time()
        while not self._stop.is_set():
            if time.time() - self._last_use > IDLE_S:
                logger.info("phone stream %s/%s idle — stopping", self.serial, self.camera_id)
                return
            try:
                w, h = self.size
                url = _link(self.serial).url(f"/video?camera={self.camera_id}&w={w}&h={h}&q={self.quality}")
                with urllib.request.urlopen(url, timeout=10) as resp:
                    self.error = ""
                    while not self._stop.is_set() and time.time() - self._last_use <= IDLE_S:
                        headers = {}
                        line = resp.readline()
                        while line and line.strip() != b"--frame":
                            line = resp.readline()
                        if not line:
                            raise PhoneCameraError("stream ended")
                        while True:
                            line = resp.readline().strip()
                            if not line:
                                break
                            k, _, v = line.decode(errors="replace").partition(":")
                            headers[k.strip().lower()] = v.strip()
                        size = int(headers.get("content-length", "0"))
                        data = resp.read(size)
                        resp.readline()
                        with self._cond:
                            self.jpeg, self.seq = data, self.seq + 1
                            self.ts_ns = int(headers.get("x-timestamp-ns", "0") or 0)
                            self._cond.notify_all()
                        n += 1
                        now = time.time()
                        if now - t_fps >= 1.0:
                            self.fps, n, t_fps = round(n / (now - t_fps), 1), 0, now
            except Exception as exc:
                self.error = str(exc)
                logger.debug("phone stream %s/%s: %s", self.serial, self.camera_id, exc)
                self._stop.wait(1.0)


_STREAMS: dict[tuple[str, str], PhoneStream] = {}
_STREAMS_GUARD = threading.Lock()


def stream(serial: str, camera_id: str = "0") -> PhoneStream:
    """The shared live stream of one phone camera (started on first use)."""
    key = (serial, str(camera_id))
    with _STREAMS_GUARD:
        s = _STREAMS.get(key)
        if s is None:
            # A phone runs one camera at a time: retire its other streams.
            for other_key, other in list(_STREAMS.items()):
                if other_key[0] == serial:
                    other.stop()
                    del _STREAMS[other_key]
            s = _STREAMS[key] = PhoneStream(serial, camera_id)
        s.touch()
        return s
