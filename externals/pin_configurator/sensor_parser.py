# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Pyontrust Contributors
"""
Sensor Datasheet PDF Parser  –  register-map & address extractor.

Extracts **register maps**, **I2C/SPI device addresses**, **bit-field
definitions**, and a **device summary** from sensor/IC datasheets (PDF).

Works across all major sensor vendors:
  STMicroelectronics   LIS2DH12, LIS3DH, LSM6DSO, LSM9DS1, LPS22HH, HTS221, …
  Bosch Sensortec      BME280, BME680, BMP390, BMA456, BMI270, BMM150, …
  TDK InvenSense       ICM-20948, ICM-42688, MPU-6050, MPU-9250, ICP-10111, …
  Analog Devices       ADXL345, ADXL362, ADT7420, ADIS16470, MAX31875, MAX30102, …
  Honeywell            HMC5883L, TruStability HSC/SSC, HPM PM2.5, …
  Sensirion            SHT30, SHT40, SCD30, SCD40, SGP30, SGP40, SPS30, …
  ams-OSRAM            AS7341, TMD2725, TCS3472, TMF8801, …
  Texas Instruments    TMP117, HDC2080, OPT3001, ADS1115, INA219, INA260, …
  NXP                  FXOS8700, FXAS21002, MMA8451, MPL3115A2, …
  Infineon             DPS310, DPS368, TLV493D, TLE493D, …
  Renesas              FS3000, HS300x, ZMOD4410, ISL29125, …
  Measurement Specialties  MS5611, MS5637, MS8607, TSYS01, TSYS02, …
  Generic              Any IC with a register table in its PDF datasheet

The parser is designed to handle register-map tables in various formats:
  - "Addr | Name | R/W | Reset | Description" (most common)
  - "Register Map" sections with bit-field sub-tables
  - Multi-byte registers (16/24-bit)
  - Memory-mapped peripherals

Usage
-----
    from sensor_parser import parse_sensor_datasheet
    info = parse_sensor_datasheet("BME280.pdf")
    print(info.summary.part_number)       # "BME280"
    print(info.summary.i2c_addresses)     # [0x76, 0x77]
    for reg in info.register_map.registers:
        print(f"0x{reg.address:02X}  {reg.name}  {reg.access}")
    # Generate a ready-to-use C header
    header = info.to_c_header()
"""

from __future__ import annotations

import re
import logging
import textwrap
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Data Model
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class RegisterField:
    """One bit-field within a register."""
    name: str              # e.g. "ODR[3:0]", "BOOT", "BDU"
    bits: str              # e.g. "7:4", "7", "0"
    bit_high: int          # MSB position (e.g. 7)
    bit_low: int           # LSB position (e.g. 4)
    access: str = "RW"     # RO, RW, WO, RC (read-clear), W1C, etc.
    reset_value: int = 0   # default value for this field
    description: str = ""  # textual description


@dataclass
class SensorRegister:
    """One register in the device register map."""
    address: int           # hex address, e.g. 0x0F
    name: str              # e.g. "WHO_AM_I", "CTRL_REG1", "STATUS"
    size: int = 1          # register size in bytes (1, 2, 4)
    access: str = "RO"     # RO, RW, WO, RC, W1C
    reset_value: int = 0   # power-on reset value
    description: str = ""  # short description
    fields: list[RegisterField] = field(default_factory=list)

    @property
    def c_name(self) -> str:
        """C-friendly name (upper-case, underscores)."""
        return re.sub(r'[^A-Z0-9_]', '_',
                       self.name.upper().replace(" ", "_").replace("-", "_"))


@dataclass
class RegisterMap:
    """Complete register map for a sensor/IC."""
    registers: list[SensorRegister] = field(default_factory=list)
    base_address: int = 0       # memory-mapped base (0 for I2C/SPI devices)
    address_bits: int = 8       # 7-bit or 8-bit register addresses (8 default)
    auto_increment: bool = True # supports multi-byte burst reads

    def by_address(self, addr: int) -> Optional[SensorRegister]:
        """Look up a register by address."""
        for r in self.registers:
            if r.address == addr:
                return r
        return None

    def by_name(self, name: str) -> Optional[SensorRegister]:
        """Look up a register by name (case-insensitive)."""
        n = name.upper()
        for r in self.registers:
            if r.c_name == n or r.name.upper() == n:
                return r
        return None


@dataclass
class SensorAddress:
    """Device address information (I2C / SPI)."""
    protocol: str               # "i2c", "spi", "i2c+spi", "i3c"
    i2c_addresses: list[int] = field(default_factory=list)  # 7-bit addresses
    i2c_address_pin: str = ""   # pin name that selects address, e.g. "SDO", "AD0"
    spi_max_freq_hz: int = 0    # max SPI clock, e.g. 10_000_000
    spi_mode: int = -1          # SPI mode (0-3), -1 = unknown
    spi_word_size: int = 8      # bits per SPI word


@dataclass
class SensorSummary:
    """Top-level sensor/IC identification."""
    part_number: str = ""       # e.g. "BME280", "LIS2DH12", "ICM-42688-P"
    vendor: str = ""            # e.g. "bosch", "st", "tdk"
    vendor_name: str = ""       # e.g. "Bosch Sensortec", "STMicroelectronics"
    sensor_type: str = ""       # e.g. "accelerometer", "pressure", "imu"
    description: str = ""       # one-liner from datasheet title
    who_am_i_reg: int = -1      # address of WHO_AM_I / CHIP_ID register
    who_am_i_value: int = -1    # expected value, e.g. 0x33 for LIS2DH12
    supply_voltage_min: float = 0.0   # Vdd min in volts
    supply_voltage_max: float = 0.0   # Vdd max
    temp_range_min: float = -40.0     # operating temp range
    temp_range_max: float = 85.0


@dataclass
class SensorDatasheetInfo:
    """Everything extracted from one sensor datasheet PDF."""
    summary: SensorSummary = field(default_factory=SensorSummary)
    address: SensorAddress = field(default_factory=SensorAddress)
    register_map: RegisterMap = field(default_factory=RegisterMap)

    def to_c_header(self, guard_prefix: str = "") -> str:
        """Generate a C register-map header file."""
        return generate_register_header(self, guard_prefix)

    def to_zephyr_driver_regs(self) -> str:
        """Generate Zephyr-style register definitions (just #defines)."""
        return generate_register_defines(self)

    def to_json(self) -> dict:
        """Serialise to JSON-friendly dict."""
        return sensor_info_to_json(self)


# ═══════════════════════════════════════════════════════════════════════
#  Compiled regex patterns
# ═══════════════════════════════════════════════════════════════════════

# Sensor vendor detection (first page(s))
_SENSOR_VENDORS: list[tuple[str, str, re.Pattern]] = [
    ("bosch",    "Bosch Sensortec",       re.compile(r'BM[EAI]\d{3}|BMP\d{3}|BMG\d{3}|BMX\d{3}', re.I)),
    ("st",       "STMicroelectronics",    re.compile(r'LIS[23][A-Z]{1,3}\d{1,2}|LSM\d[A-Z]{2,3}\d?|LPS\d{2}[A-Z]{2}|HTS\d{3}|STTS\d{3}|IIS\d[A-Z]{2,3}|ISM\d{3}|ASM\d{3}', re.I)),
    ("tdk",      "TDK InvenSense",        re.compile(r'ICM[-]?\d{5}|MPU[-]?\d{4}|ICP[-]?\d{5}|IAM[-]?\d{5}', re.I)),
    ("adi",      "Analog Devices",        re.compile(r'ADXL\d{3,4}|ADT\d{4}|ADIS\d{4,5}|MAX\d{5}|LTC\d{4}', re.I)),
    ("ti",       "Texas Instruments",     re.compile(r'TMP\d{3}|HDC\d{4}|OPT\d{4}|ADS\d{4}|INA\d{3}|LM7[35]\d{0,2}', re.I)),
    ("nxp",      "NXP Semiconductors",    re.compile(r'FXOS\d{4}|FXAS\d{4,5}|MMA\d{3,4}|MPL\d{4}|LPC\d{4}|MPR\d{3}', re.I)),
    ("sensirion","Sensirion",             re.compile(r'SHT[34]\d|SCD[34]\d|SGP[34]\d|SPS\d{2}|SEN\d{2}', re.I)),
    ("honeywell","Honeywell",             re.compile(r'HMC\d{4}|HSC|SSC|HPM|HIH\d{4}|ABP\d?', re.I)),
    ("ams",      "ams-OSRAM",             re.compile(r'AS\d{4}|TMD\d{4}|TCS\d{4}|TMF\d{4}|TSL\d{4}', re.I)),
    ("infineon", "Infineon Technologies", re.compile(r'DPS\d{3}|TL[VE]\d{3}[A-Z]|TLE\d{4}', re.I)),
    ("renesas",  "Renesas",               re.compile(r'FS\d{4}|HS\d{3}|ZMOD\d{4}|ISL\d{5}', re.I)),
    ("te",       "TE Connectivity / Measurement Specialties",
                                          re.compile(r'MS\d{4}|TSYS\d{2}|HTU\d{2}', re.I)),
    ("microchip","Microchip Technology",  re.compile(r'MCP\d{4}|TC\d{4}|EMC\d{4}', re.I)),
]

# Sensor type classification
_SENSOR_TYPES: list[tuple[str, re.Pattern]] = [
    ("accelerometer",     re.compile(r'acceler|accel|linear\s*accel|vibration', re.I)),
    ("gyroscope",         re.compile(r'gyro|angular\s*rate', re.I)),
    ("imu",               re.compile(r'\bIMU\b|inertial\s*meas|6[\s-]?axis|9[\s-]?axis|6[\s-]?DoF|9[\s-]?DoF', re.I)),
    ("magnetometer",      re.compile(r'magneto|magnetic|compass|geomagnetic|hall\s*sensor', re.I)),
    ("touch",             re.compile(r'capacitive\s*touch|touch\s*sensor|touch\s*controller|touch\s*detect|cap\s*sense|captouch', re.I)),
    ("pressure",          re.compile(r'pressure|baromet|altimet', re.I)),
    ("temperature",       re.compile(r'temperature\s*sensor|digital\s*thermometer|thermal', re.I)),
    ("humidity",          re.compile(r'humidity|hygrom|moisture', re.I)),
    ("environmental",     re.compile(r'environmental|gas\s*sensor|air\s*quality|VOC|CO2|particulate', re.I)),
    ("light",             re.compile(r'ambient\s*light|lux|illumin|color\s*sensor|spectral|UV\s*sensor|proximity.*light|light.*proximity', re.I)),
    ("proximity",         re.compile(r'proximity|time[\s-]*of[\s-]*flight|ToF|ranging|distance', re.I)),
    ("current",           re.compile(r'current\s*(?:shunt|sense|monitor)|power\s*monitor|INA\d{3}', re.I)),
    ("adc",               re.compile(r'analog[\s-]*to[\s-]*digital|A/?D\s*converter|\bADC\b|ADS\d{4}', re.I)),
    ("dac",               re.compile(r'digital[\s-]*to[\s-]*analog|D/?A\s*converter|\bDAC\b', re.I)),
    ("rtc",               re.compile(r'real[\s-]*time\s*clock|\bRTC\b', re.I)),
    ("eeprom",            re.compile(r'\bEEPROM\b|serial\s*memory', re.I)),
    ("io_expander",       re.compile(r'I/?O\s*expander|port\s*expander|GPIO\s*expander', re.I)),
]

# Register-table header patterns
_RE_REG_TABLE_HDR = re.compile(
    r'(address|addr|offset|reg)\b.*\b(name|register|mnemonic)\b|'
    r'\b(name|register|mnemonic)\b.*\b(address|addr|offset)\b',
    re.I)

_RE_HEX_ADDR = re.compile(r'(?:0[xX])?([0-9A-Fa-f]{1,4})\s*[hH]?')
_RE_ACCESS = re.compile(r'\b(R/?W|RO|WO|R/W|W1C|RC|RW1C|R/W1C|read[\s/-]*only|write[\s/-]*only|read[\s/-]*write)\b', re.I)
_RE_BITFIELD = re.compile(r'(\w+)\s*\[(\d+)(?::(\d+))?\]')
_RE_BITS_RANGE = re.compile(r'\[?(\d+)(?::(\d+))?\]?')

