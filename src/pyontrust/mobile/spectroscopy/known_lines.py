"""Reference emission lines for wavelength calibration.

NIST-standard visible/near-IR lines of common discharge lamps - use these to
place calibration points on a raw spectrum (Theremino's manual calibration
workflow: identify a known line, click it, enter its nm value).
"""

from __future__ import annotations

import numpy as np

KNOWN_LINES_NM = {
    "mercury": [253.65, 296.73, 302.15, 313.16, 365.48, 404.66, 407.78,
                435.83, 491.60, 546.07, 576.96, 579.07],
    "argon":   [696.52, 706.70, 715.99, 723.38, 731.04, 738.36, 750.39,
                763.51, 772.38, 801.48, 811.53],
    "neon":    [585.25, 588.22, 607.43, 614.31, 621.70, 630.47, 638.29,
                640.78, 650.65, 653.46, 658.38, 667.82, 671.67, 692.90,
                703.24, 717.39, 724.49, 731.48, 743.89, 753.50],
    "sodium":  [588.99, 589.59],
    "helium":  [388.90, 447.15, 471.31, 492.19, 501.60, 587.56, 667.83, 706.52],
}


def nearest_line(nm: float, lamp: str = "mercury") -> tuple[float, float]:
    """Closest reference line to ``nm`` for the given lamp.

    Returns ``(line_nm, abs_distance_nm)``. Raises KeyError on unknown lamps.
    """
    if lamp not in KNOWN_LINES_NM:
        raise KeyError(f"unknown lamp {lamp!r} - choose from {sorted(KNOWN_LINES_NM)}")
    lines = np.asarray(KNOWN_LINES_NM[lamp], dtype=np.float64)
    i = int(np.argmin(np.abs(lines - float(nm))))
    return float(lines[i]), float(abs(lines[i] - nm))


__all__ = ["KNOWN_LINES_NM", "nearest_line"]
