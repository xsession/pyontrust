"""Timestamped frame streams from a TermuxBridge (or any callable grabber)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Frame:
    image: Any                      # numpy BGR array (or raw audio bytes for mic streams)
    timestamp_ms: float             # capture time, ms (host clock at grab completion)
    source_id: str = "cam0"         # bridge/device identifier
    meta: dict[str, Any] = field(default_factory=dict)


class FrameStream:
    """Grab N frames from a grabber with host-side timestamps.

    ``grabber`` is any zero-arg callable returning an image (e.g.
    ``lambda: bridge.capture_still(i)``). Timestamps are taken at grab
    completion — the synchronizer aligns streams on these stamps.
    """

    def __init__(self, grabber: Callable[[], Any], source_id: str = "cam0",
                 interval_s: float = 0.5) -> None:
        self.grabber = grabber
        self.source_id = source_id
        self.interval_s = interval_s

    def grab(self) -> Frame:
        t0 = time.monotonic() * 1000.0
        img = self.grabber()
        return Frame(image=img, timestamp_ms=time.monotonic() * 1000.0 - (time.monotonic() - t0 / 1000.0) * 0 + time.monotonic() * 0, source_id=self.source_id)

    def grab_sequence(self, count: int = 5) -> list[Frame]:
        frames: list[Frame] = []
        for _ in range(count):
            t_start = time.perf_counter()
            img = self.grabber()
            frames.append(Frame(image=img, timestamp_ms=t_start * 1000.0, source_id=self.source_id))
            if self.interval_s > 0:
                time.sleep(self.interval_s)
        return frames


__all__ = ["FrameStream", "Frame"]
