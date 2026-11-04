"""Stereo camera object analysis — pure software, no external programs.

Rectifies a stereo pair (or accepts an already-rectified one), computes
sub-pixel disparity with SGBM block matching, and converts it to **metric**
depth plus a 3-D point cloud using the pinhole model:

    Z = fx * baseline / disparity_px

Use cases: analysing objects with a stereo camera rig, coarse 3-D scanning,
gauge-style height checks. For single-camera multi-focus depth (microscopy /
macro AOI) see ``pyontrust.analysis.focus_depth`` — the two complement each
other: stereo gives fast whole-scene shape, focus stacking gives fine detail.

Public API
----------
``StereoConfig``     intrinsics + baseline + SGBM parameters (validated)
``rectify_pair()``   optional stereoRectify when R/T/K are provided
``disparity_map()``  SGBM disparity in pixels (float32, -1 where no match)
``depth_from_disparity()`` metric depth in metres
``StereoAnalyzer``   one-call pipeline -> :class:`StereoResult`
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import numpy as np

try:  # OpenCV is required for the imaging path (optional at import time)
    import cv2
except ImportError:  # pragma: no cover - exercised only without opencv
    cv2 = None

logger = logging.getLogger(__name__)


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV (cv2) is required for stereo analysis. Install with: pip install opencv-python"
        )


@dataclass(frozen=True)
class StereoConfig:
    """Stereo rig geometry + SGBM parameters.

    ``baseline_m`` is the distance between the two optical centres along X.
    ``num_disp`` must be a multiple of 16 and larger than the largest expected
    disparity in pixels (set it from the closest object you will measure).
    """

    fx: float
    fy: float
    cx: float
    cy: float
    baseline_m: float
    num_disp: int = 64
    block_size: int = 7
    min_disparity: int = 0

    def validate(self) -> None:
        if self.fx <= 0 or self.fy <= 0:
            raise ValueError("fx and fy must be > 0")
        if self.baseline_m <= 0:
            raise ValueError("baseline_m must be > 0 (metres)")
        if self.num_disp < 16 or self.num_disp % 16 != 0:
            raise ValueError("num_disp must be a multiple of 16, >= 16")
        if self.block_size < 3 or self.block_size % 2 == 0:
            raise ValueError("block_size must be an odd integer >= 3")
        if self.min_disparity < 0:
            raise ValueError("min_disparity must be >= 0")


@dataclass(frozen=True)
class StereoResult:
    """Output of :meth:`StereoAnalyzer.run`."""

    left_rect: np.ndarray     # uint8 grayscale, rectified
    right_rect: np.ndarray    # uint8 grayscale, rectified
    disparity_px: np.ndarray  # float32 (H, W); -1 where no match was found
    depth_m: np.ndarray       # float32 (H, W) metres; NaN where invalid
    points: np.ndarray        # float32 (H, W, 3) camera-frame XYZ; zeros where invalid
    valid_mask: np.ndarray    # bool (H, W)



def _to_gray(img: np.ndarray) -> np.ndarray:
    img = np.asarray(img)
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.astype(np.uint8)


def rectify_pair(
    left: np.ndarray,
    right: np.ndarray,
    K1: np.ndarray | None = None,
    K2: np.ndarray | None = None,
    R: np.ndarray | None = None,
    T: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Rectify a stereo pair to horizontal epipolar lines.

    If ``K1/K2/R/T`` (from ``cv2.calibrateCamera`` + ``stereoCalibrate``) are
    given, ``cv2.stereoRectify`` is applied; otherwise the inputs are assumed
    already rectified and only converted to grayscale.
    """
    _require_cv2()
    l = _to_gray(left)
    r = _to_gray(right)
    if R is None or T is None:
        return l, r
    if K1 is None or K2 is None:
        raise ValueError("K1 and K2 are required together with R/T")

    size = (l.shape[1], l.shape[0])
    R1, R2, P1, P2, Q, _ = cv2.stereoRectify(
        np.asarray(K1, dtype=np.float64), None,
        np.asarray(K2, dtype=np.float64), None,
        size, np.asarray(R, dtype=np.float64), np.asarray(T, dtype=np.float64),
    )
    lm = cv2.getRectifyTransform(np.asarray(K1, dtype=np.float64), None, l.shape[1::-1], R1, P1)
    rm = cv2.getRectifyTransform(np.asarray(K2, dtype=np.float64), None, r.shape[1::-1], R2, P2)
    return cv2.warpPerspective(l, lm, size), cv2.warpPerspective(r, rm, size)


