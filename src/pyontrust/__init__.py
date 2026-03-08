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
