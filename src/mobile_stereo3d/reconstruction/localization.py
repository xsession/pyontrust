"""2-D lateral feature localization in each view."""

from __future__ import annotations

import numpy as np


class FeatureLocalizer:
    """Detect corresponding 2-D features (ORB keypoints or marker centers).

    ``mode``:
      * "orb"   — ORB keypoints + BFMatcher knn (ratio test), returns matched
        point sets per view.
      * "marker"— ArUco/charuco board center estimation (single dominant target).
    """

    def __init__(self, mode: str = "orb", n_features: int = 800) -> None:
        if mode not in ("orb", "marker"):
            raise ValueError("mode must be 'orb' or 'marker'")
        self.mode = mode
        self.n_features = n_features

    def extract_features(self, image: np.ndarray) -> np.ndarray:
        """Return (N, 2) float32 feature coordinates in this view."""
        import cv2
        if self.mode == "orb":
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
            orb = cv2.ORB_create(self.n_features)
            kps, _ = orb.detectAndCompute(gray, None)
            pts = np.array([k.pt for k in kps], dtype=np.float32) if kps else np.zeros((0, 2), np.float32)
            return pts

        # marker mode: find the largest contour centroid (dominant target)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return np.zeros((0, 2), np.float32)
        c = max(contours, key=cv2.contourArea)
        m = cv2.moments(c)
        if m["m00"] == 0:
            return np.zeros((0, 2), np.float32)
        cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
        return np.array([[cx, cy]], dtype=np.float32)

    def match(self, left: np.ndarray, right: np.ndarray):
        """Return (pts_left, pts_right) matched correspondences."""
        import cv2
        if self.mode == "marker":
            pl = self.extract_features(left)
            pr = self.extract_features(right)
            return pl[:1], pr[:1]

        gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if left.ndim == 3 else left
        gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY) if right.ndim == 3 else right
        orb = cv2.ORB_create(self.n_features)
        kl, dl = orb.detectAndCompute(gray_l, None)
        kr, dr = orb.detectAndCompute(gray_r, None)
        if dl is None or dr is None:
            return np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = bf.knnMatch(dr, dl, k=2)
        good = [m[0] for m in matches if len(m) == 2 and m[0].distance < 0.75 * m[1].distance]
        # knnMatch(dr, dl): query=right descriptors → kr; train=left → kl
        pl = np.array([kl[m.trainIdx].pt for m in good], dtype=np.float32) if good else np.zeros((0, 2), np.float32)
        pr = np.array([kr[m.queryIdx].pt for m in good], dtype=np.float32) if good else np.zeros((0, 2), np.float32)
        return pl, pr


__all__ = ["FeatureLocalizer"]
