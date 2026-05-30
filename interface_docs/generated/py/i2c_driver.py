"""Auto-generated driver stub for: Locator Base I2C Sensor Bus Interface"""

from __future__ import annotations
import importlib

ENUM_TABLES = {
}

BITFIELD_DEFINITIONS = {
    "tmp117_config_tst": {
        "RESERVED_0": {"size": 1, "doc": "Reserved."},
        "SOFT_RESET": {"size": 1, "doc": "Write 1 to trigger software reset."},
        "DR_ALERT": {"size": 1, "doc": "ALERT pin function: 0 = alert, 1 = data ready."},
        "POL": {"size": 1, "doc": "ALERT pin polarity: 0 = active low, 1 = active high."},
        "T_NA": {"size": 1, "doc": "Therm/alert mode: 0 = alert, 1 = therm."},
        "AVG": {"size": 2, "doc": "Averaging: 00 = none, 01 = 8, 10 = 32, 11 = 64."},
        "CONV": {"size": 3, "doc": "Conversion cycle time (000 = 15.5ms, ..., 111 = 1s)."},
        "MOD": {"size": 2, "doc": "Mode: 00 = continuous, 01 = shutdown, 10 = continuous, 11 = one-shot."},
        "EEPROM_BUSY": {"size": 1, "doc": "Read-only: 1 = EEPROM write in progress."},
        "DATA_READY": {"size": 1, "doc": "Read-only: 1 = new temperature data available."},
        "LOW_ALERT": {"size": 1, "doc": "Read-only: low-temperature alert flag."},
        "HIGH_ALERT": {"size": 1, "doc": "Read-only: high-temperature alert flag (MSB first)."},
    },
    "cal_header_tst": {
        "MAGIC": {"size": 16, "doc": "Magic word: 0xCA1B = valid calibration block."},
        "VERSION": {"size": 8, "doc": "Calibration data format version."},
        "LENGTH": {"size": 8, "doc": "Length of cal_data block in bytes."},
        "CRC16": {"size": 16, "doc": "CRC-16-CCITT over cal_data."},
        "RESERVED": {"size": 16, "doc": "Reserved."},
    },
    "gpio_expander_tst": {
        "P0": {"size": 1, "doc": "Port bit 0."},
        "P1": {"size": 1, "doc": "Port bit 1."},
        "P2": {"size": 1, "doc": "Port bit 2."},
        "P3": {"size": 1, "doc": "Port bit 3."},
        "P4": {"size": 1, "doc": "Port bit 4."},
        "P5": {"size": 1, "doc": "Port bit 5."},
        "P6": {"size": 1, "doc": "Port bit 6."},
        "P7": {"size": 1, "doc": "Port bit 7."},
    },
    "ina219_config_tst": {
        "MODE": {"size": 3, "doc": "Operating mode (0\u20137). 7 = shunt + bus continuous."},
        "SADC": {"size": 4, "doc": "Shunt ADC resolution / averaging."},
        "BADC": {"size": 4, "doc": "Bus ADC resolution / averaging."},
        "PG": {"size": 2, "doc": "Programmable gain: 00 = \u00b140mV, 11 = \u00b1320mV."},
        "BRNG": {"size": 1, "doc": "Bus voltage range: 0 = 16V, 1 = 32V."},
        "RESERVED": {"size": 1, "doc": "Reserved."},
        "RST": {"size": 1, "doc": "Write 1 to reset all registers."},
    },
    "ina219_bus_voltage_tst": {
        "OVF": {"size": 1, "doc": "Math overflow flag."},
        "CNVR": {"size": 1, "doc": "Conversion ready flag."},
        "RESERVED": {"size": 1, "doc": "Reserved."},
        "BD": {"size": 13, "doc": "Bus voltage data (\u00d7 4mV)."},
    },
}

