"""PCAN CAN bus recorder — thin wrapper for the original recorder."""

from __future__ import annotations

from typing import Any


def create(config: dict[str, Any]) -> Any:
    """Entry-point factory for PCAN CAN recorder."""
    from pyontrust_packages.power_test_framework.recorders.pcan_can import PcanCanRecorder

    params = {k: v for k, v in config.items() if k != "type"}
    return PcanCanRecorder(**params)
