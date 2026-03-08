"""RF spectrum analysis utilities."""

from __future__ import annotations

from typing import Any

import numpy as np


def compute_power_spectrum(
    iq_samples: np.ndarray,
    sample_rate_hz: float,
    fft_size: int = 1024,
    center_freq_hz: float = 0.0,
) -> dict[str, Any]:
    """Compute power spectral density from IQ samples.

    Returns dict with 'freqs_hz' and 'power_dbm' arrays.
    """
    if len(iq_samples) < fft_size:
        fft_size = len(iq_samples)

    window = np.hanning(fft_size)
    iq_windowed = iq_samples[:fft_size] * window

    fft_result = np.fft.fftshift(np.fft.fft(iq_windowed))
    power = 20 * np.log10(np.abs(fft_result) + 1e-12)

    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0 / sample_rate_hz))
    freqs += center_freq_hz

    return {
        "freqs_hz": freqs.tolist(),
        "power_dbm": power.tolist(),
        "fft_size": fft_size,
        "sample_rate_hz": sample_rate_hz,
        "center_freq_hz": center_freq_hz,
    }


def find_peak_frequency(
    iq_samples: np.ndarray,
    sample_rate_hz: float,
    center_freq_hz: float = 0.0,
    fft_size: int = 1024,
) -> dict[str, float]:
    """Find the peak frequency and its power level."""
    result = compute_power_spectrum(iq_samples, sample_rate_hz, fft_size, center_freq_hz)
    power = np.array(result["power_dbm"])
    freqs = np.array(result["freqs_hz"])

    peak_idx = int(np.argmax(power))
    return {
        "peak_freq_hz": float(freqs[peak_idx]),
        "peak_power_dbm": float(power[peak_idx]),
    }
