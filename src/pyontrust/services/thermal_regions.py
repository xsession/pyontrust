"""Thermal regions — the single source of truth for "what to watch".

A region is a point or rectangle on the thermal image (native sensor pixels)
with a unique name and warn / max limits.  The same list drives everything:
the live overlay and readings, measurement zones and long-term tracking, so
what the user sees on the image is exactly what gets measured and logged.

Persisted as JSON (``~/.pyontrust/thermal_regions.json`` or
``$PYONTRUST_THERMAL_REGIONS``) so it survives restarts and is shared by
every browser / device talking to the gateway.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("pyontrust.services.thermal_regions")

POINT_HALF = 1          # a point measures its 3x3 neighbourhood
MAX_REGIONS = 64
_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,24}$")   # also used as CSV column prefix


def default_path() -> Path:
    env = os.environ.get("PYONTRUST_THERMAL_REGIONS")
    return Path(env) if env else Path.home() / ".pyontrust" / "thermal_regions.json"


@dataclass
class Region:
    id: str
    name: str
    kind: str          # "point" | "rect"
    x: int
    y: int
    w: int = 1
    h: int = 1
    warn_c: float = 60.0
    max_c: float = 85.0

    def bounds(self) -> tuple[int, int, int, int]:
        """(x, y, w, h) of the measured area (points -> 3x3 neighbourhood)."""
        if self.kind == "point":
            return (self.x - POINT_HALF, self.y - POINT_HALF, 2 * POINT_HALF + 1, 2 * POINT_HALF + 1)
        return (self.x, self.y, self.w, self.h)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RegionError(ValueError):
    """Invalid region data (HTTP 400)."""


class RegionStore:
    """Thread-safe, persisted list of :class:`Region`."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._regions: list[Region] | None = None   # lazy load

    @property
    def path(self) -> Path:
        return self._path or default_path()

    # ── queries ─────────────────────────────────────────────────────────

    def list(self) -> list[Region]:
        with self._lock:
            return list(self._load())

    def get(self, region_id: str) -> Region:
        for r in self.list():
            if r.id == region_id:
                return r
        raise KeyError(region_id)

    # ── mutations ───────────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> Region:
        with self._lock:
            regions = self._load()
            if len(regions) >= MAX_REGIONS:
                raise RegionError(f"At most {MAX_REGIONS} regions")
            kind = str(data.get("kind", "rect"))
            name = data.get("name") or self._next_name(regions, kind)
            region = self._validate(Region(id=uuid.uuid4().hex[:8], name=str(name), kind=kind,
                                           x=0, y=0), data, regions)
            regions.append(region)
            self._save(regions)
            return region

    def update(self, region_id: str, patch: dict[str, Any]) -> Region:
        with self._lock:
            regions = self._load()
            for i, r in enumerate(regions):
                if r.id == region_id:
                    others = [o for o in regions if o.id != region_id]
                    regions[i] = self._validate(Region(**r.to_dict()), patch, others)
                    self._save(regions)
                    return regions[i]
        raise KeyError(region_id)

    def delete(self, region_id: str) -> None:
        with self._lock:
            regions = self._load()
            kept = [r for r in regions if r.id != region_id]
            if len(kept) == len(regions):
                raise KeyError(region_id)
            self._save(kept)

    def clear(self) -> None:
        with self._lock:
            self._save([])

    # ── conversions for the consumers ───────────────────────────────────

    def measurement_zones(self) -> list[dict[str, Any]]:
        out = []
        for r in self.list():
            x, y, w, h = r.bounds()
            out.append({"name": r.name, "x": max(0, x), "y": max(0, y), "width": w, "height": h,
                        "warn_temp_c": r.warn_c, "max_temp_c": r.max_c})
        return out

    def tracking_selections(self) -> list[dict[str, Any]]:
        return [{"name": r.name, "type": "point" if r.kind == "point" else "patch",
                 "x": r.x, "y": r.y, "w": r.w, "h": r.h} for r in self.list()]

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _next_name(regions: list[Region], kind: str) -> str:
        prefix = "P" if kind == "point" else "R"
        i = 1
        while any(r.name == f"{prefix}{i}" for r in regions):
            i += 1
        return f"{prefix}{i}"

    @staticmethod
    def _validate(region: Region, data: dict[str, Any], others: list[Region]) -> Region:
        if not isinstance(data, dict):
            raise RegionError("Region data must be an object")
        r = region
        try:
            if "name" in data:
                r.name = str(data["name"]).strip()
            if "kind" in data:
                r.kind = str(data["kind"])
            for key in ("x", "y", "w", "h"):
                if key in data:
                    setattr(r, key, int(round(float(data[key]))))
            for key in ("warn_c", "max_c"):
                if key in data:
                    setattr(r, key, float(data[key]))
        except (TypeError, ValueError) as exc:
            raise RegionError(f"Invalid number: {exc}") from None
        if r.kind not in ("point", "rect"):
            raise RegionError("kind must be 'point' or 'rect'")
        if not _NAME_RE.match(r.name):
            raise RegionError("Name: 1–24 characters, letters / digits / _ . - only")
        if any(o.name == r.name for o in others):
            raise RegionError(f"A region named {r.name!r} already exists")
        if r.x < 0 or r.y < 0:
            raise RegionError("x / y must be ≥ 0")
        if r.kind == "point":
            r.w = r.h = 1
        elif r.w < 2 or r.h < 2:
            raise RegionError("Rectangles must be at least 2×2 px")
        if not -60.0 <= r.warn_c <= 400.0 or not -60.0 <= r.max_c <= 400.0:
            raise RegionError("Limits must be between -60 and 400 °C")
        if r.warn_c > r.max_c:
            raise RegionError("Warn limit must not exceed the max limit")
        return r

    def _load(self) -> list[Region]:
        if self._regions is None:
            self._regions = []
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                for item in raw.get("regions", []):
                    try:
                        self._regions.append(Region(**{k: item[k] for k in Region.__dataclass_fields__
                                                        if k in item}))
                    except TypeError:
                        logger.warning("Skipping malformed region %r", item)
            except FileNotFoundError:
                pass
            except (OSError, ValueError) as exc:
                logger.warning("Cannot read %s: %s", self.path, exc)
        return self._regions

    def _save(self, regions: list[Region]) -> None:
        self._regions = regions
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"regions": [r.to_dict() for r in regions]}, indent=2),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:  # pragma: no cover - disk issues
            logger.warning("Cannot save regions to %s: %s", self.path, exc)


def region_readings(frame: Any, regions: list[Region]) -> dict[str, dict[str, Any]]:
    """Live min / mean / max °C and limit level per region id."""
    from pyontrust.services.thermal_live import zone_stats

    zones = []
    for r in regions:
        x, y, w, h = r.bounds()
        zones.append({"name": r.id, "x": x, "y": y, "w": w, "h": h})
    out: dict[str, dict[str, Any]] = {}
    for r, s in zip(regions, zone_stats(frame, zones)):
        if "max_c" in s:
            s["level"] = "max" if s["max_c"] >= r.max_c else "warn" if s["max_c"] >= r.warn_c else "ok"
        s.pop("name", None)
        out[r.id] = s
    return out