def disparity_map(
    left_rect: np.ndarray, right_rect: np.ndarray, cfg: StereoConfig
) -> np.ndarray:
    """SGBM block-matching disparity in pixels (float32; -1 where no match)."""
    _require_cv2()
    cfg.validate()
    l = _to_gray(left_rect)
    r = _to_gray(right_rect)
    if l.shape != r.shape:
        raise ValueError(f"pair shapes differ: {l.shape} vs {r.shape}")

    sbm = cv2.StereoSGBM_create(
        minDisparity=int(cfg.min_disparity),
        numDisparities=int(cfg.num_disp),
        blockSize=int(cfg.block_size),
        uniquenessRatio=10,
        speckleWindowSize=100,
        speckleRange=32,
    )
    disp = sbm.compute(l, r)  # int16, in 1/16-pixel units; -1 invalid
    return (disp.astype(np.float32) / 16.0).clip(min=-1.0)


def depth_from_disparity(disparity_px: np.ndarray, cfg: StereoConfig) -> np.ndarray:
    """Metric depth in metres via the pinhole model ``Z = fx * B / d``."""
    _require_cv2()
    cfg.validate()
    d = np.asarray(disparity_px, dtype=np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (float(cfg.fx) * float(cfg.baseline_m)) / d
    return np.where(d > 0.5, z, np.nan).astype(np.float32)


def points_from_depth(depth_m: np.ndarray, cfg: StereoConfig) -> np.ndarray:
    """Reproject a metric depth map to camera-frame XYZ (zeros where invalid)."""
    _require_cv2()
    d = np.asarray(depth_m, dtype=np.float32)
    h, w = d.shape
    us, vs = np.meshgrid(np.arange(w), np.arange(h))
    x = (us - float(cfg.cx)) * d / float(cfg.fx)
    y = (vs - float(cfg.cy)) * d / float(cfg.fy)
    pts = np.stack([x, y, d], axis=-1).astype(np.float32)
    bad = ~np.isfinite(d)
    if bad.any():
        pts[bad] = 0.0
    return pts



class StereoAnalyzer:
    """One-call pipeline: stereo pair -> disparity, metric depth, point cloud.

    >>> cfg = StereoConfig(fx=800, fy=800, cx=320, cy=240, baseline_m=0.12)
    >>> res = StereoAnalyzer(cfg).run(left_bgr, right_bgr)
    >>> float(np.nanmedian(res.depth_m))   # median scene depth in metres
    """

    def __init__(self, cfg: StereoConfig) -> None:
        cfg.validate()
        self.cfg = cfg

    def run(
        self,
        left: np.ndarray,
        right: np.ndarray,
        K1: np.ndarray | None = None,
        K2: np.ndarray | None = None,
        R: np.ndarray | None = None,
        T: np.ndarray | None = None,
    ) -> StereoResult:
        """Analyse one stereo pair (rectify if calibration data is supplied)."""
        _require_cv2()
        lr, rr = rectify_pair(left, right, K1=K1, K2=K2, R=R, T=T)
        disp = disparity_map(lr, rr, self.cfg)
        depth = depth_from_disparity(disp, self.cfg)
        pts = points_from_depth(depth, self.cfg)
        valid = np.isfinite(depth) & (disp > 0.5)
        logger.info("stereo: %.1f%% of pixels matched", 100.0 * float(valid.mean()))
        return StereoResult(
            left_rect=lr, right_rect=rr, disparity_px=disp,
            depth_m=depth, points=pts, valid_mask=valid,
        )


__all__ = [
    "StereoConfig",
    "StereoResult",
    "StereoAnalyzer",
    "rectify_pair",
    "disparity_map",
    "depth_from_disparity",
    "points_from_depth",
]

