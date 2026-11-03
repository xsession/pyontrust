"""GCC-PHAT TDOA: sign, magnitude, matrix symmetry."""
import numpy as np
from mobile_acoustics import TDOAEstimator


def test_sign_and_magnitude():
    fs = 48000
    rng = np.random.default_rng(1)
    n = int(0.5 * fs); t = np.arange(n) / fs
    sig = np.sin(2 * np.pi * (200 * t + 800 * t ** 2)) + rng.standard_normal(n)
    tau = 3e-3
    a = sig.copy()
    b = np.zeros(n); b[int(round(tau * fs)):] = sig[:n - int(round(tau * fs))]
    est = TDOAEstimator(fs)
    d = est.pair_tdoa_s(a, b)          # arrival_a - arrival_b; b lags a -> negative
    assert abs(d + tau) < 1.5 / fs     # within ~1 sample


def test_matrix_symmetry(waveforms):
    est = TDOAEstimator(48000)
    m = est.matrix(waveforms)
    assert m.shape == (len(waveforms), len(waveforms))
    np.testing.assert_allclose(m, -m.T, atol=1e-12)
    assert np.all(np.diag(m) == 0.0)


def test_matrix_matches_geometry(rig, waveforms):
    est = TDOAEstimator(48000)
    m = est.matrix(waveforms)
    tau = np.array([np.linalg.norm(rig["source"] - mi) / 343.0 for mi in rig["mics"]])
    true_m = tau[:, None] - tau[None, :]
    # windowed-chirp GCC-PHAT: per-pair error typically 1-6 samples
    assert np.abs(m - true_m).max() < 10 / 48000


def test_too_short_rejected():
    est = TDOAEstimator(48000)
    try:
        est.pair_tdoa_s(np.zeros(3), np.zeros(3))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
