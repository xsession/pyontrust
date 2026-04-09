"""Auto-generated driver stub for: Locator Base I2C Sensor Bus Interface"""

from __future__ import annotations
from dataclasses import dataclass

class LocatorBaseI2CDriver:
    """I2C driver for Locator Base I2C Sensor Bus Interface."""

    ADDR_TEMP_SENSOR = 0x48
    ADDR_EEPROM = 0x50
    ADDR_GPIO_EXPANDER = 0x20
    ADDR_POWER_MONITOR = 0x40

    def __init__(self, bus) -> None:
        self._bus = bus

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

