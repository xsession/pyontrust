"""Instrument driver registry and discovery.

Uses ``importlib.metadata`` entry points for plugin-based instrument
registration. Built-in drivers register via ``pyproject.toml``.
Third-party packages can add their own instruments.

Usage::

    from pyontrust.instruments import discover_instruments, create_instrument

    available = discover_instruments()
    meter = create_instrument("simulated", {"sample_rate_hz": 500})
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Any

logger = logging.getLogger("pyontrust.instruments")

_ENTRY_POINT_GROUP = "pyontrust.instruments"

# Fallback registry for when entry points aren't installed (dev mode)
_BUILTIN_FACTORIES: dict[str, str] = {
    "simulated": "pyontrust.instruments.simulated:create",
    "ad3_dwf": "pyontrust.instruments.ad3_dwf:create",
    "ad3_cluster": "pyontrust.instruments.ad3_cluster:_create_ad3_cluster",
    "csv_file": "pyontrust.instruments.csv_power_meter:create_csv_file",
    "csv_process": "pyontrust.instruments.csv_power_meter:create_csv_process",
    "ppk2": "pyontrust.instruments.ad3_cluster:_create_ppk2",
    "sk120": "pyontrust.instruments.ad3_cluster:_create_sk120",
    "jlink": "pyontrust.instruments.ad3_cluster:_create_jlink",
    "hackrf": "pyontrust.instruments.ad3_cluster:_create_hackrf",
    "webcam": "pyontrust.instruments.ad3_cluster:_create_webcam",
    "pcan": "pyontrust.instruments.ad3_cluster:_create_pcan",
    "soapy": "pyontrust.instruments.ad3_cluster:_create_soapy",
    "csv_replay": "pyontrust.instruments.ad3_cluster:_create_csv_replay",
    "nrf52840_dongle": "pyontrust.instruments.ad3_cluster:_create_nrf52840_dongle",
    "aoi_camera": "pyontrust.instruments.aoi_camera:create",
    "seek_thermal": "pyontrust.instruments.seek_thermal:create",
}


def discover_instruments() -> dict[str, Any]:
    """List all registered instrument types (built-in + plugins).

    Returns a dict of {name: entry_point_or_factory_ref}.
    """
    found: dict[str, Any] = {}

    # Try importlib.metadata first
    try:
        eps = entry_points()
        if hasattr(eps, "select"):
            group = eps.select(group=_ENTRY_POINT_GROUP)
        else:
            group = eps.get(_ENTRY_POINT_GROUP, [])
        for ep in group:
            found[ep.name] = ep
    except Exception:
        pass

    # Add builtins that weren't found via entry points
    for name in _BUILTIN_FACTORIES:
        if name not in found:
            found[name] = _BUILTIN_FACTORIES[name]

    return found


def create_instrument(type_name: str, config: dict[str, Any]) -> Any:
    """Instantiate an instrument by type name and config dict.

    Tries entry points first, then falls back to builtin factories.
    """
    # Try entry points
    try:
        eps = entry_points()
        if hasattr(eps, "select"):
            group = list(eps.select(group=_ENTRY_POINT_GROUP, name=type_name))
        else:
            group = [ep for ep in eps.get(_ENTRY_POINT_GROUP, []) if ep.name == type_name]

        if group:
            factory = group[0].load()
            return factory(config)
    except Exception:
        pass

    # Fallback to builtin
    if type_name in _BUILTIN_FACTORIES:
        module_path, func_name = _BUILTIN_FACTORIES[type_name].rsplit(":", 1)
        import importlib

        mod = importlib.import_module(module_path)
        factory = getattr(mod, func_name)
        return factory(config)

    raise ValueError(f"Unknown instrument type: {type_name}")
