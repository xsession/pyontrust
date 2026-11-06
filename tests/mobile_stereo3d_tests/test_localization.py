"""Feature localization: ORB extraction + matching on synthetic patterns."""
import numpy as np
from pyontrust.mobile.stereo3d import FeatureLocalizer


def _pattern_image(shift=0):
    """Deterministic textured pattern (filled circles) shifted by `shift` px."""
    import cv2
    img = np.zeros((240, 320), dtype=np.uint8)
    rng = np.random.default_rng(42)
    for _ in range(14):
        cx = int(rng.integers(25, 295)) + shift
        cy = int(rng.integers(25, 215))
        r = int(rng.integers(6, 18))
        cv2.circle(img, (cx, cy), r, 255, -1)
    return img


def test_extract_features():
    loc = FeatureLocalizer()
    feats = loc.extract_features(_pattern_image())
    assert isinstance(feats, np.ndarray) and len(feats) > 0


def test_match_returns_correspondences():
    left = _pattern_image(shift=0)
    right = _pattern_image(shift=15)
    loc = FeatureLocalizer()
    pl, pr = loc.match(left, right)
    assert len(pl) == len(pr)
