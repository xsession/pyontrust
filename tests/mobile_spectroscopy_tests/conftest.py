"""Shared fixtures: synthetic slit-spectrum images and linear calibration."""
import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def make_slit_image(num_samples=512, lines=((100, 900.0, 3.0), (300, 700.0, 4.0)),
                    baseline=40.0, rows=8):
    """uint8 RGB slit image: one column per sensor bin, gaussian line bumps."""
    base = np.full(num_samples, baseline)
    for center, amp, width in lines:
        base += amp * np.exp(-0.5 * ((np.arange(num_samples) - center) / width) ** 2)
    img = np.zeros((rows, num_samples, 3), dtype=np.uint8)
    for ch in range(3):
        img[:, :, ch] = base.astype(np.uint8)[None, :]
    return img


@pytest.fixture
def slit_image():
    """Two emission lines at bins 100 and 300 of a 512-bin sensor."""
    return make_slit_image()


@pytest.fixture
def linear_calib():
    """Linear bin->nm calibration: bin 0 -> 400 nm, bin 511 -> 720 nm."""
    from mobile_spectroscopy import WavelengthCalibration

    return WavelengthCalibration(bins=[0.0, 511.0], nms=[400.0, 720.0])
