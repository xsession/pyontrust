"""Multi-focus capture and focus-stacking for AOI imaging.

Captures a series of stills at different lens focus positions (10+ by default)
and composites them into a single image that is sharp across a wide depth range —
the photographic equivalent of multiplane / multifocus microscopy, adapted to a
phone camera driven over ADB.

Design rationale (multi-focal imaging literature, applied to a phone lens):

* **Plane spacing** — focus positions are scheduled across the usable diopter
  range so every depth inside the sample tolerance band is in focus somewhere
  in the stack, without over-splitting the capture budget.
* **Photon budget** — exposure and gain stay constant between frames; the
  composite uses sharpness-weighted blending (weights sum to 1 per pixel), so
  defocused/noisy regions are down-weighted instead of averaged in.
* **Alignment** — changing focus induces a small zoom/parallax shift, so all
  frames are registered to a base frame before compositing.

Public API
----------
``FocusSchedule``              plane-spacing schedule (diopter positions)
``sharpness_map()``            local Laplacian-variance sharpness map
``align_stack()``              ORB + RANSAC homography registration to a base
``stack_images()``             weighted composite -> :class:`StackedResult`
``generate_synthetic_stack()`` test fixture: multi-depth scene defocused per position
``capture_focus_series()``     real capture via ADB (helper APK, else termux-camera-photo)
``FocusStacker``               facade: schedule -> capture -> align -> stack

Example
-------
>>> from pyontrust.analysis.focus_stacking import FocusStacker
>>> result = FocusStacker(n_frames=12).run(backend="termux", camera_id=0)
>>> result.image          # uint8 BGR composite, sharp over the whole depth range
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)

try:  # OpenCV is required for the imaging path (optional at import time)
    import cv2
except ImportError:  # pragma: no cover - exercised only without opencv
    cv2 = None


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV (cv2) is required for focus stacking. Install with: pip install opencv-python"
        )


# ──────────────────────────────────────────────────────────────────────
# Plane spacing — the capture schedule
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FocusSchedule:
    """A schedule of lens focus positions (diopters = 1 / metres).

    ``n_frames`` positions are spread over ``[near_diopter, far_diopter]``.
    A mild bias toward near focus is applied because AOI samples sit close to
    the lens; set ``bias=0.0`` for a uniform schedule.
    """

    n_frames: int = 12
    near_diopter: float = 0.5   # ~2 m — "infinity-ish" for a phone macro lens
    far_diopter: float = 6.0    # ~17 cm — close-up / macro end of the range
    bias: float = 0.35          # 0 = uniform, >0 pushes positions toward near focus

    def __post_init__(self) -> None:
        if self.n_frames < 2:
            raise ValueError("n_frames must be >= 2")
        if not (0.0 <= self.bias < 1.0):
            raise ValueError("bias must be in [0, 1)")

    def positions(self) -> list[float]:
        """Return the ordered focus positions (diopters), near → far."""
        t = np.linspace(0.0, 1.0, self.n_frames)
        # bias: remap t so more samples land on the near-focus side
        if self.bias > 0.0:
            t = 1.0 - (1.0 - t) ** (1.0 + 2.0 * self.bias)
        lo, hi = float(self.near_diopter), float(self.far_diopter)
        return [round(lo + (hi - lo) * ti, 4) for ti in t]

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_frames": self.n_frames,
            "near_diopter": self.near_diopter,
            "far_diopter": self.far_diopter,
            "bias": self.bias,
            "positions_diopter": self.positions(),
        }


# ──────────────────────────────────────────────────────────────────────
# Sharpness estimation
# ──────────────────────────────────────────────────────────────────────

def sharpness_map(image: np.ndarray, window: int = 9) -> np.ndarray:
    """Local variance of the Laplacian — a noise-robust focus measure.

    Parameters
    ----------
    image : uint8 BGR or grayscale frame.
    window : side length (px) of the local statistics box; odd, >= 3.

    Returns
    -------
    float32 map of absolute local Laplacian variance — a true focus measure,
    comparable across frames (no per-image rescaling).
    """
    _require_cv2()
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    if window % 2 == 0 or window < 3:
        raise ValueError("window must be an odd integer >= 3")

    blurred = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 1.0)
    lap = cv2.Laplacian(blurred, cv2.CV_32F)
    ksize = (window, window)
    mean = cv2.boxFilter(lap, cv2.CV_32F, ksize)
    sq_mean = cv2.boxFilter(lap * lap, cv2.CV_32F, ksize)
    var = np.maximum(sq_mean - mean * mean, 0.0)

    return var.astype(np.float32)


def frame_sharpness(image: np.ndarray, window: int = 9) -> float:
    """Global focus score for one frame (median of its sharpness map)."""
    m = sharpness_map(image, window=window)
    return float(np.median(m))


# ──────────────────────────────────────────────────────────────────────
# Alignment — focus change induces a small zoom/parallax shift
# ──────────────────────────────────────────────────────────────────────

def align_stack(
    images: Sequence[np.ndarray],
    base_index: int | None = None,
    max_features: int = 1500,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Register every frame to ``base_index`` with ORB + RANSAC homography.

    Returns ``(aligned_images, matrices)`` where ``matrices[i]`` is the 3x3
    warp used for frame *i* (identity for the base). Frames that fail to
    register are returned unwarped with an identity matrix — stacking still
    works, just with slightly more ghosting.
    """
    _require_cv2()
    if not images:
        raise ValueError("images must be non-empty")
    n = len(images)
    base_index = 0 if base_index is None else int(base_index)
    if not (0 <= base_index < n):
        raise ValueError(f"base_index {base_index} out of range for {n} frames")

    detector = cv2.ORB_create(nfeatures=max_features)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def _gray(img: np.ndarray) -> np.ndarray:
        return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    base_gray = _gray(images[base_index])
    kp0, desc0 = detector.detectAndCompute(base_gray, None)
    size = (images[base_index].shape[1], images[base_index].shape[0])

    aligned: list[np.ndarray] = []
    matrices: list[np.ndarray] = []
    for i, img in enumerate(images):
        if i == base_index or desc0 is None or desc0.size == 0:
            aligned.append(img)
            matrices.append(np.eye(3, dtype=np.float64))
            continue
        kpi, desci = detector.detectAndCompute(_gray(img), None)
        hom = np.eye(3, dtype=np.float64)
        if desc0 is not None and desci is not None and len(kpi) >= 8:
            matches = matcher.match(desci, desc0)
            matches = sorted(matches, key=lambda m: m.distance)[:128]
            src = np.float32([kpi[m.queryIdx].pt for m in matches])
            dst = np.float32([kp0[m.trainIdx].pt for m in matches])
            h, mask = cv2.findHomography(src, dst, cv2.RANSAC, ransacReprojThreshold=2.5)
            if h is not None and int(mask.sum()) >= 16:
                hom = h.astype(np.float64)
        aligned.append(
            cv2.warpPerspective(img, hom, size, flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)
        )
        matrices.append(hom)
    return aligned, matrices


