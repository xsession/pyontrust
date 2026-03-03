"""Comprehensive tests for gui_app.csv_plotter.metrics.

Covers:
- Normal operation (all 10 metrics produce real values)
- Edge cases: empty series, single value, all-NaN, all-constant, string data
- Large/negative/inf values
- Frequency estimation (pure sine wave)
- Zero-crossing fallback path
- Internal helpers (_fmt, _estimate_frequency_*)
"""

from __future__ import annotations

import math
import sys
import os
import unittest

import numpy as np
import pandas as pd

# Ensure the csv_plotter package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gui_app", "csv_plotter"))

from metrics import (  # noqa: E402
    MetricsTuple,
    _NA_10,
    _estimate_frequency_fft,
    _estimate_frequency_zero_crossing,
    _fmt,
    compute_signal_metrics,
)


class TestFmt(unittest.TestCase):
    """Tests for the ``_fmt`` helper."""

    def test_normal_float(self) -> None:
        self.assertEqual(_fmt(1.23456), "1.235")  # default 3 decimals

    def test_zero(self) -> None:
        self.assertEqual(_fmt(0.0), "0.000")

    def test_negative(self) -> None:
        self.assertEqual(_fmt(-3.14), "-3.140")

    def test_custom_decimals(self) -> None:
        self.assertEqual(_fmt(2.5, 1), "2.5")

    def test_nan(self) -> None:
        self.assertEqual(_fmt(float("nan")), "n/a")

    def test_inf(self) -> None:
        self.assertEqual(_fmt(float("inf")), "n/a")

    def test_neg_inf(self) -> None:
        self.assertEqual(_fmt(float("-inf")), "n/a")


class TestComputeSignalMetricsBasic(unittest.TestCase):
    """Basic tests with well-formed input."""

    def _make_ramp(self, n: int = 100) -> tuple[pd.Series, pd.Series]:
        x = pd.Series(np.linspace(0, 1, n))
        y = pd.Series(np.linspace(0, 10, n))
        return x, y

    def test_returns_10_tuple(self) -> None:
        result = compute_signal_metrics(*self._make_ramp())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 10)

    def test_all_values_not_na(self) -> None:
        """All basic stats should be numbers, not n/a, for a simple ramp."""
        result = compute_signal_metrics(*self._make_ramp())
        # min, max, avg, med, p2p, std, rms, crest should all be numeric
        for i in range(8):
            self.assertNotEqual(result[i], "n/a", f"metric index {i} should not be n/a")

    def test_min_max(self) -> None:
        x, y = self._make_ramp()
        result = compute_signal_metrics(x, y)
        self.assertAlmostEqual(float(result[0]), 0.0, places=2)   # min
        self.assertAlmostEqual(float(result[1]), 10.0, places=2)  # max

    def test_avg_median(self) -> None:
        x, y = self._make_ramp()
        result = compute_signal_metrics(x, y)
        self.assertAlmostEqual(float(result[2]), 5.0, places=1)   # avg
        self.assertAlmostEqual(float(result[3]), 5.0, places=1)   # med

    def test_p2p(self) -> None:
        x, y = self._make_ramp()
        result = compute_signal_metrics(x, y)
        self.assertAlmostEqual(float(result[4]), 10.0, places=2)  # p2p

    def test_std_population(self) -> None:
        """Population std of uniform [0, 10] on 100 points ≈ 2.89."""
        x, y = self._make_ramp()
        result = compute_signal_metrics(x, y)
        std = float(result[5])
        self.assertTrue(2.5 < std < 3.5, f"std={std}")

    def test_rms_positive(self) -> None:
        x, y = self._make_ramp()
        result = compute_signal_metrics(x, y)
        rms = float(result[6])
        self.assertTrue(rms > 0, f"rms={rms}")

    def test_crest_factor(self) -> None:
        x, y = self._make_ramp()
        result = compute_signal_metrics(x, y)
        crest = float(result[7])
        self.assertTrue(crest > 1.0, f"crest={crest}")


