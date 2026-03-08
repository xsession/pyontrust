"""AOI image processing pipeline — OpenCV-based.

Pre-processing, alignment, defect detection, and result annotation.
OpenCV is lazy-imported to keep the package importable without it.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from pyontrust.analysis.aoi.models import (
    AOIVerdict,
    Defect,
    DefectType,
    InspectionResult,
)

logger = logging.getLogger("pyontrust.analysis.aoi.processing")


def _import_cv2() -> Any:
    """Lazy-import OpenCV with a clear error message."""
    try:
        import cv2
        return cv2
    except ImportError as exc:
        raise ImportError(
            "OpenCV required for AOI processing. "
            "Install with: pip install opencv-python"
        ) from exc


# ═══════════════════════════════════════════════════════════════════════
#  Pre-processing
# ═══════════════════════════════════════════════════════════════════════


class ImagePreprocessor:
    """Correct and normalise raw camera frames.

    Pipeline: flat-field → denoise → CLAHE → sharpen.
    """

    def __init__(
        self,
        flat_field: np.ndarray | None = None,
        denoise_strength: int = 5,
        clahe_clip: float = 2.0,
        clahe_grid: tuple[int, int] = (8, 8),
    ) -> None:
        self._flat_field = flat_field
        self._denoise_strength = denoise_strength
        self._clahe_clip = clahe_clip
        self._clahe_grid = clahe_grid

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply the full correction chain."""
        cv2 = _import_cv2()
        img = frame.copy()

        # 1. Flat-field correction
        if self._flat_field is not None:
            img = cv2.divide(img, self._flat_field, scale=255)

        # 2. Denoise
        if self._denoise_strength > 0:
            if len(img.shape) == 3 and img.shape[2] >= 3:
                img = cv2.fastNlMeansDenoisingColored(
                    img, None,
                    self._denoise_strength, self._denoise_strength,
                    7, 21,
                )
            else:
                img = cv2.fastNlMeansDenoising(
                    img, None,
                    self._denoise_strength,
                    7, 21,
                )

        # 3. CLAHE (adaptive contrast enhancement)
        clahe = cv2.createCLAHE(
            clipLimit=self._clahe_clip,
            tileGridSize=self._clahe_grid,
        )
        if len(img.shape) == 3 and img.shape[2] >= 3:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            img = clahe.apply(img)

        # 4. Sharpen via unsharp mask
        blurred = cv2.GaussianBlur(img, (0, 0), 3)
        img = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

        return img


# ═══════════════════════════════════════════════════════════════════════
#  Alignment
# ═══════════════════════════════════════════════════════════════════════


