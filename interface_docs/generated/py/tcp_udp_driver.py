"""Auto-generated driver stub for: Locator Base Ethernet Control Interface"""

from __future__ import annotations
from dataclasses import dataclass

class LocatorBaseTCPDriver:
    """TCP/UDP driver for Locator Base Ethernet Control Interface."""

    TCP_PORT = 5200
    UDP_PORT = 5201

    TCP_CMD_PING = 0x0000
    TCP_CMD_GET_DEVICE_INFO = 0x0001
    TCP_CMD_GET_STATUS = 0x0002
    TCP_CMD_SET_LED = 0x0010
    TCP_CMD_SET_GPIO = 0x0011
    TCP_CMD_GET_GPIO = 0x0012
    TCP_CMD_START_MEASUREMENT = 0x0020
    TCP_CMD_GET_MEASUREMENT = 0x0021
    TCP_CMD_CAN_SEND = 0x0030
    TCP_CMD_CAN_SUBSCRIBE = 0x0031

    def __init__(self, host: str, port: int = 5200) -> None:
        self._host = host
        self._port = port

    def ping(self):
        """Connectivity check."""
        raise NotImplementedError

    def get_device_info(self):
        """Query device identification and uptime."""
        raise NotImplementedError

    def get_status(self):
        """Query overall device status."""
        raise NotImplementedError

    def set_led(self, led_mask: int, led_val: int):
        """Set LEDs by bitmask."""
        raise NotImplementedError

    def set_gpio(self, pin_mask: int, pin_val: int):
        """Set digital output pins."""
        raise NotImplementedError

    def get_gpio(self):
        """Read all GPIO states."""
        raise NotImplementedError

    def start_measurement(self, channel: int, duration_ms: int, rate_hz: int):
        """Start an ADC measurement capture."""
        raise NotImplementedError

    def get_measurement(self, meas_id: int, offset: int, count: int):
        """Read captured measurement data."""
        raise NotImplementedError

    def can_send(self, arb_id: int, is_extended: int, dlc: int, data: bytes):
        """Transmit a CAN frame via the MCU's MCAN peripheral."""
        raise NotImplementedError

    def can_subscribe(self, filter_id: int, filter_mask: int):
        """Subscribe to CAN frames. Matching frames sent as async notifications over TCP."""
        raise NotImplementedError

