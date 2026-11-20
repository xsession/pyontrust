"""Run registry — one record per test / measurement / capture run.

Every tool reports its runs here (who, which DUT, which station, when, what
outcome, what artifacts), giving a single traceable history and the data for
yield / SPC statistics.  SQLite (stdlib) with WAL so the UI can read while
runs are written.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

OUTCOMES = ("running", "pass", "fail", "error", "aborted", "done")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    tool        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    duration_s  REAL,
    operator    TEXT NOT NULL DEFAULT '',
    dut         TEXT NOT NULL DEFAULT '',
    station     TEXT NOT NULL DEFAULT '',
    outcome     TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '{}',
    artifacts   TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS runs_tool ON runs(tool, started_at);
CREATE INDEX IF NOT EXISTS runs_dut ON runs(dut);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── write ───────────────────────────────────────────────────────────
    def start(self, tool: str, kind: str, actor: dict[str, str] | None = None,
              summary: dict[str, Any] | None = None) -> str:
        actor = actor or {}
        run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO runs (id, tool, kind, started_at, operator, dut, station, outcome, summary) "
                      "VALUES (?,?,?,?,?,?,?,?,?)",
                      (run_id, tool, kind, _now(), actor.get("operator", ""), actor.get("dut", ""),
                       actor.get("station", ""), "running", json.dumps(summary or {}, default=str)))
        return run_id

    def finish(self, run_id: str, outcome: str, summary: dict[str, Any] | None = None,
               artifacts: list[str] | None = None) -> None:
        if outcome not in OUTCOMES or outcome == "running":
            raise ValueError(f"invalid outcome {outcome!r}")
        with self._lock, self._conn() as c:
            row = c.execute("SELECT started_at, summary FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            merged = {**json.loads(row["summary"] or "{}"), **(summary or {})}
            started = datetime.fromisoformat(row["started_at"])
            duration = (datetime.now(timezone.utc) - started).total_seconds()
            c.execute("UPDATE runs SET finished_at=?, duration_s=?, outcome=?, summary=?, artifacts=? WHERE id=?",
                      (_now(), round(duration, 2), outcome, json.dumps(merged, default=str),
                       json.dumps(artifacts or []), run_id))

    def record(self, tool: str, kind: str, outcome: str, actor: dict[str, str] | None = None,
               summary: dict[str, Any] | None = None, artifacts: list[str] | None = None) -> str:
        """Start + finish in one call (instant runs)."""
        run_id = self.start(tool, kind, actor, summary)
        self.finish(run_id, outcome, None, artifacts)
        return run_id

    def mark_interrupted(self) -> int:
        """Runs still 'running' from a previous process ended abnormally."""
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE runs SET outcome='error', finished_at=?, "
                            "summary=json_set(summary, '$.error', 'gateway stopped during run') "
                            "WHERE outcome='running'", (_now(),))
            return cur.rowcount

    # ── read ────────────────────────────────────────────────────────────
    @staticmethod
    def _row(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["summary"] = json.loads(d["summary"] or "{}")
        d["artifacts"] = json.loads(d["artifacts"] or "[]")
        return d

    def list(self, limit: int = 200, tool: str | None = None, outcome: str | None = None,
             dut: str | None = None, since: str | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM runs WHERE 1=1", []
        for col, val in (("tool", tool), ("outcome", outcome)):
            if val:
                sql += f" AND {col}=?"
                args.append(val)
        if dut:
            sql += " AND dut LIKE ?"
            args.append(f"%{dut}%")
        if since:
            sql += " AND started_at>=?"
            args.append(since)
        sql += " ORDER BY started_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 5000)))
        with self._conn() as c:
            return [self._row(r) for r in c.execute(sql, args)]

    def get(self, run_id: str) -> dict[str, Any]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if r is None:
            raise KeyError(run_id)
        return self._row(r)

    def stats(self, since: str | None = None) -> dict[str, Any]:
        """Per tool / kind: counts by outcome and first-pass yield (pass / (pass+fail))."""
        sql = "SELECT tool, kind, outcome, COUNT(*) n FROM runs"
        args: list[Any] = []
        if since:
            sql += " WHERE started_at>=?"
            args.append(since)
        sql += " GROUP BY tool, kind, outcome"
        groups: dict[tuple[str, str], dict[str, int]] = {}
        with self._conn() as c:
            for r in c.execute(sql, args):
                groups.setdefault((r["tool"], r["kind"]), {})[r["outcome"]] = r["n"]
        out = []
        for (tool, kind), counts in sorted(groups.items()):
            judged = counts.get("pass", 0) + counts.get("fail", 0)
            out.append({"tool": tool, "kind": kind, "counts": counts, "total": sum(counts.values()),
                        "yield": round(counts.get("pass", 0) / judged, 4) if judged else None})
        return {"since": since, "groups": out}
