"""Stereo calibration: baseline rig + JSON round-trip + checkerboard fallback."""
import numpy as np
import pytest
from mobile_stereo3d import StereoCalibration, StereoCalibrator


def test_from_baseline(rig):
    calib = rig["calib"]
    assert np.allclose(calib.R, np.eye(3))
    assert np.allclose(calib.T.reshape(-1), [120., 0., 0.])
    assert np.allclose(calib.K_left, rig["K"])


def test_json_roundtrip(rig):
    calib = rig["calib"]
    back = StereoCalibration.from_dict(calib.to_dict())
    assert np.allclose(back.K_left, calib.K_left)
    assert np.allclose(back.T.reshape(-1), calib.T.reshape(-1))


def test_checkerboard_fallback_estimate():
    """No detectable board → pinhole fallback K ≈ 0.9 * width."""
    rng = np.random.default_rng(0)
    img = (rng.random((480, 640, 3)) * 255).astype(np.uint8)
    calib = StereoCalibrator().calibrate_from_checkerboard([img], [img])
    assert abs(calib.K_left[0, 0] - 640 * 0.9) < 1e-6


def test_empty_views_rejected():
    with pytest.raises(ValueError):
        StereoCalibrator().calibrate_from_checkerboard([], [])
