"""Auto-generated driver stub for: Locator Base SPI Peripheral Bus Interface"""

from __future__ import annotations
from dataclasses import dataclass

class LocatorBaseSPIDriver:
    """SPI driver for Locator Base SPI Peripheral Bus Interface."""

    def __init__(self, bus) -> None:
        self._bus = bus

    def dac_output_write_dac(self, *args):
        """Write 12-bit output value. CS must be toggled per write."""
        raise NotImplementedError

    def adc_input_read_sample(self, *args):
        """Read single conversion result. Assert CS, clock 24 bits."""
        raise NotImplementedError

    def adc_input_write_register(self, *args):
        """Write configuration register."""
        raise NotImplementedError

    def adc_input_read_register(self, *args):
        """Read configuration register."""
        raise NotImplementedError

    def nor_flash_read_jedec_id(self, *args):
        """Read JEDEC manufacturer (0xEF), memory type (0x40), capacity (0x18)."""
        raise NotImplementedError

    def nor_flash_read_unique_id(self, *args):
        """64-bit unique serial number."""
        raise NotImplementedError

    def nor_flash_read_status_1(self, *args):
        """Status register 1 (BUSY, WEL, BP bits)."""
        raise NotImplementedError

    def nor_flash_read_status_2(self, *args):
        """Status register 2 (QE, SRL, CMP bits)."""
        raise NotImplementedError

    def nor_flash_read_status_3(self, *args):
        """Status register 3 (WPS, DRV bits)."""
        raise NotImplementedError

    def nor_flash_write_status_1(self, *args):
        """Write status register 1."""
        raise NotImplementedError

    def nor_flash_write_enable(self, *args):
        """Set Write Enable Latch (WEL). Required before program/erase."""
        raise NotImplementedError

    def nor_flash_write_disable(self, *args):
        """Clear Write Enable Latch."""
        raise NotImplementedError

    def nor_flash_read_data(self, *args):
        """Read data starting at 24-bit address. Up to SPI clock limit."""
        raise NotImplementedError

    def nor_flash_fast_read(self, *args):
        """Fast read with dummy byte. Supports higher clock speeds."""
        raise NotImplementedError

    def nor_flash_page_program(self, *args):
        """Program up to 256 bytes within a page. Requires write_enable first."""
        raise NotImplementedError

    def nor_flash_sector_erase_4k(self, *args):
        """Erase 4 KB sector."""
        raise NotImplementedError

    def nor_flash_block_erase_32k(self, *args):
        """Erase 32 KB block."""
        raise NotImplementedError

    def nor_flash_block_erase_64k(self, *args):
        """Erase 64 KB block."""
        raise NotImplementedError

    def nor_flash_chip_erase(self, *args):
        """Erase entire chip. Takes ~40 seconds."""
        raise NotImplementedError

    def nor_flash_power_down(self, *args):
        """Enter deep power-down mode (~1µA standby)."""
        raise NotImplementedError

    def nor_flash_release_power_down(self, *args):
        """Release power-down and read device ID."""
        raise NotImplementedError

