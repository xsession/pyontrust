"""Wavelength calibration - port of Theremino Spectrometer V5.0 (Module_Calibrations.vb).

The instrument is calibrated with a small set of (bin, nm) pairs taken from
known emission lines (see :mod:`mobile_spectroscopy.known_lines`). The bin<->nm
mapping is piecewise-linear between the calibration points and clamped outside
them - exactly what Theremino's ``Interpolate``/``Calib_NmToBin`` do.
"""

from __future__ import annotations

import numpy as np


def interpolate(x: np.ndarray, y: np.ndarray, xvalue: float) -> float:
    """Piecewise-linear interpolation of y at xvalue over sorted x (clamped).

    Mirrors Theremino's ``Interpolate(x(), y(), xvalue)``.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) != len(y):
        raise ValueError("x and y must have the same length")
    if len(x) == 0:
        raise ValueError("empty calibration table")
    if len(x) == 1 or xvalue <= x[0]:
        return float(y[0])
    if xvalue >= x[-1]:
        return float(y[-1])
    i = int(np.searchsorted(x, xvalue))          # first index with x[i] > xvalue
    x0, x1 = x[i - 1], x[i]
    t = (xvalue - x0) / (x1 - x0) if x1 != x0 else 0.0
    return float(y[i - 1] + t * (y[i] - y[i - 1]))


class WavelengthCalibration:
    """Sorted (bin, nm) calibration points with linear interpolation both ways."""

    def __init__(self, bins=None, nms=None) -> None:
        if bins is None or nms is None:
            raise ValueError("provide both bins and nms arrays")
        self._bins = np.asarray(bins, dtype=np.float64).reshape(-1)
        self._nms = np.asarray(nms, dtype=np.float64).reshape(-1)
        self._validate()

    def _validate(self) -> None:
        if len(self._bins) != len(self._nms):
            raise ValueError("bins and nms must have the same length")
        if len(self._bins) < 2:
            raise ValueError("need at least two calibration points")
        if np.any(np.diff(self._bins) <= 0):
            raise ValueError("bins must be strictly increasing")

    # -- properties ---------------------------------------------------------
    @property
    def bins(self) -> np.ndarray:
        return self._bins.copy()

    @property
    def nms(self) -> np.ndarray:
        return self._nms.copy()

    # -- mapping ------------------------------------------------------------
    def nm_to_bin(self, nm: float) -> float:
        """Wavelength (nm) -> raw sensor bin index (fractional)."""
        return interpolate(self._nms, self._bins, float(nm))

    def bin_to_nm(self, bin_: float) -> float:
        """Raw sensor bin index (fractional) -> wavelength (nm)."""
        return interpolate(self._bins, self._nms, float(bin_))

    def nm_to_bin_vec(self, nms) -> np.ndarray:
        """Vectorised nm -> bin mapping (clamped piecewise-linear).

        Handles non-monotonic wavelength tables by sorting the pairs first.
        """
        v = np.asarray(nms, dtype=np.float64)
        order = np.argsort(self._nms, kind="stable")
        xs, ys = self._nms[order], self._bins[order]
        return np.interp(v, xs, ys)

    def bin_to_nm_vec(self, bins) -> np.ndarray:
        """Vectorised bin -> nm mapping (clamped piecewise-linear)."""
        b = np.asarray(bins, dtype=np.float64)
        return np.interp(b, self._bins, self._nms)

    # -- editing (Theremino AddTrimmingPoint / RemoveTrimmingPoint) ---------
    def add_point(self, bin_: float, nm: float) -> None:
        """Insert a calibration point, keeping bins sorted."""
        b = np.append(self._bins, float(bin_))
        n = np.append(self._nms, float(nm))
        order = np.argsort(b, kind="stable")
        self._bins, self._nms = b[order], n[order]
        # duplicate bins are not allowed - collapse by keeping the last one
        keep = np.concatenate([[True], np.diff(self._bins) > 0])
        if not keep.all():
            self._bins, self._nms = self._bins[keep], self._nms[keep]
        self._validate()

    def remove_point(self, i: int) -> None:
        """Remove calibration point at index ``i`` (needs >= 3 points)."""
        if len(self._bins) < 3:
            raise ValueError("cannot remove - need at least three points")
        self._bins = np.delete(self._bins, i)
        self._nms = np.delete(self._nms, i)

    # -- persistence (Theremino ArrayToString / ArrayFromString) ------------
    def to_string(self) -> str:
        """``"nm1|nm2|..."`` plus bins - two pipe-separated lists."""
        return "|".join(f"{v:.6g}" for v in self._nms) + ";" + \
               "|".join(f"{v:.6g}" for v in self._bins)

    @classmethod
    def from_string(cls, s: str) -> "WavelengthCalibration":
        nms_s, bins_s = s.split(";", 1)
        return cls(bins=[float(v) for v in bins_s.split("|")],
                   nms=[float(v) for v in nms_s.split("|")])


__all__ = ["interpolate", "WavelengthCalibration"]