# I2C address patterns
_RE_I2C_ADDR = re.compile(
    r'(?:I2C|slave|device)\s*address\s*(?:is\s*)?(?:=\s*)?'
    r'(?:0[xX])?([0-9A-Fa-f]{2})\b|'
    r'(?:0[xX])([0-9A-Fa-f]{2})\s*(?:\(.*?7[\s-]*bit|when\s+(?:SDO|AD[O0]|ADDR))',
    re.I)
_RE_I2C_7BIT = re.compile(
    r'(?:7[\s-]*bit)\s*(?:address|addr)\s*[=:]\s*(?:0[xX])?([0-9A-Fa-f]{2})',
    re.I)
_RE_SPI_FREQ = re.compile(
    r'(?:SPI|SCLK|SCK)\s*(?:clock\s*)?(?:frequency|speed|max)?\s*[=:≤<]?\s*(\d+)\s*(MHz|kHz)|'
    r'(?:up\s+to\s+)(\d+)\s*(MHz|kHz)\s*(?:SPI|SCLK|SCK|serial\s*clock)|'
    r'(?:SPI|SCLK|SCK)\S{0,5}\s+(?:up\s+to\s+)?(\d+)\s*(MHz|kHz)|'
    r'(?:SPI|SCLK|SCK)[^.;\n]{0,80}up\s+to\s+(\d+)\s*(MHz|kHz)',
    re.I)
_RE_WHO_AM_I = re.compile(
    r'(?:WHO[\s_]*AM[\s_]*I|CHIP[\s_]*ID|DEVICE[\s_]*ID|ID[\s_]*REG(?:ISTER)?)\s*'
    r'(?:=|:|\s)\s*(?:0[xX])?([0-9A-Fa-f]{2})',
    re.I)


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════

def _norm_access(raw: str) -> str:
    """Normalise register access string to RO/RW/WO/RC/W1C."""
    u = raw.upper().replace(" ", "").replace("-", "").replace("/", "")
    if u in ("RW", "R/W", "READWRITE"):
        return "RW"
    if u in ("RO", "READONLY", "R"):
        return "RO"
    if u in ("WO", "WRITEONLY", "W"):
        return "WO"
    if u in ("RC", "READCLEAR"):
        return "RC"
    if "W1C" in u or "RW1C" in u:
        return "W1C"
    return "RW"


def _parse_hex(s: str) -> int:
    """Parse a hex value from various formats: 0x1F, 1Fh, 0x1f, 31."""
    s = s.strip().upper().rstrip("H")
    if s.startswith("0X"):
        s = s[2:]
    try:
        return int(s, 16)
    except ValueError:
        try:
            return int(s, 10)
        except ValueError:
            return -1


def _extract_all_text(pdf: pdfplumber.PDF) -> list[str]:
    """Extract text from all pages with error handling."""
    texts: list[str] = [""] * len(pdf.pages)
    for idx in range(len(pdf.pages)):
        try:
            texts[idx] = pdf.pages[idx].extract_text() or ""
        except Exception as exc:
            log.warning("Page %d text extraction failed: %s", idx + 1, exc)
    return texts


def _pages_matching(texts: list[str], pattern: re.Pattern) -> list[int]:
    """Return 0-based page indices whose text matches *pattern*."""
    return [i for i, t in enumerate(texts) if pattern.search(t)]


# ═══════════════════════════════════════════════════════════════════════
#  Vendor & sensor-type detection
# ═══════════════════════════════════════════════════════════════════════

def detect_sensor_vendor(texts: list[str]) -> tuple[str, str, str]:
    """
    Detect sensor vendor and part number from first pages.
    Returns (vendor_id, vendor_name, part_number).
    """
    sample = "\n".join(texts[:8])
    for vid, vname, pat in _SENSOR_VENDORS:
        m = pat.search(sample)
        if m:
            return vid, vname, m.group(0).upper()
    # Fallback: vendor keyword search
    sample_upper = sample.upper()
    kw = [
        ("bosch",    "BOSCH SENSORTEC"),
        ("st",       "STMICROELECTRONICS"),
        ("tdk",      "INVENSENSE"),
        ("adi",      "ANALOG DEVICES"),
        ("ti",       "TEXAS INSTRUMENTS"),
        ("nxp",      "NXP SEMICONDUCTORS"),
        ("nxp",      "FREESCALE SEMICONDUCTOR"),
        ("nxp",      "FREESCALE"),
        ("sensirion","SENSIRION"),
        ("honeywell","HONEYWELL"),
        ("ams",      "AMS-OSRAM"),
        ("infineon", "INFINEON"),
        ("renesas",  "RENESAS"),
        ("te",       "MEASUREMENT SPECIALTIES"),
        ("microchip","MICROCHIP TECHNOLOGY"),
    ]
    for v, kword in kw:
        if kword in sample_upper:
            return v, kword.title(), ""
    return "unknown", "Unknown", ""


def detect_sensor_type(texts: list[str]) -> str:
    """Classify the sensor type from the datasheet text."""
    sample = "\n".join(texts[:6])
    for stype, pat in _SENSOR_TYPES:
        if pat.search(sample):
            return stype
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════
#  Register-map extraction
# ═══════════════════════════════════════════════════════════════════════

def _find_register_table_pages(texts: list[str]) -> list[int]:
    """Find pages that likely contain register tables."""
    kw = re.compile(
        r'register\s*map|register\s*table|register\s*address|'
        r'memory\s*map|register\s*summary|register\s*description|'
        r'register\s*list|register\s*set|list\s*of\s*registers',
        re.I)
    return _pages_matching(texts, kw)


def _find_register_detail_pages(texts: list[str]) -> list[int]:
    """Find pages with detailed per-register bit-field descriptions."""
    kw = re.compile(
        r'bit\s*(?:field|description|assignment)|'
        r'\[\d+:\d+\]|'
        r'(?:Bit|Field)\s+\d+.*(?:Description|Name|Function)|'
        r'(?:D7|B7|Bit\s*7)\s+.*(?:D0|B0|Bit\s*0)',
        re.I)
    return _pages_matching(texts, kw)


def _is_register_table(header: list[str]) -> tuple[bool, dict[str, int]]:
    """
    Check if a table header looks like a register map.
    Returns (is_register_table, column_mapping).
    """
    hu = [h.upper().strip() for h in header]
    cols: dict[str, int] = {}

    for ci, h in enumerate(hu):
        if not h:
            continue
        # Normalise multi-line header cells (PDF tables may have \n in cells)
        h_norm = re.sub(r'\s+', ' ', h).strip()
        if re.search(r'^ADDR|^OFFSET|^REG\s*ADDR|^ADDRESS', h_norm):
            cols["addr"] = ci
        elif re.search(r'^REGISTER\s*NAME|^NAME|^REGISTER$|^MNEMONIC|^SYMBOL|^REG\s*NAME', h_norm):
            cols["name"] = ci
        elif re.search(r'^TYPE|^ACCESS|^R/?W|^MODE', h_norm):
            cols["access"] = ci
        elif re.search(r'^RESET|^DEFAULT|^POR|^INITIAL', h_norm):
            cols["reset"] = ci
        elif re.search(r'^DESC|^FUNCTION|^COMMENT|^NOTE', h_norm):
            cols["desc"] = ci
        elif re.search(r'^SIZE|^WIDTH|^BYTES|^BITS', h_norm):
            cols["size"] = ci
        elif re.search(r'^BIT', h_norm):
            # Could be bit-field columns (Bit 7, Bit 6, …)
            cols.setdefault("bitcols", ci)

    # Must have at least address and name
    if "addr" in cols and "name" in cols:
        return True, cols
    # Some datasheets reverse order: name first, then address
    for ci, h in enumerate(hu):
        if re.search(r'ADDR|OFFSET', h) and ci > 0:
            cols["addr"] = ci
            for cj, h2 in enumerate(hu):
                if cj != ci and re.search(r'NAME|REG|MNEMONIC', h2):
                    cols["name"] = cj
                    break
            if "name" in cols:
                return True, cols

    return False, {}


def _extract_registers_from_table(
    tbl: list[list[str]], cols: dict[str, int]
) -> list[SensorRegister]:
    """Extract register entries from a table with known column mapping."""
    regs: list[SensorRegister] = []
    seen_addrs: set[int] = set()

    for row in tbl[1:]:  # skip header
        if not row:
            continue
        # Address
        addr_ci = cols["addr"]
        if addr_ci >= len(row) or not row[addr_ci]:
            continue
        raw_addr = str(row[addr_ci]).strip()
        if not raw_addr or raw_addr in ("—", "-", "–", "…", "Reserved"):
            continue
        addr = _parse_hex(raw_addr)
        if addr < 0 or addr > 0xFFFF:
            continue
        if addr in seen_addrs:
            continue  # skip duplicates from continuation rows

        # Name
        name_ci = cols["name"]
        if name_ci >= len(row) or not row[name_ci]:
            continue
        name = str(row[name_ci]).strip()
        if not name or name.upper() in ("RESERVED", "—", "-", "–", "N/A"):
            name = f"RESERVED_{addr:02X}"
            # Still track it — reserved registers are useful in maps
        name = re.sub(r'[\s\-]+', '_', name).upper()
        name = re.sub(r'[^A-Z0-9_]', '', name)
        if not name:
            continue

        # Access
        access = "RW"
        if "access" in cols:
            aci = cols["access"]
            if aci < len(row) and row[aci]:
                access = _norm_access(str(row[aci]).strip())

        # Reset value
        reset = 0
        if "reset" in cols:
            rci = cols["reset"]
            if rci < len(row) and row[rci]:
                rv = _parse_hex(str(row[rci]).strip())
                if rv >= 0:
                    reset = rv

        # Size
        size = 1
        if "size" in cols:
            sci = cols["size"]
            if sci < len(row) and row[sci]:
                try:
                    sv = int(str(row[sci]).strip())
                    if 1 <= sv <= 4:
                        size = sv
                except ValueError:
                    pass

        # Description
        desc = ""
        if "desc" in cols:
            dci = cols["desc"]
            if dci < len(row) and row[dci]:
                desc = str(row[dci]).strip()

        seen_addrs.add(addr)
        regs.append(SensorRegister(
            address=addr, name=name, size=size,
            access=access, reset_value=reset, description=desc,
        ))

    return regs


def _extract_bitfields_from_table(
    tbl: list[list[str]], reg_name: str
) -> list[RegisterField]:
    """
    Extract bit-field definitions from a per-register detail table.
    Common formats:
      Bit | Name | Access | Reset | Description
      7:4 | ODR  | RW     | 0     | Output data rate
    """
    fields: list[RegisterField] = []
    if not tbl or len(tbl) < 2:
        return fields

    header = [str(c).strip().upper() if c else "" for c in tbl[0]]
    bit_col = name_col = access_col = reset_col = desc_col = -1

    for ci, h in enumerate(header):
        if re.search(r'^BIT', h) and bit_col < 0:
            bit_col = ci
        elif re.search(r'^NAME|^FIELD|^MNEMONIC|^SYMBOL', h) and name_col < 0:
            name_col = ci
        elif re.search(r'^ACCESS|^TYPE|^R/?W|^MODE', h) and access_col < 0:
            access_col = ci
        elif re.search(r'^RESET|^DEFAULT|^POR', h) and reset_col < 0:
            reset_col = ci
        elif re.search(r'^DESC|^FUNCTION|^COMMENT', h) and desc_col < 0:
            desc_col = ci

    if bit_col < 0 or name_col < 0:
        return fields

    for row in tbl[1:]:
        if not row or len(row) <= max(bit_col, name_col):
            continue
        bits_raw = str(row[bit_col]).strip() if row[bit_col] else ""
        fname = str(row[name_col]).strip() if row[name_col] else ""
        if not bits_raw or not fname:
            continue
        if fname.upper() in ("RESERVED", "—", "-", "UNUSED"):
            continue

        # Parse bit range
        bm = _RE_BITS_RANGE.search(bits_raw)
        if bm:
            bit_high = int(bm.group(1))
            bit_low = int(bm.group(2)) if bm.group(2) else bit_high
        else:
            try:
                bit_high = bit_low = int(bits_raw)
            except ValueError:
                continue

        faccess = "RW"
        if access_col >= 0 and access_col < len(row) and row[access_col]:
            faccess = _norm_access(str(row[access_col]).strip())

        freset = 0
        if reset_col >= 0 and reset_col < len(row) and row[reset_col]:
            rv = _parse_hex(str(row[reset_col]).strip())
            if rv >= 0:
                freset = rv

        fdesc = ""
        if desc_col >= 0 and desc_col < len(row) and row[desc_col]:
            fdesc = str(row[desc_col]).strip()

        fname_clean = re.sub(r'[\s\-]+', '_', fname).upper()
        fname_clean = re.sub(r'[^A-Z0-9_]', '', fname_clean)
        bits_str = f"{bit_high}:{bit_low}" if bit_high != bit_low else str(bit_high)

        fields.append(RegisterField(
            name=fname_clean, bits=bits_str,
            bit_high=bit_high, bit_low=bit_low,
            access=faccess, reset_value=freset,
            description=fdesc,
        ))

    return fields