I2C_DEVICE_METADATA = {'temp_sensor': {'address': '0x48', 'part': 'TMP117', 'doc': 'High-accuracy digital temperature sensor. ±0.1°C from -20°C to +50°C.\n', 'registers': {'temperature': {'doc': 'Temperature result. Raw × 0.0078125 = °C.', 'flags': ['read'], 'path': 'TEMP_SENSOR/TEMPERATURE', 'type': 'int16', 'unit': '0.0078125 °C / LSB', 'addr': '0x00', 'reset_value': 32768, 'device_name': 'temp_sensor'}, 'config': {'doc': 'Configuration and control register.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/CONFIG', 'type': 'tmp117_config_tun', 'bitfield': 'TMP117_CONFIG_TST', 'addr': '0x01', 'reset_value': 544, 'device_name': 'temp_sensor'}, 't_high_limit': {'doc': 'High-temperature alert threshold.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/T_HIGH_LIMIT', 'type': 'int16', 'unit': '0.0078125 °C / LSB', 'addr': '0x02', 'reset_value': 24576, 'device_name': 'temp_sensor'}, 't_low_limit': {'doc': 'Low-temperature alert threshold.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/T_LOW_LIMIT', 'type': 'int16', 'unit': '0.0078125 °C / LSB', 'addr': '0x03', 'reset_value': 32768, 'device_name': 'temp_sensor'}, 'eeprom_unlock': {'doc': 'Write 0x8000 to unlock EEPROM for writing.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/EEPROM_UNLOCK', 'type': 'uint16', 'addr': '0x04', 'device_name': 'temp_sensor'}, 'eeprom1': {'doc': 'EEPROM user storage word 1.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/EEPROM1', 'type': 'uint16', 'addr': '0x05', 'device_name': 'temp_sensor'}, 'eeprom2': {'doc': 'EEPROM user storage word 2.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/EEPROM2', 'type': 'uint16', 'addr': '0x06', 'device_name': 'temp_sensor'}, 'temperature_offset': {'doc': 'User temperature offset correction.', 'flags': ['read', 'write'], 'path': 'TEMP_SENSOR/TEMPERATURE_OFFSET', 'type': 'int16', 'unit': '0.0078125 °C / LSB', 'addr': '0x07', 'device_name': 'temp_sensor'}, 'device_id': {'doc': 'Device ID. Should read 0x0117.', 'flags': ['read'], 'path': 'TEMP_SENSOR/DEVICE_ID', 'type': 'uint16', 'addr': '0x0f', 'reset_value': 279, 'device_name': 'temp_sensor'}}}, 'eeprom': {'address': '0x50', 'part': 'AT24C02', 'doc': '256-byte I²C EEPROM for calibration data and board-specific configuration storage.\n', 'registers': {'cal_header': {'doc': 'Calibration data header (magic + version + CRC).', 'flags': ['read', 'write'], 'path': 'EEPROM/CAL_HEADER', 'type': 'cal_header_tst', 'bitfield': 'CAL_HEADER_TST', 'addr': '0x00', 'length': 8, 'device_name': 'eeprom'}, 'cal_data': {'doc': 'Calibration coefficients block.', 'flags': ['read', 'write'], 'path': 'EEPROM/CAL_DATA', 'type': 'bytes', 'addr': '0x08', 'length': 240, 'device_name': 'eeprom'}, 'board_info': {'doc': 'Board serial number and revision (8 bytes).', 'flags': ['read', 'write'], 'path': 'EEPROM/BOARD_INFO', 'type': 'bytes', 'addr': '0xf8', 'length': 8, 'device_name': 'eeprom'}}}, 'gpio_expander': {'address': '0x20', 'part': 'PCF8574', 'doc': '8-bit I/O expander for auxiliary digital I/O. Directly read or write the 8-bit port.\n', 'registers': {'port': {'doc': 'Read = input pin state. Write = output latch. Bits written as 1 are pulled high (quasi-bidirectional).\n', 'flags': ['read', 'write'], 'path': 'GPIO_EXPANDER/PORT', 'type': 'gpio_expander_tun', 'bitfield': 'GPIO_EXPANDER_TST', 'device_name': 'gpio_expander'}}}, 'power_monitor': {'address': '0x40', 'part': 'INA219', 'doc': 'Current and power monitor on the supply rail. Shunt resistor: 0.1 Ω.\n', 'registers': {'config': {'doc': 'Configuration register.', 'flags': ['read', 'write'], 'path': 'POWER_MONITOR/CONFIG', 'type': 'ina219_config_tun', 'bitfield': 'INA219_CONFIG_TST', 'addr': '0x00', 'reset_value': 14751, 'device_name': 'power_monitor'}, 'shunt_voltage': {'doc': 'Shunt voltage measurement.', 'flags': ['read'], 'path': 'POWER_MONITOR/SHUNT_VOLTAGE', 'type': 'int16', 'unit': '10 µV / LSB', 'addr': '0x01', 'device_name': 'power_monitor'}, 'bus_voltage': {'doc': 'Bus voltage measurement.', 'flags': ['read'], 'path': 'POWER_MONITOR/BUS_VOLTAGE', 'type': 'ina219_bus_voltage_tun', 'unit': '4 mV / LSB (bits 15:3)', 'bitfield': 'INA219_BUS_VOLTAGE_TST', 'addr': '0x02', 'device_name': 'power_monitor'}, 'power': {'doc': 'Power = current × bus_voltage. LSB set by cal register.', 'flags': ['read'], 'path': 'POWER_MONITOR/POWER', 'type': 'uint16', 'addr': '0x03', 'device_name': 'power_monitor'}, 'current': {'doc': 'Measured current.', 'flags': ['read'], 'path': 'POWER_MONITOR/CURRENT', 'type': 'int16', 'unit': 'Depends on calibration register', 'addr': '0x04', 'device_name': 'power_monitor'}, 'calibration': {'doc': 'Calibration value. Sets current and power LSB.', 'flags': ['read', 'write'], 'path': 'POWER_MONITOR/CALIBRATION', 'type': 'uint16', 'addr': '0x05', 'device_name': 'power_monitor'}}}}

