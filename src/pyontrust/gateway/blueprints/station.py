"""Station blueprint — health, operator / DUT session, instruments, runs, audit.

Routes (under ``/station``)
---------------------------
GET  /                          page
GET  /api/overview              station, session, readiness, counts (one call for the header)
GET|POST /api/session           operator + active DUT (cookies; logged)
GET|PUT  /api/config            station name / location
GET  /api/selftest[?tool=id]    self-test results (all tools or one)
GET  /api/readiness             ready flag + reasons (failing self-tests, overdue calibration)
GET|POST /api/instruments       instrument register
PATCH|DELETE /api/instruments/<id>
GET  /api/runs                  run history (?tool ?outcome ?dut ?limit ?since)
GET  /api/runs/<id>             one run
GET  /api/runs/stats            counts + first-pass yield per tool (?days)
GET  /api/runs/export.csv       run history as CSV
GET  /api/audit                 audit trail (?tool ?q ?limit)
GET  /api/audit/verify          hash-chain integrity check
GET  /api/audit/export.jsonl    raw audit trail
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from flask import Blueprint, Response, jsonify, request

from pyontrust.gateway import context
from pyontrust.services.audit import AuditLog
from pyontrust.services.instruments import InstrumentError, InstrumentRegister
from pyontrust.services.runs import RunRegistry

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "station"
bp = Blueprint("station", __name__, static_folder=str(_WEB_DIR), static_url_path="/static")


# ── station singletons (one per data directory) ─────────────────────────

@lru_cache(maxsize=4)
def _audit(path: str) -> AuditLog:
    return AuditLog(pathlib.Path(path) / "audit")


@lru_cache(maxsize=4)
def _runs(path: str) -> RunRegistry:
    reg = RunRegistry(pathlib.Path(path) / "runs.sqlite")
    reg.mark_interrupted()       # runs left 'running' by a previous process
    return reg


@lru_cache(maxsize=4)
def _instruments(path: str) -> InstrumentRegister:
    return InstrumentRegister(pathlib.Path(path) / "instruments.json")


def audit_log() -> AuditLog:
    return _audit(str(context.data_dir()))


def runs() -> RunRegistry:
    return _runs(str(context.data_dir()))


def instruments() -> InstrumentRegister:
    return _instruments(str(context.data_dir()))


def _body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _err(msg: str, status: int) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": msg}), status


# ── page / overview ─────────────────────────────────────────────────────

@bp.route("/")
def index() -> Response:
    return bp.send_static_file("index.html")


def _readiness(selftest: dict[str, Any] | None = None) -> dict[str, Any]:
    reasons = []
    for it in instruments().list():
        if it["status"] == "overdue":
            reasons.append(f"{it['name']}: calibration overdue since {it['cal_due']}")
    if selftest:
        for tool, res in selftest["results"].items():
            for c in res["checks"]:
                if c["status"] == "fail":
                    reasons.append(f"{tool}: {c['name']} — {c['detail']}")
    return {"ready": not reasons, "reasons": reasons}


@bp.route("/api/overview")
def overview() -> Response:
    a = context.actor()
    return jsonify({"ok": True, "station": context.station_config(),
                    "session": {"operator": a["operator"], "dut": a["dut"]},
                    "instruments": instruments().summary(),
                    "readiness": _readiness()})


@bp.route("/api/session", methods=["GET", "POST"])
def session() -> Response:
    if request.method == "GET":
        a = context.actor()
        return jsonify({"ok": True, "operator": a["operator"], "dut": a["dut"]})
    body = _body()
    resp = jsonify({"ok": True})
    out = {}
    for key, cookie in (("operator", context.OPERATOR_COOKIE), ("dut", context.DUT_COOKIE)):
        if key in body:
            value = context.clean(body[key])
            out[key] = value
            if value:
                resp.set_cookie(cookie, value, samesite="Strict", max_age=365 * 86400, secure=request.is_secure)
            else:
                resp.delete_cookie(cookie)
    resp.set_data(json.dumps({"ok": True, **out}))
    return resp


@bp.route("/api/config", methods=["GET", "PUT"])
def config() -> Response:
    if request.method == "PUT":
        return jsonify({"ok": True, "station": context.save_station_config(_body())})
    return jsonify({"ok": True, "station": context.station_config()})


# ── health ──────────────────────────────────────────────────────────────

@bp.route("/api/selftest")
def selftest() -> Response:
    from pyontrust.gateway.selftests import providers, run_all

    tool = request.args.get("tool")
    if tool and tool not in providers():
        return _err(f"No self-test for {tool!r}", 404)
    return jsonify({"ok": True, **run_all(tool)})


@bp.route("/api/readiness")
def readiness() -> Response:
    from pyontrust.gateway.selftests import run_all

    return jsonify({"ok": True, **_readiness(run_all())})


# ── instruments ─────────────────────────────────────────────────────────

@bp.route("/api/instruments", methods=["GET", "POST"])
def instruments_index() -> Response:
    if request.method == "POST":
        try:
            return jsonify({"ok": True, "instrument": instruments().create(_body())}), 201
        except InstrumentError as exc:
            return _err(str(exc), 400)
    return jsonify({"ok": True, "instruments": instruments().list(), "summary": instruments().summary()})


@bp.route("/api/instruments/<inst_id>", methods=["PATCH", "DELETE"])
def instruments_item(inst_id: str) -> Response:
    try:
        if request.method == "DELETE":
            instruments().delete(inst_id)
            return jsonify({"ok": True})
        return jsonify({"ok": True, "instrument": instruments().update(inst_id, _body())})
    except KeyError:
        return _err("No such instrument", 404)
    except InstrumentError as exc:
        return _err(str(exc), 400)


# ── runs ────────────────────────────────────────────────────────────────

def _since_days(days: Any) -> str | None:
    try:
        d = int(days)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) - timedelta(days=d)).isoformat(timespec="seconds") if d > 0 else None


def _run_filters() -> dict[str, Any]:
    a = request.args
    return {"tool": a.get("tool") or None, "outcome": a.get("outcome") or None, "dut": a.get("dut") or None,
            "since": _since_days(a.get("days")) or a.get("since") or None,
            "limit": a.get("limit", 200, type=int)}


@bp.route("/api/runs")
def runs_index() -> Response:
    return jsonify({"ok": True, "runs": runs().list(**_run_filters())})


@bp.route("/api/runs/stats")
def runs_stats() -> Response:
    return jsonify({"ok": True, **runs().stats(_since_days(request.args.get("days", 30)))})


@bp.route("/api/runs/export.csv")
def runs_export() -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["id", "tool", "kind", "started_at", "finished_at", "duration_s", "operator", "dut", "station", "outcome"]
    w.writerow(cols + ["summary", "artifacts"])
    for r in runs().list(**{**_run_filters(), "limit": 5000}):
        w.writerow([r[c] for c in cols] + [json.dumps(r["summary"]), ";".join(r["artifacts"])])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=pyontrust_runs.csv"})


@bp.route("/api/runs/<run_id>")
def runs_item(run_id: str) -> Response:
    try:
        return jsonify({"ok": True, "run": runs().get(run_id)})
    except KeyError:
        return _err("No such run", 404)


# ── audit ───────────────────────────────────────────────────────────────

@bp.route("/api/audit")
def audit_index() -> Response:
    a = request.args
    return jsonify({"ok": True, "entries": audit_log().query(limit=a.get("limit", 200, type=int),
                                                              tool=a.get("tool") or None,
                                                              text=a.get("q") or None)})


@bp.route("/api/audit/verify")
def audit_verify() -> Response:
    return jsonify(audit_log().verify())


@bp.route("/api/audit/export.jsonl")
def audit_export() -> Response:
    lines = "\n".join(json.dumps(e, ensure_ascii=False) for e in reversed(audit_log().query(limit=5000)))
    return Response(lines + "\n", mimetype="application/x-ndjson",
                    headers={"Content-Disposition": "attachment; filename=pyontrust_audit.jsonl"})