# ──────────────────────────────────────────────────────────────────────
# Composite — sharpness-weighted blend (photon-budget friendly)
# ──────────────────────────────────────────────────────────────────────

@dataclass
class StackedResult:
    """Output of :func:`stack_images`."""

    image: np.ndarray                      # uint8 BGR composite
    focus_map: np.ndarray                  # int32 index of the winning frame per pixel
    weight_maps: list[np.ndarray]          # float32, one normalised map per input frame
    sharpness_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape": list(self.image.shape),
            "n_frames": len(self.weight_maps),
            "sharpness_stats": self.sharpness_stats,
            "focus_map_coverage": _coverage_report(self.focus_map, len(self.weight_maps)),
        }


def _coverage_report(focus_map: np.ndarray, n_frames: int) -> dict[str, Any]:
    """Fraction of pixels won by each frame (how the depth range is shared)."""
    total = focus_map.size or 1
    counts = np.bincount(focus_map.ravel(), minlength=n_frames)
    return {str(i): round(float(c) / total, 4) for i, c in enumerate(counts)}


def stack_images(
    images: Sequence[np.ndarray],
    window: int = 9,
    gamma: float = 2.0,
    feather_sigma: float = 3.0,
    align: bool = True,
    base_index: int | None = None,
) -> StackedResult:
    """Composite a focus series into one image sharp across the depth range.

    Per pixel the frame with the highest local sharpness wins; weights are
    raised to ``gamma`` (crisper selection), normalised so they sum to 1
    (no SNR loss from naive averaging) and lightly feathered to avoid seams.

    Parameters
    ----------
    images : sequence of uint8 BGR frames, ideally at different focus positions.
    window : sharpness-map box size (px).
    gamma : selection sharpness exponent; 1 = pure proportional blend.
    feather_sigma : Gaussian smoothing applied to the weight maps (px); 0 disables.
    align : register frames to ``base_index`` before compositing.
    base_index : which frame is the alignment reference (default: sharpest).
    """
    _require_cv2()
    images = [np.asarray(im) for im in images]
    if not images:
        raise ValueError("images must be non-empty")
    h, w = images[0].shape[:2]
    for i, im in enumerate(images):
        if im.shape[:2] != (h, w):
            raise ValueError(f"frame {i} shape {im.shape[:2]} != base {(h, w)}")

    if align:
        if base_index is None:
            scores = [frame_sharpness(im, window) for im in images]
            base_index = int(np.argmax(scores))
        images, _mats = align_stack(images, base_index=base_index)

    maps = [sharpness_map(im, window=window) ** gamma for im in images]
    total = np.sum(maps, axis=0)
    total[total == 0.0] = 1.0
    weights = [m / total for m in maps]
    if feather_sigma > 0:
        weights = [cv2.GaussianBlur(wgt, (0, 0), float(feather_sigma)) for wgt in weights]
        renorm = np.sum(weights, axis=0)
        renorm[renorm == 0.0] = 1.0
        weights = [wgt / renorm for wgt in weights]

    focus_map = np.argmax(np.stack(weights), axis=0).astype(np.int32)
    float_frames = [im.astype(np.float32) for im in images]
    if len(float_frames[0].shape) == 2:
        composite = np.tensordot(np.stack(weights, axis=0), np.stack(float_frames, axis=0), axes=(1, 0))
    else:
        # (n, h, w) x (n, h, w, c) -> (h, w, c)
        composite = np.einsum("nhw,nhwk->hwk", np.stack(weights), np.stack(float_frames))
    composite = np.clip(composite, 0.0, 255.0).astype(np.uint8)

    stats = {
        "base_index": int(base_index) if base_index is not None else None,
        "per_frame_median_sharpness": [round(float(np.median(m ** (1 / max(gamma, 1e-9)))), 4) for m in maps],
        "window_px": window,
        "gamma": gamma,
    }
    return StackedResult(image=composite, focus_map=focus_map, weight_maps=weights, sharpness_stats=stats)


