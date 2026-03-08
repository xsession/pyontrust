"""Recorder registry and discovery.

Mirrors the instrument registry pattern for background recorders.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger("pyontrust.recorders")

_BUILTIN_FACTORIES: dict[str, str] = {
    "process": "pyontrust.recorders.process:create",
    "hackrf_iq": "pyontrust.recorders.hackrf_iq:create",
    "ffmpeg_webcam": "pyontrust.recorders.ffmpeg_webcam:create",
    "pcan_can": "pyontrust.recorders.pcan_can:create",
    "nrf52840_dongle": "pyontrust.recorders.nrf52840_dongle:create",
    "wireshark_tshark": "pyontrust.recorders.process:create_tshark",
    "aoi": "pyontrust.recorders.aoi:create",
    "thermal": "pyontrust.recorders.thermal:create",
}


def create_recorder(type_name: str, config: dict[str, Any]) -> Any:
    """Instantiate a recorder by type name and config dict."""
    # Try entry points first
    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            group = list(eps.select(group="pyontrust.recorders", name=type_name))
        else:
            group = [ep for ep in eps.get("pyontrust.recorders", []) if ep.name == type_name]

        if group:
            factory = group[0].load()
            return factory(config)
    except Exception:
        pass

    # Fallback to builtin
    if type_name in _BUILTIN_FACTORIES:
        module_path, func_name = _BUILTIN_FACTORIES[type_name].rsplit(":", 1)
        mod = importlib.import_module(module_path)
        factory = getattr(mod, func_name)
        return factory(config)

    raise ValueError(f"Unknown recorder type: {type_name}")


def discover_recorders() -> dict[str, Any]:
    """Return all registered recorder types (entry-points + builtins)."""
    found: dict[str, Any] = dict(_BUILTIN_FACTORIES)
    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            group = eps.select(group="pyontrust.recorders")
        else:
            group = eps.get("pyontrust.recorders", [])
        for ep in group:
            found[ep.name] = str(ep)
    except Exception:
        pass
    return found