def _extract_bitfields_bosch_style(
    tbl: list[list[str]], reg_name: str
) -> list[RegisterField]:
    """
    Extract bit-fields from Bosch-style register description tables.

    These tables look like:
        | (empty) | Register 0xF4 | (empty) | Name | Description |
        | (empty) | "ctrl_meas"   | (empty) | (empty) | (empty) |
        | Bit 7,6,5 | ...         | (empty) | osrs_t[2:0] | Controls ... |
        | Bit 4,3,2 | ...         | (empty) | osrs_p[2:0] | Controls ... |
        | Bit 1, 0 | ...          | (empty) | mode[1:0]   | Controls ... |

    The key is: rows contain "Bit N, N, N" in an early column and
    field names (often with [n:m] notation) in a later column.
    """
    fields: list[RegisterField] = []
    if not tbl or len(tbl) < 3:
        return fields

    for row in tbl[1:]:
        if not row:
            continue
        row_strs = [str(c).strip() if c else "" for c in row]
        all_text = " ".join(row_strs)

        # Find a "Bit N, N, N" or "Bit N" pattern in any column
        bit_match = re.search(r'Bit\s+([\d,\s]+)', all_text, re.I)
        if not bit_match:
            continue

        # Parse the bit numbers
        bit_nums_raw = bit_match.group(1).strip()
        bit_nums = [int(x.strip()) for x in re.findall(r'\d+', bit_nums_raw)]
        if not bit_nums:
            continue
        bit_high = max(bit_nums)
        bit_low = min(bit_nums)

        # Find the field name — look for something with [n:m] or a short identifier
        fname = ""
        fdesc = ""
        for cell in row_strs:
            if not cell:
                continue
            # Skip cells that are just the bit pattern or the register address
            if re.match(r'^Bit\s', cell, re.I):
                continue
            if re.match(r'^Register|^"', cell, re.I):
                continue
            # Field name with bracket notation: "osrs_t[2:0]"
            nm = re.search(r'(\w+)\s*\[\d+(?::\d+)?\]', cell)
            if nm and not fname:
                fname = nm.group(1).strip()
                continue
            # If cell looks like a short name (no spaces, < 30 chars)
            if not fname and len(cell) < 30 and not re.search(r'\s{2,}', cell):
                fname = cell
                continue
            # Otherwise it's probably the description
            if cell and len(cell) > 10:
                fdesc = cell

        if not fname:
            continue

        fname_clean = re.sub(r'[\s\-]+', '_', fname).upper()
        fname_clean = re.sub(r'\[.*?\]', '', fname_clean)  # remove [n:m]
        fname_clean = re.sub(r'[^A-Z0-9_]', '', fname_clean)
        if not fname_clean:
            continue

        bits_str = f"{bit_high}:{bit_low}" if bit_high != bit_low else str(bit_high)

        fields.append(RegisterField(
            name=fname_clean, bits=bits_str,
            bit_high=bit_high, bit_low=bit_low,
            access="RW",
            description=fdesc[:200],
        ))

    return fields


def _extract_pointer_registers(texts: list[str]) -> list[SensorRegister]:
    """
    Extract registers from datasheets that use pointer-addressed schemes.

    Some sensors (e.g. TI LM73) use a Pointer Register to select internal
    registers.  The datasheet describes them as:
        "Pointer Address 00h (Read Only)"
        "PointerAddress01h(R/W)"
        "Reset State: 40h"

    This function scans the text for these patterns.
    """
    regs: list[SensorRegister] = []
    seen: set[int] = set()
    full_text = "\n".join(texts)

    # Pattern: "Pointer Address XXh" followed by register info
    # The TI datasheet merges spaces so also handle "PointerAddressXXh"
    ptr_pat = re.compile(
        r'(?:Pointer\s*Address\s*)'
        r'(?:0[xX])?([0-9A-Fa-f]{1,4})\s*[hH]?'
        r'\s*\(([^)]*)\)',
        re.I)

    # Also look for name from preceding section header like
    # "7.5.1.2 Temperature Data Register" or "7.5.1.6 Control/Status Register"
    section_pat = re.compile(
        r'(?:\d+\.)+\d+\s+(.+?)\s*(?:Register|Reg)\s*$',
        re.MULTILINE | re.I)
    sections: list[tuple[int, str]] = []
    for m in section_pat.finditer(full_text):
        sections.append((m.start(), m.group(1).strip()))

    # Also match "ResetState:XXh" or "Reset State: XXh"
    reset_pat = re.compile(
        r'Reset\s*State\s*[:\s]+(?:0[xX])?([0-9A-Fa-f]{1,8})\s*[hH]?',
        re.I)

    for m in ptr_pat.finditer(full_text):
        addr = _parse_hex(m.group(1))
        if addr < 0 or addr > 0xFF or addr in seen:
            continue

        access_raw = m.group(2).strip()
        access = "RW"
        if re.search(r'read\s*only|RO', access_raw, re.I):
            access = "RO"
        elif re.search(r'write\s*only|WO', access_raw, re.I):
            access = "WO"

        # Find the register name from the nearest preceding section header
        name = f"REG_{addr:02X}"
        for sec_pos, sec_name in reversed(sections):
            if sec_pos < m.start() and (m.start() - sec_pos) < 500:
                cname = sec_name.upper().replace(" ", "_").replace("-", "_")
                cname = re.sub(r'[^A-Z0-9_]', '', cname)
                if cname and len(cname) > 2:
                    # Remove common prefixes like "LM73_"
                    name = re.sub(r'^(?:THE\s*)?', '', cname).strip('_')
                break

        # Find reset value nearby
        reset = 0
        vicinity = full_text[m.end():m.end() + 200]
        rm = reset_pat.search(vicinity)
        if rm:
            rv = _parse_hex(rm.group(1))
            if rv >= 0:
                reset = rv

        seen.add(addr)
        regs.append(SensorRegister(
            address=addr, name=name, access=access,
            reset_value=reset,
            description=f"Pointer register 0x{addr:02X}",
        ))

    return regs


def _extract_registers_from_text(texts: list[str]) -> list[SensorRegister]:
    """
    Text-based fallback: scan for register definitions in plain text.
    Matches patterns like:
      "0x0F  WHO_AM_I  R  0x33  Device identification register"
      "Register 0x20  CTRL_REG1 (Read/Write)"
    """
    regs: list[SensorRegister] = []
    seen: set[int] = set()

    # Pattern 1: "0xHH  NAME  access  description"
    pat1 = re.compile(
        r'(?:0[xX])([0-9A-Fa-f]{2,4})\s{1,8}'
        r'([A-Z][A-Z0-9_]{2,30})\s{1,8}'
        r'(R/?W|RO|WO|R|W|Read|Write|Read/Write|Read-only|Write-only)?',
        re.I)

    # Pattern 2: "Register 0xHH: NAME"
    pat2 = re.compile(
        r'[Rr]egister\s+(?:0[xX])?([0-9A-Fa-f]{2,4})\s*[:\s]+([A-Z_][A-Z0-9_]{2,30})',
    )

    # Pattern 3: "NAME (address 0xHH)"
    pat3 = re.compile(
        r'([A-Z][A-Z0-9_]{2,30})\s*\(\s*(?:addr(?:ess)?[:\s]*)?(?:0[xX])([0-9A-Fa-f]{2,4})\s*(?:[hH])?\s*\)',
    )

    for txt in texts:
        for line in txt.split('\n'):
            line = line.strip()
            if not line:
                continue

            for pat, addr_grp, name_grp, access_grp in [
                (pat1, 1, 2, 3),
                (pat2, 1, 2, None),
                (pat3, 2, 1, None),
            ]:
                m = pat.search(line)
                if not m:
                    continue
                addr = _parse_hex(m.group(addr_grp))
                name = m.group(name_grp).strip().upper()
                name = re.sub(r'[\s\-]+', '_', name)
                name = re.sub(r'[^A-Z0-9_]', '', name)
                if addr < 0 or addr > 0xFFFF or not name or addr in seen:
                    continue
                if name in ("RESERVED", "TABLE", "REGISTER", "SECTION", "PAGE",
                            "FIGURE", "NOTE", "BIT", "DESCRIPTION"):
                    continue
                access = "RW"
                if access_grp and m.group(access_grp):
                    access = _norm_access(m.group(access_grp))
                seen.add(addr)
                regs.append(SensorRegister(
                    address=addr, name=name, access=access,
                    description=line[:120],
                ))
                break  # first pattern wins

    return regs


def _extract_category_access_table(
    pdf: pdfplumber.PDF, texts: list[str]
) -> dict[str, str]:
    """
    Extract register category → access mapping from structured tables.

    Some datasheets (e.g. BMP280) have a table like:
      Row 0: Reserved registers | Calibration data | Control registers | Data registers | …
      Row 1: do not write      | read only        | read / write      | read only      | …

    Returns dict like: {"control": "RW", "data": "RO", "status": "RO", "reset": "WO", …}
    """
    category_access: dict[str, str] = {}

    # Scan register map pages for category access tables
    reg_pages = _find_register_table_pages(texts)
    for idx in reg_pages:
        try:
            page_tables = pdf.pages[idx].extract_tables()
        except Exception:
            continue
        for tbl in page_tables:
            if not tbl or len(tbl) < 2:
                continue
            # Check if this table has category keywords in its header
            header = [str(c).strip().lower() if c else "" for c in tbl[0]]
            header_text = " ".join(header)

            # Must contain at least 2 of these category keywords
            kw_count = sum(1 for kw in ("control", "data", "status", "reset",
                                        "calibration", "reserved", "revision")
                          if kw in header_text)
            if kw_count < 2:
                continue

            # Found it — match headers to access values in the next row(s)
            for row in tbl[1:]:
                if not row:
                    continue
                row_strs = [str(c).strip().lower() if c else "" for c in row]
                row_text = " ".join(row_strs)
                if "read" not in row_text and "write" not in row_text:
                    continue

                # Match each header column to its access value
                for ci, h in enumerate(header):
                    if ci >= len(row_strs) or not row_strs[ci]:
                        continue
                    access_raw = row_strs[ci]
                    if "read" not in access_raw and "write" not in access_raw:
                        continue

                    access_val = _norm_access(access_raw.replace("do not write", "RO"))
                    # Handle "do not write" as a special case
                    if "do not" in access_raw and "write" in access_raw:
                        access_val = "RO"
                    elif "write only" in access_raw:
                        access_val = "WO"

                    # Map header to category
                    for cat in ("control", "data", "status", "reset",
                                "calibration", "reserved", "revision"):
                        if cat in h:
                            category_access[cat] = access_val
                            break

                if category_access:
                    break  # got what we need
            if category_access:
                break
        if category_access:
            break

    return category_access


