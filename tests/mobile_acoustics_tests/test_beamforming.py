"""Delay-and-sum beamforming power map."""
import numpy as np
from pyontrust.mobile.acoustics import AcousticGrid, DelayAndSumBeamformer


def test_peak_near_source(rig, waveforms):
    grid = AcousticGrid(x_range=(-1, 2.5), y_range=(-2, 2), z_range=(0.3, 3), n_per_axis=16)
    bf = DelayAndSumBeamformer(rig["mics"], sample_rate=48000)
    p = bf.localize(waveforms, grid)
    assert np.linalg.norm(p - rig["source"]) < 2.5   # grid resolution + coherence


def test_power_map_shape_and_finite(rig, waveforms):
    grid = AcousticGrid(x_range=(-1, 2), y_range=(-1, 2), z_range=(0.3, 2), n_per_axis=8)
    bf = DelayAndSumBeamformer(rig["mics"], sample_rate=48000)
    pmap = bf.power_map(waveforms, grid)
    assert len(pmap) == len(grid.points)
    assert np.all(np.isfinite(pmap)) and (pmap > 0).any()


def test_two_mic_minimum():
    try:
        DelayAndSumBeamformer(np.array([[0., 0., 0.]]))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
