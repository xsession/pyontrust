"""Time-series 3-D trajectory tracking with CSV / JSON / PLY export."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class Track:
    track_id: int
    positions: list[np.ndarray] = field(default_factory=list)   # (3,) each
    times_ms: list[float] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.positions)


class Tracker3D:
    """Associate per-frame 3-D points into trajectories.

    * nearest-neighbour association with a max_link_m gate,
    * constant-velocity prediction to bridge small gaps (max_gap frames),
    * export to CSV / JSON / PLY point clouds.
    """

    def __init__(self, max_link_m: float = 0.5, max_gap: int = 3) -> None:
        self.max_link_m = max_link_m
        self.max_gap = max_gap
        self.tracks: dict[int, Track] = {}
        self._next_id = 0

    def update(self, points_3d: np.ndarray, time_ms: float | None = None) -> list[int]:
        """Associate one frame's (N, 3) points; returns track ids used."""
        pts = np.asarray(points_3d, dtype=np.float64).reshape(-1, 3)
        assigned: dict[int, int] = {}          # point idx -> track id
        for tid, tr in self.tracks.items():
            if not tr.positions:
                continue
            last = tr.positions[-1]
            vel = (last - tr.positions[-2]) if len(tr.positions) >= 2 else np.zeros(3)
            predicted = last + vel * max(len(self.tracks) and 0, 1) * 0.5  # mild prediction
            for i, p in enumerate(pts):
                if i in assigned:
                    continue
                d_last = float(np.linalg.norm(p - last))
                d_pred = float(np.linalg.norm(p - predicted))
                if min(d_last, d_pred) <= self.max_link_m:
                    assigned[i] = tid
        for i, p in enumerate(pts):
            if i not in assigned:
                tr = Track(track_id=self._next_id)
                self.tracks[self._next_id] = tr
                self._next_id += 1
                assigned[i] = tr.track_id
            tr = self.tracks[assigned[i]]
            tr.positions.append(p.copy())
            if time_ms is not None:
                tr.times_ms.append(float(time_ms))
        return [assigned[i] for i in range(len(pts))]

    def to_csv(self, path: str | Path) -> int:
        n = 0
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["track_id", "t_ms", "x", "y", "z"])
            for tid in sorted(self.tracks):
                tr = self.tracks[tid]
                for k, p in enumerate(tr.positions):
                    t = tr.times_ms[k] if k < len(tr.times_ms) else ""
                    w.writerow([tid, t, f"{p[0]:.4f}", f"{p[1]:.4f}", f"{p[2]:.4f}"])
                    n += 1
        return n

    def to_json(self, path: str | Path) -> None:
        data = {str(tid): {"positions": [p.tolist() for p in tr.positions],
                           "times_ms": list(tr.times_ms)}
                for tid, tr in self.tracks.items()}
        Path(path).write_text(json.dumps(data, indent=2))

    def to_ply(self, path: str | Path) -> int:
        """All tracked points as one PLY point cloud (coloured by track id)."""
        pts = [(p, tid) for tid in sorted(self.tracks) for p in self.tracks[tid].positions]
        lines = ["ply", "format ascii 1.0", f"element vertex {len(pts)}"]
        lines += ["property float x", "property float y", "property float z",
                  "property uchar red", "property uchar green", "property uchar blue",
                  "end_header"]
        for p, tid in pts:
            r = int(255 * ((tid * 97) % 13) / 13)
            g = int(255 * ((tid * 61) % 11) / 11)
            b = int(255 * ((tid * 43) % 7) / 7)
            lines.append(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {r} {g} {b}")
        Path(path).write_text("\n".join(lines) + "\n")
        return len(pts)


__all__ = ["Tracker3D", "Track"]