def _extract_calibration_registers(texts: list[str]) -> list[SensorRegister]:
    """
    Extract calibration/compensation register definitions from text.

    Common patterns (Bosch BMP280/BME280/BME680):
      "0x88 / 0x89  dig_T1  unsigned short"
      "0x8A / 0x8B  dig_T2  signed short"
    """
    regs: list[SensorRegister] = []
    seen: set[int] = set()
    full_text = "\n".join(texts)

    # Pattern: "0xHH / 0xHH  dig_XX  type"
    calib_pat = re.compile(
        r'(?:0[xX])([0-9A-Fa-f]{2})\s*/\s*(?:0[xX])([0-9A-Fa-f]{2})\s+'
        r'(dig_[A-Z]\d+)\s+'
        r'(unsigned|signed)\s+(short|int|long|char)',
        re.I)

    for m in calib_pat.finditer(full_text):
        addr_lo = int(m.group(1), 16)
        addr_hi = int(m.group(2), 16)
        name = m.group(3).upper()
        is_unsigned = m.group(4).lower() == "unsigned"
        dtype = m.group(5).lower()

        if addr_lo in seen:
            continue
        seen.add(addr_lo)

        size = 2 if dtype == "short" else 4 if dtype in ("int", "long") else 1
        regs.append(SensorRegister(
            address=addr_lo,
            name=f"CALIB_{name}",
            size=size,
            access="RO",
            description=f"Calibration {name} ({'u' if is_unsigned else 's'}{size*8})",
        ))

    return regs


def extract_register_map(
    pdf: pdfplumber.PDF, texts: list[str]
) -> RegisterMap:
    """
    Extract the complete register map from a sensor PDF.

    Strategy:
    1. Find "register map" / "register table" pages
    2. Parse structured tables (address | name | access | …)
    3. Find per-register bit-field detail tables
    4. Fall back to text-based extraction if tables fail
    """
    regmap = RegisterMap()
    all_regs: list[SensorRegister] = []

    # ── Phase 1: structured register-summary tables ──
    reg_pages = _find_register_table_pages(texts)
    log.info("Register table candidate pages: %s", reg_pages)

    for idx in reg_pages:
        try:
            page_tables = pdf.pages[idx].extract_tables()
        except Exception:
            continue
        for tbl in page_tables:
            if not tbl or len(tbl) < 3:
                continue
            header = [str(c).strip() if c else "" for c in tbl[0]]
            is_reg, cols = _is_register_table(header)
            if is_reg:
                found = _extract_registers_from_table(tbl, cols)
                all_regs.extend(found)
                log.info("Page %d: extracted %d registers from table", idx + 1, len(found))

    # ── Phase 2: per-register bit-field detail tables ──
    detail_pages = _find_register_detail_pages(texts)
    log.info("Bit-field detail candidate pages: %s", detail_pages[:20])

    # Build a lookup for registers we already have
    reg_by_name: dict[str, SensorRegister] = {}
    for r in all_regs:
        reg_by_name[r.name] = r
        # Also index without common prefixes
        for prefix in ("REG_", "R_"):
            if r.name.startswith(prefix):
                reg_by_name[r.name[len(prefix):]] = r

    for idx in detail_pages:
        txt = texts[idx]
        # Try to identify which register this page describes
        # Common pattern: "Register name: CTRL_REG1 (20h)"
        reg_hdr = re.search(
            r'(?:Register|Reg)\s*(?:name)?[:\s]*([A-Z][A-Z0-9_]+)\s*'
            r'(?:\(?\s*(?:0[xX])?([0-9A-Fa-f]{2,4})[hH]?\s*\)?)?',
            txt)
        target_reg = None
        if reg_hdr:
            rname = reg_hdr.group(1).upper().replace("-", "_").replace(" ", "_")
            target_reg = reg_by_name.get(rname)
            if not target_reg and reg_hdr.group(2):
                addr = _parse_hex(reg_hdr.group(2))
                for r in all_regs:
                    if r.address == addr:
                        target_reg = r
                        break

        try:
            page_tables = pdf.pages[idx].extract_tables()
        except Exception:
            continue

        for tbl in page_tables:
            if not tbl or len(tbl) < 2:
                continue
            header = [str(c).strip().upper() if c else "" for c in tbl[0]]
            has_bit = any(re.search(r'BIT', h) for h in header)
            has_name = any(re.search(r'NAME|FIELD|MNEMONIC', h) for h in header)

            # BMP280-style: first column is register addr "Register 0xF3"
            # and rows have "Bit 7, 6, 5" in an inner column
            # Skip range headers like "Register 0xF7-0xF9" (multi-register tables)
            reg_in_header = None
            if not has_bit:
                for h in header:
                    # Skip range patterns: "Register 0xF7-" or "0xF7…0xF9"
                    if re.search(r'0[xX][0-9A-Fa-f]{2,4}\s*[-–…]', h):
                        continue
                    hm = re.search(r'(?:REGISTER|REG)\s*(?:0[xX])([0-9A-Fa-f]{2,4})\b', h)
                    if hm:
                        haddr = _parse_hex(hm.group(1))
                        for r in all_regs:
                            if r.address == haddr:
                                reg_in_header = r
                                break
                        break

            if reg_in_header and len(tbl) >= 3:
                # Try to extract bitfields from BMP280-style table
                fields = _extract_bitfields_bosch_style(tbl, reg_in_header.name)
                if fields:
                    reg_in_header.fields = fields
                    log.debug("Added %d Bosch-style fields to register %s",
                              len(fields), reg_in_header.name)
            elif has_bit and has_name:
                rname = target_reg.name if target_reg else "UNKNOWN"
                fields = _extract_bitfields_from_table(tbl, rname)
                if fields and target_reg:
                    target_reg.fields = fields
                    log.debug("Added %d fields to register %s", len(fields), rname)

            # Also try to find the register from "Register 0xHH" patterns in
            # the page text if we still don't have a target
            if not target_reg and not reg_in_header and has_bit:
                # Scan for "Register 0xHH" in the text near the table
                page_reg_pats = re.findall(
                    r'Register\s+(?:0[xX])([0-9A-Fa-f]{2,4})\s+"?(\w+)"?',
                    txt, re.I)
                for addr_hex, rname in page_reg_pats:
                    addr = _parse_hex(addr_hex)
                    for r in all_regs:
                        if r.address == addr:
                            fields = _extract_bitfields_from_table(tbl, r.name)
                            if fields and not r.fields:
                                r.fields = fields
                                log.debug("Added %d fields to register %s (page scan)",
                                          len(fields), r.name)
                            break

    # ── Phase 2b: pointer-based register extraction (e.g. TI LM73) ──
    # Some datasheets use "Pointer Address XXh" to identify registers
    if not all_regs:
        pointer_regs = _extract_pointer_registers(texts)
        if pointer_regs:
            all_regs.extend(pointer_regs)
            log.info("Extracted %d pointer-based registers", len(pointer_regs))

    # ── Phase 2c: calibration registers (Bosch BMP/BME style) ──
    calib_regs = _extract_calibration_registers(texts)
    if calib_regs:
        existing_addrs = {r.address for r in all_regs}
        new_calib = [r for r in calib_regs if r.address not in existing_addrs]
        if new_calib:
            all_regs.extend(new_calib)
            log.info("Extracted %d calibration registers", len(new_calib))

    # ── Phase 3: text fallback if tables gave us nothing ──
    if not all_regs:
        log.info("No register tables found, falling back to text extraction")
        all_regs = _extract_registers_from_text(texts)

    # ── Phase 4: infer access types from text & tables ──
    # Some datasheets have category-access tables (BMP280 page 24 table 1):
    #   Row 0: "Reserved registers | Calibration data | Control registers | ..."
    #   Row 1: "do not write       | read only       | read / write       | ..."
    category_access = _extract_category_access_table(pdf, texts)
    if category_access:
        log.info("Category access map: %s", category_access)

    # Also try text-based patterns as fallback
    full_text = "\n".join(texts)
    if not category_access:
        cat_pat = re.compile(
            r'(Control|Data|Status|Calibration|Reset|Revision)\s*'
            r'(?:registers?)?[^.\n]{0,60}?'
            r'(read[\s/]*only|write[\s/]*only|read\s*/?\s*write)',
            re.I)
        for m in cat_pat.finditer(full_text):
            cat = m.group(1).lower()
            access_val = _norm_access(m.group(2))
            category_access[cat] = access_val

    for r in all_regs:
        if r.access == "RW":  # only override default "RW"
            name_u = r.name.upper()

            # Try category-based access
            inferred = None
            if any(k in name_u for k in ('CTRL', 'CONFIG', 'CONTROL')):
                inferred = category_access.get("control")
            elif any(k in name_u for k in ('_MSB', '_LSB', '_XLSB', 'PRESS', 'TEMP',
                                           'DATA', 'CALIB')):
                inferred = category_access.get("data") or category_access.get("calibration")
            elif 'STATUS' in name_u:
                inferred = category_access.get("status")
            elif 'RESET' in name_u:
                inferred = category_access.get("reset")
            elif name_u in ('ID', 'CHIP_ID', 'WHO_AM_I', 'IDENTIFICATION'):
                inferred = category_access.get("revision") or "RO"

            if inferred:
                r.access = inferred

    # Deduplicate and sort by address
    seen: set[int] = set()
    unique: list[SensorRegister] = []
    for r in sorted(all_regs, key=lambda r: r.address):
        if r.address not in seen:
            seen.add(r.address)
            unique.append(r)
    regmap.registers = unique
    log.info("Total unique registers extracted: %d", len(unique))
    return regmap


# ═══════════════════════════════════════════════════════════════════════
#  I2C / SPI address extraction
# ═══════════════════════════════════════════════════════════════════════

