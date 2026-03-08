"""WebSocket relay — fans EventBus channels out to browser clients.

Uses ``flask-sock`` (or Server-Sent Events fallback) to push real-time
events from the :class:`~pyontrust.core.events.EventBus` to connected
dashboard clients.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any

logger = logging.getLogger("pyontrust.gateway.ws")


def register_websocket(app: Any) -> None:
    """Attach WebSocket routes to the Flask app (requires flask-sock).

    If ``flask-sock`` is not installed, registers an SSE fallback at
    ``/api/events/stream``.
    """
    try:
        from flask_sock import Sock
        sock = Sock(app)
        _register_ws_routes(app, sock)
        logger.info("WebSocket relay enabled (flask-sock)")
    except ImportError:
        logger.info("flask-sock not installed — using SSE fallback")
        _register_sse_fallback(app)


def _register_ws_routes(app: Any, sock: Any) -> None:
    """Register ``/ws/events`` for full-duplex event streaming."""

    @sock.route("/ws/events")
    def ws_events(ws: Any) -> None:
        """Stream all EventBus channels to the WebSocket client."""
        log_svc = app.extensions.get("log_service")
        if log_svc is None:
            ws.close(reason="Log service not available")
            return

        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=5000)
        subscribed_channels: list[str] = []

        def _on_event(event: Any, ch_name: str = "") -> None:
            d: dict[str, Any] = {"ch": ch_name}
            if hasattr(event, "__dataclass_fields__"):
                for fname in event.__dataclass_fields__:
                    val = getattr(event, fname)
                    if isinstance(val, (bytes, memoryview)):
                        d[fname] = f"<{len(val)} bytes>"
                    elif hasattr(val, "shape"):
                        d[fname] = f"<array {val.shape}>"
                    else:
                        d[fname] = val
            try:
                q.put_nowait(d)
            except queue.Full:
                pass  # Drop oldest on overflow

        # Subscribe to all channels
        for name, ch in log_svc.bus.all_channels().items():
            cb = lambda ev, _name=name: _on_event(ev, ch_name=_name)
            ch.subscribe(cb)
            subscribed_channels.append(name)

        try:
            # Send initial handshake
            ws.send(json.dumps({
                "type": "hello",
                "channels": subscribed_channels,
            }))

            while True:
                try:
                    msg = q.get(timeout=0.5)
                    ws.send(json.dumps(msg, default=str))
                except queue.Empty:
                    # Send keepalive
                    ws.send(json.dumps({"type": "ping", "t": time.time()}))
                except Exception:
                    break
        except Exception:
            pass  # Client disconnected


def _register_sse_fallback(app: Any) -> None:
    """Register ``/api/events/stream`` as a Server-Sent Events endpoint."""
    from flask import Response, stream_with_context

    @app.route("/api/events/stream")
    def sse_stream() -> Response:
        log_svc = app.extensions.get("log_service")
        if log_svc is None:
            return Response("Log service not available", status=503)

        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=5000)

        def _on_event(event: Any, ch_name: str = "") -> None:
            d: dict[str, Any] = {"ch": ch_name}
            if hasattr(event, "__dataclass_fields__"):
                for fname in event.__dataclass_fields__:
                    val = getattr(event, fname)
                    if isinstance(val, (bytes, memoryview)):
                        continue
                    elif hasattr(val, "shape"):
                        continue
                    else:
                        d[fname] = val
            try:
                q.put_nowait(d)
            except queue.Full:
                pass

        for name, ch in log_svc.bus.all_channels().items():
            cb = lambda ev, _name=name: _on_event(ev, ch_name=_name)
            ch.subscribe(cb)

        def generate():
            while True:
                try:
                    msg = q.get(timeout=1.0)
                    yield f"data: {json.dumps(msg, default=str)}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'ping', 't': time.time()})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
