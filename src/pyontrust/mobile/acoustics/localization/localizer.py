"""3-D source localization from TDOA hyperbolas (least squares)."""

from __future__ import annotations

import numpy as np


class SourceLocalizer:
    """Solve for the emitter position given mic positions + pairwise TDOAs.

    Model:  c * tdoa[i][j] = |p - m_i| - |p - m_j|   (c = speed of sound).
    Linearised Gauss-Newton around an initial guess; converges in a few
    iterations for well-conditioned arrays (baseline >= ~0.3 x range).
    """

    def __init__(self, mic_positions: np.ndarray, c_sound: float = 343.0) -> None:
        self.mics = np.asarray(mic_positions, dtype=np.float64).reshape(-1, 3)
        if len(self.mics) < 2:
            raise ValueError("need at least two microphones")
        self.c = float(c_sound)

    def _residuals(self, p: np.ndarray, tdoa: np.ndarray) -> np.ndarray:
        d = np.linalg.norm(self.mics - p[None, :], axis=1)      # (M,)
        res = (d[:, None] - d[None, :]) / self.c                # (M,M) predicted TDOA
        return (res - tdoa).ravel()

    def localize(self, tdoa: np.ndarray, guess: np.ndarray | None = None,
                 max_iter: int = 60, tol: float = 1e-9) -> np.ndarray:
        """tdoa: (M,M) signed seconds → source position (3,) in metres.

        Capped-step Gauss-Newton with multi-start: TDOA least-squares has a
        shallow far-field valley that naive GN walks off into, so each start is
        limited to local steps and the best-residual solution wins.
        """
        m = len(self.mics)
        tdoa = np.asarray(tdoa, dtype=np.float64).reshape(m, m)

        centroid = self.mics.mean(axis=0)
        radius = float(np.max(np.linalg.norm(self.mics - centroid, axis=1))) or 1.0
        med_range = max(float(np.median(np.abs(tdoa))) * self.c, 0.25 * radius)
        max_step_m = max(4.0 * radius, 1.0)

        starts: list[np.ndarray] = []
        if guess is not None:
            starts.append(np.asarray(guess, dtype=np.float64).reshape(3))
        for s in (0.5, 1.0, 2.0):
            r_ = s * med_range + 0.5 * radius
            for axis in range(3):
                for sign in (+1, -1):
                    p0 = centroid.copy()
                    p0[axis] += sign * r_
                    starts.append(p0)
        starts.append(centroid + np.array([0.0, 0.0, med_range]))

        best_p, best_res = None, float("inf")
        for p in starts:
            p = self._refine(p, tdoa, max_iter, tol, max_step_m)
            res = float(np.linalg.norm(self._residuals(p, tdoa)))
            if np.all(np.isfinite(p)) and res < best_res:
                best_p, best_res = p, res
        return best_p

    def _refine(self, p: np.ndarray, tdoa: np.ndarray, max_iter: int,
                tol: float, max_step_m: float) -> np.ndarray:
        m = len(self.mics)
        for _ in range(max_iter):
            r = self._residuals(p, tdoa)
            J = np.zeros((m * m, 3))
            eps = 1e-7
            for k in range(3):
                pk = p.copy(); pk[k] += eps
                J[:, k] = (self._residuals(pk, tdoa) - r) / eps
            try:
                step, *_ = np.linalg.lstsq(J, -r, rcond=None)
            except np.linalg.LinAlgError:
                break
            # cap the step so we cannot jump into the far-field valley
            nrm = float(np.linalg.norm(step))
            if nrm > max_step_m:
                step = step * (max_step_m / nrm)
            lam = 1e-3
            while True:
                p_new = p + step / (1.0 + lam * np.linalg.norm(step) + 1e-12)
                if np.all(np.isfinite(p_new)) and np.linalg.norm(self._residuals(p_new, tdoa)) < np.linalg.norm(r):
                    break
                lam *= 5.0
                if lam > 1e6:
                    p_new = p
                    break
            moved = float(np.linalg.norm(p_new - p))
            if moved < tol * max(1.0, float(np.linalg.norm(p))):
                return p_new
            p = p_new
        return p

    def bearing(self, tdoa: np.ndarray, guess: np.ndarray | None = None) -> np.ndarray:
        """Unit direction from array centroid to the source (bearing-only use)."""
        p = self.localize(tdoa, guess=guess)
        v = p - self.mics.mean(axis=0)
        n = np.linalg.norm(v)
        return v / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])


__all__ = ["SourceLocalizer"]