def extract_addresses(texts: list[str]) -> SensorAddress:
    """
    Extract device communication addresses from the datasheet text.
    Detects I2C 7-bit addresses, SPI parameters, address-select pins.
    """
    addr = SensorAddress(protocol="unknown")
    sample = "\n".join(texts[:30])  # scan more pages for address info
    sample_upper = sample.upper()

    # ── Protocol detection ──
    has_i2c = bool(re.search(r'\bI2C\b|I²C|\bIIC\b|TWI|2-wire', sample, re.I))
    has_spi = bool(re.search(r'\bSPI\b|3-wire|4-wire|serial\s*peripheral', sample, re.I))
    has_i3c = bool(re.search(r'\bI3C\b|MIPI\s*I3C', sample, re.I))

    if has_i2c and has_spi:
        addr.protocol = "i2c+spi"
    elif has_i2c:
        addr.protocol = "i2c"
    elif has_spi:
        addr.protocol = "spi"
    elif has_i3c:
        addr.protocol = "i3c"

    # ── I2C addresses ──
    i2c_addrs: set[int] = set()

    # Direct "slave address 0x76/0x77" style
    for m in _RE_I2C_ADDR.finditer(sample):
        val = m.group(1) or m.group(2)
        if val:
            a = int(val, 16)
            if 0x03 <= a <= 0x77:  # valid 7-bit range
                i2c_addrs.add(a)

    # "7-bit address = 0xHH"
    for m in _RE_I2C_7BIT.finditer(sample):
        a = int(m.group(1), 16)
        if 0x03 <= a <= 0x77:
            i2c_addrs.add(a)

    # Table-based: look for address tables
    # Pattern: "SDO = GND → 0x76", "SDO = VDD → 0x77"
    # Also handle "SDO to GND ... 0x76" and "Connecting SDO to GND results in ... (0x76)"
    addr_table_pat = re.compile(
        r'(?:SDO|AD[O0]|ADDR|SA0|A0)\s*(?:=|to)?\s*(?:GND|LOW|0|VSS|VDD|HIGH|1|VDDIO)\s*'
        r'[→:=\s]+\s*(?:0[xX])([0-9A-Fa-f]{2})',
        re.I)
    for m in addr_table_pat.finditer(sample):
        a = int(m.group(1), 16)
        if 0x03 <= a <= 0x77:
            i2c_addrs.add(a)

    # Extended pattern: "Connecting SDO to GND results in slave address ... (0x76)"
    addr_long_pat = re.compile(
        r'(?:SDO|AD[O0]|ADDR|SA0|A0)\s+(?:to\s+)?(?:GND|LOW|VSS|VDD|HIGH|VDDIO)\s+'
        r'.{0,80}?(?:0[xX])([0-9A-Fa-f]{2})',
        re.I)
    for m in addr_long_pat.finditer(sample):
        a = int(m.group(1), 16)
        if 0x03 <= a <= 0x77:
            i2c_addrs.add(a)

    # Broader pattern: "110110xb" style binary address notation
    bin_pat = re.compile(r'([01]{6,7})[xX]?\s*(?:R/?W|b\s*=)', re.I)
    for m in bin_pat.finditer(sample):
        bits = m.group(1).replace('x', '0').replace('X', '0')
        try:
            a = int(bits, 2)
            if 0x03 <= a <= 0x77:
                i2c_addrs.add(a)
                # Also add the alternate (x=1)
                bits_alt = m.group(1).replace('x', '1').replace('X', '1')
                a2 = int(bits_alt, 2)
                if 0x03 <= a2 <= 0x77:
                    i2c_addrs.add(a2)
        except ValueError:
            pass

    # Broader: "choose address 0x5A, 0x5B, 0x5C, 0x5D" or "slave address 0x5A"
    # Require "slave", "I2C", "device", or "choose" before "address" to avoid
    # matching register addresses like "register address 0x2B".
    broad_addr = re.compile(
        r'(?:slave|I2C|device|choose|select)\s+(?:\S+\s+){0,3}address\s+'
        r'(?:0[xX])([0-9A-Fa-f]{2})'
        r'(?:\s*,\s*(?:0[xX])([0-9A-Fa-f]{2}))?'
        r'(?:\s*,\s*(?:0[xX])([0-9A-Fa-f]{2}))?'
        r'(?:\s*,\s*(?:0[xX])([0-9A-Fa-f]{2}))?',
        re.I)
    for m in broad_addr.finditer(sample):
        for g in range(1, 5):
            val = m.group(g)
            if val:
                a = int(val, 16)
                if 0x03 <= a <= 0x77:
                    i2c_addrs.add(a)

    # Parenthesized hex after binary address: "slave address 1110110 (0x76)"
    paren_hex = re.compile(
        r'(?:slave|I2C|device)\s+address\s+[01]{6,7}\s*\(\s*(?:0[xX])([0-9A-Fa-f]{2})\s*\)',
        re.I)
    for m in paren_hex.finditer(sample):
        a = int(m.group(1), 16)
        if 0x03 <= a <= 0x77:
            i2c_addrs.add(a)

    # Standalone parenthesized hex near "slave address" context:
    # "results in slave address\n1110110 (0x76)" or "slave address 1110111 (0x77)"
    paren_near_addr = re.compile(
        r'(?:slave|I2C|device)\s+address\s*(?:\S+\s+){0,5}\(\s*(?:0[xX])([0-9A-Fa-f]{2})\s*\)',
        re.I)
    for m in paren_near_addr.finditer(sample):
        a = int(m.group(1), 16)
        if 0x03 <= a <= 0x77:
            i2c_addrs.add(a)

    # Binary address with explicit hex in parentheses anywhere:
    # "1110110 (0x76)" or "1001000(0x48)"
    bin_with_hex = re.compile(
        r'[01]{6,7}\s*\(\s*(?:0[xX])([0-9A-Fa-f]{2})\s*\)')
    for m in bin_with_hex.finditer(sample):
        a = int(m.group(1), 16)
        if 0x03 <= a <= 0x77:
            i2c_addrs.add(a)

    # Table-based binary addresses without hex (e.g. LM73):
    # Table rows contain 7-bit binary addresses like "1001000\n1001001\n1001010"
    # near keywords like "DEVICE ADDRESS" or "ADDRESS PIN"
    if not i2c_addrs and re.search(r'DEVICE\s*ADDRESS|ADDRESS\s*PIN|SLAVE\s*ADDRESS', sample_upper):
        # Find all 7-bit binary strings that look like I2C addresses
        bin_addr_pat = re.compile(r'\b([01]{7})\b')
        for m in bin_addr_pat.finditer(sample):
            bits = m.group(1)
            try:
                a = int(bits, 2)
                if 0x03 <= a <= 0x77:
                    i2c_addrs.add(a)
            except ValueError:
                pass

    addr.i2c_addresses = sorted(i2c_addrs)

    # ── Address pin ──
    addr_pin_pat = re.compile(
        r'(?:pin|input)\s*(SDO|AD[O0]|ADDR|SA0|A0)\s*'
        r'(?:selects?|configures?|determines?|sets?)\s*(?:the\s+)?'
        r'(?:slave\s+)?(?:I2C\s+)?address',
        re.I)
    m = addr_pin_pat.search(sample)
    if m:
        addr.i2c_address_pin = m.group(1).upper()
    else:
        # "ADDR Slave Address Pin" or "ADDR IC² Slave Address Pin"
        m2 = re.search(
            r'\b(SDO|AD[O0]|ADDR|SA0|A0)\b\s+(?:\S+\s+){0,3}(?:slave\s+)?address\s*pin',
            sample, re.I)
        if m2:
            addr.i2c_address_pin = m2.group(1).upper()
        else:
            # "ADDR ... Address Select Input" (TI LM73 style)
            m2b = re.search(
                r'\b(SDO|AD[O0]|ADDR|SA0|A0)\b\s+(?:\S+\s+){0,5}address\s*select',
                sample, re.I)
            if m2b:
                addr.i2c_address_pin = m2b.group(1).upper()
            else:
                # "SDO/SA0 ... GND ... 0x76 ... VDD ... 0x77" style
                m3 = re.search(r'(SDO|AD[O0]|SA0|A0)\s+.*(?:GND|VDD).*(?:0[xX][0-9A-Fa-f]{2})', sample, re.I)
                if m3:
                    addr.i2c_address_pin = m3.group(1).upper()
                else:
                    # "SDO to GND ... 0x76" / "changeable by SDO" / "SDO pin"
                    m4 = re.search(
                        r'\b(SDO|AD[O0]|SA0|A0)\b.*(?:GND|VDD|VDDIO|address)',
                        sample, re.I)
                    if m4:
                        addr.i2c_address_pin = m4.group(1).upper()

    # ── SPI parameters ──
    m = _RE_SPI_FREQ.search(sample)
    if m:
        # Groups 1,2 for first alt; 3,4 for second; 5,6 for third; 7,8 for fourth
        freq_str = m.group(1) or m.group(3) or m.group(5) or m.group(7)
        unit_str = m.group(2) or m.group(4) or m.group(6) or m.group(8)
        if freq_str and unit_str:
            freq = int(freq_str)
            unit = unit_str.upper()
            addr.spi_max_freq_hz = freq * (1_000_000 if unit == "MHZ" else 1_000)

    # SPI mode
    _Q = r"""['\u2018\u2019\u201C\u201D"']?"""  # ASCII + Unicode smart quotes
    spi_mode_pat = re.compile(
        r'SPI\s*mode\s*' + _Q + r'(\d)' + _Q +
        r'|CPOL\s*=\s*' + _Q + r'(\d)' + _Q + r'\s*,?\s*CPHA\s*=\s*' + _Q + r'(\d)' + _Q,
        re.I)
    m = spi_mode_pat.search(sample)
    if m:
        if m.group(1):
            addr.spi_mode = int(m.group(1))
        elif m.group(2) and m.group(3):
            cpol, cpha = int(m.group(2)), int(m.group(3))
            addr.spi_mode = cpol * 2 + cpha

    # BMP280-style: "CPOL = CPHA = '0'" means mode 0, "CPOL = CPHA = '1'" means mode 3
    if addr.spi_mode < 0:
        cpol_cpha = re.compile(
            r"CPOL\s*=\s*CPHA\s*=\s*" + _Q + r"(\d)" + _Q, re.I)
        modes_found = []
        for m2 in cpol_cpha.finditer(sample):
            val = int(m2.group(1))
            modes_found.append(val * 2 + val)  # CPOL=CPHA=0 → mode 0; CPOL=CPHA=1 → mode 3
        if modes_found:
            addr.spi_mode = modes_found[0]  # primary mode

    return addr


# ═══════════════════════════════════════════════════════════════════════
#  Summary extraction (device ID, voltage, temp range)
# ═══════════════════════════════════════════════════════════════════════

def _extract_sensor_summary(
    texts: list[str], vendor: str, vendor_name: str, part_number: str
) -> SensorSummary:
    """Extract top-level sensor info."""
    summary = SensorSummary(
        part_number=part_number, vendor=vendor, vendor_name=vendor_name,
    )
    scan = "\n".join(texts[:10])

    # Sensor type
    summary.sensor_type = detect_sensor_type(texts)

    # Description — usually the first meaningful line or subtitle
    for line in scan.split('\n'):
        line = line.strip()
        if len(line) > 15 and not line.startswith('©') and not re.match(r'^Rev|^Doc|^www', line, re.I):
            # Skip part number lines and copyright
            if any(k in line.lower() for k in ('digital', 'sensor', 'accel', 'gyro', 'press',
                                                'temperature', 'humidity', 'magnetic', 'mems',
                                                'imu', 'converter', 'monitor', 'expander')):
                summary.description = line[:200]
                break

    # WHO_AM_I / CHIP_ID
    for m in _RE_WHO_AM_I.finditer(scan):
        v = int(m.group(1), 16)
        if 0 < v < 256:
            summary.who_am_i_value = v
            break

    # Find the WHO_AM_I register address from context
    who_pat = re.compile(
        r'(?:WHO[\s_]*AM[\s_]*I|CHIP[\s_]*ID|DEVICE[\s_]*ID)\s*'
        r'(?:\(?\s*(?:0[xX])([0-9A-Fa-f]{2})\s*\)?)',
        re.I)
    m = who_pat.search(scan)
    if m:
        summary.who_am_i_reg = int(m.group(1), 16)

    # Supply voltage — try most specific patterns first
    _v_found = False

    # 1) Electrical table: "VDD ... 1.71 1.8 3.6 V" (min typ max on ONE line)
    vdd_line_table = re.compile(
        r'\bVDD\b[^\n]{0,60}?(\d+\.\d+)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s*V',
        re.I)
    mt = vdd_line_table.search(scan)
    if mt:
        vals = sorted([float(mt.group(i)) for i in (1, 2, 3)])
        if 0.5 <= vals[0] <= 5.5:
            summary.supply_voltage_min = vals[0]
            summary.supply_voltage_max = vals[-1]
            _v_found = True

    # 2) "VDD = 1.8 to 3.6 V" or "supply = 2.7 to 5.5 V"
    if not _v_found:
        vdd_pat = re.compile(
            r'(?:VDD|supply|V_?DD)\s*[=:]\s*(\d+\.?\d*)\s*(?:V|to)\s*'
            r'(?:to\s+)?(\d+\.?\d*)\s*V?',
            re.I)
        m = vdd_pat.search(scan)
        if m:
            summary.supply_voltage_min = float(m.group(1))
            summary.supply_voltage_max = float(m.group(2))
            _v_found = True

    # 3) Generic "1.71 V to 3.6 V"
    if not _v_found:
        vrange = re.search(r'(\d+\.?\d*)\s*V\s*(?:to|\u2013|-)\s*(\d+\.?\d*)\s*V', scan)
        if vrange:
            v1, v2 = float(vrange.group(1)), float(vrange.group(2))
            if 0.5 <= v1 <= 5.5 and 0.5 <= v2 <= 5.5:
                summary.supply_voltage_min = min(v1, v2)
                summary.supply_voltage_max = max(v1, v2)
                _v_found = True

    # 4) Bosch-style single typical: "VDD 1.80 V"
    if not _v_found:
        vdd_single = re.search(r'\bVDD\s+(\d+\.\d+)\s*V', scan, re.I)
        if vdd_single:
            v = float(vdd_single.group(1))
            if 0.8 <= v <= 5.5:
                summary.supply_voltage_min = round(v * 0.9, 2)
                summary.supply_voltage_max = round(v * 1.1, 2)

    # Operating temperature
    temp_pat = re.compile(
        r'(?:operating|ambient)\s*(?:temperature)?[:\s]*'
        r'([+-]?\d+)\s*°?C?\s*(?:to|-)\s*([+-]?\d+)\s*°?C?',
        re.I)
    m = temp_pat.search(scan)
    if m:
        summary.temp_range_min = float(m.group(1))
        summary.temp_range_max = float(m.group(2))

    return summary


