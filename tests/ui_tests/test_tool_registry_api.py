"""Tool registry wiring: app registration, /api/tools, /api/activity, shell nav."""
from __future__ import annotations

import time

import pytest

pytest.importorskip("flask")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import pyontrust.services.thermal_tracking as tt
    from pyontrust.gateway.app import create_app

    monkeypatch.setattr(tt, "_DEFAULT_LOG_DIR", tmp_path / "logs")
    monkeypatch.chdir(tmp_path)
    app = create_app(artifacts_root=str(tmp_path / "artifacts"), extra_config={"TESTING": True})
    with app.test_client() as c:
        yield c


def test_every_registered_tool_is_served(client):
    from pyontrust.gateway import tools

    data = client.get("/api/tools").get_json()
    assert [t["id"] for t in data["tools"]] == [t.id for t in tools.TOOLS]
    assert data["default"] == tools.DEFAULT_TOOL
    for t in data["tools"]:
        assert client.get(t["url"]).status_code == 200, t["id"]


def test_shell_nav_comes_from_registry(client):
    from pyontrust.gateway import tools

    page = client.get("/").get_data(as_text=True)
    assert "{{" not in page, "unrendered template placeholder"
    for t in tools.TOOLS:
        assert f'data-tool="{t.id}"' in page and f'href="{t.url}"' in page


def test_activity_reports_busy_tools_only(client):
    import pyontrust.gateway.blueprints.thermal_measurement as tm

    assert client.get("/api/activity").get_json()["activity"] == {}
    r = client.post("/thermal/api/tracking/start", json={
        "selections": [{"name": "P1", "type": "point", "x": 5, "y": 5}],
        "interval_s": 0.2, "camera": {"mode": "simulated"}})
    assert r.status_code == 200, r.get_json()
    try:
        time.sleep(0.3)
        busy = client.get("/api/activity").get_json()["activity"]
        assert busy["thermal"]["state"] == "running"
        assert "tracking" in busy["thermal"]["label"].lower()
    finally:
        tm._tracking.stop()
    assert "thermal" not in client.get("/api/activity").get_json()["activity"]
