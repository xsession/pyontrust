"""Tests for pyontrust.phone.fastlink against a fake on-device telemetry server."""
from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from pyontrust.phone.fastlink import FastLink, FastLinkError


class FakeAppServer:
    """Emulates FastTelemetryService: acks commands, pushes batch/event frames."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.commands: list[dict] = []
        self.client = None
        self._stop = threading.Event()

    def start(self) -> "FakeAppServer":
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()
        return self

    def _serve(self) -> None:
        self.sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.client = conn
            f = conn.makefile("rb")
            for line in iter(f.readline, b""):
                if not line.strip():
                    continue
                cmd = json.loads(line)
                self.commands.append(cmd)
                reply = {"type": "ack", "ok": True}
                if cmd.get("cmd") == "start":
                    reply["msg"] = f"started: {','.join(cmd.get('streams', []))}"
                    self._push_stream_data()
                elif cmd.get("cmd") == "status":
                    reply.update({"port": self.port, "streams": ["sensors"], "client_connected": True})
                elif cmd.get("cmd") == "record":
                    reply["msg"] = "/sdcard/Android/data/com.pyontrust.android/files/rec_test.wav"
                conn.sendall((json.dumps(reply) + "\n").encode())

    def _push_stream_data(self) -> None:
        assert self.client is not None
        sensor_batch = {
            "type": "batch", "stream": "sensors", "n": 2,
            "samples": [[1000, 1, 9_810_000, -2_048_000, 0], [2000, 5, 512_000_000, 0, 0]],
        }
        touch_event = {"type": "event", "kind": "touch_down", "t_ns": 3000, "x": 120.5, "y": 86.0}
        audio_batch = {
            "type": "batch", "stream": "audio", "n": 1,
            "samples": [[42, 1_234, 2_500]],
        }
        for frame in (sensor_batch, touch_event, audio_batch):
            self.client.sendall((json.dumps(frame) + "\n").encode())

    def stop(self) -> None:
        self._stop.set()
        try:
            if self.client:
                self.client.close()
        except OSError:
            pass
        self.sock.close()


@pytest.fixture()
def app():
    srv = FakeAppServer().start()
    yield srv
    srv.stop()


class TestFastLinkCommands:
    def test_start_ack(self, app):
        link = FastLink(port=app.port, forward=False)
        try:
            ack = link.connect().start(streams=("sensors", "touch"))
            assert ack["ok"] is True and "sensors" in ack["msg"]
        finally:
            link.close()

    def test_vibrate_command_shape(self, app):
        with FastLink(port=app.port, forward=False) as link:
            ack = link.vibrate(250)
            assert ack["ok"] is True
        assert {"cmd": "vibrate", "ms": 250} in app.commands

    def test_status(self, app):
        with FastLink(port=app.port, forward=False) as link:
            st = link.status()
            assert st.get("port") == app.port and st["client_connected"] is True

    def test_record_returns_path(self, app):
        with FastLink(port=app.port, forward=False) as link:
            ack = link.record(1500)
            assert "rec_test.wav" in ack["msg"]



class TestFastLinkSamples:
    def test_flattened_sensor_rows(self, app):
        with FastLink(port=app.port, forward=False) as link:
            link.start(streams=("sensors",))
            samples = list(link.iter_samples(timeout_s=0.3))
        acc = [x for x in samples if x.get("stream") == "sensors" and x.get("type") == 1]
        assert len(acc) == 1
        assert acc[0]["t_ns"] == 1000
        assert acc[0]["x"] == pytest.approx(9.81, rel=1e-6)  # gravity on X

    def test_touch_event_passthrough(self, app):
        with FastLink(port=app.port, forward=False) as link:
            link.start(streams=("touch",))
            samples = list(link.iter_samples(timeout_s=0.3))
        evs = [x for x in samples if x.get("kind") == "touch_down"]
        assert len(evs) == 1 and evs[0]["t_ns"] == 3000

    def test_audio_rms_scaling(self, app):
        with FastLink(port=app.port, forward=False) as link:
            link.start(streams=("audio",))
            samples = list(link.iter_samples(timeout_s=0.3))
        aud = [x for x in samples if x.get("stream") == "audio"]
        assert len(aud) == 1 and aud[0]["rms"] == pytest.approx(0.1234, rel=1e-6)

    def test_collect_window(self, app):
        with FastLink(port=app.port, forward=False) as link:
            link.start(streams=("sensors", "touch"))
            data = link.collect(duration_s=0.4)
        assert len(data["sensors"]) >= 1
        assert any(e.get("kind") == "touch_down" for e in data["events"])

    def test_connection_refused_raises(self):
        with pytest.raises(FastLinkError, match="cannot reach"):
            FastLink(port=1, forward=False).connect(timeout_s=0.5)

