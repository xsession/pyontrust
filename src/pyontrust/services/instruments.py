"""Instrument register — what is on the bench and whether it is in calibration.

Each instrument: name, kind, model, serial, location, calibration due date,
certificate reference, notes.  Status per instrument:

* ``ok``        — calibration valid for more than ``DUE_SOON_DAYS``
* ``due_soon``  — due within ``DUE_SOON_DAYS``
* ``overdue``   — past due: measurements with it are not traceable
* ``no_cal``    — no due date recorded (e.g. not a measuring instrument)
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import date
from pathlib import Path
from typing import Any

DUE_SOON_DAYS = 30
FIELDS = ("name", "kind", "model", "serial", "location", "cal_due", "cal_cert", "notes")


class InstrumentError(ValueError):
    pass


def cal_status(cal_due: str | None, today: date | None = None) -> tuple[str, int | None]:
    """(status, days until due)."""
    if not cal_due:
        return "no_cal", None
    days = (date.fromisoformat(cal_due) - (today or date.today())).days
    return ("overdue" if days < 0 else "due_soon" if days <= DUE_SOON_DAYS else "ok"), days


class InstrumentRegister:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("instruments", [])
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"instruments": items}, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _validate(data: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
        item = dict(base or {})
        for f in FIELDS:
            if f in data:
                item[f] = str(data[f] or "").strip()[:200]
        if not item.get("name"):
            raise InstrumentError("name is required")
        if item.get("cal_due"):
            try:
                date.fromisoformat(item["cal_due"])
            except ValueError:
                raise InstrumentError("cal_due must be a date (YYYY-MM-DD)") from None
        return item

    def list(self) -> list[dict[str, Any]]:
        out = []
        for it in self._load():
            status, days = cal_status(it.get("cal_due"))
            out.append({**it, "status": status, "days_to_due": days})
        return out

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            item = self._validate(data)
            item["id"] = uuid.uuid4().hex[:8]
            items.append(item)
            self._save(items)
            return item

    def update(self, inst_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            for i, it in enumerate(items):
                if it.get("id") == inst_id:
                    items[i] = {**self._validate(data, it), "id": inst_id}
                    self._save(items)
                    return items[i]
        raise KeyError(inst_id)

    def delete(self, inst_id: str) -> None:
        with self._lock:
            items = self._load()
            kept = [it for it in items if it.get("id") != inst_id]
            if len(kept) == len(items):
                raise KeyError(inst_id)
            self._save(kept)

    def summary(self) -> dict[str, int]:
        counts = {"ok": 0, "due_soon": 0, "overdue": 0, "no_cal": 0}
        for it in self.list():
            counts[it["status"]] += 1
        return counts
