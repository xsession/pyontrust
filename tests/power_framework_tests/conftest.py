"""Shared setup for power-framework tests.

The ``lab_bench`` package lives under ``tools/`` (kept out of the main
``pyontrust`` distribution because it is a standalone lab instrument
framework).  Put ``tools/`` on ``sys.path`` so ``import lab_bench...``
works from anywhere in this test directory.
"""

import sys
from pathlib import Path

_TOOLS_DIR = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
