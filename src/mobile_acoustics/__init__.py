"""Multi-phone microphone matrix: acoustic noise-source finding.

Pipeline: N phones record the same sound source (Termux mic capture, host-
timestamped) -> GCC-PHAT cross-correlation gives pairwise time-difference-of-
arrival (TDOA) -> least-squares hyperbola intersection yields the 3-D source
position; delay-and-sum and MVDR beamformers over a spatial grid produce
acoustic power maps as cross-checks / bearing-only fallbacks. Per-phone clock
skew is calibrated with a shared beep before TDOA solving.

Reference approach: nGene Beamforming Toolkit (delay-and-sum + MVDR).
"""

from .capture import MicStream, MultiMicCapture
from .localization import TDOAEstimator, SourceLocalizer
from .beamforming import DelayAndSumBeamformer, AcousticGrid, MVDRBeamformer
from .calibration import ClockSkewCalibrator, beep_template, apply_skew_correction

__all__ = [
    "MicStream", "MultiMicCapture",
    "TDOAEstimator", "SourceLocalizer",
    "DelayAndSumBeamformer", "AcousticGrid", "MVDRBeamformer",
    "ClockSkewCalibrator", "beep_template", "apply_skew_correction",
]
