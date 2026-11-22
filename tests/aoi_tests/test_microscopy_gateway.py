"""Microscopy gateway: multi-camera capture, focus sweeps, per-source stacks.

Cameras are replaced by in-test fakes (the product only accepts real ones);
the frames come from the synthetic focus stack, a test fixture.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")


@pytest.fixture()
def frames():
    from pyontrust.analysis.focus_stacking import generate_synthetic_stack

    stack, _ = generate_synthetic_stack(n_frames=4, size=(120, 160), seed=3)
    return stack


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from flask import Flask

    import pyontrust.gateway.blueprints.microscopy as mb

    monkeypatch.setattr(mb, "_RUNS_DIR", tmp_path / "runs")
    mb._STACKS.clear()
    mb._LAST.clear()
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(mb.bp, url_prefix="/micro")
    with app.test_client() as c:
        yield c
    mb._STACKS.clear()


def fake_cameras(monkeypatch, frames_by_source):
    """Each source returns its next frame (live and still alike)."""
    import pyontrust.gateway.blueprints.microscopy as mb

    iters = {k: iter(v) for k, v in frames_by_source.items()}

    def grab(src):
        return next(iters[":".join(map(str, src))])

    monkeypatch.setattr(mb, "_still", grab)
    monkeypatch.setattr(mb, "_live_frame", grab)


# ── sources ────────────────────────────────────────────────────────────

def test_source_parsing():
    from pyontrust.services.camera_sources import _source_arg

    assert _source_arg("usb:2") == ("usb", 2)
    assert _source_arg("phone:MWS7N17623000254:2") == ("phone", "MWS7N17623000254", "2")
    for bad in ("phone::0", "phone:abc", "phone:a b:0", "phone:x;rm:0", "cam:1", "usb:x", "synthetic"):
        with pytest.raises(ValueError):
            _source_arg(bad)


def test_prepare_rotates_and_caps_size():
    from pyontrust.services.camera_sources import _prepare

    f = np.zeros((300, 400, 3), np.uint8)
    assert _prepare(f, 90).shape[:2] == (400, 300)
    assert _prepare(f, 0, 200).shape[:2] == (150, 200)
    with pytest.raises(ValueError):
        _prepare(f, 45)


def test_cameras_lists_every_phone_camera_with_roles(client, monkeypatch):
    from pyontrust.instruments import phone_camera as pc
    from pyontrust.services import camera_sources as cs

    monkeypatch.setattr(cs, "_probe_cameras", lambda: [{"index": 2, "name": "USB 2.0 Camera"}])
    monkeypatch.setattr(pc, "list_phones", lambda: [pc.Phone("SER1", "device", "EVA_L09"),
                                                    pc.Phone("SER2", "unauthorized")])
    monkeypatch.setattr(pc, "cameras", lambda serial: [
        {"id": "0", "facing": "back", "focal_mm": 3.82, "sensor_mm": [4.98, 3.73], "max_size": [4000, 3000],
         "min_focus_diopters": 10, "listed": True},
        {"id": "1", "facing": "front", "focal_mm": 2.64, "sensor_mm": [2.75, 1.99], "max_size": [2592, 1944],
         "listed": True},
        {"id": "2", "facing": "back", "focal_mm": 2.19, "sensor_mm": [4.4, 3.3], "max_size": [2592, 1944],
         "listed": False, "api": "camera1", "min_focus_diopters": 10}])
    cams = client.get("/micro/api/cameras").get_json()["cameras"]
    assert [c["source"] for c in cams] == ["phone:SER1:0", "phone:SER1:2", "phone:SER1:1", None, "usb:2"]
    assert [c.get("role") for c in cams[:3]] == ["main", "wide", "front"]   # wide: larger field of view
    assert cams[0]["fov_deg"] == 66 and cams[0]["manual_focus"] and cams[0]["min_focus_mm"] == 100
    assert cams[1]["hidden"] and cams[1]["manual_focus"] is False, "old-API camera: no manual focus"
    assert "Allow USB debugging" in cams[3]["label"]


# ── simultaneous capture ───────────────────────────────────────────────

def test_simultaneous_capture_into_per_source_stacks(client, monkeypatch, frames):
    fake_cameras(monkeypatch, {"phone:A:0": frames, "usb:2": [f[:, ::-1].copy() for f in frames]})
    for i in range(3):
        d = client.post("/micro/api/capture", json={"sources": ["phone:A:0", "usb:2"]}).get_json()
        assert d["ok"], d
        assert d["results"]["phone:A:0"]["count"] == i + 1 and d["results"]["usb:2"]["count"] == i + 1
    st = client.get("/micro/api/stack").get_json()
    assert st["count"] == 6 and len(st["stacks"]["usb:2"]["thumbs"]) == 3
    client.post("/micro/api/stack/undo", json={"source": "usb:2"})
    st = client.get("/micro/api/stack?thumbs=0").get_json()
    assert st["stacks"]["usb:2"]["count"] == 2 and st["stacks"]["phone:A:0"]["count"] == 3

    d = client.post("/micro/api/run", json={"step_um": 5}).get_json()
    assert d["ok"], d
    assert {r["source"] for r in d["results"]} == {"phone:A:0", "usb:2"}
    for r in d["results"]:
        assert r["ok"] and r["stats"]["metric_from_focus"] is False
        assert {"heightmap_png", "mesh_stl", "stacked_png"} <= set(r["exports"])
        resp = client.get(r["export_urls"]["mesh_stl"])
        assert resp.status_code == 200 and resp.data
    assert client.get("/micro/api/export/9/mesh_stl").status_code == 404

    client.post("/micro/api/stack/clear", json={"source": "usb:2"})
    assert set(client.get("/micro/api/stack?thumbs=0").get_json()["stacks"]) == {"phone:A:0"}
    client.post("/micro/api/stack/clear", json={})
    assert client.get("/micro/api/stack?thumbs=0").get_json()["count"] == 0


def test_one_failing_camera_does_not_block_the_other(client, monkeypatch, frames):
    import pyontrust.gateway.blueprints.microscopy as mb

    def grab(src):
        if src[0] == "usb":
            raise RuntimeError("USB camera unplugged")
        return frames[0]

    monkeypatch.setattr(mb, "_still", grab)
    d = client.post("/micro/api/capture", json={"sources": ["phone:A:0", "usb:2"]}).get_json()
    assert d["ok"] and d["results"]["phone:A:0"]["ok"]
    assert "unplugged" in d["results"]["usb:2"]["error"]


def test_size_mismatch_rejected_per_source(client, monkeypatch, frames):
    fake_cameras(monkeypatch, {"usb:2": [frames[0], np.zeros((50, 50, 3), np.uint8)]})
    client.post("/micro/api/capture", json={"sources": ["usb:2"]})
    r = client.post("/micro/api/capture", json={"sources": ["usb:2"]})
    assert r.status_code == 502 and "differs" in r.get_json()["results"]["usb:2"]["error"]


def test_run_needs_two_planes_and_valid_params(client):
    assert client.post("/micro/api/run", json={}).status_code == 400
    assert client.post("/micro/api/run", json={"step_um": "x"}).status_code == 400
    assert client.post("/micro/api/run", json={"step_um": -1}).status_code == 400


# ── focus sweep (phones) ───────────────────────────────────────────────

def test_focus_sweep_drives_the_lens_and_gives_metric_depth(client, monkeypatch, frames):
    from pyontrust.instruments import phone_camera as pc

    focus_calls, it = [], iter(frames)
    monkeypatch.setattr(pc, "stream", lambda serial, cam: None)
    monkeypatch.setattr(pc, "set_focus",
                        lambda serial, mode, diopters=None: focus_calls.append((mode, diopters)) or {})
    monkeypatch.setattr(pc, "capture", lambda serial, cam: next(it))
    d = client.post("/micro/api/sweep", json={"sources": ["phone:A:0"], "n_frames": 4,
                                              "near_mm": 100, "far_mm": 250, "settle_ms": 100}).get_json()
    assert d["ok"], d
    assert d["distances_mm"] == [250.0, 200.0, 150.0, 100.0]
    manual = [round(dio, 3) for mode, dio in focus_calls if mode == "manual"]
    assert manual == [4.0, 5.0, 6.667, 10.0]                      # diopters = 1000 / mm
    assert focus_calls[-1] == ("continuous", None), "autofocus restored after the sweep"
    assert client.get("/micro/api/stack?thumbs=0").get_json()["stacks"]["phone:A:0"]["z_mm"] == [250, 200, 150, 100]
    r = client.post("/micro/api/run", json={}).get_json()["results"][0]
    assert r["ok"] and r["stats"]["metric_from_focus"] is True


def test_sweep_rejects_usb_and_bad_ranges(client):
    assert client.post("/micro/api/sweep", json={"sources": ["usb:2"]}).status_code == 400
    assert client.post("/micro/api/sweep", json={"sources": ["phone:A:0"],
                                                 "near_mm": 300, "far_mm": 100}).status_code == 400


# ── real hardware only ─────────────────────────────────────────────────

def test_no_synthetic_source(client):
    assert client.post("/micro/api/capture", json={"sources": ["synthetic"]}).status_code == 400


def test_synthetic_stack_refused_outside_tests(monkeypatch):
    from pyontrust.analysis.focus_stacking import generate_synthetic_stack
    from pyontrust.core.simulation_guard import SimulationDisabled

    monkeypatch.delenv("PYONTRUST_ALLOW_SIMULATION", raising=False)
    with pytest.raises(SimulationDisabled):
        generate_synthetic_stack(n_frames=2, size=(32, 32))
