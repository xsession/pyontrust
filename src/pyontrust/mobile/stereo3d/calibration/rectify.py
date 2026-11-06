"""Epipolar rectification: align scanlines so correspondence search is 1-D."""

from __future__ import annotations

import numpy as np


class StereoRectifier:
    """Compute and apply stereo rectification maps (cv2.stereoRectify)."""

    def __init__(self, calib) -> None:
        self.calib = calib
        w, h = calib.image_size
        R1, R2, P1, P2, Q, self.roi1, self.roi2 = cv2_stereo_rectify(
            calib.K_left, calib.D_left, calib.K_right, calib.D_right, (w, h), calib.R, calib.T)
        self.map1x = _undistort_map(calib.K_left, calib.D_left, R1, P1, (w, h))
        self.map2x = _undistort_map(calib.K_right, calib.D_right, R2, P2, (w, h))
        self.Q = Q

    def rectify(self, left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        import cv2
        return (cv2.remap(left, *self.map1x, interpolation=cv2.INTER_LINEAR),
                cv2.remap(right, *self.map2x, interpolation=cv2.INTER_LINEAR))

    def depth_from_disparity(self, disparity: np.ndarray) -> np.ndarray:
        """Z = Q[0][2] / disp (standard rectified stereo relation)."""
        with np.errstate(divide="ignore", invalid="ignore"):
            z = self.Q[2, 3] / disparity
        return np.where(disparity > 1e-6, z, np.nan)


def cv2_stereo_rectify(K1, D1, K2, D2, size, R, T):
    import cv2
    w, h = int(size[0]), int(size[1])
    return cv2.stereoRectify(np.asarray(K1), np.asarray(D1).reshape(-1),
                             np.asarray(K2), np.asarray(D2).reshape(-1),
                             (w, h), np.asarray(R), np.asarray(T).reshape(3, 1),
                             flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)


def _undistort_map(K, D, Rr, P, size):
    import cv2
    return cv2.initUndistortRectifyMap(np.asarray(K), np.asarray(D).reshape(-1),
                                       np.asarray(Rr), np.asarray(P), (int(size[0]), int(size[1])), cv2.CV_32F)


__all__ = ["StereoRectifier"]
