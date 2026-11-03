"""Timestamp matching across streams with drop-frame management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .frame_stream import Frame


@dataclass
class AlignedPair:
    left: Frame
    right: Frame
    delta_ms: float                 # |t_left - t_right|


class StreamSynchronizer:
    """Match frames from two (or more) streams by timestamp.

    * tolerance_ms — max allowed clock skew for a pair to be accepted;
      pairs beyond it are dropped (drop-frame management).
    * greedy nearest-neighbor matching in time order (streams are assumed
      roughly rate-matched, as they are when grabbed back-to-back over ADB).
    """

    def __init__(self, streams: Sequence[FrameStream], tolerance_ms: float = 250.0) -> None:
        if len(streams) < 2:
            raise ValueError("need at least two streams")
        self.streams = list(streams)
        self.tolerance_ms = tolerance_ms

    def grab_aligned(self, count: int = 1) -> list[AlignedPair]:
        """Grab ``count`` aligned pairs from all streams (2-stream case)."""
        left_frames = self.streams[0].grab_sequence(count * 2)[:count * 2]
        right_frames = self.streams[1].grab_sequence(count * 2)[:count * 2]
        return self.match(left_frames, right_frames, count)

    def match(self, left: Sequence[Frame], right: Sequence[Frame],
              max_pairs: int | None = None) -> list[AlignedPair]:
        pairs: list[AlignedPair] = []
        used_r: set[int] = set()
        for lf in left:
            best_i, best_dt = -1, float("inf")
            for i, rf in enumerate(right):
                if i in used_r:
                    continue
                dt = abs(lf.timestamp_ms - rf.timestamp_ms)
                if dt < best_dt:
                    best_i, best_dt = i, dt
            if best_i >= 0 and best_dt <= self.tolerance_ms:
                used_r.add(best_i)
                pairs.append(AlignedPair(left=lf, right=right[best_i], delta_ms=best_dt))
                if max_pairs is not None and len(pairs) >= max_pairs:
                    break
        return pairs


__all__ = ["StreamSynchronizer", "AlignedPair"]
