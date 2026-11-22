"""Default HIL profile and default lab bench."""
from __future__ import annotations

import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_shipped_defaults_use_real_instruments_only():
    profile = json.loads((REPO / "data/profiles/default.json").read_text())
    bench = json.loads((REPO / "data/benches/default.json").read_text())
    assert profile["instruments"]["power_meter"]["type"] == "ppk2"
    assert profile["instruments"]["power_meter"]["mode"] == "ampere"      # never powers the target
    assert all(i["type"] != "simulated" for i in bench["instruments"])
    assert profile["steps"]


def test_bench_accepts_list_and_mapping_shapes():
    from pyontrust.core.lab_bench import LabBench

    lst = LabBench.from_dict({"name": "b", "instruments": [
        {"type": "ppk2", "enabled": True, "params": {"mode": "ampere"}},
        {"type": "ppk2", "enabled": False, "params": {"mode": "source"}},
    ]})
    assert list(lst.instruments) == ["ppk2", "ppk2_2"]
    assert lst.instruments["ppk2"].params == {"mode": "ampere"}
    assert lst.instruments["ppk2_2"].enabled is False

    mapping = LabBench.from_dict({"name": "b", "instruments": {"meter": {"type": "ppk2", "mode": "ampere"}}})
    assert mapping.instruments["meter"].type == "ppk2"
    assert mapping.instruments["meter"].params == {"mode": "ampere"}


def test_bench_service_loads_and_connects_the_default(monkeypatch):
    import pyontrust.services.bench_service as bs

    monkeypatch.chdir(REPO)
    created = []
    monkeypatch.setattr(bs, "create_instrument", lambda t, p: created.append(t) or object())
    svc = bs.BenchService()
    assert svc.load()["loaded"] is True
    assert svc.instantiate_all() == {"ppk2": "ok", "seek_thermal": "ok", "android_sensors": "ok"}
    assert [s["status"] for s in svc.instrument_status()] == ["connected"] * 3
    assert created == ["ppk2", "seek_thermal", "android_sensors"]


def test_profile_resolution_and_listing(monkeypatch):
    from pyontrust.services import test_service as ts

    monkeypatch.chdir(REPO)
    assert ts.resolve_profile_path(None) == pathlib.Path("data/profiles/default.json")
    assert ts.resolve_profile_path("sleep_current") == pathlib.Path("data/profiles/sleep_current.json")
    with pytest.raises(FileNotFoundError):
        ts.resolve_profile_path("does_not_exist")
    profiles = ts.list_profiles()
    assert profiles[0]["name"] == "default" and profiles[0]["default"] is True


def test_hil_start_without_profile_runs_the_default(monkeypatch, tmp_path):
    from flask import Flask

    import pyontrust.gateway.blueprints.hil as hil
    from pyontrust.services import test_service as ts

    monkeypatch.chdir(REPO)
    seen = {}

    def fake_run(profile, repo_root, *, artifacts_root=None, lab_bench_path=None):
        seen["name"], seen["artifacts"] = profile.name, artifacts_root
        return tmp_path

    monkeypatch.setattr(ts, "run_profile", fake_run)
    monkeypatch.setattr(hil, "_track_run", lambda *a: None)
    svc = ts.TestService(artifacts_root=tmp_path)
    app = Flask(__name__)
    app.extensions["test_service"] = svc
    app.register_blueprint(hil.bp, url_prefix="/hil")
    with app.test_client() as c:
        assert c.get("/hil/api/profiles").get_json()["default"] == "default"
        r = c.post("/hil/api/start", json={})
        assert r.status_code == 200 and r.get_json()["profile"].endswith("default.json")
        svc._current_thread.join(5)
        assert c.post("/hil/api/start", json={"profile": "nope"}).status_code == 404
    assert seen == {"name": "default", "artifacts": tmp_path}
    assert svc.history(1)[0]["state"] == "finished"


def test_ppk2_picks_the_data_interface(monkeypatch):
    import sys
    import types

    sys.path.insert(0, str(REPO / "tools"))
    from lab_bench.power_test_framework.instruments import ppk2

    ports = [types.SimpleNamespace(device="/dev/ttyACM0", location="1-2.2:1.3"),
             types.SimpleNamespace(device="/dev/ttyACM1", location="1-2.2:1.1")]
    import serial.tools.list_ports as lp

    monkeypatch.setattr(lp, "comports", lambda: ports)
    assert ppk2._pick_data_port(["/dev/ttyACM0", "/dev/ttyACM1"]) == "/dev/ttyACM1"
