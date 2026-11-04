"""Tests for pyontrust.analysis.stereo (native stereo-camera analysis)."""
from __future__ import annotations

import numpy as np
import pytest

from pyontrust.analysis.stereo import (
    StereoAnalyzer,
    StereoConfig,
    depth_from_disparity,
    disparity_map,
    points_from_depth,
    rectify_pair,
)


def _cfg(**kw):
    base = dict(fx=500.0, fy=500.0, cx=160.0, cy=120.0, baseline_m=8.0 / 500.0, num_disp=32)
    base.update(kw)
    return StereoConfig(**base)


def _pair(shift: int = 8):
    """Textured left image + right image shifted by ``shift`` px (true depth 1 m)."""
    rng = np.random.default_rng(11)
    h, w = 240, 320
    tex = rng.integers(60, 200, (h, w), dtype=np.uint8)
    for _ in range(40):
        x, y = int(rng.integers(10, w - 30)), int(rng.integers(10, h - 30))
        tex[y:y + 20, x:x + 25] = rng.integers(0, 255)
    right = np.roll(tex, -shift, axis=1)
    right[:, :shift] = tex[:, :shift]
    return tex, right


class TestConfigValidation:
    def test_valid_config_passes(self):
        _cfg().validate()

    @pytest.mark.parametrize("kw", [
        dict(fx=-1), dict(baseline_m=0.0), dict(num_disp=30),
        dict(block_size=8), dict(min_disparity=-1),
    ])
    def test_bad_values_rejected(self, kw):
        with pytest.raises(ValueError):
            _cfg(**kw).validate()


class TestDepthRecovery:
    def test_uniform_shift_recovers_true_depth(self):
        left, right = _pair(shift=8)
        res = StereoAnalyzer(_cfg()).run(left, right)
        inner = res.depth_m[40:-40, 40:-40]
        assert float(np.isfinite(inner).mean()) > 0.95
        assert float(np.nanmedian(inner)) == pytest.approx(1.0, rel=0.02)

    def test_centre_point_in_camera_frame(self):
        left, right = _pair(shift=8)
        res = StereoAnalyzer(_cfg()).run(left, right)
        p = res.points[120, 160]
        assert np.allclose(p, [0.0, 0.0, 1.0], atol=0.05)

    def test_invalid_disparity_gives_nan_depth(self):
        d = depth_from_disparity(np.array([[8.0, -1.0, 0.3]]), _cfg())
        assert np.isfinite(d[0, 0]) and not np.isfinite(d[0, 1]) and not np.isfinite(d[0, 2])

    def test_points_zero_where_invalid(self):
        d = depth_from_disparity(np.array([[8.0, -1.0]]), _cfg())
        pts = points_from_depth(d, _cfg())
        assert np.all(pts[0, 1] == 0.0) and np.isfinite(pts[0, 0]).all()



class TestRectifyAndShapes:
    def test_passthrough_without_calibration(self):
        left, right = _pair()
        lr, rr = rectify_pair(left, right)
        assert lr.dtype == np.uint8 and lr.ndim == 2
        assert lr.shape == left.shape

    def test_r_t_requires_intrinsics(self):
        left, right = _pair()
        R = np.eye(3)
        T = np.array([0.016, 0.0, 0.0])
        with pytest.raises(ValueError, match="K1 and K2"):
            rectify_pair(left, right, R=R, T=T)

    def test_disparity_shape_mismatch_rejected(self):
        a = np.zeros((32, 48), np.uint8)
        b = np.zeros((40, 48), np.uint8)
        with pytest.raises(ValueError, match="shapes differ"):
            disparity_map(a, b, _cfg())