# ═══════════════════════════════════════════════════════════════════════
#  C code generation
# ═══════════════════════════════════════════════════════════════════════

def generate_register_header(info: SensorDatasheetInfo, guard_prefix: str = "") -> str:
    """
    Generate a complete C header with register map definitions.

    Output includes:
    - Include guard
    - Device info comment
    - I2C addresses
    - Register address #defines
    - Bit-field masks and shifts
    - WHO_AM_I expected value
    """
    pn = info.summary.part_number or "SENSOR"
    prefix = guard_prefix or pn.upper().replace("-", "_").replace(" ", "_")
    guard = f"__{prefix}_REGS_H__"

    lines: list[str] = []
    lines.append(f"/* SPDX-License-Identifier: Apache-2.0 */")
    lines.append(f"/**")
    lines.append(f" * @file {prefix.lower()}_regs.h")
    lines.append(f" * @brief Register map for {pn}")
    if info.summary.description:
        lines.append(f" *        {info.summary.description}")
    lines.append(f" *")
    lines.append(f" * Auto-generated by Pyontrust Sensor Parser.")
    lines.append(f" * Vendor: {info.summary.vendor_name}")
    lines.append(f" * Type:   {info.summary.sensor_type}")
    lines.append(f" */")
    lines.append(f"")
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append(f"")

    # I2C addresses
    if info.address.i2c_addresses:
        lines.append("/* ---- I2C Addresses ---- */")
        for i, a in enumerate(info.address.i2c_addresses):
            suffix = f"_{i}" if len(info.address.i2c_addresses) > 1 else ""
            lines.append(f"#define {prefix}_I2C_ADDR{suffix}  0x{a:02X}u")
        if info.address.i2c_address_pin:
            lines.append(f"/* Address selected by {info.address.i2c_address_pin} pin */")
        lines.append(f"")

    # WHO_AM_I
    if info.summary.who_am_i_value >= 0:
        lines.append("/* ---- Device Identification ---- */")
        if info.summary.who_am_i_reg >= 0:
            lines.append(f"#define {prefix}_WHO_AM_I_REG   0x{info.summary.who_am_i_reg:02X}u")
        lines.append(f"#define {prefix}_WHO_AM_I_VAL   0x{info.summary.who_am_i_value:02X}u")
        lines.append(f"")

    # Register addresses
    if info.register_map.registers:
        lines.append("/* ---- Register Addresses ---- */")
        max_name_len = max(len(f"{prefix}_REG_{r.c_name}") for r in info.register_map.registers)
        for r in info.register_map.registers:
            defname = f"{prefix}_REG_{r.c_name}"
            pad = " " * (max_name_len - len(defname) + 2)
            comment = f"  /* {r.access}"
            if r.reset_value:
                comment += f", reset=0x{r.reset_value:02X}"
            if r.description:
                comment += f" - {_ascii_safe_text(r.description)[:60]}"
            comment += " */"
            lines.append(f"#define {defname}{pad}0x{r.address:02X}u{comment}")
        lines.append(f"")

    # Bit-field masks and shifts for registers that have field info
    regs_with_fields = [r for r in info.register_map.registers if r.fields]
    if regs_with_fields:
        lines.append("/* ---- Bit-Field Definitions ---- */")
        for r in regs_with_fields:
            lines.append(f"")
            lines.append(f"/* {r.c_name} (0x{r.address:02X}) bit fields */")
            for f in r.fields:
                width = f.bit_high - f.bit_low + 1
                mask = ((1 << width) - 1) << f.bit_low
                fname = f"{prefix}_{r.c_name}_{f.name}"
                lines.append(f"#define {fname}_SHIFT  {f.bit_low}u")
                lines.append(f"#define {fname}_MASK   0x{mask:02X}u")
                if width == 1:
                    lines.append(f"#define {fname}_BIT    (1u << {f.bit_low})")
        lines.append(f"")

    lines.append(f"#endif /* {guard} */")
    return _ascii_safe_text("\n".join(lines))


def generate_register_defines(info: SensorDatasheetInfo) -> str:
    """
    Generate just the #define block for embedding in a Zephyr driver .c file.
    (No include guard / header — suitable for inlining into driver_generator output.)
    """
    pn = info.summary.part_number or "SENSOR"
    prefix = pn.upper().replace("-", "_").replace(" ", "_")
    lines: list[str] = []

    for r in info.register_map.registers:
        lines.append(f"#define REG_{r.c_name}  0x{r.address:02X}u")

    if info.summary.who_am_i_value >= 0:
        lines.append(f"")
        lines.append(f"#define EXPECTED_WHO_AM_I  0x{info.summary.who_am_i_value:02X}u")

    return _ascii_safe_text("\n".join(lines))


def _ascii_safe_text(value: str) -> str:
    text = _repair_common_mojibake(value)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        '"': '"',
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "*",
        "\u2026": "...",
        "\u2192": "->",
        "\u00b0": " deg",
        "\u00b5": "u",
        "\u00d7": "x",
        "\u2500": "-",
        "\u2502": "|",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("ascii", "replace").decode("ascii")


