"""Persistent one-point calibration for the Seek Thermal camera.

The Seek Compact reports raw sensor counts; absolute temperature is an
estimate until calibrated against a known-temperature reference (the same
approach as Seek's own apps).  This module stores a single offset in °C:

    calibrated_temp = raw_estimate + offset

where ``offset = reference_c − median(raw_frame)`` at calibration time.

The value persists across gateway restarts and applies to every consumer
that grabs frames through :class:`SeekThermalCamera` (FlowLab blocks, the
thermal measurement dashboard, services).

File location: ``~/.pyontrust/thermal_calibration.json``
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("pyontrust.instruments.thermal_calibration")

_LOCK = threading.Lock()


def calibration_file() -> Path:
    """Path of the persistent calibration file."""
    return Path(os.environ.get(
        "PYONTRUST_THERMAL_CAL_FILE",
        str(Path.home() / ".pyontrust" / "thermal_calibration.json"),
    ))


def _read_raw() -> dict[str, Any]:
    path = calibration_file()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def load_offset_c() -> float:
    """Return the stored calibration offset in °C (0.0 if none)."""
    try:
        return float(_read_raw().get("offset_c", 0.0))
    except (TypeError, ValueError):
        return 0.0


def load_info() -> dict[str, Any]:
    """Return the full calibration record (offset + provenance)."""
    data = _read_raw()
    if not data:
        return {"calibrated": False, "offset_c": 0.0}
    out = {
        "calibrated": True,
        "offset_c": float(data.get("offset_c", 0.0)),
        "reference_c": data.get("reference_c"),
        "scene_median_c": data.get("scene_median_c"),
        "set_at": data.get("set_at"),
    }
    return out


def save_offset(offset_c: float, reference_c: float | None = None,
                scene_median_c: float | None = None) -> dict[str, Any]:
    """Persist a new calibration offset. Returns the stored record."""
    import datetime

    path = calibration_file()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "offset_c": round(float(offset_c), 3),
            "reference_c": float(reference_c) if reference_c is not None else None,
            "scene_median_c": (round(float(scene_median_c), 1)
                               if scene_median_c is not None else None),
            "set_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
    logger.info("Thermal calibration saved: offset=%+.2f C (ref=%s)",
                record["offset_c"], record["reference_c"])
    return load_info()


def clear() -> dict[str, Any]:
    """Remove the stored calibration (offset back to zero)."""
    path = calibration_file()
    with _LOCK:
        try:
            path.unlink()
        except OSError:
            pass
    logger.info("Thermal calibration cleared")
    return {"calibrated": False, "offset_c": 0.0}
