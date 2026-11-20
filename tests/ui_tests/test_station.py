"""Station: audit trail, run registry, instruments, self-tests, error envelope."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

pytest.importorskip("flask")

from pyontrust.services.audit import AuditLog, redact  # noqa: E402
from pyontrust.services.instruments import InstrumentRegister, cal_status  # noqa: E402
from pyontrust.services.runs import RunRegistry  # noqa: E402

LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


# ── audit log ──────────────────────────────────────────────────────────

def test_audit_chain_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit")
    for i in range(5):
        log.append({"action": f"POST /x/{i}", "operator": "ana"})
    assert log.verify() == {"ok": True, "entries": 5, "head": log.query(limit=1)[0]["hash"]}
    assert AuditLog(tmp_path / "audit").append({"action": "after restart"})["seq"] == 6   # chain resumes

    f = next((tmp_path / "audit").glob("*.jsonl"))
    lines = f.read_text().splitlines()
    edited = json.loads(lines[2]); edited["operator"] = "mallory"
    f.write_text("\n".join(lines[:2] + [json.dumps(edited)] + lines[3:]) + "\n")
    v = AuditLog(tmp_path / "audit").verify()
    assert not v["ok"] and v["seq"] == 3 and "modified" in v["error"]

    f.write_text("\n".join(lines[:2] + lines[3:]) + "\n")          # delete an entry
    v = AuditLog(tmp_path / "audit").verify()
    assert not v["ok"] and "chain broken" in v["error"]


def test_redact_hides_secrets_and_bounds_size():
    r = redact({"password": "x", "api_token": "y", "v": "a" * 500, "list": list(range(50))})
    assert r["password"] == "***" and r["api_token"] == "***"
    assert len(r["v"]) <= 120 and len(r["list"]) == 11


# ── runs ───────────────────────────────────────────────────────────────

def test_runs_lifecycle_and_yield(tmp_path):
    reg = RunRegistry(tmp_path / "runs.sqlite")
    actor = {"operator": "ana", "dut": "PCB-7", "station": "S1"}
    for outcome in ("pass", "pass", "fail", "error"):
        rid = reg.start("thermal", "measurement", actor, {"mode": "soak"})
        reg.finish(rid, outcome, {"max": 40}, ["/r.html"])
    r = reg.list(tool="thermal")[0]
    assert r["dut"] == "PCB-7" and r["summary"] == {"mode": "soak", "max": 40} and r["artifacts"] == ["/r.html"]
    g = reg.stats()["groups"][0]
    assert g["total"] == 4 and g["yield"] == round(2 / 3, 4), "errors don't count in first-pass yield"
    with pytest.raises(ValueError):
        reg.finish(rid, "maybe")


def test_interrupted_runs_are_closed(tmp_path):
    reg = RunRegistry(tmp_path / "runs.sqlite")
    rid = reg.start("hil", "profile")
    assert RunRegistry(tmp_path / "runs.sqlite").mark_interrupted() == 1
    r = reg.get(rid)
    assert r["outcome"] == "error" and "gateway stopped" in r["summary"]["error"]


# ── instruments ────────────────────────────────────────────────────────

def test_calibration_status():
    today = date(2026, 6, 1)
    assert cal_status(None, today) == ("no_cal", None)
    assert cal_status("2026-05-31", today)[0] == "overdue"
    assert cal_status("2026-06-20", today)[0] == "due_soon"
    assert cal_status("2027-01-01", today)[0] == "ok"


def test_instrument_register_validates(tmp_path):
    reg = InstrumentRegister(tmp_path / "i.json")
    it = reg.create({"name": "PSU", "cal_due": "2030-01-01"})
    with pytest.raises(ValueError):
        reg.create({"name": ""})
    with pytest.raises(ValueError):
        reg.update(it["id"], {"cal_due": "next week"})
    assert reg.update(it["id"], {"serial": "SN1"})["serial"] == "SN1"


# ── wired into the gateway ─────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from pyontrust.gateway.app import create_app

    monkeypatch.chdir(tmp_path)
    app = create_app(artifacts_root=str(tmp_path / "a"), extra_config={"TESTING": True})
    with app.test_client() as c:
        yield c


def test_actions_are_audited_with_session_context(client):
    client.post("/station/api/session", json={"operator": "Ana K", "dut": "PCB-0042"}, environ_base=LOCAL)
    client.post("/thermal/api/regions", json={"kind": "point", "x": 5, "y": 5, "name": "TP1"}, environ_base=LOCAL)
    client.post("/thermal/api/zone_readings", json={"zones": []}, environ_base=LOCAL)    # read-only: skipped
    entries = client.get("/station/api/audit", environ_base=LOCAL).get_json()["entries"]
    actions = [e["action"] for e in entries]
    assert "POST /thermal/api/regions" in actions and "POST /thermal/api/zone_readings" not in actions
    e = next(x for x in entries if x["action"] == "POST /thermal/api/regions")
    assert e["operator"] == "Ana K" and e["dut"] == "PCB-0042" and e["tool"] == "thermal" and e["status"] == 201
    assert client.get("/station/api/audit/verify", environ_base=LOCAL).get_json()["ok"]


def test_overdue_instrument_blocks_readiness_and_flags_nav(client):
    past = (date.today() - timedelta(days=3)).isoformat()
    client.post("/station/api/instruments", json={"name": "DMM 34461A", "cal_due": past}, environ_base=LOCAL)
    ov = client.get("/station/api/overview", environ_base=LOCAL).get_json()
    assert not ov["readiness"]["ready"] and "overdue" in ov["readiness"]["reasons"][0]
    act = client.get("/api/activity", environ_base=LOCAL).get_json()["activity"]
    assert act["station"]["state"] == "error"


def test_selftest_runs_every_provider(client):
    d = client.get("/station/api/selftest", environ_base=LOCAL).get_json()
    assert {"station", "thermal", "micro", "can", "waveforms", "flowlab", "hil"} <= set(d["results"])
    for res in d["results"].values():
        assert res["status"] in ("pass", "warn", "fail") and res["checks"]


def test_flowlab_run_is_registered(client):
    client.post("/station/api/session", json={"operator": "ana", "dut": "D1"}, environ_base=LOCAL)
    r = client.post("/flowlab/api/execute", json={"blocks": [], "connections": []}, environ_base=LOCAL)
    run_id = r.get_json()["run_id"]
    run = client.get(f"/station/api/runs/{run_id}", environ_base=LOCAL).get_json()["run"]
    assert run["tool"] == "flowlab" and run["operator"] == "ana" and run["dut"] == "D1"
    assert run["outcome"] in ("pass", "fail", "done", "error")
    assert "flowlab" in client.get("/station/api/runs/export.csv", environ_base=LOCAL).get_data(as_text=True)


@pytest.mark.parametrize("name", ["../../evil", "a/b", "..", "", "x" * 100, "/etc/passwd"])
def test_flowlab_rejects_path_traversal(client, name, tmp_path):
    r = client.post("/flowlab/api/save", json={"name": name, "diagram": {}}, environ_base=LOCAL)
    assert r.status_code == 400
    assert not (tmp_path / "evil.json").exists()


def test_api_errors_use_one_envelope(client):
    r = client.get("/station/api/runs/does-not-exist", environ_base=LOCAL)
    d = r.get_json()
    assert r.status_code == 404 and d["ok"] is False and d["error"]
    r = client.get("/api/nope", environ_base=LOCAL)
    d = r.get_json()
    assert r.status_code == 404 and d["request_id"] and r.headers["X-Request-ID"] == d["request_id"]
