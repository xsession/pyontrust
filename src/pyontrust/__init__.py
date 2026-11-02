"""Pyontrust — Enterprise embedded test & measurement platform.

Unified platform for automated testing, hardware-in-the-loop (HIL),
multi-domain debugging, and real-time multi-channel logging.

Usage::

    from pyontrust.core import PowerSample, PowerTrace, PowerTestRunner
    from pyontrust.hal import PowerMeter, Recorder, SdrHal
    from pyontrust.instruments import discover_instruments, create_instrument
    
    # HIL testing with Analog Discovery 3
    from pyontrust.hil import AD3Interface, HILTestFixture
    from pyontrust.boards.locator_base import LOCATOR_BASE, LocatorBaseAD3
"""

__version__ = "2026.3.0"

# --- Self-contained bootstrap ---------------------------------------------
# Several drivers (PPK2, SK120, J-Link, HackRF, webcam, PCAN/nRF52840
# recorders) and the legacy test-suite import the top-level
# ``lab_bench`` package that lives next to ``src/`` in this repo.
# Make it importable no matter where pyontrust is imported from, without
# requiring any external install.
import sys as _sys

try:  # pragma: no cover - trivial bootstrap
    import lab_bench  # noqa: F401
except ImportError:
    try:
        from pathlib import Path as _Path

        _repo_root = str(_Path(__file__).resolve().parents[2])
        if _repo_root not in _sys.path:
            _sys.path.insert(0, _repo_root)
        import lab_bench  # noqa: F401
    except ImportError:  # pragma: no cover - package genuinely absent
        pass
