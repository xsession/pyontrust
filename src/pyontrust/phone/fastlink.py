"""FastLink — low-latency client for the on-device FastTelemetryService.

Instead of one ``adb shell`` round-trip per measurement (tens of ms each),
the app streams samples over a single TCP connection (via ``adb forward``)
with on-device batching and nanoTime timestamps:

    from pyontrust.phone.fastlink import FastLink
    with FastLink(serial="ABC123") as link:
        link.start(streams=("sensors", "touch"))
        for sample in link.iter_samples(timeout_s=0.5):
            ...          # {t_ns, stream, type?, x, y, z} / touch rows
        data = link.collect(duration_s=2.0)   # ring-buffer snapshot

Commands: start/stop/vibrate/tone/record/status — all newline-delimited JSON.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from typing import Any, Iterator, Sequence

DEFAULT_PORT = 4780


class FastLinkError(RuntimeError):
    """Connection or protocol error talking to the telemetry service."""


class FastLink:
    """TCP client for FastTelemetryService (newline-delimited JSON)."""

    def __init__(
        self,
        serial: str | None = None,
        port: int = DEFAULT_PORT,
        adb_path: str | None = None,
        forward: bool = True,
        host: str = "127.0.0.1",
    ) -> None:
        self.serial = serial
        self.port = int(port)
        self.adb_path = adb_path or os.environ.get("ADB_PATH", "adb")
        self.forward = forward          # False in tests (fake server on localhost)
        self.host = host
        self._sock: socket.socket | None = None
        self._buf = b""
        self._pending: list[dict[str, Any]] = []  # data frames seen while waiting for acks

    # ── connection lifecycle ────────────────────────────────────────────
    def connect(self, timeout_s: float = 5.0) -> "FastLink":
        if self.forward:
            adb = [self.adb_path] + (["-s", self.serial] if self.serial else [])
            r = subprocess.run(adb + ["forward", f"tcp:{self.port}", f"tcp:{self.port}"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                raise FastLinkError(f"adb forward failed: {r.stderr.strip()}")
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=timeout_s)
        except OSError as exc:
            raise FastLinkError(
                f"cannot reach telemetry service on {self.host}:{self.port} "
                "(is FastTelemetryService running? am start-foreground-service ...)"
            ) from exc
        self._sock.settimeout(None)  # reads use select() with explicit timeouts
        return self

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        if self.forward and self.serial is not None or (self.forward and self.serial is None):
            pass  # forward rules are per-device; remove only what we added below

    def __enter__(self) -> "FastLink":
        return self.connect()

    def __exit__(self, *exc: Any) -> None:
        self.close()


    # ── low-level protocol ──────────────────────────────────────────────
    def _send(self, payload: dict[str, Any]) -> None:
        if self._sock is None:
            raise FastLinkError("not connected")
        data = (json.dumps(payload) + "\n").encode()
        self._sock.sendall(data)

    def read_frames(self, timeout_s: float = 1.0) -> list[dict[str, Any]]:
        """Read all complete JSON frames available within ``timeout_s``."""
        import select

        if self._sock is None:
            raise FastLinkError("not connected")
        frames: list[dict[str, Any]] = []
        if self._pending:
            frames.extend(self._pending)
            self._pending.clear()
        deadline = timeout_s
        while True:
            r, _, _ = select.select([self._sock], [], [], max(deadline, 0.0))
            if not r:
                break
            chunk = self._sock.recv(65536)
            if not chunk:
                raise FastLinkError("connection closed by device")
            self._buf += chunk
            deadline -= 0.02  # small budget per recv round; keeps latency low
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    frames.append(json.loads(line))
                except json.JSONDecodeError:
                    raise FastLinkError(f"bad frame from device: {line[:80]!r}")
        return frames

    def _command(self, cmd: str, **kw: Any) -> dict[str, Any]:
        """Send a command and wait for its ack (bounded)."""
        self._send({"cmd": cmd, **kw})
        deadline = 5.0
        import time as _time

        while True:
            frames = self.read_frames(timeout_s=min(0.25, max(deadline, 0.01)))
            kept: list[dict[str, Any]] = []
            for f in frames:
                if f.get("type") == "ack":
                    self._pending.extend(kept)  # data frames that arrived with the ack
                    return f
                kept.append(f)
            self._pending.extend(kept)
            deadline -= 0.25
            if deadline <= 0:
                raise FastLinkError(f"no ack for {cmd!r} within 5 s")

    # ── command API ─────────────────────────────────────────────────────
    def start(self, streams: Sequence[str] = ("sensors", "touch"), rate_hz: int = 500) -> dict[str, Any]:
        return self._command("start", streams=list(streams), rate_hz=int(rate_hz))

    def stop(self) -> dict[str, Any]:
        return self._command("stop")

    def vibrate(self, ms: int = 300) -> dict[str, Any]:
        return self._command("vibrate", ms=int(ms))

    def tone(self, freq_hz: float = 1000.0, ms: int = 400) -> None:
        """Trigger a speaker tone (fire-and-forget; used for sonar/auditory tests)."""
        self._send({"cmd": "tone", "freq": float(freq_hz), "ms": int(ms)})

    def record(self, ms: int = 2000) -> dict[str, Any]:
        """Record ``ms`` of mic audio to a WAV file on the device; ack carries the path."""
        return self._command("record", ms=int(ms))

    def status(self) -> dict[str, Any]:
        return self._command("status")

    # ── sample iteration / collection ───────────────────────────────────
    @staticmethod
    def _flatten(frame: dict[str, Any]) -> list[dict[str, Any]]:
        if frame.get("type") != "batch":
            return [frame]  # events/acks pass through as-is
        stream = frame.get("stream", "")
        out: list[dict[str, Any]] = []
        for row in frame.get("samples", []):
            d: dict[str, Any] = {"t_ns": int(row[0]), "stream": stream}
            if stream == "sensors" and len(row) >= 5:
                d.update(type=int(row[1]), x=row[2] / 1e6, y=row[3] / 1e6, z=row[4] / 1e6)
            elif stream == "touch" and len(row) >= 5:
                d.update(action=int(row[1]), x=row[2], y=row[3], pressure=row[4])
            elif stream == "audio" and len(row) >= 3:
                d.update(t_ms=int(row[0]), rms=row[1] / 1e4, peak=row[2] / 1e4)
            out.append(d)
        return out

    def iter_samples(self, timeout_s: float = 0.5) -> Iterator[dict[str, Any]]:
        """Yield flattened samples/events until no data arrives within ``timeout_s``."""
        for frame in self.read_frames(timeout_s=timeout_s):
            yield from self._flatten(frame)

    def collect(self, duration_s: float = 2.0) -> dict[str, Any]:
        """Collect a fixed window of telemetry into per-stream lists (for analysis)."""
        import time as _time

        out: dict[str, list[dict[str, Any]]] = {"sensors": [], "touch": [], "audio": [], "events": []}
        t0 = _time.monotonic()
        while _time.monotonic() - t0 < duration_s:
            for s in self.iter_samples(timeout_s=0.1):
                if s.get("type") == "event" or ("kind" in s and "stream" not in s):
                    out["events"].append(s)
                elif "stream" in s:
                    out.setdefault(s["stream"], []).append(s)
        return out


__all__ = ["FastLink", "FastLinkError", "DEFAULT_PORT"]

