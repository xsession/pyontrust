"""Thermal gateway: live frame / tracking with the simulated fallback."""
from __future__ import annotations

import time

import pytest

pytest.importorskip("cv2")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from flask import Flask

    import pyontrust.gateway.blueprints.thermal_measurement as tm
    import pyontrust.services.thermal_tracking as tt

    monkeypatch.setenv("PYONTRUST_THERMAL_CAL_FILE", str(tmp_path / "cal.json"))
    monkeypatch.setattr(tt, "_DEFAULT_LOG_DIR", tmp_path / "logs")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(tm.bp, url_prefix="/thermal")
    with app.test_client() as c:
        yield c
    tm._tracking.stop()
    tm._live.release()


def test_frame_simulated_and_camera_reused(client):
    import pyontrust.gateway.blueprints.thermal_measurement as tm

    from pyontrust.instruments.seek_thermal import create

    opened = []
    tm._live._factory = lambda cfg: opened.append(cfg) or create(cfg)
    try:
        r = client.get("/thermal/api/frame?mode=simulated")
        d = r.get_json()
        assert r.status_code == 200 and d["ok"], d
        assert d["mode"] == "simulated"
        assert d["width"] > 0 and d["image_b64"]
        client.get("/thermal/api/frame?mode=simulated")
        assert tm._live.is_open
        assert len(opened) == 1, "live camera must stay open between polls"
    finally:
        tm._live._factory = None


def test_status_reports_calibration_and_tracking(client):
    d = client.get("/thermal/api/status").get_json()
    assert d["tracking_running"] is False
    assert d["calibration"]["calibrated"] is False


def test_tracking_simulated_roundtrip(client):
    r = client.post("/thermal/api/tracking/start", json={
        "selections": [{"name": "P1", "type": "point", "x": 10, "y": 10},
                       {"name": "U1", "type": "patch", "x": 60, "y": 45, "w": 12, "h": 10}],
        "interval_s": 0.2,
        "camera": {"mode": "simulated"},
    })
    d = r.get_json()
    assert r.status_code == 200 and d["ok"], d
    assert d["camera_mode"] == "simulated"

    deadline = time.time() + 5
    st = {}
    while time.time() < deadline:
        st = client.get("/thermal/api/status").get_json()
        tr = client.get("/thermal/api/tracking/status").get_json()
        if tr["samples"] >= 2:
            break
        time.sleep(0.1)
    assert tr["samples"] >= 2
    assert set(tr["latest"]) == {"P1", "U1"}
    assert st["tracking_running"] is True

    # live frame is served from the tracking camera while it runs
    assert client.get("/thermal/api/frame").get_json()["mode"] == "tracking"
    # measurement must not grab the camera underneath the tracking session
    assert client.post("/thermal/api/start", json={"mode": "continuous"}).status_code == 409

    assert client.post("/thermal/api/tracking/stop").get_json()["ok"]
    assert client.get("/thermal/api/tracking/export.csv").status_code == 200


def test_tracking_bad_interval(client):
    r = client.post("/thermal/api/tracking/start", json={
        "selections": [{"x": 1, "y": 1}], "interval_s": "abc"})
    assert r.status_code == 400


def test_calibration_offset_cache_tracks_file(tmp_path, monkeypatch):
    from pyontrust.instruments import thermal_calibration as tcal

    monkeypatch.setenv("PYONTRUST_THERMAL_CAL_FILE", str(tmp_path / "c.json"))
    assert tcal.load_offset_c() == 0.0
    tcal.save_offset(1.5, reference_c=24.0, scene_median_c=22.5)
    assert tcal.load_offset_c() == 1.5
    tcal.clear()
    assert tcal.load_offset_c() == 0.0


def test_default_mode_never_falls_back_to_simulated(client):
    """Without an explicit mode the real camera is used — no silent fake frames."""
    from pyontrust.instruments.libseek_driver import detect_camera

    if detect_camera():
        pytest.skip("Seek camera attached")
    r = client.get("/thermal/api/frame")
    d = r.get_json()
    assert r.status_code == 502 and not d["ok"]
    assert "Seek" in d["error"]