class LocatorBaseI2CDriver:
    """I2C driver for Locator Base I2C Sensor Bus Interface."""

    ENUM_TABLES = ENUM_TABLES
    BITFIELD_DEFINITIONS = BITFIELD_DEFINITIONS
    DEVICE_METADATA = I2C_DEVICE_METADATA

    ADDR_TEMP_SENSOR = 0x48
    ADDR_EEPROM = 0x50
    ADDR_GPIO_EXPANDER = 0x20
    ADDR_POWER_MONITOR = 0x40

    def __init__(self, bus) -> None:
        self._bus = bus

    def get_device_metadata(self, device_name):
        return self.DEVICE_METADATA.get(device_name, {})

    def get_register_metadata(self, device_name, register_name):
        return self.get_device_metadata(device_name).get("registers", {}).get(register_name, {})

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

    def get_converted_value(self, device_name, register_name, raw_value=None):
        metadata = self.get_register_metadata(device_name, register_name)
        if raw_value is None:
            reader = getattr(self, f"read_{device_name}_{register_name}", None)
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

    def read_temp_sensor_temperature(self):
        """Temperature result. Raw × 0.0078125 = °C."""
        raise NotImplementedError

    def read_temp_sensor_config(self):
        """Configuration and control register."""
        raise NotImplementedError

    def write_temp_sensor_config(self, value):
        """Configuration and control register."""
        raise NotImplementedError

    def read_temp_sensor_t_high_limit(self):
        """High-temperature alert threshold."""
        raise NotImplementedError

    def write_temp_sensor_t_high_limit(self, value):
        """High-temperature alert threshold."""
        raise NotImplementedError

    def read_temp_sensor_t_low_limit(self):
        """Low-temperature alert threshold."""
        raise NotImplementedError

    def write_temp_sensor_t_low_limit(self, value):
        """Low-temperature alert threshold."""
        raise NotImplementedError

    def read_temp_sensor_eeprom_unlock(self):
        """Write 0x8000 to unlock EEPROM for writing."""
        raise NotImplementedError

    def write_temp_sensor_eeprom_unlock(self, value):
        """Write 0x8000 to unlock EEPROM for writing."""
        raise NotImplementedError

    def read_temp_sensor_eeprom1(self):
        """EEPROM user storage word 1."""
        raise NotImplementedError

    def write_temp_sensor_eeprom1(self, value):
        """EEPROM user storage word 1."""
        raise NotImplementedError

    def read_temp_sensor_eeprom2(self):
        """EEPROM user storage word 2."""
        raise NotImplementedError

    def write_temp_sensor_eeprom2(self, value):
        """EEPROM user storage word 2."""
        raise NotImplementedError

    def read_temp_sensor_temperature_offset(self):
        """User temperature offset correction."""
        raise NotImplementedError

    def write_temp_sensor_temperature_offset(self, value):
        """User temperature offset correction."""
        raise NotImplementedError

    def read_temp_sensor_device_id(self):
        """Device ID. Should read 0x0117."""
        raise NotImplementedError

    def read_eeprom_cal_header(self):
        """Calibration data header (magic + version + CRC)."""
        raise NotImplementedError

    def write_eeprom_cal_header(self, value):
        """Calibration data header (magic + version + CRC)."""
        raise NotImplementedError

    def read_eeprom_cal_data(self):
        """Calibration coefficients block."""
        raise NotImplementedError

    def write_eeprom_cal_data(self, value):
        """Calibration coefficients block."""
        raise NotImplementedError

    def read_eeprom_board_info(self):
        """Board serial number and revision (8 bytes)."""
        raise NotImplementedError

    def write_eeprom_board_info(self, value):
        """Board serial number and revision (8 bytes)."""
        raise NotImplementedError

    def read_gpio_expander_port(self):
        """Read = input pin state. Write = output latch. Bits written as 1 are pulled high (quasi-bidirectional).
"""
        raise NotImplementedError

    def write_gpio_expander_port(self, value):
        """Read = input pin state. Write = output latch. Bits written as 1 are pulled high (quasi-bidirectional).
"""
        raise NotImplementedError

    def read_power_monitor_config(self):
        """Configuration register."""
        raise NotImplementedError

    def write_power_monitor_config(self, value):
        """Configuration register."""
        raise NotImplementedError

    def read_power_monitor_shunt_voltage(self):
        """Shunt voltage measurement."""
        raise NotImplementedError

    def read_power_monitor_bus_voltage(self):
        """Bus voltage measurement."""
        raise NotImplementedError

    def read_power_monitor_power(self):
        """Power = current × bus_voltage. LSB set by cal register."""
        raise NotImplementedError

    def read_power_monitor_current(self):
        """Measured current."""
        raise NotImplementedError

    def read_power_monitor_calibration(self):
        """Calibration value. Sets current and power LSB."""
        raise NotImplementedError

    def write_power_monitor_calibration(self, value):
        """Calibration value. Sets current and power LSB."""
        raise NotImplementedError

