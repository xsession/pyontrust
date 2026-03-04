from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

from .acquisition import Frame


@dataclass(frozen=True)
class RecordingSpec:
    """Replay schema v1.

    Stored as NPZ with:
    - schema_version: int
    - sample_rate_hz: float
    - t0_s: float
    - ch0/ch1/...: float32 arrays
    """

    schema_version: int = 1


def write_npz(path: str, frame: Frame) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload: dict[str, object] = {
        "schema_version": np.asarray(1, dtype=np.int32),
        "sample_rate_hz": np.asarray(frame.sample_rate_hz, dtype=np.float64),
        "t0_s": np.asarray(frame.t0_s, dtype=np.float64),
    }
    for ch, arr in frame.channels.items():
        payload[f"ch{int(ch)}"] = np.asarray(arr, dtype=np.float32)
    np.savez(path, **payload)
    return path
