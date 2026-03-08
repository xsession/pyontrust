"""Profile / layout / limit CRUD service.

Manages the ``profiles/``, ``benches/``, and ``limits/`` directories
and provides read/write/list operations for JSON configuration files
used by the test framework and gateway.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

logger = logging.getLogger("pyontrust.services.config_service")


class ConfigService:
    """CRUD service for JSON config files (profiles, limits, benches).

    Usage::

        svc = ConfigService(base_dir=".")
        profiles = svc.list_profiles()
        data     = svc.read_profile("sleep_current.json")
        svc.write_profile("sleep_current.json", data)
    """

    def __init__(
        self,
        base_dir: str | pathlib.Path = ".",
        profiles_subdir: str = "profiles",
        benches_subdir: str = "benches",
        limits_subdir: str = "limits",
    ) -> None:
        self._base = pathlib.Path(base_dir)
        self._profiles_dir = self._base / profiles_subdir
        self._benches_dir = self._base / benches_subdir
        self._limits_dir = self._base / limits_subdir

    # ── Profiles ────────────────────────────────────────────────────

    def list_profiles(self) -> list[dict[str, Any]]:
        return self._list_json(self._profiles_dir)

    def read_profile(self, name: str) -> dict[str, Any] | None:
        return self._read_json(self._profiles_dir, name)

    def write_profile(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._write_json(self._profiles_dir, name, data)

    def delete_profile(self, name: str) -> bool:
        return self._delete_json(self._profiles_dir, name)

    # ── Benches ─────────────────────────────────────────────────────

    def list_benches(self) -> list[dict[str, Any]]:
        return self._list_json(self._benches_dir)

    def read_bench(self, name: str) -> dict[str, Any] | None:
        return self._read_json(self._benches_dir, name)

    def write_bench(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._write_json(self._benches_dir, name, data)

    def delete_bench(self, name: str) -> bool:
        return self._delete_json(self._benches_dir, name)

    # ── Limits ──────────────────────────────────────────────────────

    def list_limits(self) -> list[dict[str, Any]]:
        return self._list_json(self._limits_dir)

    def read_limits(self, name: str) -> dict[str, Any] | None:
        return self._read_json(self._limits_dir, name)

    def write_limits(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._write_json(self._limits_dir, name, data)

    def delete_limits(self, name: str) -> bool:
        return self._delete_json(self._limits_dir, name)

    # ── Generic internals ───────────────────────────────────────────

    @staticmethod
    def _safe_name(name: str) -> str:
        """Sanitise filename to prevent path traversal."""
        base = pathlib.PurePosixPath(name).name
        if not base:
            base = "untitled.json"
        if not base.endswith(".json"):
            base += ".json"
        return base

    def _list_json(self, directory: pathlib.Path) -> list[dict[str, Any]]:
        if not directory.is_dir():
            return []
        results: list[dict[str, Any]] = []
        for f in sorted(directory.iterdir()):
            if f.suffix.lower() != ".json" or not f.is_file():
                continue
            try:
                sz = f.stat().st_size
                mtime = f.stat().st_mtime
            except OSError:
                sz, mtime = 0, 0.0
            results.append({
                "name": f.name,
                "path": str(f),
                "size": sz,
                "mtime": mtime,
            })
        return results

    def _read_json(
        self, directory: pathlib.Path, name: str,
    ) -> dict[str, Any] | None:
        safe = self._safe_name(name)
        target = (directory / safe).resolve()
        if not str(target).startswith(str(directory.resolve())):
            logger.warning("Path traversal blocked: %s", name)
            return None
        if not target.is_file():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Failed to read %s", target, exc_info=True)
            return None

    def _write_json(
        self, directory: pathlib.Path, name: str, data: dict[str, Any],
    ) -> dict[str, Any]:
        safe = self._safe_name(name)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / safe
        try:
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            try:
                tmp.replace(target)
            except Exception:
                target.write_text(json.dumps(data, indent=2), encoding="utf-8")
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
            return {"saved": True, "name": safe, "path": str(target)}
        except Exception as exc:
            return {"error": str(exc)}

    def _delete_json(self, directory: pathlib.Path, name: str) -> bool:
        safe = self._safe_name(name)
        target = (directory / safe).resolve()
        if not str(target).startswith(str(directory.resolve())):
            return False
        if not target.is_file():
            return False
        try:
            target.unlink()
            return True
        except Exception:
            return False
