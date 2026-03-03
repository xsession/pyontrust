#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Project lifecycle manager — replaces the PySide6 App singleton + Project.

Wraps CoreDB, FileDB, and project-level settings without any Qt dependency.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure OpenFOAM-compatible locale (same as desktop main.py)
# ---------------------------------------------------------------------------
os.environ.setdefault("LC_NUMERIC", "C")


class _ProjectHandle:
    """Lightweight struct holding one open project's state."""

    def __init__(self, path: Path, coredb, filedb=None):
        self.path = path
        self.name = path.name
        self.coredb = coredb
        self.filedb = filedb
        self.uuid = str(uuid.uuid4())


class ProjectManager:
    """Replaces the module-level ``app = App()`` singleton from PySide6.

    Usage from Flask:
        from domain.project_manager import project_manager
        db = project_manager.coredb   # → _CoreDB instance
    """

    def __init__(self):
        self._current: Optional[_ProjectHandle] = None
        self._recent: list[str] = []

    # ── predicates ────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self._current is not None

    def ensure_open(self):
        if not self._current:
            raise RuntimeError("No project is currently open")

    # ── accessors ─────────────────────────────────────────────────────────

    @property
    def current(self) -> _ProjectHandle:
        self.ensure_open()
        return self._current

    @property
    def coredb(self):
        """Return the baramFlow CoreDB singleton (lxml + XSD)."""
        self.ensure_open()
        # CoreDB is a module-level singleton accessed via coredb.CoreDB()
        from baramFlow.coredb import coredb as coredb_mod
        return coredb_mod.CoreDB()

    @property
    def project_path(self) -> Path:
        return self.current.path

    # ── lifecycle ─────────────────────────────────────────────────────────

    def open(self, path: str) -> dict:
        """Open an existing BaramFlow project (.bm HDF5 file or directory containing one)."""
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Project path does not exist: {p}")

        # If user pointed to a directory, look for a .bm file inside
        if p.is_dir():
            candidates = list(p.glob("*.bm"))
            if not candidates:
                raise FileNotFoundError(f"No .bm project file found in {p}")
            p = candidates[0]

        from baramFlow.coredb import coredb as coredb_mod

        # Destroy previous DB if any
        try:
            coredb_mod.destroy()
        except Exception:
            pass

        # Load project — the HDF5 file contains the XML config
        coredb_mod.loadDB(str(p))
        db = coredb_mod.CoreDB()

        self._current = _ProjectHandle(path=p, coredb=db)
        self._add_recent(str(p))
        log.info("Opened project: %s", p)
        return self._summary()

    def create(self, path: str) -> dict:
        """Create a new (empty) BaramFlow project.

        *path* can be:
          - A full file path  (e.g. ``C:/projects/mycase.bm``)
          - A directory path  (e.g. ``C:/projects/mycase``) — a ``.bm`` file
            will be created inside it with the directory's name.
        """
        p = Path(path).resolve()

        # If the path has no .bm suffix, treat it as a directory and
        # create the HDF5 file inside it.
        if p.suffix != ".bm":
            project_dir = p
            project_dir.mkdir(parents=True, exist_ok=True)
            p = project_dir / (project_dir.name + ".bm")
        else:
            p.parent.mkdir(parents=True, exist_ok=True)

        from baramFlow.coredb import coredb as coredb_mod

        try:
            coredb_mod.destroy()
        except Exception:
            pass

        coredb_mod.createDB()
        db = coredb_mod.CoreDB()

        self._current = _ProjectHandle(path=p, coredb=db)
        # Persist immediately — saveAs writes an HDF5 file
        db.saveAs(str(p))
        self._add_recent(str(p))
        log.info("Created new project: %s", p)
        return self._summary()

    def save(self):
        """Save current project to disk (HDF5 .bm file)."""
        self.ensure_open()
        p = self._current.path
        # Ensure parent directory exists (safety net)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.coredb.save(str(p))
        log.info("Saved project: %s", p)

    def close(self):
        from baramFlow.coredb import coredb as coredb_mod
        try:
            coredb_mod.destroy()
        except Exception:
            pass
        self._current = None
        log.info("Project closed")

    # ── recent projects ───────────────────────────────────────────────────

    def list_recent(self) -> list[str]:
        return list(self._recent)

    def _add_recent(self, path: str):
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:20]

    # ── helpers ───────────────────────────────────────────────────────────

    def _summary(self) -> dict:
        if not self._current:
            return {}
        return {
            "path": str(self._current.path),
            "name": self._current.name,
            "uuid": self._current.uuid,
        }


# ---------------------------------------------------------------------------
# Module-level singleton (like ``app = App()`` in baramFlow)
# ---------------------------------------------------------------------------
project_manager = ProjectManager()
