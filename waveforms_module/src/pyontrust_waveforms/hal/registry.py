from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import InstrumentHal

_HAL_REGISTRY: dict[str, Callable[[dict[str, Any]], InstrumentHal]] = {}


def register_hal(name: str, factory: Callable[[dict[str, Any]], InstrumentHal]) -> None:
    _HAL_REGISTRY[name] = factory


def create_hal(name: str, config: dict[str, Any]) -> InstrumentHal:
    if name not in _HAL_REGISTRY:
        raise KeyError(f"Unknown HAL '{name}'. Registered: {sorted(_HAL_REGISTRY)}")
    return _HAL_REGISTRY[name](config)


def list_hals() -> list[str]:
    return sorted(_HAL_REGISTRY)
