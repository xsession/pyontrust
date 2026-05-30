from __future__ import annotations

import os

import pytest

from pyontrust.boards.locator_base import LOCATOR_BASE
from pyontrust.hil import HILTestFixture


ENABLE_HIL = os.environ.get("PYONTRUST_ENABLE_HIL") == "1"
HIL_APP_PATH = "samples/basic/blink"


@pytest.fixture(scope="session")
def hil_enabled() -> bool:
    return ENABLE_HIL


@pytest.fixture(scope="session")
def hil_fixture():
    if not ENABLE_HIL:
        pytest.skip("Set PYONTRUST_ENABLE_HIL=1 to run hardware-in-the-loop checks")

    fixture = HILTestFixture(board=LOCATOR_BASE)
    with fixture:
        yield fixture