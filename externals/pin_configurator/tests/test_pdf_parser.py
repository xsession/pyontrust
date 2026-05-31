# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the PDF parser module (offline, no PDF file required)."""

import sys
import pathlib
import pytest

_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from pdf_parser import (
    DatasheetInfo,
    DeviceSummary,
    PackageInfo,
    PackagePin,
    PinMuxEntry,
    _decode_stm32_package_label,
    _finalize_packages,
    _generic_parse_package_table,
    _generic_parse_pinmux_table,
    _norm_periph,
    _stm32_parse_af,
)


class TestDataModels:
    """Verify the data model classes can be constructed correctly."""

    def test_pin_mux_entry(self):
        entry = PinMuxEntry(
            pin_name="PA0",
            pincm=1,
            function_id=2,
            function_name="UART0_TX",
            peripheral="uart0",
            signal="tx",
        )
        assert entry.pin_name == "PA0"
        assert entry.function_id == 2
        assert entry.function_name == "UART0_TX"

    def test_package_pin(self):
        pin = PackagePin(
            number=1,
            name="PA0",
            port="A",
            kind="io",
        )
        assert pin.number == 1
        assert pin.name == "PA0"

    def test_package_info(self):
        pkg = PackageInfo(
            name="LQFP48",
            pin_count=48,
            pins=[
                PackagePin(number=i, name=f"P{i}", kind="io")
                for i in range(1, 49)
            ],
        )
        assert pkg.pin_count == 48
        assert len(pkg.pins) == 48

    def test_device_summary(self):
        summary = DeviceSummary(
            soc="MSPM0G3507",
            vendor="TI",
            flash_size_kb=128,
            sram_size_kb=32,
            clock_hz=80_000_000,
        )
        assert summary.soc == "MSPM0G3507"
        assert summary.flash_size_kb == 128

    def test_datasheet_info_construction(self):
        info = DatasheetInfo(
            device=DeviceSummary(
                soc="TEST_MCU",
                vendor="TEST",
                flash_size_kb=256,
                sram_size_kb=64,
                clock_hz=120_000_000,
            ),
            packages=[],
            pin_mux={},
        )
        assert info.device.soc == "TEST_MCU"
        assert len(info.packages) == 0


class TestVendorDetection:
    """Test vendor auto-detection logic from part numbers."""

    @pytest.fixture(autouse=True)
    def _import_module(self):
        """Import the module for vendor detection tests."""
        try:
            from datasheet_fetcher import identify_vendor
            self.identify_vendor = identify_vendor
        except ImportError:
            pytest.skip("datasheet_fetcher not available")

    @pytest.mark.parametrize("part_number,expected_vendor", [
        ("STM32F401RE", "stm"),
        ("STM32L476RG", "stm"),
        ("MSPM0G3507", "ti"),
        ("NRF52840", "nordic"),
        ("ESP32", "esp"),
        ("ATSAMD21G18", "microchip"),
    ])
    def test_vendor_identification(self, part_number, expected_vendor):
        """Verify known part numbers map to correct vendors."""
        result = self.identify_vendor(part_number)
        assert result is not None
        vendor_name = result.get("vendor", "") if isinstance(result, dict) else str(result)
        assert expected_vendor.lower() in vendor_name.lower()


