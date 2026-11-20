"""Regions: store validation / persistence and the state + regions API."""
from __future__ import annotations

import time

import numpy as np
import pytest

from pyontrust.services.thermal_regions import RegionError, RegionStore, region_readings


@pytest.fixture()
def store(tmp_path):
    return RegionStore(tmp_path / "regions.json")


def test_create_names_persist_and_reload(store, tmp_path):
    a = store.create({"kind": "rect", "x": 10, "y": 5, "w": 20, "h": 10})
    b = store.create({"kind": "point", "x": 3, "y": 4, "w": 50})
    assert (a.name, b.name) == ("R1", "P1")
    assert (b.w, b.h) == (1, 1), "points have no size"
    again = RegionStore(tmp_path / "regions.json").list()
    assert [r.to_dict() for r in again] == [a.to_dict(), b.to_dict()]


@pytest.mark.parametrize("bad", [
    {"kind": "rect", "x": 0, "y": 0, "w": 1, "h": 5},           # too small
    {"kind": "blob", "x": 0, "y": 0},                            # unknown kind
    {"kind": "point", "x": -1, "y": 0},                          # negative
    {"kind": "point", "x": 1, "y": 1, "name": "bad name!"},      # CSV-unsafe name
    {"kind": "point", "x": 1, "y": 1, "warn_c": 90, "max_c": 80},
    {"kind": "point", "x": "abc", "y": 1},
])
def test_validation(store, bad):
    with pytest.raises(RegionError):
        store.create(bad)
    assert store.list() == []


def test_unique_names_on_update(store):
    a = store.create({"kind": "point", "x": 1, "y": 1, "name": "U1"})
    b = store.create({"kind": "point", "x": 2, "y": 2})
    with pytest.raises(RegionError):
        store.update(b.id, {"name": "U1"})
    assert store.update(a.id, {"name": "U1", "max_c": 70}).max_c == 70   # own name is fine


def test_consumer_conversions(store):
    store.create({"kind": "rect", "x": 10, "y": 5, "w": 20, "h": 10, "name": "VREG"})
    store.create({"kind": "point", "x": 0, "y": 7, "name": "TP1"})
    zones = store.measurement_zones()
    assert zones[0] == {"name": "VREG", "x": 10, "y": 5, "width": 20, "height": 10,
                        "warn_temp_c": 60.0, "max_temp_c": 85.0}
    assert zones[1]["width"] == 3 and zones[1]["x"] == 0, "point -> 3x3, clipped at the edge"
    sels = store.tracking_selections()
    assert [s["type"] for s in sels] == ["patch", "point"]


def test_region_readings_levels(store):
    frame = np.full((20, 30), 25.0, np.float32)
    frame[5:10, 10:20] = 72.0
    hot = store.create({"kind": "rect", "x": 10, "y": 5, "w": 10, "h": 5, "warn_c": 60, "max_c": 80})
    pt = store.create({"kind": "point", "x": 2, "y": 2})
    r = region_readings(frame, store.list())
    assert r[hot.id]["level"] == "warn" and r[hot.id]["max_c"] == 72.0
    assert r[pt.id]["level"] == "ok" and r[pt.id]["pixels"] == 9


# ── API ────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from flask import Flask

    import pyontrust.gateway.blueprints.thermal_measurement as tm
    import pyontrust.services.thermal_tracking as tt

    monkeypatch.setattr(tm, "_regions", RegionStore(tmp_path / "regions.json"))
    monkeypatch.setattr(tm, "_feed", tm.LiveFeed())
    monkeypatch.setattr(tt, "_DEFAULT_LOG_DIR", tmp_path / "logs")
    monkeypatch.setenv("PYONTRUST_THERMAL_CAL_FILE", str(tmp_path / "cal.json"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(tm.bp, url_prefix="/thermal")
    with app.test_client() as c:
        yield c
    tm._tracking.stop()
    tm._live.release()


def test_regions_crud_api(client):
    r = client.post("/thermal/api/regions", json={"kind": "rect", "x": 4, "y": 4, "w": 10, "h": 8})
    assert r.status_code == 201
    rid = r.get_json()["region"]["id"]
    assert client.patch(f"/thermal/api/regions/{rid}", json={"name": "U7", "warn_c": 50}).get_json()["region"]["name"] == "U7"
    assert client.patch(f"/thermal/api/regions/{rid}", json={"w": 1}).status_code == 400
    assert client.patch("/thermal/api/regions/nope", json={}).status_code == 404
    assert [x["name"] for x in client.get("/thermal/api/regions").get_json()["regions"]] == ["U7"]
    assert client.delete(f"/thermal/api/regions/{rid}").status_code == 200
    assert client.delete(f"/thermal/api/regions/{rid}").status_code == 404


def test_state_snapshot_includes_live_readings(client):
    import pyontrust.gateway.blueprints.thermal_measurement as tm

    rid = client.post("/thermal/api/regions", json={"kind": "rect", "x": 0, "y": 0, "w": 4, "h": 4}).get_json()["region"]["id"]
    s = client.get("/thermal/api/state").get_json()
    assert s["activity"] == "idle" and s["regions"][0]["reading"] is None   # no live frame yet
    for key in ("camera", "calibration", "flat_field", "live", "measurement", "tracking"):
        assert key in s
    tm._feed.update(np.full((154, 206), 31.5, np.float32), {"width": 206, "height": 154, "mode": "seek"})
    s = client.get("/thermal/api/state").get_json()
    assert s["regions"][0]["id"] == rid
    assert s["regions"][0]["reading"]["mean_c"] == 31.5 and s["regions"][0]["reading"]["level"] == "ok"


def test_tracking_uses_regions_and_locks_them(client):
    client.post("/thermal/api/regions", json={"kind": "point", "x": 10, "y": 10, "name": "TP1"})
    rid = client.post("/thermal/api/regions", json={"kind": "rect", "x": 50, "y": 40, "w": 12, "h": 10, "name": "U1"}).get_json()["region"]["id"]
    r = client.post("/thermal/api/tracking/start", json={"interval_s": 0.2, "camera": {"mode": "simulated"}})
    assert r.status_code == 200, r.get_json()
    for _ in range(50):
        st = client.get("/thermal/api/state").get_json()
        if st["tracking"]["samples"] >= 1:
            break
        time.sleep(0.1)
    assert st["activity"] == "tracking" and st["tracking"]["names"] == ["TP1", "U1"]
    # regions are frozen while their names are CSV columns of a live session
    assert client.patch(f"/thermal/api/regions/{rid}", json={"name": "U2"}).status_code == 409
    assert client.post("/thermal/api/regions", json={"kind": "point", "x": 1, "y": 1}).status_code == 409
    client.post("/thermal/api/tracking/stop")
    assert client.patch(f"/thermal/api/regions/{rid}", json={"name": "U2"}).status_code == 200


def test_capture_single_uses_regions(client):
    client.post("/thermal/api/regions", json={"kind": "rect", "x": 60, "y": 45, "w": 12, "h": 10, "name": "HOT"})
    d = client.post("/thermal/api/capture_single", json={"camera": {"mode": "simulated"}}).get_json()
    assert [z["zone_name"] for z in d["snapshot"]["zones"]] == ["HOT"]