class BoardAligner:
    """Register a captured image to a golden reference using feature matching."""

    def __init__(
        self,
        reference_image: np.ndarray,
        method: str = "orb",
        min_matches: int = 10,
    ) -> None:
        self._reference = reference_image
        self._method = method
        self._min_matches = min_matches

    def align(self, captured: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Align *captured* to the reference.

        Returns:
            ``(aligned_image, homography_matrix)``

        Raises:
            RuntimeError: If not enough feature matches are found.
        """
        cv2 = _import_cv2()

        ref_gray = self._to_gray(self._reference)
        cap_gray = self._to_gray(captured)

        # Feature detection
        if self._method == "sift":
            detector = cv2.SIFT_create(nfeatures=5000)
            norm = cv2.NORM_L2
        else:
            detector = cv2.ORB_create(nfeatures=5000)
            norm = cv2.NORM_HAMMING

        kp_ref, desc_ref = detector.detectAndCompute(ref_gray, None)
        kp_cap, desc_cap = detector.detectAndCompute(cap_gray, None)

        if desc_ref is None or desc_cap is None:
            raise RuntimeError("Feature detection failed — not enough texture.")

        # KNN matching + Lowe's ratio test
        matcher = cv2.BFMatcher(norm, crossCheck=False)
        matches = matcher.knnMatch(desc_cap, desc_ref, k=2)
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]

        if len(good) < self._min_matches:
            raise RuntimeError(
                f"Only {len(good)} feature matches (need ≥{self._min_matches}). "
                "Check lighting or camera position."
            )

        # Homography via RANSAC
        pts_cap = np.float32(
            [kp_cap[m.queryIdx].pt for m in good]
        ).reshape(-1, 1, 2)
        pts_ref = np.float32(
            [kp_ref[m.trainIdx].pt for m in good]
        ).reshape(-1, 1, 2)

        H, mask = cv2.findHomography(pts_cap, pts_ref, cv2.RANSAC, 5.0)
        h, w = ref_gray.shape[:2]
        aligned = cv2.warpPerspective(captured, H, (w, h))

        inliers = int(mask.sum()) if mask is not None else 0
        logger.info(
            "Alignment: %d/%d inliers, det(H)=%.3f",
            inliers, len(good), np.linalg.det(H),
        )
        return aligned, H

    @staticmethod
    def _to_gray(img: np.ndarray) -> np.ndarray:
        cv2 = _import_cv2()
        if len(img.shape) == 3 and img.shape[2] >= 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img


# ═══════════════════════════════════════════════════════════════════════
#  Defect Detection
# ═══════════════════════════════════════════════════════════════════════


class DefectDetector:
    """Detect defects by comparing an aligned image against a golden reference."""

    def __init__(
        self,
        reference: np.ndarray,
        diff_threshold: int = 30,
        min_defect_area: int = 50,
    ) -> None:
        self._reference = reference
        self._threshold = diff_threshold
        self._min_area = min_defect_area

    def detect(self, aligned: np.ndarray) -> list[Defect]:
        """Run difference-based defect detection."""
        cv2 = _import_cv2()

        ref_gray = BoardAligner._to_gray(self._reference)
        cap_gray = BoardAligner._to_gray(aligned)

        # Absolute difference
        diff = cv2.absdiff(ref_gray, cap_gray)

        # Threshold + morphology cleanup
        _, binary = cv2.threshold(diff, self._threshold, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        defects: list[Defect] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self._min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            defect_type = self._classify(
                contour,
                ref_gray[y : y + h, x : x + w],
                cap_gray[y : y + h, x : x + w],
            )
            confidence = min(1.0, area / (self._min_area * 10))

            defects.append(Defect(
                defect_type=defect_type,
                x=x, y=y, width=w, height=h,
                confidence=confidence,
                description=f"area={area:.0f}px² ar={w / max(h, 1):.2f}",
            ))

        logger.info("DefectDetector: %d defect(s) above threshold.", len(defects))
        return defects

    @staticmethod
    def _classify(
        contour: np.ndarray,
        ref_roi: np.ndarray,
        cap_roi: np.ndarray,
    ) -> DefectType:
        """Heuristic defect classification from geometry + intensity."""
        cv2 = _import_cv2()
        _, _, w, h = cv2.boundingRect(contour)
        aspect = w / max(h, 1)
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / max(perimeter ** 2, 1)

        ref_mean = float(ref_roi.mean()) if ref_roi.size else 128.0
        cap_mean = float(cap_roi.mean()) if cap_roi.size else 128.0

        if cap_mean < ref_mean - 40 and area > 500:
            return DefectType.MISSING_COMPONENT
        if aspect > 3.0 or aspect < 0.33:
            return DefectType.SOLDER_BRIDGE
        if cap_mean > ref_mean + 30:
            return DefectType.EXCESS_SOLDER
        if circularity > 0.7 and area < 300:
            return DefectType.INSUFFICIENT_SOLDER
        return DefectType.CONTAMINATION


# ═══════════════════════════════════════════════════════════════════════
#  Result Annotation
# ═══════════════════════════════════════════════════════════════════════


class ResultAnnotator:
    """Draw defect overlays and verdict banners on inspection images."""

    _COLORS: dict[AOIVerdict, tuple[int, int, int]] = {
        AOIVerdict.PASS: (0, 200, 0),
        AOIVerdict.FAIL: (0, 0, 255),
        AOIVerdict.WARN: (0, 180, 255),
        AOIVerdict.REVIEW: (255, 180, 0),
    }

    @classmethod
    def annotate(cls, image: np.ndarray, result: InspectionResult) -> np.ndarray:
        """Return a copy of *image* with defect bounding boxes and verdict banner."""
        cv2 = _import_cv2()

        annotated = image.copy()
        if len(annotated.shape) == 2:
            annotated = cv2.cvtColor(annotated, cv2.COLOR_GRAY2BGR)

        for defect in result.defects:
            color = cls._COLORS.get(defect.severity, (255, 255, 255))
            cv2.rectangle(
                annotated,
                (defect.x, defect.y),
                (defect.x + defect.width, defect.y + defect.height),
                color, 2,
            )
            label = f"{defect.defect_type.value} ({defect.confidence:.0%})"
            cv2.putText(
                annotated, label,
                (defect.x, max(defect.y - 8, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
            )

        # Verdict banner
        verdict_color = cls._COLORS.get(result.verdict, (255, 255, 255))
        banner = f"VERDICT: {result.verdict.value}  |  {result.total_defect_count} defect(s)"
        cv2.putText(
            annotated, banner,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, verdict_color, 2,
        )
        return annotated
