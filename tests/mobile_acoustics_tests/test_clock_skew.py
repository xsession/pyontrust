"""Clock-skew calibration with a shared beep."""
import numpy as np
from mobile_acoustics import ClockSkewCalibrator, apply_skew_correction, beep_template


def test_beep_template_shape_and_energy():
    x = beep_template(freq=1000.0, duration_s=0.25, sample_rate=48000)
    assert len(x) == int(0.25 * 48000)
    assert np.max(np.abs(x)) <= 1.0 + 1e-9
    # dominant frequency is the requested tone
    fs = 48000
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f0 = float(np.fft.rfftfreq(len(x), 1 / fs)[np.argmax(spec)])
    assert abs(f0 - 1000.0) < 50


def test_lag_sign_convention():
    from mobile_acoustics.calibration.clock_skew import _cross_lag_samples

    x = beep_template(sample_rate=48000)
    L = 37
    y = np.zeros_like(x); y[L:] = x[:-L]            # arrives later -> +L
    z = np.zeros_like(x); z[:len(x) - L] = x[L:]    # arrives earlier -> -L
    assert _cross_lag_samples(x, y, 1000) == L
    assert _cross_lag_samples(x, z, 1000) == -L


def test_calibrate_recovers_skews():
    rng = np.random.default_rng(7)
    mics = np.array([[0., 0., 0.], [1.5, 0., 0.], [0.75, 1.2, 0.], [0.75, 0.6, 0.8]])
    src = np.array([0.9, -0.6, 1.4])
    c, fs = 343.0, 48000
    skews_true = np.array([0.0, 0.0021, -0.0013, 0.0007])
    d = np.linalg.norm(mics - src, axis=1) / c
    arrival = d + skews_true

    n = int(0.5 * fs)
    sig = rng.standard_normal(n)
    recs = []
    base = min(int(round(a * fs)) for a in arrival)
    for i in range(len(mics)):
        lag = int(round(arrival[i] * fs)) - base
        w = np.zeros(n)
        w[lag:] = sig[:n - lag] + 0.01 * rng.standard_normal(max(1, n - lag))
        recs.append(w)

    est = ClockSkewCalibrator(mics, c=c).calibrate(recs, sample_rate=fs, source_pos=src)
    assert np.allclose(est, skews_true - skews_true[0], atol=5e-5)   # ~2 samples at 48 kHz


def test_apply_skew_correction_properties():
    tdoa = np.array([[0.0, 1e-3, -2e-3], [-1e-3, 0.0, 3e-3], [2e-3, -3e-3, 0.0]])
    skews = np.array([0.0, 5e-4, -7e-4])
    out = apply_skew_correction(tdoa, skews)
    assert np.allclose(np.diag(out), 0.0)
    assert np.allclose(out, -out.T, atol=1e-12)          # antisymmetry preserved
    # correction removes exactly the skew part: residual equals true geometry
    expected = tdoa - (skews[:, None] - skews[None, :])
    np.fill_diagonal(expected, 0.0)
    assert np.allclose(out, expected)


def test_apply_skew_correction_shape_mismatch():
    try:
        apply_skew_correction(np.zeros((2, 2)), np.zeros(3))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
