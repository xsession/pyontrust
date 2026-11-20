"""Append-only, hash-chained audit log of actions on the station.

One JSON object per line in monthly files (``audit-YYYY-MM.jsonl``).  Each
entry stores ``prev`` (hash of the previous entry) and ``hash`` (SHA-256 of
its own canonical JSON incl. ``prev``), so editing, inserting or deleting an
entry breaks the chain and :meth:`AuditLog.verify` reports where.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger("pyontrust.services.audit")

GENESIS = "0" * 64
_SECRET_KEYS = ("token", "password", "secret", "passwd", "api_key", "authorization")


def _canonical(entry: dict[str, Any]) -> bytes:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def redact(value: Any, depth: int = 0) -> Any:
    """Bounded, secret-free summary of a request body for the log."""
    if depth > 3:
        return "…"
    if isinstance(value, dict):
        out = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= 25:
                out["…"] = f"{len(value) - 25} more keys"
                break
            out[str(k)[:40]] = "***" if any(s in str(k).lower() for s in _SECRET_KEYS) else redact(v, depth + 1)
        return out
    if isinstance(value, list):
        items = [redact(v, depth + 1) for v in value[:10]]
        return items + [f"… {len(value) - 10} more"] if len(value) > 10 else items
    if isinstance(value, str):
        return value if len(value) <= 120 else value[:117] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:120]


class AuditLog:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash: str | None = None
        self._seq = 0

    # ── write ───────────────────────────────────────────────────────────
    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._last_hash is None:
                self._recover_tail()
            now = time.time()
            entry = {
                "seq": self._seq + 1,
                "ts": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="milliseconds"),
                **{k: v for k, v in event.items() if k not in ("seq", "ts", "prev", "hash")},
                "prev": self._last_hash,
            }
            entry["hash"] = hashlib.sha256(_canonical(entry)).hexdigest()
            path = self.dir / f"audit-{entry['ts'][:7]}.jsonl"
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                fh.flush()
            self._last_hash, self._seq = entry["hash"], entry["seq"]
            return entry

    def _recover_tail(self) -> None:
        last = None
        for entry in self._iter_files():
            last = entry
        self._last_hash = last["hash"] if last else GENESIS
        self._seq = int(last["seq"]) if last else 0

    # ── read ────────────────────────────────────────────────────────────
    def _files(self) -> list[Path]:
        return sorted(self.dir.glob("audit-*.jsonl"))

    def _iter_files(self) -> Iterator[dict[str, Any]]:
        for path in self._files():
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except ValueError:
                            yield {"_corrupt": line[:200], "_file": path.name}

    def query(self, limit: int = 200, tool: str | None = None, text: str | None = None,
              since: str | None = None) -> list[dict[str, Any]]:
        """Newest first, filtered."""
        out: list[dict[str, Any]] = []
        needle = (text or "").lower()
        for entry in self._iter_files():
            if "_corrupt" in entry:
                continue
            if tool and entry.get("tool") != tool:
                continue
            if since and entry.get("ts", "") < since:
                continue
            if needle and needle not in json.dumps(entry, ensure_ascii=False).lower():
                continue
            out.append(entry)
        return list(reversed(out))[:max(1, min(limit, 5000))]

    def verify(self) -> dict[str, Any]:
        """Re-hash the whole chain; report the first broken entry if any."""
        prev, count = GENESIS, 0
        for entry in self._iter_files():
            count += 1
            if "_corrupt" in entry:
                return {"ok": False, "entries": count, "error": f"unreadable line in {entry['_file']}"}
            if entry.get("prev") != prev:
                return {"ok": False, "entries": count, "seq": entry.get("seq"),
                        "error": "chain broken (entry missing, inserted or reordered)"}
            if hashlib.sha256(_canonical(entry)).hexdigest() != entry.get("hash"):
                return {"ok": False, "entries": count, "seq": entry.get("seq"),
                        "error": "entry content was modified"}
            prev = entry["hash"]
        return {"ok": True, "entries": count, "head": prev}
