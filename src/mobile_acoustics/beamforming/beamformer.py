"""Delay-and-sum beamforming over a spatial grid (nGene-style power map)."""

from __future__ import annotations

import numpy as np


class AcousticGrid:
    """Rectangular 3-D search grid in metres."""

    def __init__(self, x_range: tuple[float, float] = (-2.0, 2.0),
                 y_range: tuple[float, float] = (-2.0, 2.0),
                 z_range: tuple[float, float] = (0.5, 3.0),
                 n_per_axis: int = 16) -> None:
        xs = np.linspace(*x_range, n_per_axis)
        ys = np.linspace(*y_range, n_per_axis)
        zs = np.linspace(*z_range, max(2, n_per_axis // 2))
        self.points = np.array([(x, y, z) for x in xs for y in ys for z in zs])


class DelayAndSumBeamformer:
    """Steer a delay-and-sum beam across the grid; peak cell ≈ noise source.

    For each candidate point p and mic m we apply delay tau_m = |p - m| / c,
    sum the (windowed) waveforms coherently, and record |sum|^2 as acoustic
    power at p. The grid point with maximum power is the estimate.
    """

    def __init__(self, mic_positions: np.ndarray, sample_rate: int = 48000,
                 c_sound: float = 343.0) -> None:
        self.mics = np.asarray(mic_positions, dtype=np.float64).reshape(-1, 3)
        if len(self.mics) < 2:
            raise ValueError("need at least two microphones for beamforming")
        self.fs = int(sample_rate)
        self.c = float(c_sound)

    def power_map(self, waveforms: Sequence[np.ndarray], grid: AcousticGrid) -> np.ndarray:
        """(G,) coherent power at each grid point (normalised by mic count)."""
        wfs = [np.asarray(w, dtype=np.float64).reshape(-1) for w in waveforms]
        n = min(len(w) for w in wfs)
        wfs = [w[:n] for w in wfs]
        win = np.hanning(n)

        powers = np.zeros(len(grid.points))
        for gi, p in enumerate(grid.points):
            acc = np.zeros(n)
            for m_idx, mic in enumerate(self.mics):
                tau_s = float(np.linalg.norm(p - mic)) / self.c
                lag = int(round(tau_s * self.fs))
                w = wfs[m_idx]
                if lag >= n:
                    acc += np.zeros(n)          # point behind/beyond this mic's record — skip coherently
                    continue
                delayed = np.roll(w, -lag)      # align arrival to t=0 at candidate p
                acc += delayed * win
            powers[gi] = float(np.sum(acc ** 2)) / (len(self.mics) ** 2)
        return powers

    def localize(self, waveforms: Sequence[np.ndarray], grid: AcousticGrid) -> np.ndarray:
        """Grid point of maximum coherent power → estimated source position."""
        pmap = self.power_map(waveforms, grid)
        best = int(np.argmax(pmap))
        return grid.points[best].copy()


from typing import Sequence

__all__ = ["DelayAndSumBeamformer", "AcousticGrid"]
