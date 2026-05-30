"""Auto-generated driver stub for: Locator Base CANopen MCU Interface"""

from __future__ import annotations
import importlib

ENUM_TABLES = {
}

BITFIELD_DEFINITIONS = {
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

FIELD_METADATA_BY_GROUP = {'info': {'device_name': {'mlx': '0x100800', 'flags': ['read'], 'doc': 'Contains the device name. E.g.: "Locator Base"\n', 'path': 'LOCATORBASE/INFO/DEVICE_NAME', 'type': 'string', 'reader_name': 'read_device_name', 'writer_name': None}, 'hw_version': {'mlx': '0x100900', 'flags': ['read', 'write'], 'doc': 'Hardware version (PCB article ID). E.g.: "EL-30-10-00"\n', 'path': 'LOCATORBASE/INFO/HW_VERSION', 'type': 'string', 'reader_name': 'read_hw_version', 'writer_name': 'write_hw_version'}, 'fw_version': {'mlx': '0x100a00', 'flags': ['read'], 'doc': 'Firmware version. Format: "FW vX.Y"\n', 'path': 'LOCATORBASE/INFO/FW_VERSION', 'type': 'string', 'reader_name': 'read_fw_version', 'writer_name': None}}, 'store_parameters': {'save_all_parameters': {'mlx': '0x101001', 'flags': ['read', 'write'], 'doc': 'Write 0x65766173 ("save") to persist all parameters to flash.\n', 'path': 'LOCATORBASE/STORE_PARAMETERS/SAVE_ALL_PARAMETERS', 'type': 'uint32', 'reader_name': 'read_save_all_parameters', 'writer_name': 'write_save_all_parameters'}, 'save_comm_parameters': {'mlx': '0x101002', 'flags': ['read', 'write'], 'doc': 'Persist communication-related parameters.\n', 'path': 'LOCATORBASE/STORE_PARAMETERS/SAVE_COMM_PARAMETERS', 'type': 'uint32', 'reader_name': 'read_save_comm_parameters', 'writer_name': 'write_save_comm_parameters'}, 'save_app_parameters': {'mlx': '0x101003', 'flags': ['read', 'write'], 'doc': 'Persist application-related parameters.\n', 'path': 'LOCATORBASE/STORE_PARAMETERS/SAVE_APP_PARAMETERS', 'type': 'uint32', 'reader_name': 'read_save_app_parameters', 'writer_name': 'write_save_app_parameters'}}, 'service_info': {'stored_node_id': {'mlx': '0x100b00', 'flags': ['read', 'write'], 'doc': 'CAN node ID stored in flash. Default 0x10.\n', 'path': 'LOCATORBASE/SERVICE_INFO/STORED_NODE_ID', 'type': 'uint16', 'reader_name': 'read_stored_node_id', 'writer_name': 'write_stored_node_id'}, 'stored_can_speed': {'mlx': '0x314420', 'flags': ['read', 'write'], 'doc': 'CAN baud rate stored in flash (kbps).\n', 'path': 'LOCATORBASE/SERVICE_INFO/STORED_CAN_SPEED', 'type': 'uint16', 'reader_name': 'read_stored_can_speed', 'writer_name': 'write_stored_can_speed'}, 'serial_num': {'mlx': '0x312301', 'flags': ['read', 'write'], 'doc': 'Manufacturer serial number. E.g.: "LB301000-0001V1"\n', 'path': 'LOCATORBASE/SERVICE_INFO/SERIAL_NUM', 'type': 'string', 'reader_name': 'read_serial_num', 'writer_name': 'write_serial_num'}, 'lss_vid': {'mlx': '0x312302', 'flags': ['read', 'write'], 'doc': 'LSS vendor ID.\n', 'path': 'LOCATORBASE/SERVICE_INFO/LSS_VID', 'type': 'uint32', 'reader_name': 'read_lss_vid', 'writer_name': 'write_lss_vid'}, 'lss_pid': {'mlx': '0x312303', 'flags': ['read', 'write'], 'doc': 'LSS product ID.\n', 'path': 'LOCATORBASE/SERVICE_INFO/LSS_PID', 'type': 'uint32', 'reader_name': 'read_lss_pid', 'writer_name': 'write_lss_pid'}, 'lss_rev': {'mlx': '0x312304', 'flags': ['read', 'write'], 'doc': 'LSS product revision.\n', 'path': 'LOCATORBASE/SERVICE_INFO/LSS_REV', 'type': 'uint32', 'reader_name': 'read_lss_rev', 'writer_name': 'write_lss_rev'}, 'lss_sn': {'mlx': '0x312305', 'flags': ['read', 'write'], 'doc': 'LSS product serial number.\n', 'path': 'LOCATORBASE/SERVICE_INFO/LSS_SN', 'type': 'uint32', 'reader_name': 'read_lss_sn', 'writer_name': 'write_lss_sn'}}, 'config': {'nick_name': {'mlx': '0x312c00', 'flags': ['read', 'write'], 'doc': 'User-assignable name to differentiate multiple boards.\n', 'path': 'LOCATORBASE/CONFIG/NICK_NAME', 'type': 'string', 'reader_name': 'read_nick_name', 'writer_name': 'write_nick_name'}, 'cal_date': {'mlx': '0x312c01', 'flags': ['read', 'write'], 'doc': 'Last calibration date (ISO-8601).\n', 'path': 'LOCATORBASE/CONFIG/CAL_DATE', 'type': 'string', 'reader_name': 'read_cal_date', 'writer_name': 'write_cal_date'}}, 'digital_outputs': {'led_control': {'mlx': '0x620001', 'flags': ['read', 'write'], 'doc': 'LED on/off control bitmask.\n', 'path': 'LOCATORBASE/DIGITAL_OUTPUTS/LED_CONTROL', 'type': 'led_control_tun', 'reader_name': 'read_led_control', 'writer_name': 'write_led_control', 'bitfield': 'LED_CONTROL_TST'}}, 'digital_inputs': {'button_state': {'mlx': '0x600001', 'flags': ['read'], 'doc': 'Current state of user buttons.\n', 'path': 'LOCATORBASE/DIGITAL_INPUTS/BUTTON_STATE', 'type': 'button_state_tun', 'reader_name': 'read_button_state', 'writer_name': None, 'bitfield': 'BUTTON_STATE_TST'}}, 'status': {'device_status': {'mlx': '0x400001', 'flags': ['read'], 'doc': 'Bit-mapped device status word.\n', 'path': 'LOCATORBASE/STATUS/DEVICE_STATUS', 'type': 'device_status_tun', 'reader_name': 'read_device_status', 'writer_name': None, 'bitfield': 'DEVICE_STATUS_TST'}, 'board_temperature': {'mlx': '0x400002', 'flags': ['read'], 'doc': 'On-board temperature sensor reading × 10.\n', 'path': 'LOCATORBASE/STATUS/BOARD_TEMPERATURE', 'type': 'int16', 'reader_name': 'read_board_temperature', 'writer_name': None, 'unit': '0.1 °C'}, 'supply_voltage': {'mlx': '0x400003', 'flags': ['read'], 'doc': 'Supply rail voltage in millivolts.\n', 'path': 'LOCATORBASE/STATUS/SUPPLY_VOLTAGE', 'type': 'uint16', 'reader_name': 'read_supply_voltage', 'writer_name': None, 'unit': 'mV'}}}

class LocatorBaseOD:
    """CANopen object dictionary for Locator Base CANopen MCU Interface."""

    FIELD_METADATA_BY_GROUP = FIELD_METADATA_BY_GROUP
    ENUM_TABLES = ENUM_TABLES
    BITFIELD_DEFINITIONS = BITFIELD_DEFINITIONS

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

    def __init__(self, node, conversion_context: dict | None = None) -> None:
        self._node = node
        self._generated_conversion_context = dict(conversion_context or {})

    def get_field_metadata(self, group_name, field_name):
        return self.FIELD_METADATA_BY_GROUP.get(group_name, {}).get(field_name, {})

    def get_enum_table(self, type_name):
        return self.ENUM_TABLES.get(type_name, {})

    def get_bitfield_definition(self, type_name):
        return self.BITFIELD_DEFINITIONS.get(type_name, {})

    def _get_raw_value(self, group_name, field_name):
        metadata = self.get_field_metadata(group_name, field_name)
        reader_name = metadata.get("reader_name") or f"read_{field_name}"
        reader = getattr(self, reader_name, None)
        if reader is None:
            raise AttributeError(f"No reader available for {group_name}.{field_name}")
        return reader()

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

    def _apply_conversion_callable(self, conversion_callable, raw_value, conversion_context):
        try:
            return conversion_callable(raw_value, **conversion_context)
        except TypeError:
            try:
                return conversion_callable(raw_value)
            except TypeError:
                try:
                    return conversion_callable(value=raw_value, **conversion_context)
                except TypeError:
                    return raw_value

    def get_converted_value(self, group_name, field_name, raw_value=None):
        metadata = self.get_field_metadata(group_name, field_name)
        if raw_value is None:
            raw_value = self._get_raw_value(group_name, field_name)

        conversion_spec = metadata.get("conversion")
        if not conversion_spec:
            return raw_value

        conversion_callable = self._load_conversion_callable(conversion_spec)
        if conversion_callable is None:
            return raw_value

        conversion_context = dict(self._generated_conversion_context)
        return self._apply_conversion_callable(conversion_callable, raw_value, conversion_context)

    def get_additional_log_fields_schema(self, group_name):
        return {
            f"{field_name}_converted": None
            for field_name, metadata in self.FIELD_METADATA_BY_GROUP.get(group_name, {}).items()
            if metadata.get("conversion")
        }

    def get_additional_log_values(self, group_name, values):
        converted_values = {}
        for field_name, metadata in self.FIELD_METADATA_BY_GROUP.get(group_name, {}).items():
            if not metadata.get("conversion") or field_name not in values:
                continue
            converted_values[f"{field_name}_converted"] = self.get_converted_value(
                group_name,
                field_name,
                values[field_name],
            )
        return converted_values

    def read_device_name(self):
        """Contains the device name. E.g.: "Locator Base"
"""
        return self._node.sdo_read(0x100800)

    def read_hw_version(self):
        """Hardware version (PCB article ID). E.g.: "EL-30-10-00"
"""
        return self._node.sdo_read(0x100900)

    def write_hw_version(self, value):
        """Hardware version (PCB article ID). E.g.: "EL-30-10-00"
"""
        self._node.sdo_write(0x100900, value)

    def read_fw_version(self):
        """Firmware version. Format: "FW vX.Y"
"""
        return self._node.sdo_read(0x100a00)

    def read_save_all_parameters(self):
        """Write 0x65766173 ("save") to persist all parameters to flash.
"""
        return self._node.sdo_read(0x101001)

    def write_save_all_parameters(self, value):
        """Write 0x65766173 ("save") to persist all parameters to flash.
"""
        self._node.sdo_write(0x101001, value)

    def read_save_comm_parameters(self):
        """Persist communication-related parameters.
"""
        return self._node.sdo_read(0x101002)

    def write_save_comm_parameters(self, value):
        """Persist communication-related parameters.
"""
        self._node.sdo_write(0x101002, value)

    def read_save_app_parameters(self):
        """Persist application-related parameters.
"""
        return self._node.sdo_read(0x101003)

    def write_save_app_parameters(self, value):
        """Persist application-related parameters.
"""
        self._node.sdo_write(0x101003, value)

    def read_stored_node_id(self):
        """CAN node ID stored in flash. Default 0x10.
"""
        return self._node.sdo_read(0x100b00)

    def write_stored_node_id(self, value):
        """CAN node ID stored in flash. Default 0x10.
"""
        self._node.sdo_write(0x100b00, value)

    def read_stored_can_speed(self):
        """CAN baud rate stored in flash (kbps).
"""
        return self._node.sdo_read(0x314420)

    def write_stored_can_speed(self, value):
        """CAN baud rate stored in flash (kbps).
"""
        self._node.sdo_write(0x314420, value)

    def read_serial_num(self):
        """Manufacturer serial number. E.g.: "LB301000-0001V1"
"""
        return self._node.sdo_read(0x312301)

    def write_serial_num(self, value):
        """Manufacturer serial number. E.g.: "LB301000-0001V1"
"""
        self._node.sdo_write(0x312301, value)

    def read_lss_vid(self):
        """LSS vendor ID.
"""
        return self._node.sdo_read(0x312302)

    def write_lss_vid(self, value):
        """LSS vendor ID.
"""
        self._node.sdo_write(0x312302, value)

    def read_lss_pid(self):
        """LSS product ID.
"""
        return self._node.sdo_read(0x312303)

    def write_lss_pid(self, value):
        """LSS product ID.
"""
        self._node.sdo_write(0x312303, value)

    def read_lss_rev(self):
        """LSS product revision.
"""
        return self._node.sdo_read(0x312304)

    def write_lss_rev(self, value):
        """LSS product revision.
"""
        self._node.sdo_write(0x312304, value)

    def read_lss_sn(self):
        """LSS product serial number.
"""
        return self._node.sdo_read(0x312305)

    def write_lss_sn(self, value):
        """LSS product serial number.
"""
        self._node.sdo_write(0x312305, value)

    def read_nick_name(self):
        """User-assignable name to differentiate multiple boards.
"""
        return self._node.sdo_read(0x312c00)

    def write_nick_name(self, value):
        """User-assignable name to differentiate multiple boards.
"""
        self._node.sdo_write(0x312c00, value)

    def read_cal_date(self):
        """Last calibration date (ISO-8601).
"""
        return self._node.sdo_read(0x312c01)

    def write_cal_date(self, value):
        """Last calibration date (ISO-8601).
"""
        self._node.sdo_write(0x312c01, value)

    def read_led_control(self):
        """LED on/off control bitmask.
"""
        return self._node.sdo_read(0x620001)

    def write_led_control(self, value):
        """LED on/off control bitmask.
"""
        self._node.sdo_write(0x620001, value)

    def read_button_state(self):
        """Current state of user buttons.
"""
        return self._node.sdo_read(0x600001)

    def read_device_status(self):
        """Bit-mapped device status word.
"""
        return self._node.sdo_read(0x400001)

    def read_board_temperature(self):
        """On-board temperature sensor reading × 10.
"""
        return self._node.sdo_read(0x400002)

    def read_supply_voltage(self):
        """Supply rail voltage in millivolts.
"""
        return self._node.sdo_read(0x400003)

