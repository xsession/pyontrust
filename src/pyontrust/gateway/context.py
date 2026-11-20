"""Who is acting: operator, device under test, station, client.

The operator and the current DUT serial are chosen once in the shell and
kept in cookies (``pyontrust_operator`` / ``pyontrust_dut``); API clients may
send ``X-Operator`` / ``X-DUT`` headers instead.  Every audit entry and run
record carries this context.
"""
from __future__ import annotations

import json
import os
import re
import socket
from pathlib import Path
from typing import Any

OPERATOR_COOKIE = "pyontrust_operator"
DUT_COOKIE = "pyontrust_dut"
_CLEAN = re.compile(r"[^\w .@+\-/#:]")


def data_dir() -> Path:
    """Persistent station data (audit log, runs DB, instruments, station config)."""
    d = Path(os.environ.get("PYONTRUST_DATA_DIR", Path.home() / ".pyontrust"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def clean(value: Any, limit: int = 64) -> str:
    """Printable, bounded identifier (safe for logs, CSV and HTML)."""
    return _CLEAN.sub("", str(value or "")).strip()[:limit]


def station_config() -> dict[str, Any]:
    path = data_dir() / "station.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("name", socket.gethostname())
    cfg.setdefault("location", "")
    return cfg


def save_station_config(cfg: dict[str, Any]) -> dict[str, Any]:
    current = station_config()
    current.update({k: clean(v, 80) for k, v in cfg.items() if k in ("name", "location")})
    (data_dir() / "station.json").write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def actor() -> dict[str, str]:
    """Context of the current request (empty strings outside a request)."""
    from flask import has_request_context, request

    station = station_config()["name"]
    if not has_request_context():
        return {"operator": "", "dut": "", "station": station, "client": ""}
    return {
        "operator": clean(request.headers.get("X-Operator") or request.cookies.get(OPERATOR_COOKIE)),
        "dut": clean(request.headers.get("X-DUT") or request.cookies.get(DUT_COOKIE)),
        "station": station,
        "client": clean(request.remote_addr),
    }
