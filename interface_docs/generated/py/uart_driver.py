"""Auto-generated driver stub for: Locator Base UART Debug Interface"""

from __future__ import annotations
import importlib

ENUM_TABLES = {
    "uart_event_code_ten": {
        "EVT_BUTTON_PRESS": 0x1,
        "EVT_BUTTON_RELEASE": 0x2,
        "EVT_TEMP_WARNING": 0x10,
        "EVT_TEMP_CRITICAL": 0x11,
        "EVT_VOLTAGE_LOW": 0x20,
        "EVT_VOLTAGE_HIGH": 0x21,
        "EVT_CAN_BUS_OFF": 0x30,
        "EVT_WATCHDOG": 0xfe,
        "EVT_FAULT": 0xff,
    },
    "uart_ack_ten": {
        "ACK": 0x6,
        "NAK": 0x15,
        "NAK_INVALID_CMD": 0x80,
        "NAK_INVALID_PARAM": 0x81,
        "NAK_BUSY": 0x82,
        "NAK_CRC_ERROR": 0x83,
    },
}

BITFIELD_DEFINITIONS = {
    "uart_frame_header_tst": {
        "START": {"size": 8, "doc": "Start-of-frame byte. Always 0xAA.\n"},
        "CMD_ID": {"size": 8, "doc": "Command identifier.\n"},
        "PAYLOAD_LEN": {"size": 8, "doc": "Number of payload bytes following this header.\n"},
        "SEQ": {"size": 8, "doc": "Sequence counter for request/response matching.\n"},
    },
    "led_control_tst": {
        "LED_STATUS": {"size": 1, "doc": "Status LED (PA2 / DOUT0). 1 = on.\n"},
        "LED_USER": {"size": 1, "doc": "User LED (PA4 / DOUT1). 1 = on.\n"},
        "LED_ERROR": {"size": 1, "doc": "Error indicator LED (PA9 / DOUT2). 1 = on.\n"},
        "LED_COMM": {"size": 1, "doc": "Communication activity LED (PA25 / DOUT3). 1 = on.\n"},
        "RESERVED": {"size": 4, "doc": "Reserved.\n"},
    },
    "button_state_tst": {
        "BTN_USER": {"size": 1, "doc": "User button (PA18 / DIN3). 1 = pressed.\n"},
        "RESERVED": {"size": 7, "doc": "Reserved.\n"},
    },
    "device_status_tst": {
        "ACTIVE": {"size": 1, "doc": "Node is active and operational.\n"},
        "ERROR": {"size": 1, "doc": "Error flag. Check error register for details.\n"},
        "CAN_OK": {"size": 1, "doc": "CAN bus operational (no bus-off).\n"},
        "TEMP_WARN": {"size": 1, "doc": "Board temperature exceeds warning threshold.\n"},
        "CAL_VALID": {"size": 1, "doc": "Calibration data is valid and loaded.\n"},
        "RESERVED": {"size": 11, "doc": "Reserved.\n"},
    },
}

