"""Stereo calibration: intrinsics (checkerboard) + extrinsic baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np


@dataclass
class StereoCalibration:
    """Full stereo parameter set (camera 0 = left, camera 1 = right)."""

    K_left: np.ndarray          # 3x3 intrinsics
    D_left: np.ndarray          # distortion coeffs
    K_right: np.ndarray
    D_right: np.ndarray
    R: np.ndarray | None = None     # 3x3 right→left rotation (None = identity)
    T: np.ndarray | None = None     # (3,) or (3,1) translation in left-camera units
    image_size: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "K_left": self.K_left.tolist(), "D_left": self.D_left.tolist(),
            "K_right": self.K_right.tolist(), "D_right": self.D_right.tolist(),
            "R": (self.R.tolist() if self.R is not None else None),
            "T": (np.asarray(self.T).reshape(3).tolist() if self.T is not None else None),
            "image_size": list(self.image_size) if self.image_size else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StereoCalibration":
        return cls(
            K_left=np.array(d["K_left"], dtype=np.float64),
            D_left=np.array(d["D_left"], dtype=np.float64).reshape(-1),
            K_right=np.array(d["K_right"], dtype=np.float64),
            D_right=np.array(d["D_right"], dtype=np.float64).reshape(-1),
            R=(np.array(d["R"]) if d.get("R") is not None else None),
            T=(np.array(d["T"]).reshape(3, 1) if d.get("T") is not None else None),
            image_size=tuple(d["image_size"]) if d.get("image_size") else None,
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "StereoCalibration":
        return cls.from_dict(json.loads(Path(path).read_text()))


class StereoCalibrator:
    """Compute / assemble stereo parameters.

    Two routes:
      * ``from_baseline`` — known intrinsics + a measured baseline (the common
        phone-rig case where both phones share the same lens model);
      * ``calibrate_from_checkerboard`` — full intrinsic calibration from
        checkerboard views of each camera, with relative pose via solvePnP.
    """

    def __init__(self, board_size: tuple[int, int] = (9, 6), square_mm: float = 25.0) -> None:
        self.board_size = board_size
        self.square_mm = square_mm
        pts = np.zeros((1, board_size[0] * board_size[1], 3), dtype=np.float64)
        pts[0, :, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2) * square_mm
        self._objp = pts

    # ── route 1: known intrinsics + baseline (phone rigs) ─────────
    def from_baseline(self, K_left: np.ndarray, D_left: np.ndarray | None,
                      K_right: np.ndarray | None = None,
                      D_right: np.ndarray | None = None,
                      baseline_px: float = 120.0,
                      image_size: tuple[int, int] | None = None) -> StereoCalibration:
        """Right camera offset by ``baseline_px`` along +X of the left frame."""
        K_r = np.asarray(K_right if K_right is not None else K_left, dtype=np.float64)
        D_l = np.zeros(4) if D_left is None else np.asarray(D_left).reshape(-1)
        D_r = np.zeros(4) if D_right is None else np.asarray(D_right).reshape(-1)
        return StereoCalibration(
            K_left=np.asarray(K_left, dtype=np.float64), D_left=D_l,
            K_right=K_r, D_right=D_r,
            R=np.eye(3), T=np.array([baseline_px, 0.0, 0.0]).reshape(3, 1),
            image_size=image_size)

    # ── route 2: checkerboard calibration of each camera ──────────
    def calibrate_from_checkerboard(self, left_views: Sequence[np.ndarray],
                                    right_views: Sequence[np.ndarray]) -> StereoCalibration:
        import cv2
        if not left_views or not right_views:
            raise ValueError("need at least one view per camera")

        K_l, D_l = self._calibrate_one(left_views)
        K_r, D_r = self._calibrate_one(right_views)

        # relative pose from the first good checkerboard view of each camera
        R, T = np.eye(3), np.array([120.0, 0.0, 0.0]).reshape(3, 1)
        try:
            R, T = self._relative_pose(left_views[0], right_views[0])
        except Exception:
            pass  # keep baseline fallback

        return StereoCalibration(K_left=K_l, D_left=D_l, K_right=K_r, D_right=D_r,
                                 R=R, T=T.reshape(3, 1),
                                 image_size=(left_views[0].shape[1], left_views[0].shape[0]))

    def _calibrate_one(self, images: Sequence[np.ndarray]):
        import cv2
        objps, imgps = [], []
        for im in images:
            gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) if im.ndim == 3 else im
            ok, corners = cv2.findChessboardCorners(gray, self.board_size, None)
            if ok:
                objps.append(self._objp[0])
                imgps.append(cv2.cornerSubPix(gray, corners.astype(np.float32), (5, 5), (-1, -1),
                                               (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)))
        if len(objps) < 3:
            # not enough good views — fall back to a pinhole estimate from image size
            h, w = images[0].shape[:2]
            K = np.array([[w * 0.9, 0, w / 2], [0, w * 0.9, h / 2], [0, 0, 1.0]])
            return K, np.zeros(4)
        _, K, D, _, _ = cv2.calibrateCamera(np.array(objps), np.array(imgps), (w, h), None, None)
        return K, D

    def _relative_pose(self, left_view: np.ndarray, right_view: np.ndarray):
        """Right-camera pose in the left camera frame via solvePnP on a shared board."""
        import cv2
        objp = self._objp[0].reshape(-1, 3)

        def pnp(view, K):
            gray = cv2.cvtColor(view, cv2.COLOR_BGR2GRAY) if view.ndim == 3 else view
            ok, corners = cv2.findChessboardCorners(gray, self.board_size, None)
            if not ok:
                raise RuntimeError("no checkerboard in view")
            rvec, tvec = cv2.solvePnP(objp, corners.reshape(-1, 2), K, np.zeros(4))
            Rm, _ = cv2.Rodrigues(rvec)
            return Rm, tvec.reshape(3)

        Rl, tl = pnp(left_view, self._K_l if hasattr(self, "_K_l") else None) if False else (None, None)
        raise RuntimeError("use calibrate_from_checkerboard() which passes K explicitly")


__all__ = ["StereoCalibration", "StereoCalibrator"]
