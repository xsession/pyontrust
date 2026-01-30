from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Dict, List, Tuple


Callback = Callable[[Any], None]


@dataclass
class _Sub:
    callback: Callback
    fps_limit: int
    last_ts: float = 0.0


class PubSub:
    def __init__(self) -> None:
        self._lock = Lock()
        self._subs: Dict[str, List[_Sub]] = {}

    def publish(self, topic: str, msg: Any) -> None:
        now = time.time()
        with self._lock:
            subs = list(self._subs.get(topic, []))
        for s in subs:
            min_dt = 1.0 / max(1, int(s.fps_limit))
            if now - s.last_ts < min_dt:
                continue
            s.last_ts = now
            try:
                s.callback(msg)
            except Exception:
                # subscriptions are best-effort
                continue

    def subscribe(self, topic: str, callback: Callback, *, fps_limit: int = 30) -> Callable[[], None]:
        sub = _Sub(callback=callback, fps_limit=fps_limit)
        with self._lock:
            self._subs.setdefault(topic, []).append(sub)

        def _unsub() -> None:
            with self._lock:
                if topic in self._subs and sub in self._subs[topic]:
                    self._subs[topic].remove(sub)

        return _unsub
