"""Microscopy gateway: synthetic run, captured-stack run, exports."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from flask import Flask

    import pyontrust.gateway.blueprints.microscopy as mb

    monkeypatch.setattr(mb, "_RUNS_DIR", tmp_path / "runs")
    mb._STACK.clear()
    mb._STACK_SHARPNESS.clear()
    mb._LAST.clear()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(mb.bp, url_prefix="/micro")
    with app.test_client() as c:
        yield c
    mb._STACK.clear()
    mb._STACK_SHARPNESS.clear()


def test_synthetic_run_and_exports(client):
    r = client.post("/micro/api/run", json={"source": "synthetic", "n_frames": 4,
                                            "width": 160, "height": 120})
    d = r.get_json()
    assert r.status_code == 200 and d["ok"], d
    assert d["stats"]["source"] == "synthetic"
    assert {"heightmap_png", "mesh_stl", "stacked_png", "report_json"} <= set(d["exports"])
    for key, url in d["export_urls"].items():
        resp = client.get(url)
        assert resp.status_code == 200, key
        assert resp.data
    assert client.get("/micro/api/export/nope").status_code == 404


def test_captured_requires_two_frames(client):
    r = client.post("/micro/api/run", json={"source": "captured"})
    assert r.status_code == 400


def test_capture_stack_with_fake_camera(client, monkeypatch):
    import pyontrust.gateway.blueprints.microscopy as mb
    from pyontrust.analysis.focus_stacking import generate_synthetic_stack

    frames, _ = generate_synthetic_stack(n_frames=4, size=(120, 160), seed=3)
    it = iter(frames)
    monkeypatch.setattr(mb._camera, "grab", lambda dev: next(it))

    for i in range(4):
        d = client.post("/micro/api/capture", json={"device": 0}).get_json()
        assert d["ok"] and d["count"] == i + 1

    st = client.get("/micro/api/stack").get_json()
    assert st["count"] == 4 and len(st["thumbs"]) == 4

    assert client.post("/micro/api/stack/undo").get_json()["count"] == 3

    d = client.post("/micro/api/run", json={"source": "captured", "step_um": 5}).get_json()
    assert d["ok"], d
    assert d["stats"]["n_frames"] == 3 and d["stats"]["source"] == "captured"

    # A frame of a different size is rejected instead of breaking the stack.
    monkeypatch.setattr(mb._camera, "grab", lambda dev: np.zeros((50, 50, 3), np.uint8))
    assert client.post("/micro/api/capture", json={"device": 0}).status_code == 409

    assert client.post("/micro/api/stack/clear").get_json()["count"] == 0


def test_bad_device_and_params(client):
    assert client.get("/micro/api/preview?device=abc").status_code == 400
    assert client.post("/micro/api/run", json={"step_um": "x"}).status_code == 400
    assert client.post("/micro/api/run", json={"source": "bogus"}).status_code == 400


def test_stream_with_fake_camera(client, monkeypatch):
    import pyontrust.gateway.blueprints.microscopy as mb

    frame = np.random.default_rng(0).integers(0, 255, (120, 160, 3), dtype=np.uint8)
    monkeypatch.setattr(mb._camera, "grab", lambda dev, fresh=True: frame)
    r = client.get("/micro/api/stream?device=0", buffered=False)
    assert r.status_code == 200 and r.mimetype == "multipart/x-mixed-replace"
    part = next(iter(r.response))
    r.close()
    assert part.startswith(b"--frame") and b"\xff\xd8" in part
    st = client.get("/micro/api/live_stats").get_json()
    assert st["active"] and st["width"] == 160 and st["sharpness"] > 0
