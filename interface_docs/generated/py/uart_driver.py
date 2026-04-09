"""Auto-generated driver stub for: Locator Base UART Debug Interface"""

from __future__ import annotations
from dataclasses import dataclass

class LocatorBaseUARTDriver:
    """UART driver for Locator Base UART Debug Interface."""

    BAUD_RATE = 115200

    CMD_GET_VERSION = 0x01
    CMD_GET_STATUS = 0x02
    CMD_RESET = 0x03
    CMD_SET_LED = 0x10
    CMD_GET_LED = 0x11
    CMD_SET_GPIO = 0x12
    CMD_GET_GPIO = 0x13
    CMD_READ_ADC = 0x20
    CMD_SET_PWM = 0x30
    CMD_WRITE_CAL = 0x40
    CMD_READ_CAL = 0x41
    CMD_ASYNC_EVENT = 0xe0

    def __init__(self, port: str) -> None:
        self._port = port
        self._serial = None

    def get_version(self):
        """Query firmware version."""
        raise NotImplementedError

    def get_status(self):
        """Query overall device status."""
        raise NotImplementedError

    def reset(self, mode: int):
        """Reset the device. Response sent before reset."""
        raise NotImplementedError

    def set_led(self, led_id: int, state: int):
        """Control individual LED."""
        raise NotImplementedError

    def get_led(self, led_id: int):
        """Read current LED state."""
        raise NotImplementedError

    def set_gpio(self, pin_mask: int, value: int):
        """Set digital output pins."""
        raise NotImplementedError

    def get_gpio(self):
        """Read all digital I/O states."""
        raise NotImplementedError

    def read_adc(self, channel: int):
        """Read single ADC channel."""
        raise NotImplementedError

    def set_pwm(self, channel: int, freq_hz: int, duty_pct: int):
        """Configure PWM output."""
        raise NotImplementedError

    def write_cal(self, offset: int, length: int, data: bytes):
        """Write calibration data to EEPROM."""
        raise NotImplementedError

    def read_cal(self, offset: int, length: int):
        """Read calibration data from EEPROM."""
        raise NotImplementedError

    def async_event(self):
        """Asynchronous event from device (unsolicited)."""
        raise NotImplementedError

