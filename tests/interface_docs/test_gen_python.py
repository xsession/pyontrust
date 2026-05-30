from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DOCS_DIR = REPO_ROOT / "interface_docs"
if str(INTERFACE_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(INTERFACE_DOCS_DIR))


from generators.gen_python import gen_python_driver  # noqa: E402


def test_gen_python_driver_canopen_renders_metadata_and_conversion_hooks() -> None:
    data = {
        "interface": {
            "title": "Demo Interface",
            "transport": "canopen",
            "canopen": {
                "object dictionary": {
                    "sensors": {
                        "temperature": {
                            "mlx": 0x310001,
                            "flags": ["read"],
                            "type": {"format": "uint", "size": 16},
                            "doc": "Board temperature",
                            "unit": "°C",
                            "conversion": {
                                "implementation": {
                                    "python": {
                                        "module": "demo.conversions",
                                        "function": "convert_temperature",
                                    }
                                }
                            },
                        },
                        "status": {
                            "mlx": 0x310002,
                            "flags": ["read", "write"],
                            "type": "EXT__StatusEnum",
                            "doc": "Board status",
                        },
                        "flags_word": {
                            "mlx": 0x310003,
                            "flags": ["read"],
                            "type": "EXT__FlagsUnion",
                            "doc": "Bitfield-backed status flags",
                        },
                    }
                }
            },
        }
    }
    types = {
        "StatusEnum": {
            "format": "enum",
            "size": 8,
            "values": {"idle": 0x0, "run": 0x1},
        },
        "FlagsUnion": {
            "format": "union",
            "size": 8,
            "fields": {"all": {"format": "uint", "size": 8}, "bits": "EXT__FlagsBits"},
            "codegen": {"py": {"display": "bits"}},
        },
        "FlagsBits": {
            "format": "bitfield",
            "size": 8,
            "fields": {
                "ACTIVE": {"size": 1, "doc": "Node is active"},
                "ERROR": {"size": 1, "doc": "Node has an error"},
            },
        },
    }

    output = gen_python_driver(data, types, "DemoBoard", enum_formats=["StatusEnum"])

    assert 'ENUM_TABLES = {' in output
    assert '"StatusEnum": {' in output
    assert '"idle": 0x0,' in output
    assert 'BITFIELD_DEFINITIONS = {' in output
    assert 'FIELD_METADATA_BY_GROUP = {' in output
    assert "'unit': 'degC'" in output
    assert "'enum_table': 'STATUSENUM'" in output
    assert "'bitfield': 'FLAGSBITS'" in output
    assert 'def get_converted_value(self, group_name, field_name, raw_value=None):' in output
    assert 'def get_additional_log_fields_schema(self, group_name):' in output
    assert 'self._generated_conversion_context = dict(conversion_context or {})' in output
    assert 'def read_temperature(self):' in output
    assert 'def write_status(self, value):' in output


def test_gen_python_driver_output_compiles_for_canopen_metadata_template() -> None:
    data = {
        "interface": {
            "title": "Compile Demo",
            "transport": "canopen",
            "canopen": {
                "object dictionary": {
                    "status": {
                        "uptime": {
                            "mlx": 0x310004,
                            "flags": ["read"],
                            "type": {"format": "uint", "size": 32},
                        }
                    }
                }
            },
        }
    }

    output = gen_python_driver(data, {}, "CompileDemo")
    compile(output, "generated_canopen_driver.py", "exec")


def test_gen_python_driver_rs485_renders_register_metadata_and_helpers() -> None:
    data = {
        "interface": {
            "title": "Modbus Demo",
            "transport": "rs485",
            "rs485": {
                "modbus": {
                    "slave_id": 0x10,
                    "registers": {
                        "holding": [
                            {
                                "addr": 0x0001,
                                "name": "status",
                                "type": "EXT__StatusEnum",
                                "flags": ["read", "write"],
                                "doc": "Current status",
                            }
                        ],
                        "input": [
                            {
                                "addr": 0x0002,
                                "name": "temperature",
                                "type": "int16",
                                "flags": ["read"],
                                "unit": "°C",
                                "doc": "Temperature",
                            }
                        ],
                        "discrete": [
                            {"addr": 0x0003, "name": "fault", "doc": "Fault state"}
                        ],
                    },
                }
            },
        }
    }
    types = {
        "StatusEnum": {
            "format": "enum",
            "size": 8,
            "values": {"idle": 0x0, "run": 0x1},
        }
    }

    output = gen_python_driver(data, types, "DemoModbus", enum_formats=["StatusEnum"])

    assert "MODBUS_REGISTER_METADATA =" in output
    assert "'holding': {'status':" in output
    assert "'input': {'temperature':" in output
    assert "'discrete': {'fault':" in output
    assert "'unit': 'degC'" in output
    assert "'enum_table': 'STATUSENUM'" in output
    assert "def get_register_metadata(self, register_name, register_group=\"holding\"):" in output
    assert "def get_converted_value(self, register_name, raw_value=None, register_group=\"holding\"):" in output
    compile(output, "generated_modbus_driver.py", "exec")


def test_gen_python_driver_i2c_renders_device_and_register_metadata() -> None:
    data = {
        "interface": {
            "title": "I2C Demo",
            "transport": "i2c",
            "i2c": {
                "devices": [
                    {
                        "address": 0x48,
                        "name": "temp_sensor",
                        "part": "TMP117",
                        "doc": "Temperature sensor",
                        "registers": [
                            {
                                "addr": 0x00,
                                "name": "temperature",
                                "type": "EXT__ConfigUnion",
                                "flags": ["read"],
                                "unit": "°C",
                                "doc": "Temperature register",
                            }
                        ],
                    }
                ]
            },
        }
    }
    types = {
        "ConfigUnion": {
            "format": "union",
            "size": 16,
            "fields": {"all": {"format": "uint", "size": 16}, "bits": "EXT__ConfigBits"},
            "codegen": {"py": {"display": "bits"}},
        },
        "ConfigBits": {
            "format": "bitfield",
            "size": 16,
            "fields": {"ACTIVE": {"size": 1, "doc": "Active bit"}},
        },
    }

    output = gen_python_driver(data, types, "DemoI2C")

    assert "I2C_DEVICE_METADATA =" in output
    assert "'temp_sensor': {'address': '0x48'" in output
    assert "'registers': {'temperature':" in output
    assert "'unit': 'degC'" in output
    assert "'bitfield': 'CONFIGBITS'" in output
    assert "def get_device_metadata(self, device_name):" in output
    assert "def get_register_metadata(self, device_name, register_name):" in output
    assert "def get_converted_value(self, device_name, register_name, raw_value=None):" in output
    compile(output, "generated_i2c_driver.py", "exec")