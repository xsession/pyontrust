"""End-to-end round trip: slit image -> pipeline -> peak wavelengths."""
import numpy as np
from mobile_spectroscopy import SpectrometerPipeline, find_peaks, nearest_line


def test_lines_detected_near_true_wavelengths(linear_calib, slit_image):
    pipe = SpectrometerPipeline(linear_calib, nm_min=400, nm_max=720, n_bins=641)
    spec = pipe.process_image(slit_image)        # lines at bins 100 and 300
    nm_axis = np.linspace(400, 720, 641)

    peaks = find_peaks(spec, delta=3)
    assert len(peaks) >= 2
    p_nm = [float(nm_axis[i]) for i, _ in peaks]

    true_nm = [400 + 100 / 511 * 320, 400 + 300 / 511 * 320]      # ~462.8 and ~590.8
    for want in true_nm:
        assert any(abs(got - want) < 3.0 for got in p_nm), (want, p_nm)


def test_known_line_matching():
    line, dist = nearest_line(436.2)
    assert (line, round(dist, 2)) == (435.83, 0.37)
    line, dist = nearest_line(591.0, lamp="sodium")
    assert line in (588.99, 589.59) and dist < 3.0
