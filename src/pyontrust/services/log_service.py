"""Multi-channel event-bus manager service.

Provides a singleton :class:`LogService` that owns the
:class:`~pyontrust.core.events.EventBus` and offers convenience methods
for the gateway (recent events, subscribe, channel listing).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from pyontrust.core.events import (
    CanFrameEvent,
    Channel,
    EventBus,
    MarkerEvent,
    PowerEvent,
    RfSampleEvent,
    TimestampedEvent,
    VisionEvent,
)

logger = logging.getLogger("pyontrust.services.log_service")

# Default channel definitions (name → event type)
_DEFAULT_CHANNELS: dict[str, type[TimestampedEvent]] = {
    "power": PowerEvent,
    "can": CanFrameEvent,
    "rf": RfSampleEvent,
    "video": VisionEvent,
    "marker": MarkerEvent,
}


class LogService:
    """Owns the EventBus and provides a gateway-friendly façade.

    Typical usage::

        log = LogService()
        log.ensure_channels()           # create default channels
        log.publish("power", event)     # publish to a channel
        recent = log.recent("power")    # get last N events
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or EventBus()

    @property
    def bus(self) -> EventBus:
        return self._bus

    # ── Channel management ──────────────────────────────────────────

    def ensure_channels(self) -> None:
        """Create all default channels if they don't already exist."""
        for name, etype in _DEFAULT_CHANNELS.items():
            if self._bus.get_channel(name) is None:
                self._bus.create_channel(name, etype)
                logger.debug("Created channel %r (%s)", name, etype.__name__)

    def create_channel(
        self, name: str, event_type: type[TimestampedEvent] | None = None,
    ) -> Channel:
        """Create or return an existing channel."""
        existing = self._bus.get_channel(name)
        if existing is not None:
            return existing
        etype = event_type or TimestampedEvent
        return self._bus.create_channel(name, etype)

    def list_channels(self) -> list[dict[str, Any]]:
        """Return metadata for all channels."""
        result: list[dict[str, Any]] = []
        for name, ch in self._bus.all_channels().items():
            result.append({
                "name": name,
                "event_type": ch.event_type.__name__,
                "buffer_size": len(ch._buffer),
                "subscribers": len(ch._subscribers),
            })
        return result

    # ── Publish / Subscribe ─────────────────────────────────────────

    def publish(self, channel_name: str, event: TimestampedEvent) -> None:
        """Publish an event to a named channel."""
        ch = self._bus.get_channel(channel_name)
        if ch is None:
            logger.warning("Channel %r does not exist — event dropped", channel_name)
            return
        ch.publish(event)

    def subscribe(self, channel_name: str, callback: Callable) -> bool:
        """Subscribe to a named channel.  Returns False if not found."""
        ch = self._bus.get_channel(channel_name)
        if ch is None:
            return False
        ch.subscribe(callback)
        return True

    def recent(
        self, channel_name: str, n: int = 1000
    ) -> list[TimestampedEvent]:
        """Return the *n* most recent events from a channel."""
        ch = self._bus.get_channel(channel_name)
        if ch is None:
            return []
        return ch.recent(n)

    def recent_as_dicts(
        self, channel_name: str, n: int = 1000
    ) -> list[dict[str, Any]]:
        """Return recent events serialised to JSON-safe dicts."""
        events = self.recent(channel_name, n)
        out: list[dict[str, Any]] = []
        for ev in events:
            d: dict[str, Any] = {"ch": channel_name}
            # Serialize dataclass fields
            if hasattr(ev, "__dataclass_fields__"):
                for fname in ev.__dataclass_fields__:
                    val = getattr(ev, fname)
                    # Skip large binary/numpy fields
                    if isinstance(val, (bytes, memoryview)):
                        d[fname] = f"<{len(val)} bytes>"
                    elif hasattr(val, "shape"):
                        d[fname] = f"<array {val.shape}>"
                    else:
                        d[fname] = val
            out.append(d)
        return out
