"""Spectral processing pipeline - port of Theremino Spectrometer V5.0.

Processing order (mirrors ``Module_Spectrometer.vb``):

1. ``extract_column_samples``  <- ``Bitmap_To_ReceivedSamples``: each slit-image
   column is summed over rows with per-channel weights -> one raw sample/bin.
2. ``correct_for_irradiance``  <- ``CorrectForIrradiance``: multiply by an
   interpolated (nm -> coeff) response table to flatten sensor+optics response.
3. scale to 0..65535 and subtract the dark level (ADC min).
4. optional multi-frame averaging (``Array_AverageFiltered``).
5. ``spatial_filter``          <- ``Add_SpatialFilter``: two-pass symmetric
   exponential smoothing.
6. ``resample_to_nm_grid``     <- ``Array_UpDownFiltered_To_Array_Calibrated``:
   uniform wavelength grid via piecewise-linear calibration mapping.
7. background subtraction (clipped at zero).

numpy-only; no scipy dependency.
"""

from __future__ import annotations

import numpy as np

from .calibration import WavelengthCalibration


def extract_column_samples(image, kred: float = 1.0, kgreen: float = 1.0,
                           kblue: float = 1.0) -> np.ndarray:
    """One raw sample per image column (slit axis).

    ``image`` is ``(H, W, 3)`` uint8 RGB; for each column i the result is
    ``sum_rows(R*Kred + G*Kgreen + B*Kblue)`` - exactly Theremino's
    ``Bitmap_To_ReceivedSamples`` with its Kred/Kgreen/Kblue weights.
    """
    img = np.asarray(image)
    if img.ndim != 3 or img.shape[2] not in (3,):
        raise ValueError("expected an (H, W, 3) RGB image")
    img = img.astype(np.float64)
    return img[:, :, 0].sum(axis=0) * kred + \
           img[:, :, 1].sum(axis=0) * kgreen + \
           img[:, :, 2].sum(axis=0) * kblue


def spatial_filter(x, kfilter: float = 0.5) -> np.ndarray:
    """Two-pass symmetric exponential smoothing (Theremino ``Add_SpatialFilter``).

    Forward pass:  v_i = v_{i-1} + (x_i - v_{i-1}) * k,   out_f[i] = v_i / 2
    Backward pass: same recurrence right-to-left,          out_b[i] = v_i / 2
    result = out_f + out_b.

    Note: Theremino carries the IIR state from the forward into the backward
    pass; here each pass starts fresh so the filter is symmetric and
    deterministic (identical output for a constant input, no edge memory).
    """
    x = np.asarray(x, dtype=np.float64)
    if len(x) == 0:
        return x.copy()
    k = float(np.clip(kfilter, 1e-9, 1.0))

    def _pass(a):
        v = float(a[0])          # seed with first sample: no startup transient, constants pass through exactly
        out = np.empty_like(a)
        for i in range(len(a)):
            v += (a[i] - v) * k
            out[i] = v / 2.0
        return out

    return _pass(x) + _pass(x[::-1])[::-1]


def resample_to_nm_grid(samples, calib: WavelengthCalibration,
                        nm_min: float = 380.0, nm_max: float = 750.0,
                        n_bins: int = 256) -> np.ndarray:
    """Uniform wavelength grid (Theremino ``Array_UpDownFiltered_To_Array_Calibrated``).

    Output bin i corresponds to ``nm_min + (nm_max - nm_min) * i / n_bins`` and
    takes the value of the raw sample at calibration-mapped bin
    ``calib.nm_to_bin(nm)`` (clamped to the sensor range, nearest bin).
    """
    samples = np.asarray(samples, dtype=np.float64)
    n_raw = len(samples)
    out = np.empty(int(n_bins), dtype=np.float64)
    for i in range(n_bins):
        nm = nm_min + (nm_max - nm_min) * i / n_bins
        bin_ = int(round(calib.nm_to_bin(nm)))
        if bin_ < 0:
            bin_ = 0
        if bin_ > n_raw - 1:
            bin_ = n_raw - 1
        out[i] = samples[bin_]
    return out


def subtract_background(spectrum, background) -> np.ndarray:
    """Subtract a stored background spectrum, clipping at zero."""
    spec = np.asarray(spectrum, dtype=np.float64)
    bg = np.asarray(background, dtype=np.float64).reshape(-1)
    n = min(len(spec), len(bg))
    out = spec.copy()
    if n:
        out[:n] = np.maximum(out[:n] - bg[:n], 0.0)
    return out


