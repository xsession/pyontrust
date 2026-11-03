"""Wavelength calibration (port of Module_Calibrations.vb)."""
import numpy as np
import pytest
from mobile_spectroscopy import WavelengthCalibration, interpolate


def test_interpolate_linear_and_clamped():
    assert interpolate([10, 20, 30], [100, 200, 300], 15) == 150.0
    assert interpolate([10, 20, 30], [100, 200, 300], 5) == 100.0     # clamp low
    assert interpolate([10, 20, 30], [100, 200, 300], 99) == 300.0    # clamp high


def test_round_trip_mapping():
    c = WavelengthCalibration(bins=[0, 100, 500], nms=[400, 500, 700])
    assert abs(c.nm_to_bin(600) - 300) < 1e-9
    assert abs(c.bin_to_nm(250) - 575.0) < 1e-9


def test_add_point_keeps_sorted_and_consistent():
    c = WavelengthCalibration(bins=[0, 100, 500], nms=[400, 500, 700])
    c.add_point(250, 600)
    assert len(c.bins) == 4
    assert np.all(np.diff(c.bins) > 0)
    assert abs(c.nm_to_bin(600) - 250) < 1e-9


def test_remove_point():
    c = WavelengthCalibration(bins=[0, 100, 500], nms=[400, 500, 700])
    c.remove_point(1)
    assert len(c.bins) == 2
    with pytest.raises(ValueError):
        c.remove_point(0)          # only two points left


def test_string_round_trip():
    c = WavelengthCalibration(bins=[0, 100, 500], nms=[400, 500, 700])
    c.add_point(250, 600)
    c2 = WavelengthCalibration.from_string(c.to_string())
    assert (c2.bins == c.bins).all() and (c2.nms == c.nms).all()


def test_validation():
    with pytest.raises(ValueError):
        WavelengthCalibration(bins=[0, 1], nms=[400])          # length mismatch
    with pytest.raises(ValueError):
        WavelengthCalibration(bins=[5], nms=[500])             # <2 points
    with pytest.raises(ValueError):
        WavelengthCalibration(bins=[5, 3], nms=[500, 400])     # not increasing
