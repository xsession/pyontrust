"""Shared fixtures: synthetic stereo rig (known K/R/T)."""
import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def rig():
    """Synthetic calibrated stereo pair (left camera frame is world)."""
    K = np.array([[600.0, 0.0, 320.0], [0.0, 600.0, 240.0], [0.0, 0.0, 1.0]])
    from pyontrust.mobile.stereo3d import StereoCalibrator
    calib = StereoCalibrator().from_baseline(
        K, np.zeros(4), K.copy(), np.zeros(4), baseline_px=120.0, image_size=(640, 480))
    return {"K": K, "R": calib.R, "T": calib.T.reshape(3), "calib": calib}


def project(K, R, T, P):
    """Project a (3,) world point with camera (K, R, T) → (2,) pixel."""
    X = R @ P + T
    v = K @ X
    return v[:2] / v[2]