# ──────────────────────────────────────────────────────────────────────
# Synthetic multi-depth fixture (artificial camera feed for tests)
# ──────────────────────────────────────────────────────────────────────

def _textured_region(w: int, h: int, base_color, hatch_gap: int = 6, seed: int = 0) -> np.ndarray:
    """PCB-like textured patch (traces/hatch) — strong local variance when in focus."""
    rng = np.random.default_rng(seed)
    region = np.zeros((h, w, 3), dtype=np.uint8)
    region[:] = base_color
    for y in range(0, h, hatch_gap):                       # horizontal traces
        cv2.line(region, (0, y), (w, y), tuple(int(c * 1.4) % 256 for c in base_color), 2)
    for x in range(rng.integers(8, w - 8), w, int(w / 9)):  # vertical traces
        cv2.line(region, (x, 0), (x, h), tuple(int(c * 1.3) % 256 for c in base_color), 2)
    return region


def _plane_near(w: int, h: int) -> np.ndarray:
    """Near plane: IC chip with pins on a textured pad field."""
    layer = _textured_region(w, h, (38, 74, 40), seed=11)
    cv2.rectangle(layer, (int(0.25 * w), int(0.2 * h)), (int(0.75 * w), int(0.8 * h)), (16, 16, 16), -1)
    for i in range(10):                                    # pins both sides
        x = int((0.30 + 0.045 * i) * w)
        cv2.rectangle(layer, (x, int(0.12 * h)), (x + 8, int(0.2 * h)), (70, 150, 215), -1)
        cv2.rectangle(layer, (x, int(0.8 * h)), (x + 8, int(0.88 * h)), (70, 150, 215), -1)
    cv2.putText(layer, "U1", (int(0.42 * w), int(0.55 * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (230, 230, 230), 2)
    return layer


def _plane_mid(w: int, h: int) -> np.ndarray:
    """Mid plane: connector with gold fingers on a textured pad field."""
    layer = _textured_region(w, h, (46, 84, 52), seed=22)
    cv2.rectangle(layer, (int(0.15 * w), int(0.25 * h)), (int(0.85 * w), int(0.75 * h)), (20, 20, 20), -1)
    for i in range(14):                                    # gold fingers
        x = int((0.19 + 0.046 * i) * w)
        cv2.rectangle(layer, (x, int(0.35 * h)), (x + 10, int(0.65 * h)), (60, 140, 210), -1)
    cv2.putText(layer, "J3", (int(0.44 * w), int(0.22 * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (225, 225, 225), 2)
    return layer


def _plane_far(w: int, h: int) -> np.ndarray:
    """Far plane: resistor array + silkscreen on a textured pad field."""
    layer = _textured_region(w, h, (40, 78, 46), seed=33)
    for i in range(6):                                     # resistors
        x = int((0.12 + 0.13 * i) * w)
        cv2.rectangle(layer, (x, int(0.35 * h)), (x + int(0.09 * w), int(0.6 * h)), (140, 110, 70), -1)
        cv2.rectangle(layer, (x, int(0.35 * h)), (x + 8, int(0.6 * h)), (200, 200, 200), -1)
        cv2.rectangle(layer, (x + int(0.09 * w) - 8, int(0.35 * h)), (x + int(0.09 * w), int(0.6 * h)), (200, 200, 200), -1)
    cv2.putText(layer, "R-ARRAY", (int(0.3 * w), int(0.85 * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (215, 215, 215), 2)
    return layer


def generate_synthetic_stack(
    n_frames: int = 12,
    size=(640, 480),
    seed: int = 7,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Artificial camera feed: a multi-depth PCB scene captured at ``n_frames`` focus positions.

    The image is split into three horizontal depth planes (near / mid / far).
    A frame focused at position ``f`` blurs plane ``k`` by a defocus PSF whose
    width grows with |f - focus_k| — exactly what a real lens does, so the
    fixture exercises alignment + sharpness-weighted compositing end to end.

    Returns ``(frames, meta)`` where ``meta`` carries the schedule and each
    plane's box + the frame index at which that plane is best focused.
    """
    _require_cv2()
    h, w = size
    rng = np.random.default_rng(seed)

    schedule = FocusSchedule(n_frames=n_frames)
    positions = schedule.positions()
    lo, hi = schedule.near_diopter, schedule.far_diopter

    # plane focal distances spread across the usable range (plane spacing!)
    layer_focuses = [lo + 0.18 * (hi - lo), lo + 0.5 * (hi - lo), lo + 0.82 * (hi - lo)]
    planes = [_plane_near(w, h // 3), _plane_mid(w, h // 3), _plane_far(w, h - 2 * (h // 3))]
    boxes = [(0, 0, w, h // 3), (0, h // 3, w, h // 3), (0, 2 * (h // 3), w, h - 2 * (h // 3))]

    frames: list[np.ndarray] = []
    for i, focus in enumerate(positions):
        # small zoom/parallax emulating the refocus magnification change
        zoom = 1.0 + 0.03 * (i / max(n_frames - 1, 1) - 0.5)
        canvas = np.zeros((h, w, 3), dtype=np.float32)
        for k, plane in enumerate(planes):
            sigma = 0.4 + 5.0 * abs(focus - layer_focuses[k]) / (hi - lo)   # defocus PSF width
            blurred = cv2.GaussianBlur(plane, (0, 0), float(sigma))
            if zoom != 1.0:
                zw, zh = int(w * zoom), int(h // 3 * zoom)
                blurred = cv2.resize(blurred, (zw, zh), interpolation=cv2.INTER_AREA)
                y0 = max(0, k * (h // 3) - (zh - h // 3) // 2)
                x0 = max(0, -(zw - w) // 2)
                ys, ye = max(0, y0), min(h, y0 + zh)
                xs, xe = max(0, x0), min(w, x0 + zw)
                canvas[ys:ye, xs:xe] += blurred[ys - y0:ye - y0, xs - x0:xe - x0]
            else:
                canvas[k * (h // 3):(k + 1) * (h // 3)] += blurred.astype(np.float32)
        noise = rng.normal(0.0, 1.8, size=(h, w, 3)).astype(np.float32)
        frames.append(np.clip(canvas + noise, 0, 255).astype(np.uint8))

    layer_focus_indices = [int(np.argmin([abs(p - lf) for p in positions])) for lf in layer_focuses]
    meta = {
        "schedule": schedule.to_dict(),
        "layer_focuses": [round(f, 4) for f in layer_focuses],
        "boxes": boxes,
        "layer_focus_indices": layer_focus_indices,
    }
    return frames, meta



# ──────────────────────────────────────────────────────────────────────
# Real capture over ADB (phone as the AOI camera)
# ──────────────────────────────────────────────────────────────────────

def _adb(*args: str, timeout: int = 30) -> str:
    r = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 and "error" in out.lower():
        raise RuntimeError(f"adb {' '.join(args[:4])} failed: {out.strip()[:200]}")
    return out


def _helper_apk_present() -> bool:
    try:
        return "com.pyontrust.camera" in _adb("shell", "pm", "list", "packages", timeout=15)
    except Exception:
        return False


def capture_focus_series(
    n_frames: int = 12,
    camera_id: int = 0,
    out_dir: str | Path = "/tmp/pyontrust_focus_stack",
    backend: str = "auto",
    interval_s: float = 1.5,
    schedule: FocusSchedule | None = None,
) -> list[np.ndarray]:
    """Capture ``n_frames`` stills from the phone camera over ADB.

    Backends (in preference order for ``"auto"``):

    * ``helper`` — ``com.pyontrust.camera`` APK sets a manual focus distance per
      frame (true different-focus capture). Requires the helper APK installed.
    * ``termux`` — ``termux-camera-photo`` via Termux:API. No manual focus
      control on stock termux-api, so frames are AF-locked stills; stacking
      still benefits from sensor noise averaging and any AF drift between shots.

    Returns the loaded BGR frames (also saved as JPEG under ``out_dir``).
    """
    _require_cv2()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    use_helper = (backend == "helper") or (backend == "auto" and _helper_apk_present())
    if backend == "helper" and not _helper_apk_present():
        raise RuntimeError(
            "helper backend requested but com.pyontrust.camera is not installed on the device"
        )

    TERMUX_BIN = "/data/data/com.termux/files/usr/bin/termux-camera-photo"
    HELPER_PKG = "com.pyontrust.camera"
    HELPER_CAPDIR = f"/sdcard/Android/data/{HELPER_PKG}/files/captures"
    if use_helper:
        # helper APK writes into its own external files dir (Huawei blocks app-created /sdcard dirs)
        remote_dir = HELPER_CAPDIR
    else:
        # Termux home is writable by the app uid; sdcard dirs created via adb shell are not.
        remote_dir = "/data/data/com.termux/files/home/pyontrust_focus"
        _adb("shell", "run-as", "com.termux.api", "sh", "-c",
             f"rm -rf {remote_dir} && mkdir -p {remote_dir}", timeout=20)

    for i in range(n_frames):
        remote = f"{remote_dir}/frame_{i:02d}.jpg"
        local = out / f"frame_{i:02d}.jpg"
        if use_helper:
            # explicit component (bypasses stopped-state limits); file path via data URI because
            # this am build rejects --ez; focus distance in diopters from the schedule.
            sched = schedule or FocusSchedule(n_frames=n_frames)
            _adb("shell", "am", "broadcast", "-n", f"{HELPER_PKG}/.CaptureReceiver",
                 "-a", "com.pyontrust.camera.CAPTURE",
                 "--ei", "req_id", str(i), "--ef", "focus", str(sched.positions()[i]),
                 "-d", f"file:///{remote_dir}/frame_{i:02d}.jpg", timeout=45)
            time.sleep(8)  # capture is async on-device; ~1-3s typical, allow headroom
            with open(local, "wb") as fh:
                subprocess.run(f'adb shell cat {remote_dir}/frame_{i:02d}.jpg',
                               shell=True, stdout=fh, timeout=60)
        else:
            # termux-camera-photo v0.5x CLI: single positional <file>; default camera 0 (back).
            _adb("shell", "run-as", "com.termux.api", TERMUX_BIN, remote, timeout=90)
            with open(local, "wb") as fh:
                subprocess.run(f"adb shell run-as com.termux.api cat {remote}",
                               shell=True, stdout=fh, timeout=60)
        if not local.exists() or local.stat().st_size == 0:
            raise RuntimeError(f"capture {i} failed (no file pulled)")
        img = cv2.imread(str(local))
        if img is None:
            raise RuntimeError(f"capture {i}: unreadable JPEG at {local}")
        logger.info("captured frame %d/%d via %s", i + 1, n_frames, "helper" if use_helper else "termux")
        if interval_s > 0 and i < n_frames - 1:
            import time as _time
            _time.sleep(interval_s)

    return [cv2.imread(str(out / f"frame_{i:02d}.jpg")) for i in range(n_frames)]


# ──────────────────────────────────────────────────────────────────────
# Facade
# ──────────────────────────────────────────────────────────────────────

class FocusStacker:
    """One-call multi-focus capture + stacking.

    >>> stacker = FocusStacker(n_frames=12)
    >>> result = stacker.run(backend="termux")          # real phone feed
    >>> result = stacker.run(frames=my_list)             # or pre-captured frames
    """

    def __init__(self, n_frames: int = 12, schedule: FocusSchedule | None = None,
                 window: int = 9, gamma: float = 2.0, feather_sigma: float = 3.0,
                 align: bool = True) -> None:
        self.schedule = schedule or FocusSchedule(n_frames=n_frames)
        if n_frames != len(self.schedule.positions()):
            raise ValueError("n_frames must match the schedule length")
        self.window = window
        self.gamma = gamma
        self.feather_sigma = feather_sigma
        self.align = align

    def run(
        self,
        frames: Sequence[np.ndarray] | None = None,
        backend: str = "auto",
        camera_id: int = 0,
        out_dir: str | Path = "/tmp/pyontrust_focus_stack",
    ) -> StackedResult:
        if frames is None:
            frames = capture_focus_series(
                n_frames=len(self.schedule.positions()),
                camera_id=camera_id,
                out_dir=out_dir,
                backend=backend,
                schedule=self.schedule,
            )
        result = stack_images(
            list(frames), window=self.window, gamma=self.gamma,
            feather_sigma=self.feather_sigma, align=self.align,
        )
        result.sharpness_stats["schedule"] = self.schedule.to_dict()
        return result


__all__ = [
    "FocusSchedule",
    "StackedResult",
    "FocusStacker",
    "sharpness_map",
    "frame_sharpness",
    "align_stack",
    "stack_images",
    "generate_synthetic_stack",
    "capture_focus_series",
]