def _first_mjpeg_part(resp) -> bytes:
    it = iter(resp.response)
    chunk = next(it)
    resp.close()
    return chunk


def test_stream_simulated_is_mjpeg(client):
    r = client.get("/thermal/api/stream?mode=simulated", buffered=False)
    assert r.status_code == 200
    assert r.mimetype == "multipart/x-mixed-replace"
    part = _first_mjpeg_part(r)
    assert part.startswith(b"--frame") and b"\xff\xd8" in part  # JPEG SOI
    meta = client.get("/thermal/api/stream_meta").get_json()
    assert meta["ok"] and meta["mode"] == "simulated" and meta["max_c"] > meta["min_c"]


def test_stream_without_camera_shows_status_frame(client):
    from pyontrust.instruments.libseek_driver import detect_camera

    if detect_camera():
        pytest.skip("Seek camera attached")
    r = client.get("/thermal/api/stream", buffered=False)
    part = _first_mjpeg_part(r)
    assert b"\xff\xd8" in part
    meta = client.get("/thermal/api/stream_meta").get_json()
    assert not meta["ok"] and "Seek" in meta["error"]


@pytest.fixture()
def prod_client(monkeypatch):
    """Gateway as users run it (not TESTING) — the simulator must be unavailable."""
    from flask import Flask

    import pyontrust.gateway.blueprints.thermal_measurement as tm

    monkeypatch.delenv("PYONTRUST_ALLOW_SIMULATION", raising=False)
    app = Flask(__name__)
    app.register_blueprint(tm.bp, url_prefix="/thermal")
    with app.test_client() as c:
        yield c


def test_simulator_removed_outside_tests(prod_client, monkeypatch):
    import pyontrust.gateway.blueprints.thermal_measurement as tm

    assert prod_client.get("/thermal/api/status").get_json()["simulated_available"] is False
    r = prod_client.post("/thermal/api/capture_single", json={"camera": {"mode": "simulated"}})
    assert r.status_code == 400 and "removed" in r.get_json()["error"]
    r = prod_client.post("/thermal/api/start", json={"camera": {"mode": "simulated"}})
    assert r.status_code == 400
    # an explicit ?mode=simulated is ignored -> the real camera is requested
    seen = []

    def fake_display(mode="seek"):
        seen.append(mode)
        raise tm.FrameError(502, "no camera")

    monkeypatch.setattr(tm._arbiter, "display_frame", fake_display)
    assert prod_client.get("/thermal/api/frame?mode=simulated").status_code == 502
    assert seen == ["seek"]


def test_zone_readings_from_live_frame(client, monkeypatch):
    import numpy as np

    import pyontrust.gateway.blueprints.thermal_measurement as tm

    frame = np.full((154, 206), 25.0, np.float32)
    frame[20:30, 40:60] = 70.0
    monkeypatch.setattr(tm, "_feed", tm.LiveFeed())
    tm._feed.update(frame, {"width": 206, "height": 154, "mode": "seek"})
    d = client.post("/thermal/api/zone_readings", json={"zones": [
        {"name": "U1", "x": 40, "y": 20, "w": 20, "h": 10},
        {"name": "BG", "x": 100, "y": 100, "width": 10, "height": 10},
        {"name": "OUT", "x": 500, "y": 500, "w": 5, "h": 5},
    ]}).get_json()
    assert d["ok"]
    z = {e["name"]: e for e in d["zones"]}
    assert z["U1"]["min_c"] == 70.0 and z["U1"]["max_c"] == 70.0
    assert z["BG"]["mean_c"] == 25.0
    assert z["OUT"]["pixels"] == 0 and "max_c" not in z["OUT"]


def test_zone_readings_without_live_frame(client, monkeypatch):
    import pyontrust.gateway.blueprints.thermal_measurement as tm

    monkeypatch.setattr(tm, "_feed", tm.LiveFeed())
    assert client.post("/thermal/api/zone_readings", json={"zones": []}).status_code == 409
