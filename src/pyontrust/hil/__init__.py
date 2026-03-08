"""Analog Discovery 3 Hardware-in-the-Loop (HIL) testing interface.

This module provides a high-level interface for using the Analog Discovery 3
as a comprehensive test instrument for embedded systems development,
specifically for Zephyr RTOS driver testing.
"""

from pyontrust.hil.ad3_interface import AD3Interface
from pyontrust.hil.digital_io import DigitalIO
from pyontrust.hil.analog_io import AnalogIO
from pyontrust.hil.protocols import SPIController, I2CController, UARTController
from pyontrust.hil.test_fixture import HILTestFixture

__all__ = [
    "AD3Interface",
    "DigitalIO",
    "AnalogIO",
    "SPIController",
    "I2CController",
    "UARTController",
    "HILTestFixture",
]
