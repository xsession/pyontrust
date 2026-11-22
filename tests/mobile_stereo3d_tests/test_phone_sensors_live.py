"""Diagnostic → Live Data for phones: sensors read through the pyontrust phone app.

The phone app is replaced by an in-test fake of ``phone_camera.read_sensor``.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def fake_app(monkeypatch):
    import pyontrust.instruments.android_sensors as asens
    import pyontrust.instruments.phone_camera as pc

    calls: list[tuple[str, str]] = []

    def read_sensor(serial, sensor_type, window_ms=150):
        calls.append((serial, sensor_type))
        if sensor_type == "barometer":
            raise pc.PhoneCameraError(f"phone {serial}: this phone has no barometer sensor")
        x = 1.0 if serial == "PHONE_A" else 2.0
        return {"ok": True, "type": sensor_type, "name": "fake", "stale": False,
                "samples": [[0.00, x, 0.1, 9.8], [0.02, x, 0.2, 9.7]]}

    monkeypatch.setattr(pc, "read_sensor", read_sensor)
    monkeypatch.setattr(asens, "_adb_available", lambda: True)
    monkeypatch.setattr(asens, "_adb_device_info", lambda serial=None: {"model": "Fake", "serial": serial or ""})
    monkeypatch.setattr(asens, "_adb_resolve_serial", lambda: "PHONE_A")
    return calls


def test_reads_the_requested_phone_through_the_app(fake_app):
    from pyontrust.instruments.android_sensors import AndroidSensorInstrument

    inst = AndroidSensorInstrument(mode="adb", serial="PHONE_B")
    inst.open()
    r = inst.read_accelerometer(duration_s=0.1)
    assert fake_app == [("PHONE_B", "accelerometer")]
    assert r["n_samples"] == 2 and r["x"] == [2.0, 2.0] and r["z"] == [9.8, 9.7]
    assert r["unit"] == "m/s²" and r["stale"] is False

    missing = inst._impl.read_sensor("barometer", 0.1)
    assert missing["n_samples"] == 0 and "no barometer" in missing["error"]


def test_default_phone_when_no_serial(fake_app):
    from pyontrust.instruments.android_sensors import AndroidSensorInstrument

    inst = AndroidSensorInstrument(mode="adb")
    inst.open()
    assert inst.read_gyroscope(0.1)["x"] == [1.0, 1.0]
    assert fake_app == [("PHONE_A", "gyroscope")]


def test_live_stream_sends_samples_of_the_chosen_phone(fake_app):
    from flask import Flask

    import pyontrust.gateway.blueprints.diagnostic as diag

    app = Flask(__name__)
    app.register_blueprint(diag.bp, url_prefix="/diag")
    with app.test_client() as c:
        resp = c.get("/diag/api/live/stream?hw_type=android_sensors&sensor=accelerometer"
                     "&rate_ms=100&mode=adb&serial=PHONE_B", buffered=False)
        # hop-by-hop headers make WSGI servers (waitress) abort the response
        assert "Connection" not in resp.headers
        assert resp.mimetype == "text/event-stream"
        chunk = next(iter(resp.response))
        chunk = chunk.decode() if isinstance(chunk, bytes) else chunk
        for stop in list(diag._active_streams.values()):
            stop.set()
        resp.close()
    msg = json.loads(chunk.split("data: ", 1)[1])
    assert msg["data"]["x"] == [2.0, 2.0]
    assert fake_app[0] == ("PHONE_B", "accelerometer")
