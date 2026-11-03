"""TDOA hyperbola localization + bearing."""
import numpy as np
from mobile_acoustics import TDOAEstimator, SourceLocalizer


def test_localize_within_tolerance(rig, waveforms):
    est = TDOAEstimator(48000)
    m = est.matrix(waveforms)
    loc = SourceLocalizer(rig["mics"], c_sound=343.0)
    p = loc.localize(m)
    assert np.linalg.norm(p - rig["source"]) < 1.5   # sample-quantized TDOA + geometry


def test_solution_satisfies_constraints(rig, waveforms):
    """The returned point must fit the measured TDOAs (residuals ~ measurement noise)."""
    est = TDOAEstimator(48000)
    m = est.matrix(waveforms)
    loc = SourceLocalizer(rig["mics"], c_sound=343.0)
    p = loc.localize(m)
    d = np.linalg.norm(rig["mics"] - p, axis=1)
    pred = (d[:, None] - d[None, :]) / 343.0
    assert np.abs(pred - m).max() < 10 / 48000   # ~ measurement noise of the TDOA stage


def test_bearing_accuracy(rig, waveforms):
    est = TDOAEstimator(48000)
    m = est.matrix(waveforms)
    loc = SourceLocalizer(rig["mics"], c_sound=343.0)
    b = loc.bearing(m)
    true_dir = rig["source"] - rig["mics"].mean(axis=0)
    true_dir /= np.linalg.norm(true_dir)
    assert float(np.dot(b, true_dir)) > 0.90


def test_single_mic_rejected():
    try:
        SourceLocalizer(np.array([[0., 0., 0.]]))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
