"""Auto-generated driver stub for: Locator Base RS-485 Modbus Interface"""

from __future__ import annotations
from dataclasses import dataclass

class LocatorBaseModbusDriver:
    """Modbus RTU driver for Locator Base RS-485 Modbus Interface."""

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

