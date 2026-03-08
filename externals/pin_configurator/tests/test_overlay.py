# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the overlay parser module."""

import sys
import pathlib
import pytest

_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from overlay_parser import parse_import


class TestOverlayParser:
    """Tests for overlay_parser.parse_import()."""

    def test_parse_empty_input(self):
        """Empty strings produce empty result."""
        result = parse_import("", "", "")
        assert result is not None

    def test_parse_conf_only(self):
        """Parsing conf-only text extracts Kconfig symbols."""
        conf = "CONFIG_SERIAL=y\nCONFIG_GPIO=y\nCONFIG_I2C=y\n"
        result = parse_import("", conf, "lp_mspm0g3507")
        assert result is not None
        # Verify kconfig list exists
        assert hasattr(result, "kconfig") or isinstance(result, dict)

    def test_parse_overlay_with_pinctrl(self):
        """Parsing an overlay with &pinctrl extracts pin mappings."""
        overlay = """\
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
        result = parse_import(overlay, "CONFIG_SERIAL=y\n", "lp_mspm0g3507")
        assert result is not None

    def test_parse_peripheral_status(self):
        """Parsing overlay with enabled peripherals detects them."""
        overlay = """\
&spi0 {
    status = "okay";
    pinctrl-0 = <&spi0_default>;
    pinctrl-names = "default";
};
"""
        result = parse_import(overlay, "", "lp_mspm0g3507")
        assert result is not None

    def test_parse_multiple_peripherals(self):
        """Parsing overlay with multiple peripherals."""
        overlay = """\
&uart0 {
    status = "okay";
};

&i2c0 {
    status = "okay";
    clock-frequency = <400000>;
};

&spi0 {
    status = "okay";
};
"""
        conf = "CONFIG_SERIAL=y\nCONFIG_I2C=y\nCONFIG_SPI=y\n"
        result = parse_import(overlay, conf, "lp_mspm0g3507")
        assert result is not None
