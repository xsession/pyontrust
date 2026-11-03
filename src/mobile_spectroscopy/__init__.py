"""Multi-phone spectroscopy: slit-image spectrometer pipeline.

Port of the Theremino Spectrometer V5.0 processing chain (VB.NET, used as
design reference): RGB-weighted column extraction from a diffraction-grating
slit image -> irradiance correction -> dark-level subtraction -> multi-frame
averaging -> two-pass spatial smoothing -> piecewise-linear wavelength
calibration resampling -> background subtraction -> peak/dip detection.

numpy-only; pair with ``mobile_stereo3d.controller.TermuxBridge.capture_still``
to grab slit images from an Android phone camera.
"""

from .calibration import interpolate, WavelengthCalibration
from .pipeline import (SpectrometerPipeline, correct_for_irradiance,
                       extract_column_samples, resample_to_nm_grid,
                       spatial_filter, subtract_background)
from .peaks import find_dips, find_peaks
from .known_lines import KNOWN_LINES_NM, nearest_line

__all__ = [
    "interpolate", "WavelengthCalibration",
    "SpectrometerPipeline", "correct_for_irradiance", "extract_column_samples",
    "resample_to_nm_grid", "spatial_filter", "subtract_background",
    "find_dips", "find_peaks",
    "KNOWN_LINES_NM", "nearest_line",
]
