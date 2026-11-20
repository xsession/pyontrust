"""Real hardware only — simulated devices are test doubles, not product features.

pyontrust measures real devices: every tool, API, FlowLab block and profile
works with real drivers, and a missing device is reported as missing — never
silently replaced by synthetic data (a test must not pass on numbers that did
not come from hardware).

The simulator classes remain *only* as test doubles for the automated test
suite, which enables them explicitly with ``PYONTRUST_ALLOW_SIMULATION=1``
(see ``tests/conftest.py``).  Anywhere else, constructing one raises
:class:`SimulationDisabled` with a "connect the real device" message.
"""
from __future__ import annotations

import os

ENV = "PYONTRUST_ALLOW_SIMULATION"


class SimulationDisabled(RuntimeError):
    """A simulated device was requested outside the test suite."""


def allowed() -> bool:
    return os.environ.get(ENV) == "1"


def require(what: str) -> None:
    """Raise unless simulation is enabled for tests."""
    if not allowed():
        raise SimulationDisabled(
            f"{what} is a simulated device — pyontrust works with real hardware only. "
            f"Connect the real device and select it (simulators are test doubles: {ENV}=1).")
