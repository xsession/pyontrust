"""Auto-generated driver stub for: Locator Base RS-485 Modbus Interface"""

from __future__ import annotations
import importlib

ENUM_TABLES = {
    "baud_rate_ten": {
        "BAUD_1200": 0,
        "BAUD_2400": 1,
        "BAUD_4800": 2,
        "BAUD_9600": 3,
        "BAUD_19200": 4,
        "BAUD_38400": 5,
        "BAUD_57600": 6,
        "BAUD_115200": 7,
    },
    "modbus_exception_ten": {
        "ILLEGAL_FUNCTION": 0x1,
        "ILLEGAL_DATA_ADDRESS": 0x2,
        "ILLEGAL_DATA_VALUE": 0x3,
        "SLAVE_DEVICE_FAILURE": 0x4,
        "ACKNOWLEDGE": 0x5,
        "SLAVE_DEVICE_BUSY": 0x6,
    },
}

BITFIELD_DEFINITIONS = {
}

MODBUS_REGISTER_METADATA = {'holding': {'device_status': {'doc': 'Bit-mapped device status word.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/HOLDING/DEVICE_STATUS', 'type': 'device_status_tun', 'addr': '0x0000', 'register_group': 'holding'}, 'led_control': {'doc': 'LED on/off bitmask (bit 0 = LED0, bit 1 = LED1, ...).', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/LED_CONTROL', 'type': 'led_control_tun', 'addr': '0x0001', 'register_group': 'holding'}, 'fw_version_major': {'doc': 'Firmware major version number.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/HOLDING/FW_VERSION_MAJOR', 'type': 'uint16', 'addr': '0x0002', 'register_group': 'holding'}, 'fw_version_minor': {'doc': 'Firmware minor version number.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/HOLDING/FW_VERSION_MINOR', 'type': 'uint16', 'addr': '0x0003', 'register_group': 'holding'}, 'node_id': {'doc': 'Modbus slave address (1–247). Takes effect after save + reboot.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/NODE_ID', 'type': 'uint16', 'addr': '0x0004', 'register_group': 'holding'}, 'baud_rate_code': {'doc': 'Baud rate selection. See baud_rate_ten enum.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/BAUD_RATE_CODE', 'type': 'baud_rate_ten', 'enum_table': 'BAUD_RATE_TEN', 'addr': '0x0005', 'register_group': 'holding'}, 'parity_mode': {'doc': '0 = none, 1 = even, 2 = odd.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PARITY_MODE', 'type': 'uint16', 'addr': '0x0006', 'register_group': 'holding'}, 'save_config': {'doc': 'Write 0x1234 to persist holding registers 0x0004–0x0006 to flash.', 'flags': ['write'], 'path': 'LOCATORBASEMODBUS/HOLDING/SAVE_CONFIG', 'type': 'uint16', 'addr': '0x0007', 'register_group': 'holding'}, 'pwm0_freq_hz': {'doc': 'PWM channel 0 frequency in Hz (PA7 / TIMG8_CH0).', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM0_FREQ_HZ', 'type': 'uint16', 'addr': '0x0010', 'register_group': 'holding'}, 'pwm0_duty_pct': {'doc': 'PWM channel 0 duty cycle 0–100.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM0_DUTY_PCT', 'type': 'uint16', 'addr': '0x0011', 'register_group': 'holding'}, 'pwm1_freq_hz': {'doc': 'PWM channel 1 frequency in Hz (PA21 / TIMG6_CH0).', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM1_FREQ_HZ', 'type': 'uint16', 'addr': '0x0012', 'register_group': 'holding'}, 'pwm1_duty_pct': {'doc': 'PWM channel 1 duty cycle 0–100.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM1_DUTY_PCT', 'type': 'uint16', 'addr': '0x0013', 'register_group': 'holding'}, 'pwm2_freq_hz': {'doc': 'PWM channel 2 frequency in Hz (PA22 / TIMG6_CH1).', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM2_FREQ_HZ', 'type': 'uint16', 'addr': '0x0014', 'register_group': 'holding'}, 'pwm2_duty_pct': {'doc': 'PWM channel 2 duty cycle 0–100.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM2_DUTY_PCT', 'type': 'uint16', 'addr': '0x0015', 'register_group': 'holding'}, 'pwm3_freq_hz': {'doc': 'PWM channel 3 frequency in Hz (PA23 / TIMG0_CH0).', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM3_FREQ_HZ', 'type': 'uint16', 'addr': '0x0016', 'register_group': 'holding'}, 'pwm3_duty_pct': {'doc': 'PWM channel 3 duty cycle 0–100.', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/PWM3_DUTY_PCT', 'type': 'uint16', 'addr': '0x0017', 'register_group': 'holding'}, 'dout_mask': {'doc': 'Digital output state bitmask (bits 0–3 = DOUT0–DOUT3).', 'flags': ['read', 'write'], 'path': 'LOCATORBASEMODBUS/HOLDING/DOUT_MASK', 'type': 'uint16', 'addr': '0x0020', 'register_group': 'holding'}}, 'input': {'board_temperature': {'doc': 'On-board temperature sensor × 10.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/BOARD_TEMPERATURE', 'type': 'int16', 'unit': '0.1 °C', 'addr': '0x0000', 'register_group': 'input'}, 'supply_voltage': {'doc': 'Supply rail voltage in millivolts.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/SUPPLY_VOLTAGE', 'type': 'uint16', 'unit': 'mV', 'addr': '0x0001', 'register_group': 'input'}, 'adc_ch0': {'doc': 'ADC channel 0 (PA15) converted to millivolts.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/ADC_CH0', 'type': 'uint16', 'unit': 'mV', 'addr': '0x0002', 'register_group': 'input'}, 'adc_ch1': {'doc': 'ADC channel 1 (PA16) converted to millivolts.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/ADC_CH1', 'type': 'uint16', 'unit': 'mV', 'addr': '0x0003', 'register_group': 'input'}, 'adc_ch2': {'doc': 'ADC channel 2 (PA17) converted to millivolts.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/ADC_CH2', 'type': 'uint16', 'unit': 'mV', 'addr': '0x0004', 'register_group': 'input'}, 'adc_ch3': {'doc': 'ADC channel 3 (PA18) converted to millivolts.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/ADC_CH3', 'type': 'uint16', 'unit': 'mV', 'addr': '0x0005', 'register_group': 'input'}, 'din_state': {'doc': 'Digital input state bitmask (bits 0–3 = DIN0–DIN3).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/DIN_STATE', 'type': 'uint16', 'addr': '0x0006', 'register_group': 'input'}, 'uptime_s': {'doc': 'Seconds since last boot (rolls at 65535).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/UPTIME_S', 'type': 'uint16', 'addr': '0x0007', 'register_group': 'input'}, 'can_rx_count': {'doc': 'Total CAN frames received since boot.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/CAN_RX_COUNT', 'type': 'uint16', 'addr': '0x0008', 'register_group': 'input'}, 'can_tx_count': {'doc': 'Total CAN frames transmitted since boot.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/CAN_TX_COUNT', 'type': 'uint16', 'addr': '0x0009', 'register_group': 'input'}, 'error_count': {'doc': 'Cumulative error counter since boot.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/INPUT/ERROR_COUNT', 'type': 'uint16', 'addr': '0x000a', 'register_group': 'input'}}, 'discrete': {'din0': {'addr': '0x0000', 'register_group': 'discrete', 'doc': 'Digital input 0 (PA15).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/DISCRETE/DIN0', 'type': 'bool'}, 'din1': {'addr': '0x0001', 'register_group': 'discrete', 'doc': 'Digital input 1 (PA16).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/DISCRETE/DIN1', 'type': 'bool'}, 'din2': {'addr': '0x0002', 'register_group': 'discrete', 'doc': 'Digital input 2 (PA17).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/DISCRETE/DIN2', 'type': 'bool'}, 'din3': {'addr': '0x0003', 'register_group': 'discrete', 'doc': 'Digital input 3 (PA18 / button).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/DISCRETE/DIN3', 'type': 'bool'}, 'can_bus_ok': {'addr': '0x0004', 'register_group': 'discrete', 'doc': 'CAN bus operational (not bus-off).', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/DISCRETE/CAN_BUS_OK', 'type': 'bool'}, 'temp_warning': {'addr': '0x0005', 'register_group': 'discrete', 'doc': 'Temperature warning threshold exceeded.', 'flags': ['read'], 'path': 'LOCATORBASEMODBUS/DISCRETE/TEMP_WARNING', 'type': 'bool'}}}

class LocatorBaseModbusDriver:
    """Modbus RTU driver for Locator Base RS-485 Modbus Interface."""

    ENUM_TABLES = ENUM_TABLES
    BITFIELD_DEFINITIONS = BITFIELD_DEFINITIONS
    REGISTER_METADATA = MODBUS_REGISTER_METADATA

    SLAVE_ID = 0x10

    HREG_DEVICE_STATUS = 0x0000
    HREG_LED_CONTROL = 0x0001
    HREG_FW_VERSION_MAJOR = 0x0002
    HREG_FW_VERSION_MINOR = 0x0003
    HREG_NODE_ID = 0x0004
    HREG_BAUD_RATE_CODE = 0x0005
    HREG_PARITY_MODE = 0x0006
    HREG_SAVE_CONFIG = 0x0007
    HREG_PWM0_FREQ_HZ = 0x0010
    HREG_PWM0_DUTY_PCT = 0x0011
    HREG_PWM1_FREQ_HZ = 0x0012
    HREG_PWM1_DUTY_PCT = 0x0013
    HREG_PWM2_FREQ_HZ = 0x0014
    HREG_PWM2_DUTY_PCT = 0x0015
    HREG_PWM3_FREQ_HZ = 0x0016
    HREG_PWM3_DUTY_PCT = 0x0017
    HREG_DOUT_MASK = 0x0020
    IREG_BOARD_TEMPERATURE = 0x0000
    IREG_SUPPLY_VOLTAGE = 0x0001
    IREG_ADC_CH0 = 0x0002
    IREG_ADC_CH1 = 0x0003
    IREG_ADC_CH2 = 0x0004
    IREG_ADC_CH3 = 0x0005
    IREG_DIN_STATE = 0x0006
    IREG_UPTIME_S = 0x0007
    IREG_CAN_RX_COUNT = 0x0008
    IREG_CAN_TX_COUNT = 0x0009
    IREG_ERROR_COUNT = 0x000a

    def __init__(self, port: str, slave_id: int = 0x10) -> None:
        self._port = port
        self._slave_id = slave_id

    def get_register_metadata(self, register_name, register_group="holding"):
        return self.REGISTER_METADATA.get(register_group, {}).get(register_name, {})

    def get_enum_table(self, type_name):
        return self.ENUM_TABLES.get(type_name, {})

    def get_bitfield_definition(self, type_name):
        return self.BITFIELD_DEFINITIONS.get(type_name, {})

    def _load_conversion_callable(self, conversion_spec):
        python_spec = (conversion_spec or {}).get("implementation", {}).get("python", {})
        module_name = python_spec.get("module")
        function_name = python_spec.get("function")
        if not module_name or not function_name:
            return None
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            return None
        return getattr(module, function_name, None)

    def _apply_conversion_callable(self, conversion_callable, raw_value):
        try:
            return conversion_callable(raw_value)
        except TypeError:
            try:
                return conversion_callable(value=raw_value)
            except TypeError:
                return raw_value

    def get_converted_value(self, register_name, raw_value=None, register_group="holding"):
        metadata = self.get_register_metadata(register_name, register_group)
        if raw_value is None:
            reader = getattr(self, f"read_{register_name}", None)
            if reader is None:
                return raw_value
            raw_value = reader()

        conversion_spec = metadata.get("conversion")
        if not conversion_spec:
            return raw_value
        conversion_callable = self._load_conversion_callable(conversion_spec)
        if conversion_callable is None:
            return raw_value
        return self._apply_conversion_callable(conversion_callable, raw_value)

    def get_additional_log_fields_schema(self, register_group="holding"):
        return {
            f"{register_name}_converted": None
            for register_name, metadata in self.REGISTER_METADATA.get(register_group, {}).items()
            if metadata.get("conversion")
        }

    def get_additional_log_values(self, values, register_group="holding"):
        converted_values = {}
        for register_name, metadata in self.REGISTER_METADATA.get(register_group, {}).items():
            if not metadata.get("conversion") or register_name not in values:
                continue
            converted_values[f"{register_name}_converted"] = self.get_converted_value(
                register_name,
                values[register_name],
                register_group=register_group,
            )
        return converted_values

    def read_device_status(self) -> int:
        """Bit-mapped device status word."""
        raise NotImplementedError

    def read_led_control(self) -> int:
        """LED on/off bitmask (bit 0 = LED0, bit 1 = LED1, ...)."""
        raise NotImplementedError

    def write_led_control(self, value: int) -> None:
        """LED on/off bitmask (bit 0 = LED0, bit 1 = LED1, ...)."""
        raise NotImplementedError

    def read_fw_version_major(self) -> int:
        """Firmware major version number."""
        raise NotImplementedError

    def read_fw_version_minor(self) -> int:
        """Firmware minor version number."""
        raise NotImplementedError

    def read_node_id(self) -> int:
        """Modbus slave address (1–247). Takes effect after save + reboot."""
        raise NotImplementedError

    def write_node_id(self, value: int) -> None:
        """Modbus slave address (1–247). Takes effect after save + reboot."""
        raise NotImplementedError

    def read_baud_rate_code(self) -> int:
        """Baud rate selection. See baud_rate_ten enum."""
        raise NotImplementedError

    def write_baud_rate_code(self, value: int) -> None:
        """Baud rate selection. See baud_rate_ten enum."""
        raise NotImplementedError

    def read_parity_mode(self) -> int:
        """0 = none, 1 = even, 2 = odd."""
        raise NotImplementedError

    def write_parity_mode(self, value: int) -> None:
        """0 = none, 1 = even, 2 = odd."""
        raise NotImplementedError

    def write_save_config(self, value: int) -> None:
        """Write 0x1234 to persist holding registers 0x0004–0x0006 to flash."""
        raise NotImplementedError

    def read_pwm0_freq_hz(self) -> int:
        """PWM channel 0 frequency in Hz (PA7 / TIMG8_CH0)."""
        raise NotImplementedError

    def write_pwm0_freq_hz(self, value: int) -> None:
        """PWM channel 0 frequency in Hz (PA7 / TIMG8_CH0)."""
        raise NotImplementedError

    def read_pwm0_duty_pct(self) -> int:
        """PWM channel 0 duty cycle 0–100."""
        raise NotImplementedError

    def write_pwm0_duty_pct(self, value: int) -> None:
        """PWM channel 0 duty cycle 0–100."""
        raise NotImplementedError

    def read_pwm1_freq_hz(self) -> int:
        """PWM channel 1 frequency in Hz (PA21 / TIMG6_CH0)."""
        raise NotImplementedError

    def write_pwm1_freq_hz(self, value: int) -> None:
        """PWM channel 1 frequency in Hz (PA21 / TIMG6_CH0)."""
        raise NotImplementedError

    def read_pwm1_duty_pct(self) -> int:
        """PWM channel 1 duty cycle 0–100."""
        raise NotImplementedError

    def write_pwm1_duty_pct(self, value: int) -> None:
        """PWM channel 1 duty cycle 0–100."""
        raise NotImplementedError

    def read_pwm2_freq_hz(self) -> int:
        """PWM channel 2 frequency in Hz (PA22 / TIMG6_CH1)."""
        raise NotImplementedError

    def write_pwm2_freq_hz(self, value: int) -> None:
        """PWM channel 2 frequency in Hz (PA22 / TIMG6_CH1)."""
        raise NotImplementedError

    def read_pwm2_duty_pct(self) -> int:
        """PWM channel 2 duty cycle 0–100."""
        raise NotImplementedError

    def write_pwm2_duty_pct(self, value: int) -> None:
        """PWM channel 2 duty cycle 0–100."""
        raise NotImplementedError

    def read_pwm3_freq_hz(self) -> int:
        """PWM channel 3 frequency in Hz (PA23 / TIMG0_CH0)."""
        raise NotImplementedError

    def write_pwm3_freq_hz(self, value: int) -> None:
        """PWM channel 3 frequency in Hz (PA23 / TIMG0_CH0)."""
        raise NotImplementedError

    def read_pwm3_duty_pct(self) -> int:
        """PWM channel 3 duty cycle 0–100."""
        raise NotImplementedError

    def write_pwm3_duty_pct(self, value: int) -> None:
        """PWM channel 3 duty cycle 0–100."""
        raise NotImplementedError

    def read_dout_mask(self) -> int:
        """Digital output state bitmask (bits 0–3 = DOUT0–DOUT3)."""
        raise NotImplementedError

    def write_dout_mask(self, value: int) -> None:
        """Digital output state bitmask (bits 0–3 = DOUT0–DOUT3)."""
        raise NotImplementedError

    def read_board_temperature(self) -> int:
        """On-board temperature sensor × 10."""
        raise NotImplementedError

    def read_supply_voltage(self) -> int:
        """Supply rail voltage in millivolts."""
        raise NotImplementedError

    def read_adc_ch0(self) -> int:
        """ADC channel 0 (PA15) converted to millivolts."""
        raise NotImplementedError

    def read_adc_ch1(self) -> int:
        """ADC channel 1 (PA16) converted to millivolts."""
        raise NotImplementedError

    def read_adc_ch2(self) -> int:
        """ADC channel 2 (PA17) converted to millivolts."""
        raise NotImplementedError

    def read_adc_ch3(self) -> int:
        """ADC channel 3 (PA18) converted to millivolts."""
        raise NotImplementedError

    def read_din_state(self) -> int:
        """Digital input state bitmask (bits 0–3 = DIN0–DIN3)."""
        raise NotImplementedError

    def read_uptime_s(self) -> int:
        """Seconds since last boot (rolls at 65535)."""
        raise NotImplementedError

    def read_can_rx_count(self) -> int:
        """Total CAN frames received since boot."""
        raise NotImplementedError

    def read_can_tx_count(self) -> int:
        """Total CAN frames transmitted since boot."""
        raise NotImplementedError

    def read_error_count(self) -> int:
        """Cumulative error counter since boot."""
        raise NotImplementedError

