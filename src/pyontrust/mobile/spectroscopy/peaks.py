"""Peak and dip detection - port of Theremino ``MarkAllPeaks``.

A bin is a peak when it (a) beats both immediate neighbours, (b) exceeds
1% of the spectrum maximum (Theremino: ``v * 100 > MaxVisibleValue``), and
(c) dominates every sample within a +/-delta window. Dips use the same
local-minimum logic with a near-zero floor (absorption lines).
"""

from __future__ import annotations

import numpy as np


def find_peaks(samples, delta: int = 2) -> list[tuple[int, float]]:
    """Return ``(index, value)`` pairs for all peaks, sorted by index."""
    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    n = len(x)
    if n < 3:
        return []
    mx = float(x.max())
    out: list[tuple[int, float]] = []
    for i in range(1, n - 1):
        v = x[i]
        if v <= x[i - 1] or v <= x[i + 1]:
            continue
        if not (v * 100.0 > mx):          # prominence: > 1% of max
            continue
        lo, hi = max(0, i - delta), min(n - 1, i + delta)
        if np.all(x[lo:hi + 1] <= v):    # local dominance window
            out.append((i, float(v)))
    return out


def find_dips(samples, delta: int = 2) -> list[tuple[int, float]]:
    """Return ``(index, value)`` pairs for all dips (absorption lines)."""
    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    n = len(x)
    if n < 3:
        return []
    mx = float(x.max())
    out: list[tuple[int, float]] = []
    for i in range(1, n - 1):
        v = x[i]
        if v >= x[i - 1] or v >= x[i + 1]:
            continue
        if not (v * 1e7 > mx):           # Theremino floor: essentially any non-zero
            continue
        lo, hi = max(0, i - delta), min(n - 1, i + delta)
        if np.all(x[lo:hi + 1] >= v):    # local minimum window
            out.append((i, float(v)))
    return out


__all__ = ["find_peaks", "find_dips"]
