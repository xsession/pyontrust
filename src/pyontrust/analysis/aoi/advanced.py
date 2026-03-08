"""Advanced AOI analysis — scikit-image based.

Higher-fidelity inspection for solder joint grading, sub-pixel component
alignment, and via fill measurement.  All heavy dependencies are
lazy-imported.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from pyontrust.analysis.aoi.models import (
    AlignmentResult,
    SolderJointResult,
    ViaFillResult,
)

logger = logging.getLogger("pyontrust.analysis.aoi.advanced")


def _import_cv2() -> Any:
    try:
        import cv2
        return cv2
    except ImportError as exc:
        raise ImportError(
            "OpenCV required. Install with: pip install opencv-python"
        ) from exc


def _import_skimage() -> Any:
    try:
        import skimage
        return skimage
    except ImportError as exc:
        raise ImportError(
            "scikit-image required for advanced AOI analysis. "
            "Install with: pip install scikit-image"
        ) from exc


# ═══════════════════════════════════════════════════════════════════════
#  Solder Joint Analyser
# ═══════════════════════════════════════════════════════════════════════


class SolderJointAnalyzer:
    """Detect and grade solder joints using adaptive thresholding and
    shape-based feature extraction.

    Methodology:
        1. Adaptive threshold to isolate bright solder regions
        2. Morphological cleanup + connected component labelling
        3. Shape features: area, circularity, intensity stats
        4. Radial intensity profile → approximate wetting angle
        5. Grade each joint: GOOD / COLD / EXCESS / INSUFFICIENT / BRIDGE
    """

    def __init__(
        self,
        min_joint_area: int = 30,
        max_joint_area: int = 5000,
        circularity_threshold: float = 0.4,
    ) -> None:
        self._min_area = min_joint_area
        self._max_area = max_joint_area
        self._circ_thresh = circularity_threshold

    def analyze(
        self,
        image: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> list[SolderJointResult]:
        """Detect and grade solder joints in *image*."""
        cv2 = _import_cv2()
        _import_skimage()
        from skimage import filters, measure, morphology

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Adaptive threshold
        thresh = filters.threshold_local(
            gray, block_size=51, method="gaussian", offset=-10,
        )
        binary = gray > thresh

        if mask is not None:
            binary = binary & (mask > 0)

        # Morphological cleanup
        binary = morphology.remove_small_objects(binary, min_size=self._min_area)
        binary = morphology.remove_small_holes(binary, area_threshold=20)
        binary = morphology.binary_closing(binary, morphology.disk(2))

        labels = measure.label(binary)
        regions = measure.regionprops(labels, intensity_image=gray)

        results: list[SolderJointResult] = []
        for region in regions:
            if not (self._min_area <= region.area <= self._max_area):
                continue

            circularity = (4 * np.pi * region.area) / max(region.perimeter ** 2, 1)
            y, x = region.centroid

            wetting = self._estimate_wetting_angle(
                gray, int(y), int(x), region.equivalent_diameter / 2,
            )

            std_val = float(gray[labels == region.label].std())

            grade = self._grade_joint(
                area=region.area,
                circularity=circularity,
                mean_intensity=region.mean_intensity,
                std_intensity=std_val,
                wetting_angle=wetting,
            )

            results.append(SolderJointResult(
                x=int(x), y=int(y),
                area_px=region.area,
                circularity=circularity,
                mean_intensity=region.mean_intensity,
                std_intensity=std_val,
                wetting_angle_deg=wetting,
                grade=grade,
            ))

        good = sum(1 for r in results if r.grade == "GOOD")
        logger.info(
            "Solder analysis: %d joints — %d GOOD, %d defective",
            len(results), good, len(results) - good,
        )
        return results

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _estimate_wetting_angle(
        gray: np.ndarray, cy: int, cx: int, radius: float,
    ) -> float:
        """Approximate wetting angle from radial intensity gradient."""
        r = max(int(radius), 3)
        angles = np.linspace(0, 2 * np.pi, 36)
        gradients: list[float] = []

        for angle in angles:
            points: list[float] = []
            for d in range(max(r - 3, 1), r + 3):
                py = int(cy + d * np.sin(angle))
                px = int(cx + d * np.cos(angle))
                if 0 <= py < gray.shape[0] and 0 <= px < gray.shape[1]:
                    points.append(float(gray[py, px]))
            if len(points) >= 3:
                gradients.append(abs(points[-1] - points[0]))

        if not gradients:
            return 45.0
        avg_gradient = float(np.mean(gradients))
        return max(10.0, min(80.0, 80.0 - avg_gradient * 0.5))

    def _grade_joint(
        self,
        area: float,
        circularity: float,
        mean_intensity: float,
        std_intensity: float,
        wetting_angle: float,
    ) -> str:
        if circularity < 0.2:
            return "BRIDGE"
        if wetting_angle > 60:
            return "COLD"
        if area > self._max_area * 0.8:
            return "EXCESS"
        if area < self._min_area * 2:
            return "INSUFFICIENT"
        if std_intensity > 50:
            return "COLD"
        return "GOOD"


# ═══════════════════════════════════════════════════════════════════════
#  Component Alignment Checker
# ═══════════════════════════════════════════════════════════════════════


class ComponentAlignmentChecker:
    """Measure component placement accuracy using sub-pixel template matching."""

    def __init__(
        self,
        px_per_mm: float = 50.0,
        tolerance_mm: float = 0.1,
    ) -> None:
        self._px_per_mm = px_per_mm
        self._tolerance = tolerance_mm

    def check_alignment(
        self,
        image: np.ndarray,
        template: np.ndarray,
        expected_x: int,
        expected_y: int,
        component_id: str = "U1",
    ) -> AlignmentResult:
        """Measure placement offset of a component vs expected position."""
        cv2 = _import_cv2()

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template

        th, tw = tmpl.shape[:2]
        margin = max(th, tw)

        # ROI around expected location
        y1 = max(0, expected_y - margin)
        y2 = min(gray.shape[0], expected_y + th + margin)
        x1 = max(0, expected_x - margin)
        x2 = min(gray.shape[1], expected_x + tw + margin)
        roi = gray[y1:y2, x1:x2]

        if roi.shape[0] < th or roi.shape[1] < tw:
            return AlignmentResult(
                component_id=component_id,
                dx_mm=0.0, dy_mm=0.0,
                rotation_deg=0.0,
                within_tolerance=False,
            )

        # Template match
        result = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        mx, my = max_loc

        # Sub-pixel refinement via parabolic interpolation
        dx_sub, dy_sub = 0.0, 0.0
        if 0 < mx < result.shape[1] - 1 and 0 < my < result.shape[0] - 1:
            denom_x = 2 * result[my, mx] - result[my, mx + 1] - result[my, mx - 1]
            denom_y = 2 * result[my, mx] - result[my + 1, mx] - result[my - 1, mx]
            if abs(denom_x) > 1e-6:
                dx_sub = 0.5 * (result[my, mx + 1] - result[my, mx - 1]) / denom_x
            if abs(denom_y) > 1e-6:
                dy_sub = 0.5 * (result[my + 1, mx] - result[my - 1, mx]) / denom_y

        actual_x = x1 + mx + dx_sub
        actual_y = y1 + my + dy_sub

        dx_mm = (actual_x - expected_x) / self._px_per_mm
        dy_mm = (actual_y - expected_y) / self._px_per_mm
        offset_mm = np.sqrt(dx_mm ** 2 + dy_mm ** 2)

        # Rotation detection
        rotation = self._detect_rotation(roi, tmpl, mx, my)

        return AlignmentResult(
            component_id=component_id,
            dx_mm=dx_mm,
            dy_mm=dy_mm,
            rotation_deg=rotation,
            within_tolerance=offset_mm <= self._tolerance,
        )

    @staticmethod
    def _detect_rotation(
        roi: np.ndarray, template: np.ndarray, mx: int, my: int,
    ) -> float:
        """Detect rotation using log-polar phase correlation."""
        try:
            from skimage import feature, transform
        except ImportError:
            return 0.0

        th, tw = template.shape[:2]
        comp_roi = roi[my : my + th, mx : mx + tw]
        if comp_roi.shape != template.shape:
            return 0.0

        try:
            r = min(th, tw) // 2
            comp_lp = transform.warp_polar(comp_roi.astype(float), radius=r)
            tmpl_lp = transform.warp_polar(template.astype(float), radius=r)
            shift, _, _ = feature.phase_cross_correlation(tmpl_lp, comp_lp)
            return shift[0] * (360.0 / comp_lp.shape[0])
        except Exception:
            return 0.0


# ═══════════════════════════════════════════════════════════════════════
#  Via Fill Inspector
# ═══════════════════════════════════════════════════════════════════════


class ViaFillInspector:
    """Inspect via fill quality from backlight imaging.

    Methodology:
        1. Hough Circle Transform to detect vias
        2. Analyse fill ratio from intensity within via boundary
        3. Count voids using local thresholding
        4. Grade per IPC-6012 fill requirements
    """

    def __init__(
        self,
        min_radius_px: int = 5,
        max_radius_px: int = 50,
        fill_threshold: float = 0.75,
    ) -> None:
        self._min_r = min_radius_px
        self._max_r = max_radius_px
        self._fill_thresh = fill_threshold

    def inspect(self, backlight_image: np.ndarray) -> list[ViaFillResult]:
        """Inspect via fill quality from a backlight image.

        Backlit vias: bright = unfilled, dark = filled.
        """
        cv2 = _import_cv2()
        from scipy import ndimage

        gray = cv2.cvtColor(backlight_image, cv2.COLOR_BGR2GRAY) \
            if len(backlight_image.shape) == 3 else backlight_image

        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=self._min_r * 3,
            param1=100,
            param2=30,
            minRadius=self._min_r,
            maxRadius=self._max_r,
        )

        if circles is None:
            logger.warning("No vias detected in backlight image.")
            return []

        results: list[ViaFillResult] = []
        for i, (cx, cy, r) in enumerate(circles[0].astype(int)):
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (int(cx), int(cy)), int(r), 255, -1)

            via_pixels = gray[mask > 0]
            if via_pixels.size == 0:
                continue

            # Background median for threshold
            bg_pixels = gray[mask == 0]
            median_bg = float(np.median(bg_pixels)) if bg_pixels.size else 200.0
            threshold = median_bg * 0.5
            filled_pixels = int((via_pixels < threshold).sum())
            fill_ratio = filled_pixels / via_pixels.size

            # Count voids
            via_roi = gray[
                max(0, int(cy) - int(r)) : int(cy) + int(r),
                max(0, int(cx) - int(r)) : int(cx) + int(r),
            ]
            void_count = self._count_voids(via_roi, ndimage)

            grade = self._grade_fill(fill_ratio, void_count)

            results.append(ViaFillResult(
                via_id=i,
                x=int(cx), y=int(cy),
                diameter_px=float(2 * r),
                fill_ratio=fill_ratio,
                void_count=void_count,
                grade=grade,
            ))

        good = sum(1 for r in results if r.grade == "FULL")
        logger.info(
            "Via fill: %d vias — %d FULL, %d defective",
            len(results), good, len(results) - good,
        )
        return results

    @staticmethod
    def _count_voids(via_roi: np.ndarray, ndimage_mod: Any) -> int:
        cv2 = _import_cv2()
        if via_roi.size == 0:
            return 0
        _, binary = cv2.threshold(
            via_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        labeled, n_labels = ndimage_mod.label(binary)
        return max(0, n_labels - 1)

    def _grade_fill(self, fill_ratio: float, void_count: int) -> str:
        if fill_ratio > 1.05:
            return "OVERFILL"
        if fill_ratio >= self._fill_thresh and void_count == 0:
            return "FULL"
        if fill_ratio >= self._fill_thresh:
            return "PARTIAL"
        return "VOID"
