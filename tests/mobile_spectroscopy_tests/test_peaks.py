"""Peak/dip detection (port of MarkAllPeaks)."""
import numpy as np
from mobile_spectroscopy import find_dips, find_peaks


def test_find_peaks_recovers_bumps():
    x = np.full(200, 5.0)
    for c, a in ((50, 900), (140, 700)):
        x += a * np.exp(-0.5 * ((np.arange(200) - c) / 3) ** 2)
    peaks = find_peaks(x, delta=3)
    assert [i for i, _ in peaks] == [50, 140]


def test_find_peaks_rejects_sub_prominence():
    x = np.full(200, 5.0)
    x += 900 * np.exp(-0.5 * ((np.arange(200) - 50) / 3) ** 2)
    x[100] += 1                                  # value 6 < max/100 -> rejected
    peaks = find_peaks(x, delta=3)
    assert [i for i, _ in peaks] == [50]


def test_find_dips_recovers_absorption_line():
    y = np.full(200, 500.0)
    seg = np.arange(90, 110)
    y[90:110] -= 200 * np.exp(-0.5 * ((seg - 100) / 3) ** 2)
    dips = find_dips(y, delta=4)
    assert any(abs(i - 100) <= 2 for i, _ in dips)


def test_empty_and_short_input():
    assert find_peaks([]) == []
    assert find_peaks([1.0, 2.0]) == []
    assert find_dips([3.0]) == []