def _repair_common_mojibake(value: str) -> str:
    text = str(value or "")
    markers = ("Ã", "Â", "â", "ð", "€", "™")
    if not any(marker in text for marker in markers):
        return text

    candidates = [text]
    for encoding in ("latin-1", "cp1252"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        candidates.append(repaired)

    def score(candidate: str) -> tuple[int, int]:
        marker_penalty = sum(candidate.count(marker) for marker in markers)
        replacement_penalty = candidate.count("\ufffd") + candidate.count("?")
        printable = sum(1 for ch in candidate if ch.isprintable() or ch in "\r\n\t")
        return (printable - (marker_penalty * 4) - (replacement_penalty * 2), -marker_penalty)

    return max(candidates, key=score)


def _sensor_driver_name(info: SensorDatasheetInfo, override: str = "") -> str:
    raw = override.strip() or info.summary.part_number or "sensor"
    name = re.sub(r"[^a-z0-9_]+", "_", raw.lower().replace("-", "_"))
    return name.strip("_") or "sensor"


def _sensor_compatible(info: SensorDatasheetInfo, override: str = "") -> str:
    if override.strip():
        return override.strip()
    vendor = (info.summary.vendor or "vendor").strip().lower() or "vendor"
    part = (info.summary.part_number or "sensor").strip().lower().replace("_", "-")
    part = re.sub(r"[^a-z0-9-]+", "-", part).strip("-") or "sensor"
    return f"{vendor},{part}"


def _sensor_bus(info: SensorDatasheetInfo, override: str = "") -> str:
    bus = override.strip().lower()
    if bus in {"i2c", "spi"}:
        return bus
    protocol = (info.address.protocol or "").lower()
    if "i2c" in protocol:
        return "i2c"
    if "spi" in protocol:
        return "spi"
    return "i2c"


def _is_config_like_register(register: SensorRegister) -> bool:
    token = register.c_name
    markers = (
        "WHO_AM_I", "CHIP_ID", "DEVICE_ID", "ID", "STATUS", "RESET",
        "CTRL", "CONFIG", "CALIB", "TRIM", "OFFSET", "THRESH", "INT",
    )
    return any(marker in token for marker in markers)


def _sample_window(info: SensorDatasheetInfo) -> tuple[int, int]:
    scored: list[tuple[int, SensorRegister]] = []
    for register in info.register_map.registers:
        if register.access not in {"RO", "RW", "RC"}:
            continue
        if _is_config_like_register(register):
            continue
        token = register.c_name
        score = 0
        for marker in ("PRESS", "TEMP", "HUM", "OUT", "DATA", "ACC", "GYRO", "MAG", "ALS", "PROX"):
            if marker in token:
                score += 3
        if score <= 0 and register.description:
            desc = register.description.lower()
            if any(marker in desc for marker in ("sample", "measurement", "output", "data")):
                score += 2
        if score > 0:
            scored.append((score, register))

    if not scored:
        readable = [register for register in info.register_map.registers if register.access in {"RO", "RW", "RC"}]
        if readable:
            first = readable[0]
            return first.address, max(1, first.size)
        return 0, 1

    registers = sorted(
        {register.address: register for _, register in scored}.values(),
        key=lambda register: register.address,
    )
    start = registers[0].address
    end = max(register.address + max(1, register.size) - 1 for register in registers)
    return start, max(1, end - start + 1)


def _sensor_primary_channel(info: SensorDatasheetInfo) -> str:
    sensor_type = (info.summary.sensor_type or "").lower()
    if sensor_type in {"temperature"}:
        return "SENSOR_CHAN_AMBIENT_TEMP"
    if sensor_type in {"pressure", "environmental"}:
        return "SENSOR_CHAN_PRESS"
    if sensor_type in {"humidity"}:
        return "SENSOR_CHAN_HUMIDITY"
    if sensor_type in {"light"}:
        return "SENSOR_CHAN_LIGHT"
    if sensor_type in {"proximity"}:
        return "SENSOR_CHAN_PROX"
    if sensor_type in {"current"}:
        return "SENSOR_CHAN_CURRENT"
    return "SENSOR_CHAN_ALL"


def _generate_sensor_public_header(info: SensorDatasheetInfo, name: str) -> str:
    guard = f"__{name.upper()}_H__"
    regs_header = f"{name}_regs.h"
    return _ascii_safe_text(textwrap.dedent(f"""\
        /* SPDX-License-Identifier: Apache-2.0 */
        #ifndef {guard}
        #define {guard}

        #include <zephyr/device.h>
        #include <stddef.h>
        #include <stdint.h>

        #include \"{regs_header}\"

        int {name}_read_reg(const struct device *dev, uint8_t reg, uint8_t *buffer, size_t length);
        int {name}_write_reg(const struct device *dev, uint8_t reg, uint8_t value);
        int {name}_read_sample_window(const struct device *dev, uint8_t *buffer, size_t length);

        #endif /* {guard} */
    """))


def _generate_functional_zephyr_source(info: SensorDatasheetInfo, name: str, compatible: str, bus: str) -> str:
    regs_header = f"{name}_regs.h"
    primary_channel = _sensor_primary_channel(info)
    sample_start, sample_len = _sample_window(info)
    id_check = ""
    if info.summary.who_am_i_reg >= 0 and info.summary.who_am_i_value >= 0:
        id_check = textwrap.dedent(f"""\
            uint8_t chip_id = 0U;
            ret = {name}_read_reg(dev, 0x{info.summary.who_am_i_reg:02X}u, &chip_id, 1U);
            if (ret < 0) {{
                LOG_ERR(\"Failed to read device ID: %d\", ret);
                return ret;
            }}
            if (chip_id != 0x{info.summary.who_am_i_value:02X}u) {{
                LOG_ERR(\"Unexpected device ID 0x%02X\", chip_id);
                return -ENODEV;
            }}
        """)

    if bus == "spi":
        bus_include = "#include <zephyr/drivers/spi.h>"
        config_fields = "    struct spi_dt_spec spi;\n"
        helpers = textwrap.dedent(f"""\
            static int {name}_read_reg(const struct device *dev, uint8_t reg, uint8_t *buffer, size_t length)
            {{
                const struct {name}_config *cfg = dev->config;
                uint8_t address = (uint8_t)(reg | 0x80u);
                const struct spi_buf tx_bufs[] = {{{{ .buf = &address, .len = 1U }}}};
                const struct spi_buf_set tx = {{ .buffers = tx_bufs, .count = 1U }};
                const struct spi_buf rx_bufs[] = {{ {{ .buf = NULL, .len = 1U }}, {{ .buf = buffer, .len = length }} }};
                const struct spi_buf_set rx = {{ .buffers = rx_bufs, .count = 2U }};
                return spi_transceive_dt(&cfg->spi, &tx, &rx);
            }}

            static int {name}_write_reg(const struct device *dev, uint8_t reg, uint8_t value)
            {{
                const struct {name}_config *cfg = dev->config;
                uint8_t payload[2] = {{ (uint8_t)(reg & 0x7Fu), value }};
                const struct spi_buf tx_bufs[] = {{{{ .buf = payload, .len = sizeof(payload) }}}};
                const struct spi_buf_set tx = {{ .buffers = tx_bufs, .count = 1U }};
                return spi_write_dt(&cfg->spi, &tx);
            }}
        """)
        init_code = textwrap.dedent("""\
            if (!spi_is_ready_dt(&cfg->spi)) {
                LOG_ERR("SPI bus not ready");
                return -ENODEV;
            }
        """)
        config_init = "        .spi = SPI_DT_SPEC_INST_GET(inst, SPI_WORD_SET(8), 0),"
    else:
        bus_include = "#include <zephyr/drivers/i2c.h>"
        config_fields = "    struct i2c_dt_spec i2c;\n"
        helpers = textwrap.dedent(f"""\
            static int {name}_read_reg(const struct device *dev, uint8_t reg, uint8_t *buffer, size_t length)
            {{
                const struct {name}_config *cfg = dev->config;
                return i2c_burst_read_dt(&cfg->i2c, reg, buffer, length);
            }}

            static int {name}_write_reg(const struct device *dev, uint8_t reg, uint8_t value)
            {{
                const struct {name}_config *cfg = dev->config;
                return i2c_reg_write_byte_dt(&cfg->i2c, reg, value);
            }}
        """)
        init_code = textwrap.dedent("""\
            if (!i2c_is_ready_dt(&cfg->i2c)) {
                LOG_ERR("I2C bus not ready");
                return -ENODEV;
            }
        """)
        config_init = "        .i2c = I2C_DT_SPEC_INST_GET(inst),"

    description = _ascii_safe_text(info.summary.description or f"{info.summary.part_number} {info.summary.sensor_type} sensor")
    compat_macro = compatible.replace(",", "_").replace("-", "_")
    source = textwrap.dedent(f"""\
        /* SPDX-License-Identifier: Apache-2.0 */
        /**
         * @file {name}.c
         * @brief Parsed-sensor Zephyr driver for {compatible}
         *
         * {description}
         */

        #include <errno.h>
        #include <string.h>

        #include <zephyr/device.h>
        #include <zephyr/drivers/sensor.h>
        {bus_include}
        #include <zephyr/logging/log.h>

        #include \"{regs_header}\"
        #include \"{name}.h\"

        LOG_MODULE_REGISTER({name}, CONFIG_{name.upper()}_LOG_LEVEL);

        #define DT_DRV_COMPAT {compat_macro}
        #define {name.upper()}_SAMPLE_START 0x{sample_start:02X}u
        #define {name.upper()}_SAMPLE_LEN {sample_len}u

        struct {name}_config {{
        {config_fields}}};

        struct {name}_data {{
            uint8_t sample[{sample_len}u];
            uint32_t raw_value;
        }};

        {helpers}

        int {name}_read_sample_window(const struct device *dev, uint8_t *buffer, size_t length)
        {{
            if (length < {name.upper()}_SAMPLE_LEN) {{
                return -EINVAL;
            }}
            return {name}_read_reg(dev, {name.upper()}_SAMPLE_START, buffer, {name.upper()}_SAMPLE_LEN);
        }}

        static uint32_t {name}_pack_sample(const uint8_t *sample, size_t length)
        {{
            uint32_t value = 0U;
            size_t usable = length > 4U ? 4U : length;
            for (size_t index = 0; index < usable; ++index) {{
                value = (value << 8) | sample[index];
            }}
            return value;
        }}

        static int {name}_sample_fetch(const struct device *dev, enum sensor_channel chan)
        {{
            ARG_UNUSED(chan);
            struct {name}_data *data = dev->data;
            int ret = {name}_read_sample_window(dev, data->sample, sizeof(data->sample));
            if (ret < 0) {{
                return ret;
            }}
            data->raw_value = {name}_pack_sample(data->sample, sizeof(data->sample));
            return 0;
        }}

        static int {name}_channel_get(const struct device *dev, enum sensor_channel chan, struct sensor_value *val)
        {{
            struct {name}_data *data = dev->data;
            if (chan != SENSOR_CHAN_ALL && chan != {primary_channel}) {{
                return -ENOTSUP;
            }}
            val->val1 = (int32_t)data->raw_value;
            val->val2 = 0;
            return 0;
        }}

        static const struct sensor_driver_api {name}_api = {{
            .sample_fetch = {name}_sample_fetch,
            .channel_get = {name}_channel_get,
        }};

        static int {name}_init(const struct device *dev)
        {{
            const struct {name}_config *cfg = dev->config;
            ARG_UNUSED(cfg);
            int ret = 0;

        {init_code.rstrip()}

        {id_check.rstrip()}

            return 0;
        }}

        #define {name.upper()}_INST(inst)                                             \\
            static struct {name}_data {name}_data_##inst;                             \\
            static const struct {name}_config {name}_config_##inst = {{               \\
                {config_init}                                                         \\
            }};                                                                       \\
            DEVICE_DT_INST_DEFINE(inst,                                               \\
                                  {name}_init,                                        \\
                                  NULL,                                               \\
                                  &{name}_data_##inst,                                \\
                                  &{name}_config_##inst,                              \\
                                  POST_KERNEL,                                        \\
                                  CONFIG_{name.upper()}_INIT_PRIORITY,                \\
                                  &{name}_api);

        DT_INST_FOREACH_STATUS_OKAY({name.upper()}_INST)
    """)
    return _ascii_safe_text(source)


def _generate_arduino_driver(info: SensorDatasheetInfo, name: str, bus: str) -> dict:
    class_name = "".join(part.capitalize() for part in name.split("_")) + "Sensor"
    regs_header = f"{name}_regs.h"
    sample_start, sample_len = _sample_window(info)
    default_addr = info.address.i2c_addresses[0] if info.address.i2c_addresses else 0x00
    whoami_check = ""
    if info.summary.who_am_i_reg >= 0 and info.summary.who_am_i_value >= 0:
        whoami_check = textwrap.dedent(f"""\
            uint8_t chipId = 0U;
            if (!readRegister(0x{info.summary.who_am_i_reg:02X}u, chipId)) {{
              return false;
            }}
            return chipId == 0x{info.summary.who_am_i_value:02X}u;
        """)
    else:
        whoami_check = "return true;"

    header = _ascii_safe_text(textwrap.dedent(f"""\
        #pragma once

        #include <Arduino.h>
        #include <SPI.h>
        #include <Wire.h>

        #include \"{regs_header}\"

        class {class_name} {{
        public:
          bool begin(TwoWire &wire = Wire, uint8_t address = 0x{default_addr:02X});
          bool beginSPI(SPIClass &spi, uint8_t chipSelectPin, uint32_t frequency = 1000000UL);
          bool ping();
          bool readRegister(uint8_t reg, uint8_t &value);
          bool readRegisters(uint8_t reg, uint8_t *buffer, size_t length);
          bool writeRegister(uint8_t reg, uint8_t value);
          bool readSampleWindow(uint8_t *buffer, size_t length);

        private:
          bool useSpi_ = false;
          TwoWire *wire_ = nullptr;
          SPIClass *spi_ = nullptr;
          uint8_t address_ = 0x{default_addr:02X};
          uint8_t chipSelectPin_ = 0xFF;
          uint32_t spiFrequency_ = 1000000UL;
        }};
    """))

    source = _ascii_safe_text(textwrap.dedent(f"""\
        #include \"{name}.h\"

        bool {class_name}::begin(TwoWire &wire, uint8_t address) {{
          useSpi_ = false;
          wire_ = &wire;
          address_ = address;
          wire_->begin();
          return ping();
        }}

        bool {class_name}::beginSPI(SPIClass &spi, uint8_t chipSelectPin, uint32_t frequency) {{
          useSpi_ = true;
          spi_ = &spi;
          chipSelectPin_ = chipSelectPin;
          spiFrequency_ = frequency;
          pinMode(chipSelectPin_, OUTPUT);
          digitalWrite(chipSelectPin_, HIGH);
          spi_->begin();
          return ping();
        }}

        bool {class_name}::ping() {{
          {whoami_check.rstrip()}
        }}

        bool {class_name}::readRegister(uint8_t reg, uint8_t &value) {{
          return readRegisters(reg, &value, 1U);
        }}

        bool {class_name}::readRegisters(uint8_t reg, uint8_t *buffer, size_t length) {{
          if (!buffer || length == 0U) {{
            return false;
          }}
          if (useSpi_) {{
            if (!spi_) {{
              return false;
            }}
            spi_->beginTransaction(SPISettings(spiFrequency_, MSBFIRST, SPI_MODE0));
            digitalWrite(chipSelectPin_, LOW);
            spi_->transfer(static_cast<uint8_t>(reg | 0x80u));
            for (size_t index = 0; index < length; ++index) {{
              buffer[index] = spi_->transfer(0x00u);
            }}
            digitalWrite(chipSelectPin_, HIGH);
            spi_->endTransaction();
            return true;
          }}
          if (!wire_) {{
            return false;
          }}
          wire_->beginTransmission(address_);
          wire_->write(reg);
          if (wire_->endTransmission(false) != 0) {{
            return false;
          }}
          size_t received = wire_->requestFrom(static_cast<int>(address_), static_cast<int>(length));
          if (received != length) {{
            return false;
          }}
          for (size_t index = 0; index < length; ++index) {{
            buffer[index] = static_cast<uint8_t>(wire_->read());
          }}
          return true;
        }}

        bool {class_name}::writeRegister(uint8_t reg, uint8_t value) {{
          if (useSpi_) {{
            if (!spi_) {{
              return false;
            }}
            spi_->beginTransaction(SPISettings(spiFrequency_, MSBFIRST, SPI_MODE0));
            digitalWrite(chipSelectPin_, LOW);
            spi_->transfer(static_cast<uint8_t>(reg & 0x7Fu));
            spi_->transfer(value);
            digitalWrite(chipSelectPin_, HIGH);
            spi_->endTransaction();
            return true;
          }}
          if (!wire_) {{
            return false;
          }}
          wire_->beginTransmission(address_);
          wire_->write(reg);
          wire_->write(value);
          return wire_->endTransmission() == 0;
        }}

        bool {class_name}::readSampleWindow(uint8_t *buffer, size_t length) {{
          if (length < {sample_len}U) {{
            return false;
          }}
          return readRegisters(0x{sample_start:02X}u, buffer, {sample_len}U);
        }}
    """))

    example = _ascii_safe_text(textwrap.dedent(f"""\
        #include <Arduino.h>
        #include \"{name}.h\"

        {class_name} sensor;

        void setup() {{
          Serial.begin(115200);
          while (!Serial) {{
          }}

          if (!sensor.begin()) {{
            Serial.println("Sensor init failed");
            return;
          }}

          Serial.println("Sensor ready");
        }}

        void loop() {{
          uint8_t sample[{sample_len}U] = {{0}};
          if (sensor.readSampleWindow(sample, sizeof(sample))) {{
            Serial.print("Sample bytes:");
            for (size_t index = 0; index < sizeof(sample); ++index) {{
              Serial.print(' ');
              if (sample[index] < 0x10U) {{
                Serial.print('0');
              }}
              Serial.print(sample[index], HEX);
            }}
            Serial.println();
          }} else {{
            Serial.println("Sample read failed");
          }}

          delay(1000);
        }}
    """))

    return {
        "arduino_header": header,
        "arduino_source": source,
        "arduino_example": example,
    }


def _normalize_custom_template_path(path: str, driver_name: str) -> str:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        return f"custom/{driver_name}_template.txt"

    segments = []
    for segment in raw.split("/"):
        segment = re.sub(r"[^A-Za-z0-9._-]+", "_", segment.strip())
        if not segment or segment in {".", ".."}:
            continue
        segments.append(segment)

    normalized = "/".join(segments)
    if not normalized:
        return f"custom/{driver_name}_template.txt"
    if "/" not in normalized:
        normalized = f"custom/{normalized}"
    return normalized


def _render_custom_driver_template(
    template: str,
    *,
    info: SensorDatasheetInfo,
    driver_name: str,
    compatible_name: str,
    bus_name: str,
    package: dict,
    template_path: str,
) -> dict:
    context = {
        "driver_name": driver_name,
        "part_number": info.summary.part_number or "sensor",
        "vendor": info.summary.vendor or "vendor",
        "vendor_name": info.summary.vendor_name or "Vendor",
        "sensor_type": info.summary.sensor_type or "sensor",
        "compatible": compatible_name,
        "bus": bus_name,
        "description": info.summary.description or f"{info.summary.part_number} {info.summary.sensor_type} sensor",
        "register_count": str(len(info.register_map.registers)),
        "i2c_addresses": ", ".join(f"0x{address:02X}" for address in info.address.i2c_addresses),
        "zephyr_source": package.get("source_c", ""),
        "zephyr_header": package.get("header_h", ""),
        "register_header": package.get("register_header", ""),
        "register_defines": package.get("register_defines", ""),
        "arduino_header": package.get("arduino_header", ""),
        "arduino_source": package.get("arduino_source", ""),
        "arduino_example": package.get("arduino_example", ""),
    }
    context = {key: _ascii_safe_text(value) for key, value in context.items()}

    def replace_token(match: re.Match) -> str:
        token = match.group(1).strip().lower()
        return context.get(token, match.group(0))

    rendered = re.sub(r"\[\[\s*([A-Za-z0-9_]+)\s*\]\]", replace_token, template)
    return {
        "custom_template_output": _ascii_safe_text(rendered),
        "custom_template_path": _normalize_custom_template_path(template_path, driver_name),
    }


def generate_sensor_driver_package(
    info: SensorDatasheetInfo,
    *,
    name: str = "",
    compatible: str = "",
    bus: str = "",
    has_interrupt: bool = False,
    custom_template: str = "",
    custom_template_path: str = "",
) -> dict:
    from driver_generator import DriverSpec, RegisterDef, driver_to_json, generate_driver

    driver_name = _sensor_driver_name(info, name)
    compatible_name = _sensor_compatible(info, compatible)
    bus_name = _sensor_bus(info, bus)
    registers = [
        RegisterDef(name=register.c_name, address=register.address, size=register.size, rw=register.access)
        for register in info.register_map.registers
    ]

    spec = DriverSpec(
        name=driver_name,
        driver_type="sensor",
        compatible=compatible_name,
        bus=bus_name,
        description=_ascii_safe_text(info.summary.description or f"{info.summary.part_number} {info.summary.sensor_type} driver"),
        vendor=(info.summary.vendor or "vendor"),
        has_interrupt=has_interrupt,
        registers=registers,
    )
    package = driver_to_json(generate_driver(spec))
    package["source_c"] = _generate_functional_zephyr_source(info, driver_name, compatible_name, bus_name)
    package["header_h"] = _generate_sensor_public_header(info, driver_name)
    package["register_header"] = generate_register_header(info)
    package["register_defines"] = generate_register_defines(info)
    package.update(_generate_arduino_driver(info, driver_name, bus_name))
    if str(custom_template or "").strip():
        package.update(_render_custom_driver_template(
            str(custom_template),
            info=info,
            driver_name=driver_name,
            compatible_name=compatible_name,
            bus_name=bus_name,
            package=package,
            template_path=custom_template_path,
        ))
    for key, value in list(package.items()):
        if isinstance(value, str):
            package[key] = _ascii_safe_text(value)
    return package


# ═══════════════════════════════════════════════════════════════════════
#  JSON serialisation
# ═══════════════════════════════════════════════════════════════════════

def sensor_info_to_json(info: SensorDatasheetInfo) -> dict:
    """Convert SensorDatasheetInfo to a JSON-serialisable dict."""
    return {
        "summary": {
            "part_number": _ascii_safe_text(info.summary.part_number),
            "vendor": _ascii_safe_text(info.summary.vendor),
            "vendor_name": _ascii_safe_text(info.summary.vendor_name),
            "sensor_type": _ascii_safe_text(info.summary.sensor_type),
            "description": _ascii_safe_text(info.summary.description),
            "who_am_i_reg": info.summary.who_am_i_reg,
            "who_am_i_value": info.summary.who_am_i_value,
            "supply_voltage_min": info.summary.supply_voltage_min,
            "supply_voltage_max": info.summary.supply_voltage_max,
            "temp_range_min": info.summary.temp_range_min,
            "temp_range_max": info.summary.temp_range_max,
        },
        "address": {
            "protocol": _ascii_safe_text(info.address.protocol),
            "i2c_addresses": [f"0x{a:02X}" for a in info.address.i2c_addresses],
            "i2c_address_pin": _ascii_safe_text(info.address.i2c_address_pin),
            "spi_max_freq_hz": info.address.spi_max_freq_hz,
            "spi_max_freq_mhz": info.address.spi_max_freq_hz / 1_000_000 if info.address.spi_max_freq_hz else 0,
            "spi_mode": info.address.spi_mode,
            "spi_word_size": info.address.spi_word_size,
        },
        "register_map": {
            "register_count": len(info.register_map.registers),
            "address_bits": info.register_map.address_bits,
            "auto_increment": info.register_map.auto_increment,
            "registers": [
                {
                    "address": f"0x{r.address:02X}",
                    "address_int": r.address,
                    "name": _ascii_safe_text(r.name),
                    "c_name": _ascii_safe_text(r.c_name),
                    "size": r.size,
                    "access": _ascii_safe_text(r.access),
                    "reset_value": f"0x{r.reset_value:02X}",
                    "description": _ascii_safe_text(r.description),
                    "fields": [
                        {
                            "name": _ascii_safe_text(f.name),
                            "bits": f.bits,
                            "bit_high": f.bit_high,
                            "bit_low": f.bit_low,
                            "access": _ascii_safe_text(f.access),
                            "reset_value": f.reset_value,
                            "description": _ascii_safe_text(f.description),
                        }
                        for f in r.fields
                    ],
                }
                for r in info.register_map.registers
            ],
        },
    }


def sensor_info_from_json(data: dict) -> SensorDatasheetInfo:
    """Reconstruct SensorDatasheetInfo from a JSON dict."""
    s = data.get("summary", {})
    a = data.get("address", {})
    rm = data.get("register_map", {})

    summary = SensorSummary(
        part_number=s.get("part_number", ""),
        vendor=s.get("vendor", ""),
        vendor_name=s.get("vendor_name", ""),
        sensor_type=s.get("sensor_type", ""),
        description=s.get("description", ""),
        who_am_i_reg=s.get("who_am_i_reg", -1),
        who_am_i_value=s.get("who_am_i_value", -1),
        supply_voltage_min=s.get("supply_voltage_min", 0.0),
        supply_voltage_max=s.get("supply_voltage_max", 0.0),
        temp_range_min=s.get("temp_range_min", -40.0),
        temp_range_max=s.get("temp_range_max", 85.0),
    )

    i2c_addrs = []
    for x in a.get("i2c_addresses", []):
        if isinstance(x, str):
            i2c_addrs.append(int(x, 16))
        else:
            i2c_addrs.append(int(x))

    address = SensorAddress(
        protocol=a.get("protocol", "unknown"),
        i2c_addresses=i2c_addrs,
        i2c_address_pin=a.get("i2c_address_pin", ""),
        spi_max_freq_hz=a.get("spi_max_freq_hz", 0),
        spi_mode=a.get("spi_mode", -1),
        spi_word_size=a.get("spi_word_size", 8),
    )

    registers = []
    for rd in rm.get("registers", []):
        fields = []
        for fd in rd.get("fields", []):
            fields.append(RegisterField(
                name=fd["name"],
                bits=fd["bits"],
                bit_high=fd["bit_high"],
                bit_low=fd["bit_low"],
                access=fd.get("access", "RW"),
                reset_value=fd.get("reset_value", 0),
                description=fd.get("description", ""),
            ))
        addr_val = rd.get("address_int", 0)
        if addr_val == 0 and isinstance(rd.get("address"), str):
            addr_val = int(rd["address"], 16)
        registers.append(SensorRegister(
            address=addr_val,
            name=rd["name"],
            size=rd.get("size", 1),
            access=rd.get("access", "RW"),
            reset_value=int(rd.get("reset_value", "0x00"), 16) if isinstance(rd.get("reset_value"), str) else rd.get("reset_value", 0),
            description=rd.get("description", ""),
            fields=fields,
        ))

    regmap = RegisterMap(
        registers=registers,
        address_bits=rm.get("address_bits", 8),
        auto_increment=rm.get("auto_increment", True),
    )

    return SensorDatasheetInfo(
        summary=summary,
        address=address,
        register_map=regmap,
    )


# ═══════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════

def parse_sensor_datasheet(
    pdf_path: str, verbose: bool = False
) -> SensorDatasheetInfo:
    """
    Parse a sensor/IC datasheet PDF and extract register map, addresses,
    and device identification.

    Supports datasheets from Bosch, ST, TDK, ADI, TI, NXP, Sensirion,
    Honeywell, ams, Infineon, Renesas, TE, Microchip, and generic ICs.

    Parameters
    ----------
    pdf_path : str
        Path to the sensor datasheet PDF.
    verbose : bool
        Enable debug logging.

    Returns
    -------
    SensorDatasheetInfo
        Complete extracted information including register map,
        I2C/SPI addresses, bit-field definitions, and device summary.
    """
    # Always suppress pdfminer's extremely verbose per-token debug logging
    # which can output millions of lines and hang/timeout on large PDFs.
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    log.info("Parsing sensor datasheet: %s", pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        texts = _extract_all_text(pdf)
        log.info("Extracted text from %d pages", len(texts))

        # Identify sensor
        vendor, vendor_name, part_number = detect_sensor_vendor(texts)
        log.info("Detected sensor vendor: %s (%s), part: %s",
                 vendor, vendor_name, part_number)

        # Extract summary
        summary = _extract_sensor_summary(texts, vendor, vendor_name, part_number)

        # Extract addresses
        address = extract_addresses(texts)
        log.info("Protocol: %s, I2C addresses: %s",
                 address.protocol,
                 [f"0x{a:02X}" for a in address.i2c_addresses])

        # Extract register map
        regmap = extract_register_map(pdf, texts)
        log.info("Registers: %d, with bit-fields: %d",
                 len(regmap.registers),
                 sum(1 for r in regmap.registers if r.fields))

        # Cross-reference: find WHO_AM_I register in map
        if summary.who_am_i_reg < 0:
            for r in regmap.registers:
                if any(k in r.name for k in ("WHO_AM_I", "CHIP_ID", "DEVICE_ID", "ID")):
                    summary.who_am_i_reg = r.address
                    if r.reset_value > 0 and summary.who_am_i_value < 0:
                        summary.who_am_i_value = r.reset_value
                    break

        info = SensorDatasheetInfo(
            summary=summary,
            address=address,
            register_map=regmap,
        )

        log.info("Sensor parsing complete: %s (%s) — %d regs, %d I2C addrs",
                 summary.part_number, summary.sensor_type,
                 len(regmap.registers), len(address.i2c_addresses))

        return info


def identify_sensor(part_number: str) -> Optional[tuple[str, str]]:
    """
    Identify sensor vendor from a part number string (no PDF needed).

    Returns (vendor_id, vendor_name) or None.
    """
    for vid, vname, pat in _SENSOR_VENDORS:
        if pat.search(part_number):
            return vid, vname
    return None