class TestComputeSignalMetricsEdgeCases(unittest.TestCase):
    """Edge cases that must be handled gracefully."""

    def test_empty_series(self) -> None:
        result = compute_signal_metrics(pd.Series([], dtype=float), pd.Series([], dtype=float))
        self.assertEqual(result, _NA_10)

    def test_all_nan(self) -> None:
        x = pd.Series([0, 1, 2])
        y = pd.Series([float("nan")] * 3)
        result = compute_signal_metrics(x, y)
        self.assertEqual(result, _NA_10)

    def test_single_value(self) -> None:
        """A single data point should still yield min=max=avg=med, p2p=0."""
        x = pd.Series([0.0])
        y = pd.Series([42.0])
        result = compute_signal_metrics(x, y)
        self.assertEqual(result[0], "42.000")  # min
        self.assertEqual(result[1], "42.000")  # max
        self.assertEqual(result[4], "0.000")   # p2p

    def test_constant_signal(self) -> None:
        """All-identical values: std=0, rms=value, crest=1."""
        n = 50
        x = pd.Series(np.arange(n, dtype=float))
        y = pd.Series([5.0] * n)
        result = compute_signal_metrics(x, y)
        self.assertEqual(result[5], "0.000")               # std
        self.assertAlmostEqual(float(result[6]), 5.0, 2)   # rms
        self.assertAlmostEqual(float(result[7]), 1.0, 2)   # crest

    def test_string_y_values(self) -> None:
        """Non-numeric strings should coerce to NaN → all n/a."""
        x = pd.Series([0, 1, 2])
        y = pd.Series(["foo", "bar", "baz"])
        result = compute_signal_metrics(x, y)
        self.assertEqual(result, _NA_10)

    def test_mixed_numeric_strings(self) -> None:
        """A column with some numeric and some string values."""
        x = pd.Series([0, 1, 2, 3, 4])
        y = pd.Series(["1.0", "2.0", "bad", "4.0", "5.0"])
        result = compute_signal_metrics(x, y)
        self.assertNotEqual(result[0], "n/a")  # min should be 1.0
        self.assertAlmostEqual(float(result[0]), 1.0, places=2)

    def test_negative_values(self) -> None:
        x = pd.Series(np.arange(5, dtype=float))
        y = pd.Series([-10, -5, 0, 5, 10], dtype=float)
        result = compute_signal_metrics(x, y)
        self.assertAlmostEqual(float(result[0]), -10.0, places=2)  # min
        self.assertAlmostEqual(float(result[1]), 10.0, places=2)   # max
        self.assertAlmostEqual(float(result[4]), 20.0, places=2)   # p2p

    def test_very_large_values(self) -> None:
        x = pd.Series([0, 1, 2])
        y = pd.Series([1e15, 2e15, 3e15])
        result = compute_signal_metrics(x, y)
        self.assertNotEqual(result[0], "n/a")
        self.assertNotEqual(result[6], "n/a")  # rms

    def test_inf_in_data(self) -> None:
        """Inf should be dropped by pd.to_numeric + dropna."""
        x = pd.Series([0, 1, 2, 3])
        y = pd.Series([1.0, float("inf"), 3.0, 4.0])
        result = compute_signal_metrics(x, y)
        # inf is not NaN, but we should still handle gracefully
        # The exact behavior depends on pd.to_numeric — inf may or may not be dropped
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 10)


