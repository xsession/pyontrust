"""Auto-generated driver stub for: Locator Base SPI Peripheral Bus Interface"""

from __future__ import annotations
import importlib

ENUM_TABLES = {
    "ads8681_range_ten": {
        "RANGE_3VREF": 0x0,
        "RANGE_2_5VREF": 0x1,
        "RANGE_1_5VREF": 0x2,
        "RANGE_1_25VREF": 0x3,
        "RANGE_0_625VREF": 0x4,
        "RANGE_UNI_3VREF": 0x8,
        "RANGE_UNI_2_5VREF": 0x9,
        "RANGE_UNI_1_5VREF": 0xa,
        "RANGE_UNI_1_25VREF": 0xb,
    },
}

BITFIELD_DEFINITIONS = {
    "ads8681_rst_pwrctl_tst": {
        "RESERVED_LO": {"size": 1, "doc": "Reserved."},
        "NAP_EN": {"size": 1, "doc": "Nap mode enable (low power between conversions)."},
        "PWDN": {"size": 1, "doc": "Power down: 1 = active power-down."},
        "RESERVED_MID": {"size": 5, "doc": "Reserved."},
        "RST_N": {"size": 1, "doc": "Active-low reset. Write 0 to reset."},
        "RESERVED_HI": {"size": 7, "doc": "Reserved."},
    },
    "ads8681_sdo_ctl_tst": {
        "SSC_EN": {"size": 1, "doc": "Source-synchronous clock enable."},
        "SDO_MODE": {"size": 2, "doc": "SDO output mode: 00 = normal, 01 = SPI, 10 = invalid, 11 = invalid."},
        "RESERVED": {"size": 13, "doc": "Reserved."},
    },
    "w25q_status1_tst": {
        "BUSY": {"size": 1, "doc": "Erase/write in progress."},
        "WEL": {"size": 1, "doc": "Write enable latch."},
        "BP0": {"size": 1, "doc": "Block protect bit 0."},
        "BP1": {"size": 1, "doc": "Block protect bit 1."},
        "BP2": {"size": 1, "doc": "Block protect bit 2."},
        "TB": {"size": 1, "doc": "Top/bottom protect."},
        "SEC": {"size": 1, "doc": "Sector/block protect."},
        "SRP0": {"size": 1, "doc": "Status register protect 0."},
    },
    "w25q_status2_tst": {
        "SRL": {"size": 1, "doc": "Status register lock."},
        "QE": {"size": 1, "doc": "Quad SPI enable."},
        "RESERVED": {"size": 1, "doc": "Reserved."},
        "LB1": {"size": 1, "doc": "Security register lock bit 1."},
        "LB2": {"size": 1, "doc": "Security register lock bit 2."},
        "LB3": {"size": 1, "doc": "Security register lock bit 3."},
        "CMP": {"size": 1, "doc": "Complement protect."},
        "SUS": {"size": 1, "doc": "Erase/program suspend status."},
    },
}

SPI_DEVICE_METADATA = {'dac_output': {'doc': 'Single-channel 12-bit DAC for analog test stimulus. Output range 0–4.096V (with external Vref).\n', 'part': 'MCP4921', 'transactions': {'write_dac': {'doc': 'Write 12-bit output value. CS must be toggled per write.', 'type': 'write', 'word_size': 16}}, 'commands': {}}, 'adc_input': {'doc': '16-bit SAR ADC for high-resolution analog measurement. 1 MSPS, ±12.288V input range (programmable).\n', 'part': 'ADS8681', 'transactions': {'read_sample': {'doc': 'Read single conversion result. Assert CS, clock 24 bits.', 'type': 'read', 'word_size': 24}, 'write_register': {'doc': 'Write configuration register.', 'type': 'write', 'word_size': 32}, 'read_register': {'doc': 'Read configuration register.', 'type': 'read-write', 'word_size': 32}}, 'commands': {}}, 'nor_flash': {'doc': '128 Mbit (16 MB) SPI NOR flash for firmware storage, data logging, and configuration backup. 64KB erase sectors, 256-byte page program.\n', 'part': 'W25Q128JV', 'transactions': {}, 'commands': {'read_jedec_id': {'doc': 'Read JEDEC manufacturer (0xEF), memory type (0x40), capacity (0x18).', 'opcode': '0x9f', 'addr_bytes': None}, 'read_unique_id': {'doc': '64-bit unique serial number.', 'opcode': '0x4b', 'addr_bytes': None}, 'read_status_1': {'doc': 'Status register 1 (BUSY, WEL, BP bits).', 'opcode': '0x05', 'addr_bytes': None}, 'read_status_2': {'doc': 'Status register 2 (QE, SRL, CMP bits).', 'opcode': '0x35', 'addr_bytes': None}, 'read_status_3': {'doc': 'Status register 3 (WPS, DRV bits).', 'opcode': '0x15', 'addr_bytes': None}, 'write_status_1': {'doc': 'Write status register 1.', 'opcode': '0x01', 'addr_bytes': None}, 'write_enable': {'doc': 'Set Write Enable Latch (WEL). Required before program/erase.', 'opcode': '0x06', 'addr_bytes': None}, 'write_disable': {'doc': 'Clear Write Enable Latch.', 'opcode': '0x04', 'addr_bytes': None}, 'read_data': {'doc': 'Read data starting at 24-bit address. Up to SPI clock limit.', 'opcode': '0x03', 'addr_bytes': 3}, 'fast_read': {'doc': 'Fast read with dummy byte. Supports higher clock speeds.', 'opcode': '0x0b', 'addr_bytes': 3}, 'page_program': {'doc': 'Program up to 256 bytes within a page. Requires write_enable first.', 'opcode': '0x02', 'addr_bytes': 3}, 'sector_erase_4k': {'doc': 'Erase 4 KB sector.', 'opcode': '0x20', 'addr_bytes': 3}, 'block_erase_32k': {'doc': 'Erase 32 KB block.', 'opcode': '0x52', 'addr_bytes': 3}, 'block_erase_64k': {'doc': 'Erase 64 KB block.', 'opcode': '0xd8', 'addr_bytes': 3}, 'chip_erase': {'doc': 'Erase entire chip. Takes ~40 seconds.', 'opcode': '0xc7', 'addr_bytes': None}, 'power_down': {'doc': 'Enter deep power-down mode (~1µA standby).', 'opcode': '0xb9', 'addr_bytes': None}, 'release_power_down': {'doc': 'Release power-down and read device ID.', 'opcode': '0xab', 'addr_bytes': None}}}}

class LocatorBaseSPIDriver:
    """SPI driver for Locator Base SPI Peripheral Bus Interface."""

    ENUM_TABLES = ENUM_TABLES
    BITFIELD_DEFINITIONS = BITFIELD_DEFINITIONS
    DEVICE_METADATA = SPI_DEVICE_METADATA

    def __init__(self, bus) -> None:
        self._bus = bus

    def get_device_metadata(self, device_name):
        return self.DEVICE_METADATA.get(device_name, {})

    def get_enum_table(self, type_name):
        return self.ENUM_TABLES.get(type_name, {})

    def get_bitfield_definition(self, type_name):
        return self.BITFIELD_DEFINITIONS.get(type_name, {})

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

