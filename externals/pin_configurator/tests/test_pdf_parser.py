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
