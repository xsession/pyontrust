"""MVDR (Capon) adaptive beamforming."""
import numpy as np
from pyontrust.mobile.acoustics import AcousticGrid, DelayAndSumBeamformer, MVDRBeamformer


def _tone_rig(seed=11):
    rng = np.random.default_rng(seed)
    mics = np.array([[0.0, 0., 0.], [1.5, 0., 0.], [0.75, 1.2, 0.], [0.75, 0.6, 0.8]])
    src = np.array([0.9, -0.6, 1.4])
    fs, c = 48000, 343.0
    n = int(0.5 * fs)
    t = np.arange(n) / fs
    wfs = []
    for m in mics:
        lag = int(round(np.linalg.norm(src - m) / c * fs))
        w = np.zeros(n)
        w[lag:] = np.sin(2 * np.pi * 2000.0 * (t[lag:] - lag / fs)) + 0.01 * rng.standard_normal(max(1, n - lag))
        wfs.append(w)
    return mics, src, wfs


def test_two_mic_minimum():
    try:
        MVDRBeamformer(np.array([[0., 0., 0.]]))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_power_map_shape_and_finite():
    mics, _, wfs = _tone_rig()
    grid = AcousticGrid((-1, 2), (-1, 2), (0.5, 2.5), n_per_axis=8)
    pmap = MVDRBeamformer(mics).power_map(wfs, grid)
    assert len(pmap) == len(grid.points)
    assert np.all(np.isfinite(pmap)) and (pmap > 0).any()


def test_localize_near_source():
    """Fine local search: MVDR peak must sit near the true source."""
    mics, src, wfs = _tone_rig()
    d = np.arange(-30, 31) * 0.005   # +/-15 cm in 5 mm steps around the truth

    class _Grid:
        points = np.array([(src[0] + dx, src[1] + dy, src[2] + dz) for dx in d for dy in d for dz in d])

    bf = MVDRBeamformer(mics, sample_rate=48000, freq_min=1500, freq_max=4500, n_fft=2048)
    p = bf.localize(wfs, _Grid())
    assert np.linalg.norm(p - src) < 0.3


def test_interferer_suppression_beats_delay_and_sum():
    """MVDR must null the strong interferer better than D&S (contrast margin)."""
    rng = np.random.default_rng(11)
    mics = np.array([[0.0, 0., 0.], [1.5, 0., 0.], [0.75, 1.2, 0.], [0.75, 0.6, 0.8]])
    fs, c = 48000, 343.0
    n = int(0.5 * fs)
    t = np.arange(n) / fs
    srcA = np.array([2.5, -1.5, 0.8])     # strong interferer (tone @ 2 kHz)
    srcB = np.array([-0.4, 0.9, 1.6])     # weak target      (tone @ 3.5 kHz)
    wfs = []
    for m in mics:
        w = np.zeros(n)
        for pos, amp, f in ((srcA, 3.0, 2000.0), (srcB, 1.0, 3500.0)):
            lag = int(round(np.linalg.norm(pos - m) / c * fs))
            w[lag:] += amp * np.sin(2 * np.pi * f * (t[lag:] - lag / fs))
        w += 0.01 * rng.standard_normal(n)
        wfs.append(w)

    class G:
        points = np.stack([srcA, srcB])

    ds_p = DelayAndSumBeamformer(mics, sample_rate=fs).power_map(wfs, G())
    mv_p = MVDRBeamformer(mics, sample_rate=fs, freq_min=1500, freq_max=4500, n_fft=2048).power_map(wfs, G())
    ds_contrast = 10 * np.log10(ds_p[1] / ds_p[0])   # weak/strong at the two true points
    mv_contrast = 10 * np.log10(mv_p[1] / mv_p[0])
    assert mv_contrast > ds_contrast + 1.0           # MVDR wins by >= 1 dB (observed ~3.6)
