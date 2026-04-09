"""Auto-generated driver stub for: Locator Base CANopen MCU Interface"""

from __future__ import annotations
from dataclasses import dataclass

class LocatorBaseOD:
    """CANopen object dictionary for Locator Base CANopen MCU Interface."""

    INFO_DEVICE_NAME_MLX = 0x100800
    INFO_HW_VERSION_MLX = 0x100900
    INFO_FW_VERSION_MLX = 0x100a00
    STORE_PARAMETERS_SAVE_ALL_PARAMETERS_MLX = 0x101001
    STORE_PARAMETERS_SAVE_COMM_PARAMETERS_MLX = 0x101002
    STORE_PARAMETERS_SAVE_APP_PARAMETERS_MLX = 0x101003
    SERVICE_INFO_STORED_NODE_ID_MLX = 0x100b00
    SERVICE_INFO_STORED_CAN_SPEED_MLX = 0x314420
    SERVICE_INFO_SERIAL_NUM_MLX = 0x312301
    SERVICE_INFO_LSS_VID_MLX = 0x312302
    SERVICE_INFO_LSS_PID_MLX = 0x312303
    SERVICE_INFO_LSS_REV_MLX = 0x312304
    SERVICE_INFO_LSS_SN_MLX = 0x312305
    CONFIG_NICK_NAME_MLX = 0x312c00
    CONFIG_CAL_DATE_MLX = 0x312c01
    DIGITAL_OUTPUTS_LED_CONTROL_MLX = 0x620001
    DIGITAL_INPUTS_BUTTON_STATE_MLX = 0x600001
    STATUS_DEVICE_STATUS_MLX = 0x400001
    STATUS_BOARD_TEMPERATURE_MLX = 0x400002
    STATUS_SUPPLY_VOLTAGE_MLX = 0x400003

    def __init__(self, node) -> None:
        self._node = node

    def read_device_name(self):
        return self._node.sdo_read(0x100800)

    def read_hw_version(self):
        return self._node.sdo_read(0x100900)

    def write_hw_version(self, value):
        self._node.sdo_write(0x100900, value)

    def read_fw_version(self):
        return self._node.sdo_read(0x100a00)

    def read_save_all_parameters(self):
        return self._node.sdo_read(0x101001)

    def write_save_all_parameters(self, value):
        self._node.sdo_write(0x101001, value)

    def read_save_comm_parameters(self):
        return self._node.sdo_read(0x101002)

    def write_save_comm_parameters(self, value):
        self._node.sdo_write(0x101002, value)

    def read_save_app_parameters(self):
        return self._node.sdo_read(0x101003)

    def write_save_app_parameters(self, value):
        self._node.sdo_write(0x101003, value)

    def read_stored_node_id(self):
        return self._node.sdo_read(0x100b00)

    def write_stored_node_id(self, value):
        self._node.sdo_write(0x100b00, value)

    def read_stored_can_speed(self):
        return self._node.sdo_read(0x314420)

    def write_stored_can_speed(self, value):
        self._node.sdo_write(0x314420, value)

    def read_serial_num(self):
        return self._node.sdo_read(0x312301)

    def write_serial_num(self, value):
        self._node.sdo_write(0x312301, value)

    def read_lss_vid(self):
        return self._node.sdo_read(0x312302)

    def write_lss_vid(self, value):
        self._node.sdo_write(0x312302, value)

    def read_lss_pid(self):
        return self._node.sdo_read(0x312303)

    def write_lss_pid(self, value):
        self._node.sdo_write(0x312303, value)

    def read_lss_rev(self):
        return self._node.sdo_read(0x312304)

    def write_lss_rev(self, value):
        self._node.sdo_write(0x312304, value)

    def read_lss_sn(self):
        return self._node.sdo_read(0x312305)

    def write_lss_sn(self, value):
        self._node.sdo_write(0x312305, value)

    def read_nick_name(self):
        return self._node.sdo_read(0x312c00)

    def write_nick_name(self, value):
        self._node.sdo_write(0x312c00, value)

    def read_cal_date(self):
        return self._node.sdo_read(0x312c01)

    def write_cal_date(self, value):
        self._node.sdo_write(0x312c01, value)

    def read_led_control(self):
        return self._node.sdo_read(0x620001)

    def write_led_control(self, value):
        self._node.sdo_write(0x620001, value)

    def read_button_state(self):
        return self._node.sdo_read(0x600001)

    def read_device_status(self):
        return self._node.sdo_read(0x400001)

    def read_board_temperature(self):
        return self._node.sdo_read(0x400002)

    def read_supply_voltage(self):
        return self._node.sdo_read(0x400003)

