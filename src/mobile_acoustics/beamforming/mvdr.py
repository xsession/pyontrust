"""MVDR (Capon) adaptive beamforming - nGene-style adaptive power map.

Unlike delay-and-sum (equal weights), MVDR minimises total output power
subject to a unity-gain constraint in the candidate direction:

    w(p, f) = R(f)^-1 a / (a^H R^-1 a),      P(p) = 1 / (a^H R^-1 a)

where R is the cross-spectral matrix of the microphone array and
``a = exp(-j 2 pi f tau_m)`` the steering vector for candidate point p.
Off-axis interferers are nulled, so the MVDR peak is sharper than D&S - at
the cost of sensitivity to R-estimation error, mitigated here with diagonal
loading (R += delta * tr(R)/M * I). With a single-snapshot R the
matrix is rank-1, so the default delta=0.1 keeps off-axis power bounded
and grid peaks stable; lower values sharpen contrast at known points.

numpy-only; per-frequency-bin processing over a log-spaced band.
"""

from __future__ import annotations

import numpy as np


class MVDRBeamformer:
    """Steer an adaptive MVDR beam across the grid; peak cell = noise source."""

    def __init__(self, mic_positions, sample_rate: int = 48000,
                 freq_min: float = 300.0, freq_max: float = 6000.0,
                 n_fft: int = 2048, diag_load: float = 0.1, c: float = 343.0) -> None:
        self.mics = np.asarray(mic_positions, dtype=np.float64).reshape(-1, 3)
        if len(self.mics) < 2:
            raise ValueError("need at least two microphones")
        self.fs = int(sample_rate)
        self.c = float(c)
        self.freq_min = float(freq_min)
        self.freq_max = float(freq_max)
        self.n_fft = int(n_fft)
        self.diag_load = float(diag_load)

    def power_map(self, waveforms, grid) -> np.ndarray:
        """Coherent MVDR power at every grid point (averaged over the band)."""
        n = min(len(w) for w in waveforms)
        wfs = [np.asarray(w, dtype=np.float64)[:n] for w in waveforms]
        win = np.hanning(n)
        X = np.array([np.fft.rfft(w * win, self.n_fft) for w in wfs])  # (M, K)

        allf = np.fft.rfftfreq(self.n_fft, 1.0 / self.fs)
        kmin = int(np.searchsorted(allf, self.freq_min))
        kmax = int(np.searchsorted(allf, self.freq_max, side="right")) - 1
        if kmax <= kmin:
            raise ValueError("frequency band empty - widen freq_min/freq_max")
        fb = allf[kmin:kmax + 1]
        Xb = X[:, kmin:kmax + 1]

        m = len(wfs)
        ident = np.eye(m)
        g = len(grid.points)
        pts = grid.points
        tau = np.linalg.norm(pts[:, None, :] - self.mics[None, :, :], axis=2) / self.c  # (G,M)

        powers = np.zeros(g)
        for k in range(Xb.shape[1]):
            xk = Xb[:, k]
            r = np.outer(xk, xk.conj()) / m                       # (M,M) cross-spectral
            r += self.diag_load * float(np.trace(r).real) / m * ident
            rinv = np.linalg.inv(r)                                # M is tiny; inv is cheap
            a = np.exp(-2j * np.pi * fb[k] * tau)                  # (G,M) steering matrix
            denom = np.einsum("gm,mn,gn->g", a, rinv, a.conj()).real  # a^H R^-1 a per point
            with np.errstate(divide="ignore"):
                powers += np.where(denom > 0.0, 1.0 / np.maximum(denom, 1e-30), 0.0)
        return powers / Xb.shape[1]

    def localize(self, waveforms, grid) -> np.ndarray:
        """Grid point of maximum MVDR power - estimated source position."""
        pmap = self.power_map(waveforms, grid)
        best = int(np.argmax(pmap))
        return grid.points[best].copy()


__all__ = ["MVDRBeamformer"]
