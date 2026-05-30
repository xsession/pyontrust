from __future__ import annotations

import pandas as pd


def build_barriers_for_x(
    x: pd.Series,
    *,
    target: float,
    limit_in: float,
    limit_out: float,
    start_idx: int,
    end_idx: int,
):
    """Return absolute/relative barrier arrays for the provided 1-based X."""
    try:
        import numpy as np

        idx = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
        lo = int(min(start_idx, end_idx))
        hi = int(max(start_idx, end_idx))
        lim = np.where((idx >= float(lo)) & (idx <= float(hi)), float(limit_in), float(limit_out))
        rmin = float(target) - lim / 2.0
        rmax = float(target) + lim / 2.0
        dmax = lim
        return rmin, rmax, dmax
    except Exception:
        return None, None, None