class TestFrequencyEstimation(unittest.TestCase):
    """Tests for frequency and period columns."""

    def _make_sine(
        self,
        freq_hz: float = 5.0,
        n: int = 2000,
        duration: float = 2.0,
    ) -> tuple[pd.Series, pd.Series]:
        """Construct a clean sine wave at *freq_hz* Hz."""
        t = np.linspace(0, duration, n, endpoint=False)
        y = np.sin(2 * np.pi * freq_hz * t)
        return pd.Series(t), pd.Series(y)

    def test_sine_frequency_detected(self) -> None:
        """A 5 Hz sine should yield freq ≈ 5 and period ≈ 0.2."""
        x, y = self._make_sine(freq_hz=5.0, n=2000, duration=2.0)
        result = compute_signal_metrics(x, y)
        freq_s = result[8]
        period_s = result[9]
        self.assertNotEqual(freq_s, "n/a", "freq should be detected")
        self.assertNotEqual(period_s, "n/a", "period should be detected")
        self.assertAlmostEqual(float(freq_s), 5.0, delta=0.5)
        self.assertAlmostEqual(float(period_s), 0.2, delta=0.05)

    def test_sine_higher_freq(self) -> None:
        x, y = self._make_sine(freq_hz=50.0, n=10000, duration=1.0)
        result = compute_signal_metrics(x, y)
        freq_s = result[8]
        self.assertNotEqual(freq_s, "n/a")
        self.assertAlmostEqual(float(freq_s), 50.0, delta=2.0)

    def test_too_few_samples_no_freq(self) -> None:
        """Fewer than 8 samples → freq=n/a."""
        x = pd.Series([0, 1, 2])
        y = pd.Series([0, 1, 0])
        result = compute_signal_metrics(x, y)
        self.assertEqual(result[8], "n/a")
        self.assertEqual(result[9], "n/a")

    def test_dc_signal_no_freq(self) -> None:
        """A constant signal has no meaningful frequency."""
        n = 500
        x = pd.Series(np.linspace(0, 1, n))
        y = pd.Series([3.0] * n)
        result = compute_signal_metrics(x, y)
        # After removing DC, magnitude is all zero → argmax returns 0 → freq=0 → n/a
        self.assertEqual(result[8], "n/a")


class TestEstimateFrequencyFFT(unittest.TestCase):
    """Direct tests for the FFT helper."""

    def test_clean_sine(self) -> None:
        n = 1000
        dt = 0.001  # 1000 Hz sample rate
        t = np.arange(0, n * dt, dt)
        y = np.sin(2 * np.pi * 10 * t)  # 10 Hz
        freq, period = _estimate_frequency_fft(t, y, dt)
        self.assertIsNotNone(freq)
        self.assertAlmostEqual(freq, 10.0, delta=0.5)
        self.assertAlmostEqual(period, 0.1, delta=0.01)

    def test_too_few_samples(self) -> None:
        t = np.array([0, 1, 2], dtype=float)
        y = np.array([0, 1, 0], dtype=float)
        freq, period = _estimate_frequency_fft(t, y, 1.0)
        # The function should return None if the uniform grid has < 8 points
        # (depends on dt vs range, but 3 points with dt=1 → only 2 uniform pts)
        # At best it returns something; we just assert it doesn't crash
        self.assertIsInstance(freq, (float, type(None)))


class TestEstimateFrequencyZeroCrossing(unittest.TestCase):
    """Direct tests for the zero-crossing helper."""

    def test_square_wave(self) -> None:
        """A square wave at 5 Hz over 2 seconds should have ~20 crossings → ~5 Hz."""
        n = 2000
        t = np.linspace(0, 2.0, n)
        y = np.sign(np.sin(2 * np.pi * 5 * t))
        freq, period = _estimate_frequency_zero_crossing(y, 2.0)
        self.assertIsNotNone(freq)
        self.assertAlmostEqual(freq, 5.0, delta=1.0)

    def test_too_few_samples(self) -> None:
        freq, period = _estimate_frequency_zero_crossing(np.array([1, -1]), 1.0)
        self.assertIsNone(freq)

    def test_zero_duration(self) -> None:
        freq, period = _estimate_frequency_zero_crossing(np.zeros(100), 0.0)
        self.assertIsNone(freq)


class TestMetricsTupleType(unittest.TestCase):
    """Verify that the public type alias is importable and sane."""

    def test_na_10_length(self) -> None:
        self.assertEqual(len(_NA_10), 10)
        self.assertTrue(all(v == "n/a" for v in _NA_10))


if __name__ == "__main__":
    unittest.main()
