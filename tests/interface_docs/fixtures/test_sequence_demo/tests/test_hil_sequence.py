from __future__ import annotations

import pytest

from sequence import DemoBoardSequence


@pytest.mark.skipif(not __import__("os").environ.get("PYONTRUST_ENABLE_HIL") == "1", reason="HIL disabled")
def test_hil_fixture_can_optionally_boot_sample_app(hil_fixture) -> None:
    sequence = DemoBoardSequence()

    hil_fixture.load_app("samples/basic/blink", build=False, flash=False)
    hil_fixture.wait_for_boot(timeout_s=0.0)

    assert sequence.device_key == "demo_board"