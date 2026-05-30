"""Auto-generated driver stub for: Locator Base Ethernet Control Interface"""

from __future__ import annotations
import importlib

ENUM_TABLES = {
    "tcp_result_ten": {
        "OK": 0x0,
        "ERR_INVALID_CMD": 0x1,
        "ERR_INVALID_PARAM": 0x2,
        "ERR_BUSY": 0x3,
        "ERR_NOT_FOUND": 0x4,
        "ERR_TIMEOUT": 0x5,
        "ERR_INTERNAL": 0xff,
    },
    "meas_status_ten": {
        "IN_PROGRESS": 0x0,
        "DONE": 0x1,
        "ERROR": 0x2,
        "CANCELLED": 0x3,
    },
}

BITFIELD_DEFINITIONS = {
}

TCPUDP_COMMAND_METADATA = {'ping': {'id': '0x0000', 'doc': 'Connectivity check.', 'request_fields': []}, 'get_device_info': {'id': '0x0001', 'doc': 'Query device identification and uptime.', 'request_fields': []}, 'get_status': {'id': '0x0002', 'doc': 'Query overall device status.', 'request_fields': []}, 'set_led': {'id': '0x0010', 'doc': 'Set LEDs by bitmask.', 'request_fields': [{'name': 'led_mask', 'type': 'uint8', 'doc': 'Bitmask of LEDs to change'}, {'name': 'led_val', 'type': 'uint8', 'doc': 'Desired state per bit'}]}, 'set_gpio': {'id': '0x0011', 'doc': 'Set digital output pins.', 'request_fields': [{'name': 'pin_mask', 'type': 'uint8', 'doc': ''}, {'name': 'pin_val', 'type': 'uint8', 'doc': ''}]}, 'get_gpio': {'id': '0x0012', 'doc': 'Read all GPIO states.', 'request_fields': []}, 'start_measurement': {'id': '0x0020', 'doc': 'Start an ADC measurement capture.', 'request_fields': [{'name': 'channel', 'type': 'uint8', 'doc': 'ADC channel (0–3)'}, {'name': 'duration_ms', 'type': 'uint32', 'doc': 'Capture duration in ms'}, {'name': 'rate_hz', 'type': 'uint16', 'doc': 'Sample rate in Hz'}]}, 'get_measurement': {'id': '0x0021', 'doc': 'Read captured measurement data.', 'request_fields': [{'name': 'meas_id', 'type': 'uint16', 'doc': 'Session ID from start_measurement'}, {'name': 'offset', 'type': 'uint32', 'doc': 'Sample offset to read from'}, {'name': 'count', 'type': 'uint16', 'doc': 'Number of samples to read'}]}, 'can_send': {'id': '0x0030', 'doc': "Transmit a CAN frame via the MCU's MCAN peripheral.", 'request_fields': [{'name': 'arb_id', 'type': 'uint32', 'doc': 'CAN arbitration ID'}, {'name': 'is_extended', 'type': 'uint8', 'doc': '1 = 29-bit ID, 0 = 11-bit'}, {'name': 'dlc', 'type': 'uint8', 'doc': 'Data length (0–8)'}, {'name': 'data', 'type': 'bytes', 'doc': 'CAN frame data'}]}, 'can_subscribe': {'id': '0x0031', 'doc': 'Subscribe to CAN frames. Matching frames sent as async notifications over TCP.', 'request_fields': [{'name': 'filter_id', 'type': 'uint32', 'doc': 'Acceptance filter ID (0 = all)'}, {'name': 'filter_mask', 'type': 'uint32', 'doc': 'Acceptance mask'}]}}
UDP_MESSAGE_METADATA = {'heartbeat': {'id': '0x0100', 'doc': '1 Hz heartbeat broadcast for device discovery.', 'rate_hz': 1}, 'telemetry': {'id': '0x0101', 'doc': '10 Hz periodic telemetry broadcast.', 'rate_hz': 10}, 'can_frame': {'id': '0x0102', 'doc': 'Forwarded CAN frame (from can_subscribe filter).', 'rate_hz': 0}}

class LocatorBaseTCPDriver:
    """TCP/UDP driver for Locator Base Ethernet Control Interface."""

    ENUM_TABLES = ENUM_TABLES
    BITFIELD_DEFINITIONS = BITFIELD_DEFINITIONS
    COMMAND_METADATA = TCPUDP_COMMAND_METADATA
    MESSAGE_METADATA = UDP_MESSAGE_METADATA

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

    def get_command_metadata(self, command_name):
        return self.COMMAND_METADATA.get(command_name, {})

    def get_message_metadata(self, message_name):
        return self.MESSAGE_METADATA.get(message_name, {})

    def get_enum_table(self, type_name):
        return self.ENUM_TABLES.get(type_name, {})

    def get_bitfield_definition(self, type_name):
        return self.BITFIELD_DEFINITIONS.get(type_name, {})

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

