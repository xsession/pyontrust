"""Artifact storage, indexing and search service.

Manages the ``artifacts/`` directory tree produced by test runs.
Provides listing, searching, and individual artifact retrieval for
the gateway's ``/artifacts/`` Blueprint.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pyontrust.services.artifact_service")


@dataclass
class ArtifactEntry:
    """Lightweight index entry for one test-run artifact directory."""

    run_dir: str
    test_name: str = ""
    run_id: str = ""
    created: float = 0.0
    has_trace: bool = False
    has_summary: bool = False
    has_report: bool = False
    has_verdict: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


class ArtifactService:
    """Indexes and serves artifacts from the artifact root directory.

    Usage::

        svc = ArtifactService("artifacts")
        entries = svc.scan()          # re-index
        entry   = svc.get("my_test_20260301_120000")
        content = svc.read_file("my_test_20260301_120000", "summary.json")
    """

    def __init__(self, root: str | pathlib.Path = "artifacts") -> None:
        self._root = pathlib.Path(root)
        self._index: dict[str, ArtifactEntry] = {}

    @property
    def root(self) -> pathlib.Path:
        return self._root

    # ── Scanning ────────────────────────────────────────────────────

    def scan(self) -> list[ArtifactEntry]:
        """Walk the artifact root and build an in-memory index.

        Each direct child directory that contains ``meta.json`` is
        treated as a test-run artifact.
        """
        self._index.clear()
        if not self._root.is_dir():
            logger.debug("Artifact root does not exist: %s", self._root)
            return []

        entries: list[ArtifactEntry] = []
        for child in sorted(self._root.iterdir()):
            if not child.is_dir():
                continue
            meta_path = child / "meta.json"
            entry = ArtifactEntry(run_dir=str(child))
            entry.run_id = child.name

            # Parse meta.json if present
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    entry.meta = meta
                    test_info = meta.get("test", {})
                    entry.test_name = test_info.get("name", child.name)
                except Exception:
                    entry.test_name = child.name
            else:
                entry.test_name = child.name

            try:
                entry.created = child.stat().st_ctime
            except OSError:
                pass

            entry.has_trace = (child / "power_trace.csv").is_file()
            entry.has_summary = (child / "summary.json").is_file()
            entry.has_report = (child / "report.md").is_file()
            entry.has_verdict = (child / "verdict.json").is_file()

            self._index[entry.run_id] = entry
            entries.append(entry)

        # Sort newest first
        entries.sort(key=lambda e: e.created, reverse=True)
        logger.info("Indexed %d artifact(s) in %s", len(entries), self._root)
        return entries

    # ── Retrieval ───────────────────────────────────────────────────

    def list_entries(
        self, *, limit: int = 100, name_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return index entries as JSON-serialisable dicts."""
        if not self._index:
            self.scan()

        entries = list(self._index.values())
        if name_filter:
            q = name_filter.lower()
            entries = [e for e in entries if q in e.test_name.lower() or q in e.run_id.lower()]

        entries.sort(key=lambda e: e.created, reverse=True)
        return [
            {
                "run_id": e.run_id,
                "test_name": e.test_name,
                "created": e.created,
                "has_trace": e.has_trace,
                "has_summary": e.has_summary,
                "has_report": e.has_report,
                "has_verdict": e.has_verdict,
            }
            for e in entries[:limit]
        ]

    def get(self, run_id: str) -> ArtifactEntry | None:
        """Get a single entry by run-ID."""
        if not self._index:
            self.scan()
        return self._index.get(run_id)

    def read_file(self, run_id: str, filename: str) -> str | None:
        """Read a text file from a run's artifact directory.

        Returns ``None`` if not found.  Prevents path traversal.
        """
        entry = self.get(run_id)
        if entry is None:
            return None
        run_dir = pathlib.Path(entry.run_dir)
        target = (run_dir / filename).resolve()
        # Path-traversal guard
        if not str(target).startswith(str(run_dir.resolve())):
            logger.warning("Path traversal attempt: %s / %s", run_id, filename)
            return None
        if not target.is_file():
            return None
        try:
            return target.read_text(encoding="utf-8")
        except Exception:
            return None

    def read_binary(self, run_id: str, filename: str) -> bytes | None:
        """Read a binary file from a run's artifact directory."""
        entry = self.get(run_id)
        if entry is None:
            return None
        run_dir = pathlib.Path(entry.run_dir)
        target = (run_dir / filename).resolve()
        if not str(target).startswith(str(run_dir.resolve())):
            return None
        if not target.is_file():
            return None
        try:
            return target.read_bytes()
        except Exception:
            return None

    def list_files(self, run_id: str) -> list[dict[str, Any]]:
        """List all files in a run's artifact directory."""
        entry = self.get(run_id)
        if entry is None:
            return []
        run_dir = pathlib.Path(entry.run_dir)
        if not run_dir.is_dir():
            return []

        files: list[dict[str, Any]] = []
        for root, _dirs, filenames in os.walk(run_dir):
            for fname in sorted(filenames):
                fpath = pathlib.Path(root) / fname
                rel = fpath.relative_to(run_dir)
                try:
                    sz = fpath.stat().st_size
                except OSError:
                    sz = 0
                files.append({
                    "name": str(rel),
                    "size": sz,
                    "ext": fpath.suffix,
                })
        return files

    def delete(self, run_id: str) -> bool:
        """Delete an artifact directory.  Returns True on success."""
        entry = self.get(run_id)
        if entry is None:
            return False
        import shutil
        try:
            shutil.rmtree(entry.run_dir)
            self._index.pop(run_id, None)
            return True
        except Exception:
            logger.exception("Failed to delete artifact %s", run_id)
            return False
