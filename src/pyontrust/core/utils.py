"""Shared utility functions — stdlib only."""

from __future__ import annotations

import datetime
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def utc_timestamp_id() -> str:
    """Generate a UTC timestamp string for unique IDs (e.g. 20260307T153012Z)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_windows() -> bool:
    return os.name == "nt"


def is_linux() -> bool:
    return os.name == "posix" and os.uname().sysname.lower() == "linux"  # type: ignore[attr-defined]


def creationflags_no_window() -> int:
    """Windows-only: avoid opening a console window for subprocesses."""
    if not is_windows():
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class EnvPaths:
    """Represents PATH-like environment updates."""

    path: tuple[str, ...] = ()
    ld_library_path: tuple[str, ...] = ()

    def apply(self, base: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ if base is None else base)

        if self.path:
            cur = env.get("PATH", "")
            env["PATH"] = _prepend_paths(cur, self.path)

        if self.ld_library_path:
            key = "LD_LIBRARY_PATH"
            cur = env.get(key, "")
            env[key] = _prepend_paths(cur, self.ld_library_path)

        return env


def _prepend_paths(current: str, new_paths: Iterable[str]) -> str:
    parts = [p for p in current.split(os.pathsep) if p]
    out: list[str] = []
    for p in new_paths:
        if p and p not in out:
            out.append(p)
    for p in parts:
        if p not in out:
            out.append(p)
    return os.pathsep.join(out)


def repo_root_from(start: Path) -> Path:
    """Walk upward to find the repository root (heuristic: contains README.md)."""
    cur = start.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "README.md").exists():
            return parent
    return cur
