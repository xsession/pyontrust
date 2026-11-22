"""Automatic alignment of two loosely placed cameras (no calibration target).

Two phones lying side by side are never a stereo rig: their lenses differ
(different field of view → scale), one sits a little higher (vertical
offset), they are rolled against each other, and they get nudged while
working.  Block matching needs corresponding points on the *same row*, so
the right image is warped onto the left one:

* SIFT features are matched between the two live images (ratio test +
  mutual check);
* a similarity ``(scale, roll, vertical shift)`` is fitted robustly
  (RANSAC) **on the vertical coordinate only** — the horizontal coordinate
  carries the depth signal (disparity) and must not be "fitted away";
* the horizontal part uses the same scale/roll, and the disparity window
  measured from the matches is shifted to start near zero so SGBM searches
  only where the scene actually is.  The shift is remembered and added back
  before converting disparity to metric depth (parallel-axes model).

Everything is stored resolution-independently (fractions of the image
width), so an alignment estimated on a 640 px live frame applies to a
full-resolution still as well.

Public API
----------
``estimate_alignment(left, right)`` → :class:`PairAlignment`
``PairAlignment.warp_right(right, size)``  right image mapped onto left
``PairAlignment.offset_px(width)``          disparity shift to add back
``blend(old, new, alpha)``                  smooth drift tracking
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

MIN_INLIERS = 25
MAX_FEATURE_PX = 960          # features are found on (at most) this width — fast and plenty


class AlignmentError(RuntimeError):
    """The two images could not be aligned (too few common features)."""


@dataclass(frozen=True)
class PairAlignment:
    """Right-image correction, independent of the image resolution.

    Mapping (pixel coords, ``w`` = image width, centre ``(cx, cy)``)::

        x' = cx + s·cosθ·(x−cx) − s·sinθ·(y−cy) + shift·w
        y' = cy + s·sinθ·(x−cx) + s·cosθ·(y−cy) + ty·w
    """

    scale: float                  # right → left zoom (different lenses / distance)
    roll_deg: float               # rotation of the right camera relative to the left
    ty: float                     # vertical shift, fraction of the width
    shift: float                  # horizontal shift applied (disparity window start), fraction of width
    disp_span: float              # disparity range of the scene after the shift, fraction of width
    inliers: int = 0
    matches: int = 0
    residual_px: float = 0.0      # median vertical error after alignment (at estimation width)
    before_px: float = 0.0        # median vertical error before alignment
    width: int = 0                # estimation width (for reporting)
    swapped: bool = False         # matches say the right camera is on the left
    bias: float = 0.0             # extra disparity from a reference distance (depth only, not the warp)

    # ── geometry ───────────────────────────────────────────────────────
    def matrix(self, w: int, h: int) -> np.ndarray:
        th = math.radians(self.roll_deg)
        a, b = self.scale * math.sin(th), self.scale * math.cos(th)
        cx, cy = w / 2.0, h / 2.0
        return np.array([[b, -a, cx - b * cx + a * cy + self.shift * w],
                         [a, b, cy - a * cx - b * cy + self.ty * w]], np.float64)

    def warp_right(self, right: np.ndarray, size: tuple[int, int]) -> np.ndarray:
        """``right`` (already resized to ``size`` = (w, h)) warped onto the left image."""
        w, h = size
        return cv2.warpAffine(right, self.matrix(w, h), (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    def offset_px(self, width: int) -> float:
        """Disparity removed by the shift (+ reference calibration) — add it back for metric depth."""
        return (self.shift + self.bias) * width

    def num_disp(self, width: int, margin: float = 1.5) -> int:
        """SGBM search range covering the measured scene (multiple of 16, 32..256)."""
        n = int(math.ceil(self.disp_span * width * margin / 16.0)) * 16
        return max(32, min(256, n))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PairAlignment":
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in fields})


# ═══════════════════════════════════════════════════════════════════════
#  Estimation
# ═══════════════════════════════════════════════════════════════════════

def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def match_points(left: np.ndarray, right: np.ndarray, max_features: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    """Corresponding points (N×2 each, in the given images' pixels)."""
    if cv2 is None:  # pragma: no cover
        raise RuntimeError("OpenCV (cv2) is required")
    gl, gr = _gray(left), _gray(right)
    k = min(1.0, MAX_FEATURE_PX / float(gl.shape[1]))
    if k < 1.0:
        gl = cv2.resize(gl, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        gr = cv2.resize(gr, (gl.shape[1], gl.shape[0]), interpolation=cv2.INTER_AREA)
    clahe = cv2.createCLAHE(2.0, (8, 8))                         # phones expose differently
    gl, gr = clahe.apply(gl), clahe.apply(gr)
    if hasattr(cv2, "SIFT_create"):
        det, norm = cv2.SIFT_create(nfeatures=max_features), cv2.NORM_L2
    else:  # pragma: no cover - very old OpenCV
        det, norm = cv2.ORB_create(nfeatures=max_features), cv2.NORM_HAMMING
    kl, dl = det.detectAndCompute(gl, None)
    kr, dr = det.detectAndCompute(gr, None)
    if dl is None or dr is None or len(kl) < 8 or len(kr) < 8:
        return np.zeros((0, 2)), np.zeros((0, 2))
    bf = cv2.BFMatcher(norm)
    fwd = bf.knnMatch(dl, dr, k=2)
    back = {m.queryIdx: m.trainIdx for m in bf.match(dr, dl)}
    good = [m for m, n in (p for p in fwd if len(p) == 2)
            if m.distance < 0.75 * n.distance and back.get(m.trainIdx) == m.queryIdx]
    pl = np.float64([kl[m.queryIdx].pt for m in good]) / k
    pr = np.float64([kr[m.trainIdx].pt for m in good]) / k
    return pl, pr


def _fit_vertical(xr: np.ndarray, yr: np.ndarray, yl: np.ndarray) -> np.ndarray:
    """Least squares ``yl ≈ a·xr + b·yr + c``."""
    A = np.column_stack([xr, yr, np.ones_like(xr)])
    return np.linalg.lstsq(A, yl, rcond=None)[0]


def estimate_alignment(left: np.ndarray, right: np.ndarray, thresh_px: float = 1.5,
                       iters: int = 400, seed: int = 0) -> PairAlignment:
    """Alignment of ``right`` onto ``left`` (both BGR/gray, same size)."""
    if left.shape[:2] != right.shape[:2]:
        raise ValueError("left and right must have the same size (resize first)")
    h, w = left.shape[:2]
    pl, pr = match_points(left, right)
    n = len(pl)
    if n < MIN_INLIERS:
        raise AlignmentError(f"only {n} common features — point both cameras at the same textured scene")
    cx, cy = w / 2.0, h / 2.0
    xr, yr = pr[:, 0] - cx, pr[:, 1] - cy
    xl, yl = pl[:, 0] - cx, pl[:, 1] - cy

    # RANSAC on the vertical coordinate: y_l = a·x_r + b·y_r + c
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(iters):
        idx = rng.choice(n, 3, replace=False)
        try:
            p = _fit_vertical(xr[idx], yr[idx], yl[idx])
        except np.linalg.LinAlgError:
            continue
        s = math.hypot(p[0], p[1])
        if not 0.4 < s < 2.5:                                  # implausible zoom
            continue
        inl = np.abs(p[0] * xr + p[1] * yr + p[2] - yl) < thresh_px
        if best is None or inl.sum() > best.sum():
            best = inl
    if best is None or best.sum() < MIN_INLIERS:
        raise AlignmentError(f"no consistent alignment ({0 if best is None else int(best.sum())} of {n} matches agree)"
                             " — make sure both cameras see the same scene")
    for _ in range(2):                                          # refine on the inliers
        a, b, c = _fit_vertical(xr[best], yr[best], yl[best])
        resid = np.abs(a * xr + b * yr + c - yl)
        best = resid < thresh_px
    scale, roll = math.hypot(a, b), math.degrees(math.atan2(a, b))

    # horizontal: same scale/roll; disparity d = x_l − x_r' over the inliers
    xr_al = b * xr - a * yr
    d = (xl - xr_al)[best]
    lo, hi = np.percentile(d, 2), np.percentile(d, 98)
    swapped = bool(np.median(d) < -0.01 * w)
    start = lo - 0.01 * w                                       # keep a little room below the nearest/farthest point
    return PairAlignment(scale=float(scale), roll_deg=float(roll), ty=float(c / w), shift=float(start / w),
                         disp_span=float((hi - start + 0.01 * w) / w), inliers=int(best.sum()), matches=int(n),
                         residual_px=float(np.median(resid[best])),
                         before_px=float(np.median(np.abs(pl[:, 1] - pr[:, 1]))), width=int(w), swapped=swapped)


def blend(old: PairAlignment | None, new: PairAlignment, alpha: float = 0.3) -> PairAlignment:
    """Smoothly follow a drifting camera (exponential average of the parameters)."""
    if old is None:
        return new
    mix = lambda o, v: (1 - alpha) * o + alpha * v  # noqa: E731
    return replace(new, scale=mix(old.scale, new.scale), roll_deg=mix(old.roll_deg, new.roll_deg),
                   ty=mix(old.ty, new.ty), shift=mix(old.shift, new.shift), bias=old.bias,   # keep the reference calibration
                   disp_span=max(new.disp_span, mix(old.disp_span, new.disp_span)))


def epipolar_preview(left: np.ndarray, right: np.ndarray, al: PairAlignment | None, lines: int = 12) -> np.ndarray:
    """Left | right side by side with horizontal guide lines (aligned right if ``al``)."""
    h, w = left.shape[:2]
    r = al.warp_right(right, (w, h)) if al else right
    img = np.hstack([left, r]).copy()
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for i in range(1, lines + 1):
        y = int(i * h / (lines + 1))
        cv2.line(img, (0, y), (2 * w, y), (0, 255, 255) if al else (0, 0, 255), 1, cv2.LINE_AA)
    return img


__all__ = ["PairAlignment", "AlignmentError", "estimate_alignment", "match_points", "blend", "epipolar_preview"]