def correct_for_irradiance(samples, calib: WavelengthCalibration,
                           irr_nm, irr_coeffs) -> np.ndarray:
    """Flatten sensor+optics response (Theremino ``CorrectForIrradiance``).

    For every raw bin i the coefficient is interpolated from the user table
    ``(irr_nm, irr_coeffs)`` at that bin's wavelength and multiplied in.
    """
    samples = np.asarray(samples, dtype=np.float64)
    if len(irr_nm) < 2:
        return samples.copy()
    bins = np.arange(len(samples), dtype=np.float64)
    nm_per_bin = calib.bin_to_nm_vec(bins)
    coeff = np.interp(nm_per_bin, np.asarray(irr_nm, float), np.asarray(irr_coeffs, float))
    return samples * coeff


class SpectrometerPipeline:
    """Full Theremino-style chain from slit image to calibrated nm spectrum."""

    def __init__(self, calibration: WavelengthCalibration,
                 nm_min: float = 380.0, nm_max: float = 750.0, n_bins: int = 256,
                 kfilter: float = 0.5, dark_level: float | None = None,
                 average_n: int = 1) -> None:
        self.calib = calibration
        self.nm_min = float(nm_min)
        self.nm_max = float(nm_max)
        self.n_bins = int(n_bins)
        self.kfilter = float(kfilter)
        self.dark_level = dark_level

        # irradiance response table (nm -> coeff); None disables correction
        self.irr_nm: np.ndarray | None = None
        self.irr_coeffs: np.ndarray | None = None

        # multi-frame averaging (Theremino Array_AverageFiltered)
        self.average_n = max(1, int(average_n))
        self._buf: np.ndarray | None = None
        self._count = 0

        # background spectrum (in nm-grid space)
        self._background: np.ndarray | None = None

    # -- irradiance table ----------------------------------------------------
    def set_irradiance(self, irr_nm, irr_coeffs) -> None:
        self.irr_nm = np.asarray(irr_nm, dtype=np.float64).reshape(-1)
        self.irr_coeffs = np.asarray(irr_coeffs, dtype=np.float64).reshape(-1)

    # -- background ----------------------------------------------------------
    def set_background(self, spectrum) -> None:
        """Store a background spectrum (nm-grid space) for subtraction."""
        self._background = np.asarray(spectrum, dtype=np.float64).reshape(-1)

    def reset_background(self) -> None:
        self._background = None

    # -- averaging -----------------------------------------------------------
    @property
    def frames_accumulated(self) -> int:
        return self._count

    def reset_average(self) -> None:
        self._buf = None
        self._count = 0

    # -- main entry point ----------------------------------------------------
    def process_image(self, image) -> np.ndarray:
        """Run one slit image through the full chain; returns the nm spectrum.

        With ``average_n > 1`` each call accumulates a frame and the averaged
        spectrum is returned once N frames have been collected (then the
        counter resets - Theremino's repeat/average behaviour).
        """
        x = extract_column_samples(image)

        if self.irr_nm is not None:
            x = correct_for_irradiance(x, self.calib, self.irr_nm, self.irr_coeffs)

        # scale to 0..65535 (Theremino ScaleCoeff_to65536) and remove dark level
        peak = float(x.max()) if len(x) else 0.0
        if peak > 0:
            x = x * (65535.0 / peak)
        if self.dark_level is not None:
            x = np.maximum(x - self.dark_level, 0.0)

        # multi-frame averaging
        if self.average_n > 1:
            shape = x.shape
            if self._buf is None or self._buf.shape != shape:
                self.reset_average()
                self._buf = np.zeros(shape, dtype=np.float64)
            self._buf += x
            self._count += 1
            if self._count < self.average_n:
                return (self._buf / self._count).copy()   # running average
            x = self._buf / self._count
            self.reset_average()

        x = spatial_filter(x, self.kfilter)
        spec = resample_to_nm_grid(x, self.calib, self.nm_min, self.nm_max, self.n_bins)
        if self._background is not None:
            spec = subtract_background(spec, self._background)
        return spec


__all__ = [
    "extract_column_samples", "spatial_filter", "resample_to_nm_grid",
    "subtract_background", "correct_for_irradiance", "SpectrometerPipeline",
]
