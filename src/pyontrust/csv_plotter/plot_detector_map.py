from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd


def parse_detector_signal_map(text: str | None) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parts = re.split(r"[\s,;|]+", raw)
    return [str(part).strip() for part in parts if str(part).strip()]


def detector_slot_positions(rows: int, cols: int, mapping: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    mode = str(mapping or "Row-major").strip().lower()
    rows = max(1, int(rows))
    cols = max(1, int(cols))
    if mode == "column-major":
        for c in range(cols):
            for r in range(rows):
                out.append((r, c))
        return out
    if mode == "serpentine rows":
        for r in range(rows):
            col_iter = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
            for c in col_iter:
                out.append((r, c))
        return out
    for r in range(rows):
        for c in range(cols):
            out.append((r, c))
    return out


def build_detector_label_grid(
    signal_names: list[str],
    *,
    rows: int,
    cols: int,
    mapping: str,
) -> list[list[str | None]]:
    grid: list[list[str | None]] = [[None for _ in range(max(1, int(cols)))] for _ in range(max(1, int(rows)))]
    for (r, c), name in zip(detector_slot_positions(rows, cols, mapping), signal_names):
        if 0 <= r < len(grid) and 0 <= c < len(grid[r]):
            grid[r][c] = str(name)
    return grid


def reduce_detector_series(series: pd.Series, reducer: str) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return math.nan
    mode = str(reducer or "Mean").strip().lower()
    if mode == "max":
        return float(numeric.max())
    if mode == "rms":
        arr = numeric.to_numpy(dtype=float)
        return float(np.sqrt(np.mean(np.square(arr)))) if arr.size else math.nan
    if mode == "sum":
        return float(numeric.sum())
    if mode == "last sample":
        return float(numeric.iloc[-1])
    return float(numeric.mean())


def compute_anger_centroids(
    values: np.ndarray,
    coords: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if values.ndim != 2 or coords.ndim != 2 or coords.shape[1] != 2:
        return np.array([], dtype=float), np.array([], dtype=float), np.array([], dtype=float)
    if values.shape[1] != coords.shape[0]:
        return np.array([], dtype=float), np.array([], dtype=float), np.array([], dtype=float)
    weights = np.clip(np.asarray(values, dtype=float), a_min=0.0, a_max=None)
    weights[~np.isfinite(weights)] = 0.0
    energy = weights.sum(axis=1)
    valid = energy > 0.0
    if not np.any(valid):
        return np.array([], dtype=float), np.array([], dtype=float), np.array([], dtype=float)
    valid_weights = weights[valid]
    valid_energy = energy[valid]
    x = (valid_weights @ coords[:, 1]) / valid_energy
    y = (valid_weights @ coords[:, 0]) / valid_energy
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float), np.asarray(valid_energy, dtype=float)