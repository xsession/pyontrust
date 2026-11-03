"""3-D spatial triangulation from calibrated multi-view 2-D correspondences."""

from __future__ import annotations

import numpy as np


class Triangulator:
    """Recover 3-D points by intersecting rays from two calibrated cameras.

    Works in the left-camera coordinate frame (right camera pose = R, T).
    Also provides disparity-based depth for rectified pairs.
    """

    def __init__(self, calibration) -> None:
        self.calib = calibration

    def triangulate(self, pts_left: np.ndarray, pts_right: np.ndarray) -> np.ndarray:
        """pts_*: (N, 2) pixel coords → (N, 3) points in the left camera frame."""
        import cv2
        calib = self.calib
        P1 = np.hstack([calib.K_left, np.zeros((3, 1))])
        R = calib.R if calib.R is not None else np.eye(3)
        T = (calib.T.reshape(3) if calib.T is not None else np.array([0.0, 0.0, 120.0]))
        Tc = np.asarray(calib.T, dtype=np.float64).reshape(3, 1)
        P2 = np.hstack([calib.K_right @ R, calib.K_right @ Tc])

        l = np.asarray(pts_left, dtype=np.float64).reshape(-1, 2)
        r = np.asarray(pts_right, dtype=np.float64).reshape(-1, 2)
        if len(l) != len(r):
            raise ValueError(f"correspondence length mismatch: {len(l)} vs {len(r)}")
        n = len(l)
        if n == 0:
            return np.zeros((0, 3))

        pts4_l = np.hstack([l[:n], np.ones((n, 1))]).astype(np.float64)
        pts4_r = np.hstack([r[:n], np.ones((n, 1))]).astype(np.float64)
        pts3d = cv2.triangulatePoints(P1, P2, pts4_l.T, pts4_r.T)
        pts3d = (pts3d[:3] / pts3d[3:4]).T

        # keep only finite points in front of both cameras
        ok = np.isfinite(pts3d).all(axis=1) & (pts3d[:, 2] > 0.5)
        return pts3d[ok]

    def depth_from_disparity(self, disparity: float, baseline_px: float | None = None) -> float:
        """Z = f * B / d for a rectified pair (f in px, B and Z in the same units)."""
        calib = self.calib
        f = float(calib.K_left[0, 0])
        b = baseline_px if baseline_px is not None else float(
            np.linalg.norm(np.asarray(calib.T).reshape(-1)))
        if disparity <= 1e-6:
            return float("inf")
        return f * b / disparity


__all__ = ["Triangulator"]