UART_COMMAND_METADATA = {'get_version': {'id': '0x01', 'doc': 'Query firmware version.', 'request_fields': [], 'response_fields': [{'name': 'major', 'type': 'uint8', 'doc': 'Major version number'}, {'name': 'minor', 'type': 'uint8', 'doc': 'Minor version number'}, {'name': 'patch', 'type': 'uint8', 'doc': 'Patch version number'}, {'name': 'build_id', 'type': 'uint16', 'doc': 'Build counter'}]}, 'get_status': {'id': '0x02', 'doc': 'Query overall device status.', 'request_fields': [], 'response_fields': [{'name': 'status', 'type': 'device_status_tun', 'doc': 'Device status word'}, {'name': 'uptime_s', 'type': 'uint32', 'doc': 'Seconds since boot'}, {'name': 'temp_c10', 'type': 'int16', 'doc': 'Board temperature × 10'}, {'name': 'vcc_mv', 'type': 'uint16', 'doc': 'Supply voltage in mV'}]}, 'reset': {'id': '0x03', 'doc': 'Reset the device. Response sent before reset.', 'request_fields': [{'name': 'mode', 'type': 'uint8', 'doc': '0 = soft reset, 1 = bootloader'}], 'response_fields': [{'name': 'ack', 'type': 'uint8', 'doc': '0x06 = ACK'}]}, 'set_led': {'id': '0x10', 'doc': 'Control individual LED.', 'request_fields': [{'name': 'led_id', 'type': 'uint8', 'doc': 'LED index (0–3)'}, {'name': 'state', 'type': 'uint8', 'doc': '0 = off, 1 = on, 2 = toggle'}], 'response_fields': [{'name': 'ack', 'type': 'uint8', 'doc': '0x06 = ACK, 0x15 = NAK'}]}, 'get_led': {'id': '0x11', 'doc': 'Read current LED state.', 'request_fields': [{'name': 'led_id', 'type': 'uint8', 'doc': 'LED index (0–3)'}], 'response_fields': [{'name': 'state', 'type': 'uint8', 'doc': '0 = off, 1 = on'}]}, 'set_gpio': {'id': '0x12', 'doc': 'Set digital output pins.', 'request_fields': [{'name': 'pin_mask', 'type': 'uint8', 'doc': 'Bitmask of output pins'}, {'name': 'value', 'type': 'uint8', 'doc': 'Pin values (bit = 1 → high)'}], 'response_fields': [{'name': 'ack', 'type': 'uint8', 'doc': ''}]}, 'get_gpio': {'id': '0x13', 'doc': 'Read all digital I/O states.', 'request_fields': [], 'response_fields': [{'name': 'dout_state', 'type': 'uint8', 'doc': 'Current digital output states'}, {'name': 'din_state', 'type': 'uint8', 'doc': 'Current digital input states'}]}, 'read_adc': {'id': '0x20', 'doc': 'Read single ADC channel.', 'request_fields': [{'name': 'channel', 'type': 'uint8', 'doc': 'ADC channel (0–3)'}], 'response_fields': [{'name': 'raw', 'type': 'uint16', 'doc': 'Raw 12-bit ADC value'}, {'name': 'mv', 'type': 'uint16', 'doc': 'Converted millivolt value'}]}, 'set_pwm': {'id': '0x30', 'doc': 'Configure PWM output.', 'request_fields': [{'name': 'channel', 'type': 'uint8', 'doc': 'PWM channel (0–3)'}, {'name': 'freq_hz', 'type': 'uint32', 'doc': 'Frequency in Hz'}, {'name': 'duty_pct', 'type': 'uint8', 'doc': 'Duty cycle 0–100'}], 'response_fields': [{'name': 'ack', 'type': 'uint8', 'doc': ''}]}, 'write_cal': {'id': '0x40', 'doc': 'Write calibration data to EEPROM.', 'request_fields': [{'name': 'offset', 'type': 'uint16', 'doc': 'Byte offset in cal block'}, {'name': 'length', 'type': 'uint8', 'doc': 'Bytes to write (max 64)'}, {'name': 'data', 'type': 'bytes', 'doc': 'Calibration data'}], 'response_fields': [{'name': 'ack', 'type': 'uint8', 'doc': ''}]}, 'read_cal': {'id': '0x41', 'doc': 'Read calibration data from EEPROM.', 'request_fields': [{'name': 'offset', 'type': 'uint16', 'doc': 'Byte offset in cal block'}, {'name': 'length', 'type': 'uint8', 'doc': 'Bytes to read (max 64)'}], 'response_fields': [{'name': 'data', 'type': 'bytes', 'doc': 'Calibration data'}]}, 'async_event': {'id': '0xe0', 'doc': 'Asynchronous event from device (unsolicited).', 'request_fields': [], 'response_fields': []}}

class LocatorBaseUARTDriver:
    """UART driver for Locator Base UART Debug Interface."""

    ENUM_TABLES = ENUM_TABLES
    BITFIELD_DEFINITIONS = BITFIELD_DEFINITIONS
    COMMAND_METADATA = UART_COMMAND_METADATA

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

    def get_command_metadata(self, command_name):
        return self.COMMAND_METADATA.get(command_name, {})

    def get_enum_table(self, type_name):
        return self.ENUM_TABLES.get(type_name, {})

    def get_bitfield_definition(self, type_name):
        return self.BITFIELD_DEFINITIONS.get(type_name, {})

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

