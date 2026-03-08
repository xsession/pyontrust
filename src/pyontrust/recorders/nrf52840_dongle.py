"""nRF52840 dongle recorder — thin wrapper for the original recorder."""

from __future__ import annotations

from typing import Any


def create(config: dict[str, Any]) -> Any:
    """Entry-point factory for nRF52840 dongle recorder."""
    from pyontrust_packages.power_test_framework.recorders.nrf52840_dongle import Nrf52840DongleRecorder

    params = {k: v for k, v in config.items() if k != "type"}
    return Nrf52840DongleRecorder(**params)
