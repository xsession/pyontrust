"""In-process event bus for real-time multi-channel logging.

Provides typed publish/subscribe channels with thread-safe ring buffers.
All instruments publish to typed channels on a shared bus, enabling
timeline correlation across power, CAN, RF, and video streams.
"""

from __future__ import annotations

import collections
import datetime
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class TimestampedEvent:
    """Base for all events on the bus."""

    t_s: float  # Monotonic seconds since test start
    wall_time: str  # ISO 8601 wall clock
    source: str  # Instrument name

    @staticmethod
    def now_wall() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class PowerEvent(TimestampedEvent):
    """Power measurement event."""

    current_a: float = 0.0
    voltage_v: float = 0.0


@dataclass(frozen=True)
class CanFrameEvent(TimestampedEvent):
    """CAN bus frame event."""

    arbitration_id: int = 0
    data: bytes = b""
    is_extended: bool = False


@dataclass(frozen=True)
class RfSampleEvent(TimestampedEvent):
    """RF IQ sample chunk event."""

    center_freq_hz: float = 0.0
    sample_rate_hz: float = 0.0
    peak_dbm: float = 0.0
    # iq: np.ndarray intentionally omitted from base — use analysis layer


@dataclass(frozen=True)
class VisionEvent(TimestampedEvent):
    """Vision / camera event."""

    frame_path: str = ""
    detections: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AOIEvent(TimestampedEvent):
    """AOI inspection event — published when a board is inspected."""

    board_id: str = ""
    verdict: str = ""  # AOIVerdict.value
    defect_count: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThermalEvent(TimestampedEvent):
    """Thermal snapshot event — published on each thermal frame capture.

    Carries per-zone temperatures and the verdict so that downstream
    subscribers (event bus, gateway SSE, CSV logger) can react to
    thermal anomalies in real-time.
    """

    frame_index: int = 0
    global_max_c: float = 0.0
    global_mean_c: float = 0.0
    verdict: str = ""  # ThermalVerdict.value
    hotspot_x: int = 0
    hotspot_y: int = 0
    zone_readings: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class MarkerEvent(TimestampedEvent):
    """General-purpose marker event (step transitions, user annotations)."""

    label: str = ""
    fields: dict[str, Any] = field(default_factory=dict)


class Channel:
    """Thread-safe typed publish/subscribe channel with ring buffer."""

    def __init__(self, name: str, event_type: type, maxlen: int = 100_000) -> None:
        self.name = name
        self.event_type = event_type
        self._subscribers: list[Callable[[Any], None]] = []
        self._buffer: collections.deque[Any] = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def publish(self, event: Any) -> None:
        """Publish an event to all subscribers and buffer it."""
        with self._lock:
            self._buffer.append(event)
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception:
                pass  # subscriber errors must not break publishers

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for new events on this channel."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Any], None]) -> None:
        """Remove a subscriber callback."""
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def recent(self, n: int = 1000) -> list[Any]:
        """Return the most recent n events from the buffer."""
        with self._lock:
            return list(self._buffer)[-n:]

    @property
    def count(self) -> int:
        """Total events published to this channel."""
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        """Clear the ring buffer."""
        with self._lock:
            self._buffer.clear()


class EventBus:
    """Central event bus managing typed channels.

    Usage::

        bus = EventBus()
        power_ch = bus.create_channel("power", PowerEvent)
        power_ch.subscribe(lambda e: print(e))
        power_ch.publish(PowerEvent(t_s=0.1, wall_time="...", source="ad3", current_a=0.001, voltage_v=3.3))
    """

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}
        self._lock = threading.Lock()

    def create_channel(self, name: str, event_type: type, maxlen: int = 100_000) -> Channel:
        """Create a new named channel. Raises if name already exists."""
        with self._lock:
            if name in self._channels:
                raise ValueError(f"Channel '{name}' already exists")
            ch = Channel(name, event_type, maxlen=maxlen)
            self._channels[name] = ch
            return ch

    def get_channel(self, name: str) -> Channel | None:
        """Get an existing channel by name, or None."""
        return self._channels.get(name)

    def get_or_create_channel(self, name: str, event_type: type, maxlen: int = 100_000) -> Channel:
        """Get an existing channel or create a new one."""
        with self._lock:
            if name in self._channels:
                return self._channels[name]
            ch = Channel(name, event_type, maxlen=maxlen)
            self._channels[name] = ch
            return ch

    def all_channels(self) -> dict[str, Channel]:
        """Return a snapshot of all channels."""
        return dict(self._channels)

    def clear_all(self) -> None:
        """Clear all channel buffers."""
        for ch in self._channels.values():
            ch.clear()

    def remove_channel(self, name: str) -> None:
        """Remove a channel by name."""
        with self._lock:
            self._channels.pop(name, None)
