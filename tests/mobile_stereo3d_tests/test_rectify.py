"""Epipolar rectification + disparity→depth (synthetic rig)."""
import numpy as np
from pyontrust.mobile.stereo3d import StereoRectifier


def test_rectify_shapes(rig):
    rng = np.random.default_rng(3)
    left = (rng.random((480, 640)) * 255).astype(np.uint8)
    right = (rng.random((480, 640)) * 255).astype(np.uint8)
    rect = StereoRectifier(rig["calib"])
    l_r, r_r = rect.rectify(left, right)
    assert l_r.shape == left.shape and r_r.shape == right.shape


def test_depth_from_disparity_monotonic(rig):
    rect = StereoRectifier(rig["calib"])
    z = rect.depth_from_disparity(np.array([10., 20.]))
    assert np.all(np.isfinite(z)) and z[0] > z[1]


def test_zero_disparity_is_nan(rig):
    rect = StereoRectifier(rig["calib"])
    z = rect.depth_from_disparity(np.array([0.]))
    assert np.isnan(z).all()