class TestGenericFamilyTables:
    @pytest.mark.parametrize(("func_name", "expected"), [
        ("I2S4_CK", ("i2s4", "ck")),
        ("I2S3EXT_SD", ("i2s3ext", "sd")),
        ("USART2_CTS", ("usart2", "cts")),
        ("USB_FS_SOF", ("usb", "fs_sof")),
    ])
    def test_norm_periph_handles_mixed_alnum_prefixes(self, func_name, expected):
        assert _norm_periph(func_name) == expected

    def test_decode_stm32_package_label_uses_longest_reversed_digit_group(self):
        assert _decode_stm32_package_label(")2(671AGBFU") == "UFBGA176"
        assert _decode_stm32_package_label("612AGBFT") == "TFBGA216"

    def test_stm32_parse_af_keeps_slash_delimited_functions_whole(self):
        tables = [[
            ["Port", "Pin", "AF1", "AF2", "AF7"],
            ["", "", "", "", ""],
            ["GPIOA", "PA0", "TIM2_CH1/TIM2_ETR", "TIM5_CH1", "USART2_CTS/RTS"],
        ]]

        pinmux = _stm32_parse_af(tables)

        assert "PA0" in pinmux
        names = {entry.function_name for entry in pinmux["PA0"]}
        assert "TIM2_CH1" in names
        assert "TIM2_ETR" in names
        assert "USART2_CTS" in names
        assert "USART2_RTS" in names
        assert "TIM2_" not in names
        assert "CH1" not in names

    def test_generic_parse_pinmux_table_handles_stacked_headers(self):
        table = [
            ["Pin", "I/O Pin", "Supply", "A", "", "B", "", "", "B(1,2)", "", "", "C", "D", "E"],
            ["", "", "", "EIC", "REF", "ADC0", "ADC1", "SDADC", "AC", "PTC", "DAC", "SERCOM", "SERCOM-ALT", "TC TCC"],
            ["1", "PA00", "VDDANA", "EXTINT[0]", "", "", "", "", "", "", "", "", "SERCOM1/PAD[0]", "TC2/WO[0]"],
            ["2", "PA01", "VDDANA", "EXTINT[1]", "", "", "", "", "", "", "", "", "SERCOM1/PAD[1]", "TC2/WO[1]"],
        ]

        pinmux = _generic_parse_pinmux_table(table)

        assert "PA00" in pinmux
        names = {entry.function_name for entry in pinmux["PA00"]}
        assert "EXTINT[0]" in names
        assert "SERCOM1_PAD[0]" in names
        assert "TC2_WO[0]" in names

    def test_generic_parse_package_table_handles_multi_package_columns(self):
        table = [
            ["", "Pin(1)", "", "I/O Pin", "Supply", "A", "C", "D"],
            ["SAM C21E", "SAM C21G", "SAM C21J", "", "", "EIC", "SERCOM", "SERCOM-ALT"],
            ["1", "1", "1", "PA00", "VDDANA", "EXTINT[0]", "", "SERCOM1/PAD[0]"],
            ["2", "2", "2", "PA01", "VDDANA", "EXTINT[1]", "", "SERCOM1/PAD[1]"],
        ]

        packages = _generic_parse_package_table(table, "SAM C20/C21 Family Data Sheet", "PKG_p29")

        assert sorted(packages) == ["SAMC21E", "SAMC21G", "SAMC21J"]
        assert [pin.number for pin in packages["SAMC21E"]] == [1, 2]
        assert packages["SAMC21G"][0].name == "PA00"

    def test_finalize_packages_drops_subset_fallback_and_uses_real_pin_counts(self):
        raw = {
            "SAMC21G": [
                PackagePin(number=1, name="PA00", port="A", gpio_num=0, kind="io"),
                PackagePin(number=2, name="PA01", port="A", gpio_num=1, kind="io"),
                PackagePin(number=3, name="VDDANA", port="", gpio_num=-1, kind="power"),
                PackagePin(number=4, name="RESET", port="", gpio_num=-1, kind="special"),
            ],
            "PKG_p28_0": [
                PackagePin(number=1, name="PA00", port="A", gpio_num=0, kind="io"),
                PackagePin(number=2, name="PA01", port="A", gpio_num=1, kind="io"),
            ],
            "CLUSTER": [
                PackagePin(number=1, name="PB31 PB30 PA31", port="", gpio_num=-1, kind="special"),
                PackagePin(number=2, name="PC28 PC27 PC26", port="", gpio_num=-1, kind="special"),
                PackagePin(number=3, name="PA25 PA24", port="", gpio_num=-1, kind="special"),
                PackagePin(number=4, name="PB08 PB07", port="", gpio_num=-1, kind="special"),
            ],
        }

        packages = _finalize_packages(raw)

        assert [pkg.name for pkg in packages] == ["SAMC21G"]
        assert packages[0].pin_count == 4

    def test_finalize_packages_drops_high_overlap_fallback_and_renames_residual(self):
        raw = {
            "SAMC21J": [
                PackagePin(number=1, name="PA00", port="A", gpio_num=0, kind="io"),
                PackagePin(number=2, name="PA01", port="A", gpio_num=1, kind="io"),
                PackagePin(number=3, name="PA02", port="A", gpio_num=2, kind="io"),
                PackagePin(number=4, name="PA03", port="A", gpio_num=3, kind="io"),
                PackagePin(number=5, name="VDD", port="", gpio_num=-1, kind="power"),
                PackagePin(number=6, name="GND", port="", gpio_num=-1, kind="ground"),
            ],
            "PKG_p28_0": [
                PackagePin(number=1, name="PA00", port="A", gpio_num=0, kind="io"),
                PackagePin(number=2, name="PA01", port="A", gpio_num=1, kind="io"),
                PackagePin(number=3, name="PA02", port="A", gpio_num=2, kind="io"),
                PackagePin(number=4, name="PA03", port="A", gpio_num=3, kind="io"),
                PackagePin(number=5, name="VDD", port="", gpio_num=-1, kind="power"),
            ],
            "PKG_p29_0": [
                PackagePin(number=1, name="PB00", port="B", gpio_num=0, kind="io"),
                PackagePin(number=2, name="PB01", port="B", gpio_num=1, kind="io"),
                PackagePin(number=3, name="PB02", port="B", gpio_num=2, kind="io"),
                PackagePin(number=4, name="RESET", port="", gpio_num=-1, kind="special"),
            ],
        }

        packages = _finalize_packages(raw)

        assert [pkg.name for pkg in packages] == ["PACKAGE4", "SAMC21J"]
        assert packages[0].pin_count == 4
        assert packages[1].pin_count == 6
