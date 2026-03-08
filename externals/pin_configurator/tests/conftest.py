# SPDX-License-Identifier: Apache-2.0
"""Pytest fixtures for Pyontrust Pin Configurator tests."""

import sys
import pathlib

import pytest

# Ensure the package root is importable
_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))


@pytest.fixture(scope="session")
def app():
    """Create the Flask app for testing."""
    from server import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="session")
def client(app):
    """Flask test client — no running server needed."""
    return app.test_client()


@pytest.fixture()
def sample_uart_assignments():
    """Minimal UART0 pin assignments for MSPM0G3507."""
    return {
        "board": "lp_mspm0g3507",
        "assignments": [
            {
                "pin_name": "PA10", "pincm": 21, "function_id": 2,
                "af_name": "UART0_TX", "peripheral": "uart0",
                "signal": "tx", "direction": "out",
            },
            {
                "pin_name": "PA11", "pincm": 22, "function_id": 2,
                "af_name": "UART0_RX", "peripheral": "uart0",
                "signal": "rx", "direction": "in",
            },
        ],
        "peripherals": [
            {
                "name": "uart0", "dts_node": "&uart0",
                "compatible": "ti,mspm0-uart", "enabled": True,
            },
        ],
    }


@pytest.fixture()
def sample_multi_peripheral_assignments():
    """UART0 + I2C0 + GPIO pin assignments for MSPM0G3507."""
    return {
        "board": "lp_mspm0g3507",
        "assignments": [
            {
                "pin_name": "PA10", "pincm": 21, "function_id": 2,
                "af_name": "UART0_TX", "peripheral": "uart0",
                "signal": "tx", "direction": "out",
            },
            {
                "pin_name": "PA11", "pincm": 22, "function_id": 2,
                "af_name": "UART0_RX", "peripheral": "uart0",
                "signal": "rx", "direction": "in",
            },
            {
                "pin_name": "PA17", "pincm": 39, "function_id": 3,
                "af_name": "I2C0_SCL", "peripheral": "i2c0",
                "signal": "scl", "direction": "io",
            },
            {
                "pin_name": "PA18", "pincm": 40, "function_id": 3,
                "af_name": "I2C0_SDA", "peripheral": "i2c0",
                "signal": "sda", "direction": "io",
            },
        ],
        "peripherals": [
            {
                "name": "uart0", "dts_node": "&uart0",
                "compatible": "ti,mspm0-uart", "enabled": True,
            },
            {
                "name": "i2c0", "dts_node": "&i2c0",
                "compatible": "ti,mspm0-i2c", "enabled": True,
            },
            {
                "name": "gpioa", "dts_node": "&gpioa",
                "compatible": "ti,mspm0-gpio", "enabled": True,
            },
        ],
    }


@pytest.fixture()
def sample_overlay_text():
    """Sample DTS overlay text for import testing."""
    return """\
&pinctrl {
    uart0_default: uart0_default {
        group1 {
            pinmux = <PINCM1_PF_UART0_TX>;
        };
        group2 {
            pinmux = <PINCM2_PF_UART0_RX>;
            input-enable;
        };
    };
};

&uart0 {
    status = "okay";
    pinctrl-0 = <&uart0_default>;
    pinctrl-names = "default";
    current-speed = <115200>;
};
"""


@pytest.fixture()
def sample_conf_text():
    """Sample prj.conf text for import testing."""
    return "CONFIG_SERIAL=y\nCONFIG_CONSOLE=y\nCONFIG_UART_CONSOLE=y\nCONFIG_GPIO=y\n"
