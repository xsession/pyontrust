"""Spectral processing pipeline (port of Module_Spectrometer.vb)."""
import numpy as np
from pyontrust.mobile.spectroscopy import (SpectrometerPipeline, WavelengthCalibration,
                                 correct_for_irradiance, extract_column_samples,
                                 resample_to_nm_grid, spatial_filter, subtract_background)


def test_extract_column_samples_weighted():
    img = np.zeros((2, 3, 3), dtype=np.uint8)
    img[:, :, 0] = [[1, 2, 3], [4, 5, 6]]          # R channel only
    out = extract_column_samples(img, kred=2.0, kgreen=1.0, kblue=1.0)
    assert out.tolist() == [2 * (1 + 4), 2 * (2 + 5), 2 * (3 + 6)]


def test_spatial_filter_smooths_noise():
    rng = np.random.default_rng(3)
    noisy = 100.0 + rng.standard_normal(512)
    sm = spatial_filter(noisy, 0.5)
    assert sm.std() < noisy.std() * 0.8


def test_spatial_filter_constants_and_step():
    c = np.full(64, 7.5)
    assert float(np.abs(spatial_filter(c, 0.5) - 7.5).max()) == 0.0   # constants pass through exactly
    x = np.concatenate([np.zeros(256), np.ones(256)])
    s = spatial_filter(x, 0.5)
    assert abs(float(s[128:-128].mean()) - 0.5) < 0.05


def test_resample_to_nm_grid(linear_calib):
    samples = np.linspace(0, 1, 512)
    spec = resample_to_nm_grid(samples, linear_calib, 400, 720, 641)
    assert len(spec) == 641
    # bin 255.5 (mid sensor) -> nm 560 -> grid index ~320
    i = int(np.argmin(abs(np.linspace(400, 720, 641) - 560)))
    assert abs(spec[i] - samples[255]) < 0.02


def test_subtract_background_clips_at_zero():
    out = subtract_background(np.array([3.0, 12.0, 8.0]), np.array([5.0, 10.0, 20.0]))
    assert out.tolist() == [0.0, 2.0, 0.0]


def test_correct_for_irradiance_interpolates(linear_calib):
    x = np.ones(512)   # full 512-bin sensor: bin 0 -> 400 nm, bin 511 -> 720 nm
    out = correct_for_irradiance(x, linear_calib, [400.0, 720.0], [2.0, 3.0])
    assert abs(out[0] - 2.0) < 1e-9 and abs(out[-1] - 3.0) < 1e-9


def test_pipeline_output_shape_and_scale(linear_calib, slit_image):
    pipe = SpectrometerPipeline(linear_calib, nm_min=400, nm_max=720, n_bins=641)
    spec = pipe.process_image(slit_image)
    assert len(spec) == 641
    assert np.all(np.isfinite(spec)) and spec.max() > 0


def test_pipeline_averaging_accumulates(linear_calib, slit_image):
    pipe = SpectrometerPipeline(linear_calib, nm_min=400, nm_max=720, n_bins=641, average_n=3)
    s1 = pipe.process_image(slit_image)
    assert pipe.frames_accumulated == 1
    s3 = pipe.process_image(slit_image)
    pipe.process_image(slit_image)
    assert pipe.frames_accumulated == 0          # reset after N frames
    assert np.allclose(s1, s3)                   # identical frames -> identical averages


def test_pipeline_background_subtraction(linear_calib, slit_image):
    pipe = SpectrometerPipeline(linear_calib, nm_min=400, nm_max=720, n_bins=641)
    spec = pipe.process_image(slit_image)
    pipe.set_background(spec * 0.5)
    out = pipe.process_image(slit_image)
    assert np.allclose(out, spec - spec * 0.5, atol=1e-9)
