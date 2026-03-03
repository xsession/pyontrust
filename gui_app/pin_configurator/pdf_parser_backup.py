"""
MCU Datasheet PDF Parser – extracts pin-mux and package information.

Supports:
  * **Texas Instruments MSPM0** family datasheets (PINCM tables)
  * **STMicroelectronics STM32** family datasheets (AF0-AF15 tables)

The parser looks for:
  1. **Package pin-out tables** – mapping physical pin number → pin name
     for each package variant (e.g. 48-QFP, 64-QFP, 32-QFN …).
  2. **Pin-mux tables** –
     * TI: PINCM function table (function codes 0–N)
     * STM32: Alternate-function mapping tables (AF0–AF15)
  3. **Device summary** – SOC name, flash/SRAM sizes, max clock frequency.

Usage
-----
    from pdf_parser import parse_datasheet
    result = parse_datasheet("path/to/MSPM0G3507.pdf")
    result = parse_datasheet("path/to/stm32l476rg.pdf")
    # result is a DatasheetInfo dataclass
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Data model for parsed results
# ─────────────────────────────────────────────────────────────────────

@dataclass
class PinMuxEntry:
    """One alternate-function row from the PINCM table."""
    pin_name: str          # e.g. "PA0"
    pincm: int             # PINCM register index (1-based)
    function_id: int       # function code (0 = analog, 1 = GPIO, 2+ = alt)
    function_name: str     # e.g. "TIMA0_CCP0", "UART0_TX", "GPIO"
    peripheral: str        # e.g. "tima0", "uart0", "gpioa"
    signal: str            # e.g. "ccp0", "tx", "0"
    direction: str = "io"  # "in" / "out" / "io" / "analog"


@dataclass
class PackagePin:
    """One pin in a specific package."""
    number: int            # physical pin number
    name: str              # e.g. "PA0", "VDD", "GND", "NRST"
    port: str = ""         # "A" or "B" (empty for power/special)
    gpio_num: int = -1     # GPIO bit number (-1 for non-GPIO)
    kind: str = "io"       # "io" / "power" / "ground" / "special"


@dataclass
class PackageInfo:
    """Describes one physical package variant."""
    name: str              # e.g. "QFP-48", "LQFP-64"
    pin_count: int
    pins: list[PackagePin] = field(default_factory=list)


@dataclass
class DeviceSummary:
    """Top-level device info extracted from the datasheet."""
    soc: str = ""                  # e.g. "MSPM0G3507", "STM32L476RG"
    vendor: str = ""               # "ti", "st", "nordic", "nxp", …
    flash_size_kb: int = 0
    sram_size_kb: int = 0
    clock_hz: int = 0


@dataclass
class DatasheetInfo:
    """Everything extracted from one datasheet PDF."""
    device: DeviceSummary = field(default_factory=DeviceSummary)
    packages: list[PackageInfo] = field(default_factory=list)
    pin_mux: dict[str, list[PinMuxEntry]] = field(default_factory=dict)
    # key = pin_name (e.g. "PA0"), value = list of alt functions


# ─────────────────────────────────────────────────────────────────────
# Regex patterns for TI MSPM0 datasheets
# ─────────────────────────────────────────────────────────────────────

# Match pin names like PA0, PA31, PB0, PB22
_RE_PIN_NAME = re.compile(r'^P([AB])(\d+)$')

# Match package descriptions like "48-Pin LQFP", "64-Pin QFP", "32-Pin QFN"
_RE_PKG_HEADER = re.compile(
    r'(\d+)[\s-]*[Pp]in\s+([A-Z]{2,6})',
    re.IGNORECASE,
)

# Match PINCM column header patterns
_RE_PINCM_HDR = re.compile(r'PINCM|Pin\s*Name|Function', re.IGNORECASE)

# Match function entries like "TIMA0.CCP0", "UART0.TX", "GPIO"
_RE_FUNC = re.compile(r'([A-Z]+\d*)[._]?([A-Z0-9_]*)', re.IGNORECASE)

# Match typical SOC part numbers: MSPM0G3507, MSPM0L1306, etc.
_RE_SOC = re.compile(r'MSPM0[A-Z]\d{4}', re.IGNORECASE)

# Power / ground / special pin names
_PWR_NAMES = {'VDD', 'AVDD', 'DVDD', 'VCORE'}
_GND_NAMES = {'GND', 'VSS', 'AVSS', 'DVSS'}
_SPEC_NAMES = {'NRST', 'XIN', 'XOUT', 'SWDIO', 'SWCLK', 'SWO',
               'TEST', 'TCK', 'TMS', 'TDI', 'TDO'}


# ─────────────────────────────────────────────────────────────────────
# Regex patterns for STM32 datasheets
# ─────────────────────────────────────────────────────────────────────

# Match STM32 pin names: PA0, PB15, PC13, PD2, PE0, PF1, PG0, PH0, PI0, ...
_RE_STM32_PIN = re.compile(r'^P([A-I])(\d+)$')

# Match STM32 composite pin names like "PC14-OSC32_IN (PC14)" → "PC14"
_RE_STM32_PIN_COMPOSITE = re.compile(
    r'(P[A-I]\d+)\s*[-]?\s*\w*', re.IGNORECASE,
)

# Match STM32 SOC part numbers: STM32L476xx, STM32F407VG, etc.
_RE_STM32_SOC = re.compile(r'STM32[A-Z]\d{3}[A-Z0-9]*', re.IGNORECASE)

# STM32 package keywords
_RE_STM32_PKG = re.compile(
    r'(LQFP|UFBGA|WLCSP|BGA|TFBGA|TSSOP|UFQFPN|QFN|QFP|TQFP|CSP)'
    r'\s*(\d+)',
    re.IGNORECASE,
)

# STM32 power / ground / special
_STM32_PWR_NAMES = {'VDD', 'VDDA', 'VDDIO2', 'VDDUSB', 'VDD12', 'VBAT',
                    'VREF+', 'VREF-', 'VCAP1', 'VCAP2', 'VCORE', 'VLCD',
                    'VDDSMPS', 'VDD_SMPS', 'SMPS'}
_STM32_GND_NAMES = {'VSS', 'VSSA', 'VSSSMPS', 'VSS_SMPS'}
_STM32_SPEC_NAMES = {'NRST', 'BOOT0', 'PDR_ON', 'BYPASS_REG',
                     'SWDIO', 'SWCLK', 'SWO', 'JTMS', 'JTCK', 'JTDI',
                     'JTDO', 'NJTRST', 'TRACECK', 'TRACED0', 'TRACED1',
                     'TRACED2', 'TRACED3'}


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _classify_pin(name: str) -> str:
    """Return pin kind: 'io', 'power', 'ground', or 'special'."""
    upper = name.upper().replace("/", "").strip()
    if upper in _PWR_NAMES or upper in _STM32_PWR_NAMES:
        return "power"
    if upper in _GND_NAMES or upper in _STM32_GND_NAMES:
        return "ground"
    if upper in _SPEC_NAMES or upper in _STM32_SPEC_NAMES:
        return "special"
    if _RE_PIN_NAME.match(upper) or _RE_STM32_PIN.match(upper):
        return "io"
    # Heuristic: if it contains VDD/VCC → power, VSS/GND → ground
    if any(v in upper for v in ("VDD", "VCC", "VCORE", "VREF", "VBAT")):
        return "power"
    if any(v in upper for v in ("VSS", "GND")):
        return "ground"
    return "special"


def _parse_port_gpio(name: str) -> tuple[str, int]:
    """Extract (port_letter, gpio_num) from pin name, e.g. 'PA12' → ('A', 12)."""
    # TI style: PA0, PB22
    m = _RE_PIN_NAME.match(name.upper().strip())
    if m:
        return m.group(1), int(m.group(2))
    # STM32 style: PA0, PB15, PC13, PD2, PE0, PF1, PG0, PH0, PI0
    m = _RE_STM32_PIN.match(name.upper().strip())
    if m:
        return m.group(1), int(m.group(2))
    return "", -1


def _guess_direction(func_name: str, signal: str) -> str:
    """Heuristic for pin direction from function/signal name."""
    fn = func_name.upper()
    sig = signal.upper()
    # Explicit RX / input signals
    if any(k in sig for k in ("RX", "POCI", "CTS", "IDX")):
        return "in"
    if any(k in fn for k in ("_RX", "_POCI", "_CTS", "_IDX")):
        return "in"
    # Explicit TX / output signals
    if any(k in sig for k in ("TX", "PICO", "RTS", "OUT")):
        return "out"
    if any(k in fn for k in ("_TX", "_PICO", "_RTS", "COMP")):
        return "out"
    # CCP (capture/compare) → output (PWM)
    if "CCP" in fn:
        return "out"
    # SCL / SDA → bidirectional
    if any(k in sig for k in ("SCL", "SDA")):
        return "io"
    # ADC / DAC → analog
    if any(k in fn for k in ("ADC", "DAC", "COMP")):
        return "analog"
    return "io"


def _normalise_peripheral(func_name: str) -> tuple[str, str]:
    """
    Derive (peripheral_id, signal) from a function name.

    Examples:
        "TIMA0_CCP0"  → ("tima0", "ccp0")
        "UART0_TX"    → ("uart0", "tx")
        "ADC0_CH3"    → ("adc0", "ch3")
        "GPIO"        → ("gpio", "")
        "I2C1_SCL"    → ("i2c1", "scl")
        "SPI0_CS2"    → ("spi0", "cs2")
        "COMP0_OUT"   → ("comp0", "out")
        "DAC0_OUT"    → ("dac0", "out")
    """
    fn = func_name.strip()
    if not fn:
        return "", ""
    # Split on first underscore after peripheral name
    # Pattern: PERIPH_SIGNAL  or  PERIPH (no signal)
    m = re.match(r'([A-Za-z]+\d*)(?:_(.+))?', fn)
    if not m:
        return fn.lower(), ""
    periph = m.group(1).lower()
    sig = (m.group(2) or "").lower()
    return periph, sig


def _normalise_gpio_peripheral(pin_name: str) -> str:
    """Return GPIO peripheral id, e.g. 'PA12' → 'gpioa'."""
    port, _ = _parse_port_gpio(pin_name)
    if port:
        return f"gpio{port.lower()}"
    return "gpio"


# ─────────────────────────────────────────────────────────────────────
# Table detection and extraction
# ─────────────────────────────────────────────────────────────────────

def _find_pin_mux_tables(pdf: pdfplumber.PDF) -> list[list[list[str]]]:
    """
    Scan all pages for PINCM / pin-mux tables.

    TI datasheets typically have a table titled something like:
      "Table X-Y. Pin Attributes" or "PINCM Pin Functions"
    with columns like: Pin Name | PINCM | Function 0 | Function 1 | …

    Returns a list of tables (each table is a list of rows).
    """
    tables = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        # Check if this page likely contains a PINCM table
        if not re.search(r'PINCM|Pin\s*Attributes|Pin\s*Function|Digital\s*I/O\s*Features',
                         text, re.IGNORECASE):
            continue

        page_tables = page.extract_tables()
        for tbl in page_tables:
            if not tbl or len(tbl) < 2:
                continue
            # Check header row for PINCM-related columns
            header = [str(c).strip() if c else "" for c in tbl[0]]
            header_text = " ".join(header).upper()
            if "PINCM" in header_text or ("PIN" in header_text and "FUNCTION" in header_text):
                tables.append(tbl)
                log.debug("Found pin-mux table on page %d: %d rows",
                          page.page_number, len(tbl))
    return tables


def _find_package_tables(pdf: pdfplumber.PDF) -> dict[str, list[list[str]]]:
    """
    Scan for package pin-out tables.

    TI datasheets have tables like:
      "Table X-Y. Signal Descriptions" with columns per package,
    or separate "48-Pin QFP" / "64-Pin QFP" pinout diagrams with tables.

    Returns {package_name: rows}.
    """
    result: dict[str, list[list[str]]] = {}

    for page in pdf.pages:
        text = page.extract_text() or ""

        # Look for pages that have pin assignment / signal description tables
        if not re.search(
            r'Signal\s*Descriptions?|Pin\s*Diagram|Pin\s*(Out|Assignment)|'
            r'Package\s*Pin|Terminal\s*Functions',
            text, re.IGNORECASE
        ):
            continue

        page_tables = page.extract_tables()
        for tbl in page_tables:
            if not tbl or len(tbl) < 2:
                continue

            header = [str(c).strip() if c else "" for c in tbl[0]]
            header_text = " ".join(header).upper()

            # Look for columns that reference package pin numbers
            # e.g. "48-QFP Pin", "64-LQFP Pin", "Pin Number"
            pkg_cols: dict[str, int] = {}
            name_col: int = -1

            for ci, h in enumerate(header):
                h_up = h.upper().strip()
                # Find columns with package pin numbers
                m = _RE_PKG_HEADER.search(h_up)
                if m:
                    count = int(m.group(1))
                    pkg_type = m.group(2).upper()
                    pkg_name = f"{pkg_type}-{count}"
                    pkg_cols[pkg_name] = ci

                # Find pin name column
                if re.search(r'SIGNAL|PIN\s*NAME|NAME|FUNCTION', h_up):
                    name_col = ci

            if not pkg_cols:
                # Maybe it's a simpler table with just "Pin" and "Name" columns
                for ci, h in enumerate(header):
                    h_up = h.upper().strip()
                    if h_up in ("PIN", "PIN NO", "PIN NO.", "PIN NUMBER", "#"):
                        # Try to detect package from page text
                        pkg_m = _RE_PKG_HEADER.search(text)
                        if pkg_m:
                            count = int(pkg_m.group(1))
                            pkg_type = pkg_m.group(2).upper()
                            pkg_name = f"{pkg_type}-{count}"
                            pkg_cols[pkg_name] = ci

            if pkg_cols and name_col >= 0:
                for pkg_name, pin_col in pkg_cols.items():
                    if pkg_name not in result:
                        result[pkg_name] = []
                    for row in tbl[1:]:
                        if len(row) > max(pin_col, name_col):
                            pin_num_str = str(row[pin_col]).strip() if row[pin_col] else ""
                            pin_name = str(row[name_col]).strip() if row[name_col] else ""
                            if pin_num_str and pin_name:
                                result[pkg_name].append([pin_num_str, pin_name])

                log.debug("Found package table(s) on page %d: %s",
                          page.page_number, list(pkg_cols.keys()))

    return result


def _extract_device_summary(pdf: pdfplumber.PDF) -> DeviceSummary:
    """
    Extract SOC name, flash/SRAM size, and clock from the first few pages.
    """
    summary = DeviceSummary(vendor="ti")

    # Scan first 10 pages for device info
    for page in pdf.pages[:10]:
        text = page.extract_text() or ""

        # SOC name
        if not summary.soc:
            m = _RE_SOC.search(text)
            if m:
                summary.soc = m.group(0).upper()

        # Flash size: "128KB Flash" or "128-KB flash" or "Flash Memory: 128KB"
        if not summary.flash_size_kb:
            m = re.search(r'(\d+)\s*[-]?\s*KB\s+(?:Flash|Program\s*Memory)',
                          text, re.IGNORECASE)
            if not m:
                m = re.search(r'Flash\s*(?:Memory)?[:\s]+(\d+)\s*[-]?\s*KB',
                              text, re.IGNORECASE)
            if m:
                summary.flash_size_kb = int(m.group(1))

        # SRAM size
        if not summary.sram_size_kb:
            m = re.search(r'(\d+)\s*[-]?\s*KB\s+(?:SRAM|RAM|Data\s*Memory)',
                          text, re.IGNORECASE)
            if not m:
                m = re.search(r'(?:SRAM|RAM)[:\s]+(\d+)\s*[-]?\s*KB',
                              text, re.IGNORECASE)
            if m:
                summary.sram_size_kb = int(m.group(1))

        # Clock speed: "80 MHz" or "up to 80MHz"
        if not summary.clock_hz:
            m = re.search(r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*MHz\s+(?:CPU|system|clock|frequency)',
                          text, re.IGNORECASE)
            if not m:
                m = re.search(r'(?:CPU|System|Clock)\s*(?:Frequency|Speed)?[:\s]+(?:up\s+to\s+)?(\d+)\s*MHz',
                              text, re.IGNORECASE)
            if not m:
                # Common TI pattern: "80-MHz"
                m = re.search(r'(\d+)\s*-?\s*MHz', text, re.IGNORECASE)
            if m:
                summary.clock_hz = int(m.group(1)) * 1_000_000

    return summary


# ─────────────────────────────────────────────────────────────────────
# PINCM table parsing
# ─────────────────────────────────────────────────────────────────────

def _parse_pincm_table(tables: list[list[list[str]]]) -> dict[str, list[PinMuxEntry]]:
    """
    Parse extracted PINCM tables into PinMuxEntry records.

    Expected columns (order may vary):
      Pin Name | PINCM | Function 0 (Analog) | Function 1 (GPIO) |
      Function 2 | Function 3 | … | Function N

    Returns dict keyed by pin_name.
    """
    result: dict[str, list[PinMuxEntry]] = {}

    for tbl in tables:
        if len(tbl) < 2:
            continue

        # Parse header to find column indices
        header = [str(c).strip() if c else "" for c in tbl[0]]
        header_upper = [h.upper() for h in header]

        name_col = -1
        pincm_col = -1
        func_cols: list[tuple[int, int]] = []   # (col_index, function_id)

        for ci, h in enumerate(header_upper):
            if re.search(r'PIN\s*NAME|SIGNAL\s*NAME|NAME', h) and name_col < 0:
                name_col = ci
            elif "PINCM" in h:
                pincm_col = ci
            elif re.search(r'FUNCTION\s*(\d+)', h):
                m = re.search(r'FUNCTION\s*(\d+)', h)
                if m:
                    func_cols.append((ci, int(m.group(1))))
            elif re.search(r'^F(\d+)$', h.strip()):
                m = re.search(r'^F(\d+)$', h.strip())
                if m:
                    func_cols.append((ci, int(m.group(1))))

        if name_col < 0 or pincm_col < 0:
            log.warning("PINCM table missing Name or PINCM column: %s", header)
            continue

        if not func_cols:
            # If no explicit function columns, assume columns after PINCM are functions
            start = max(name_col, pincm_col) + 1
            for ci in range(start, len(header)):
                func_cols.append((ci, ci - start))

        # Parse data rows
        for row in tbl[1:]:
            if not row or len(row) <= max(name_col, pincm_col):
                continue

            pin_name = str(row[name_col]).strip() if row[name_col] else ""
            pincm_str = str(row[pincm_col]).strip() if row[pincm_col] else ""

            if not pin_name or not _RE_PIN_NAME.match(pin_name.upper()):
                continue

            pin_name = pin_name.upper()

            # Parse PINCM index
            try:
                pincm = int(re.sub(r'[^\d]', '', pincm_str))
            except (ValueError, TypeError):
                log.debug("Skipping row with non-numeric PINCM: %s", pincm_str)
                continue

            entries: list[PinMuxEntry] = []

            # Always add GPIO as function 1
            port, gpio_num = _parse_port_gpio(pin_name)
            gpio_periph = _normalise_gpio_peripheral(pin_name)

            for col_idx, func_id in func_cols:
                if col_idx >= len(row):
                    continue
                cell = str(row[col_idx]).strip() if row[col_idx] else ""
                if not cell or cell == "—" or cell == "-" or cell == "–":
                    continue

                # A cell might contain multiple functions separated by newlines / commas
                for fn_raw in re.split(r'[,\n/]', cell):
                    fn = fn_raw.strip()
                    if not fn or fn == "—":
                        continue

                    # Handle "GPIO" specifically
                    if fn.upper().startswith("GPIO"):
                        periph = gpio_periph
                        sig = str(gpio_num) if gpio_num >= 0 else ""
                        direction = "io"
                        entries.append(PinMuxEntry(
                            pin_name=pin_name,
                            pincm=pincm,
                            function_id=func_id,
                            function_name=f"GPIO{port}{gpio_num}",
                            peripheral=periph,
                            signal=sig,
                            direction=direction,
                        ))
                    else:
                        periph, sig = _normalise_peripheral(fn)
                        direction = _guess_direction(fn, sig)
                        entries.append(PinMuxEntry(
                            pin_name=pin_name,
                            pincm=pincm,
                            function_id=func_id,
                            function_name=fn.upper().replace(".", "_"),
                            peripheral=periph,
                            signal=sig,
                            direction=direction,
                        ))

            if entries:
                result.setdefault(pin_name, []).extend(entries)

    return result


# ─────────────────────────────────────────────────────────────────────
# Package table parsing
# ─────────────────────────────────────────────────────────────────────

def _parse_package_tables(
    raw: dict[str, list[list[str]]]
) -> list[PackageInfo]:
    """Convert raw package table rows into PackageInfo objects."""
    packages = []

    for pkg_name, rows in raw.items():
        # Parse pin count from package name
        m = re.search(r'(\d+)', pkg_name)
        pin_count = int(m.group(1)) if m else 0

        pins: list[PackagePin] = []
        for row in rows:
            if len(row) < 2:
                continue
            pin_num_str, pin_name = row[0], row[1]

            # Clean up
            pin_name = re.sub(r'\s+', '', pin_name).upper()
            try:
                pin_num = int(re.sub(r'[^\d]', '', pin_num_str))
            except (ValueError, TypeError):
                continue

            kind = _classify_pin(pin_name)
            port, gpio_num = _parse_port_gpio(pin_name)

            pins.append(PackagePin(
                number=pin_num,
                name=pin_name,
                port=port,
                gpio_num=gpio_num,
                kind=kind,
            ))

        # Sort by pin number
        pins.sort(key=lambda p: p.number)

        if not pin_count:
            pin_count = len(pins)

        packages.append(PackageInfo(
            name=pkg_name,
            pin_count=pin_count,
            pins=pins,
        ))

    return packages


# ─────────────────────────────────────────────────────────────────────
# Fallback: text-based extraction for difficult PDFs
# ─────────────────────────────────────────────────────────────────────

def _text_fallback_pin_mux(pdf: pdfplumber.PDF) -> dict[str, list[PinMuxEntry]]:
    """
    If pdfplumber table extraction fails, try a line-by-line regex approach
    on the raw text.  Works for TI datasheets where the PINCM table is
    rendered as plain text columns.
    """
    result: dict[str, list[PinMuxEntry]] = {}

    # Pattern: PA0  1  ANALOG  GPIO  TIMA0_CCP0  TIMG8_CCP0  SPI0_CS2 …
    line_pat = re.compile(
        r'(P[AB]\d+)\s+(\d+)\s+(.*)',
        re.IGNORECASE,
    )

    in_table = False
    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.split('\n'):
            line = line.strip()
            if re.search(r'PINCM|Pin\s*Name.*Function', line, re.IGNORECASE):
                in_table = True
                continue
            if not in_table:
                continue
            # End of table heuristic: empty line or page break
            if not line or re.match(r'^(Table|Note|Copyright|\d+\s+of\s+\d+)', line, re.IGNORECASE):
                if result:
                    in_table = False
                continue

            m = line_pat.match(line)
            if not m:
                continue

            pin_name = m.group(1).upper()
            pincm = int(m.group(2))
            funcs_str = m.group(3)

            port, gpio_num = _parse_port_gpio(pin_name)
            gpio_periph = _normalise_gpio_peripheral(pin_name)

            # Split remaining into function fields (tab or multi-space separated)
            funcs = re.split(r'\s{2,}|\t', funcs_str)

            for fid, fn_raw in enumerate(funcs):
                fn = fn_raw.strip()
                if not fn or fn in ("—", "-", "–", "N/A"):
                    continue

                if fn.upper().startswith("GPIO"):
                    result.setdefault(pin_name, []).append(PinMuxEntry(
                        pin_name=pin_name, pincm=pincm,
                        function_id=fid,
                        function_name=f"GPIO{port}{gpio_num}",
                        peripheral=gpio_periph,
                        signal=str(gpio_num),
                        direction="io",
                    ))
                elif fn.upper() in ("ANALOG", "ANA"):
                    # Skip bare analog placeholder
                    pass
                else:
                    periph, sig = _normalise_peripheral(fn)
                    direction = _guess_direction(fn, sig)
                    result.setdefault(pin_name, []).append(PinMuxEntry(
                        pin_name=pin_name, pincm=pincm,
                        function_id=fid,
                        function_name=fn.upper().replace(".", "_"),
                        peripheral=periph,
                        signal=sig,
                        direction=direction,
                    ))

    return result


# ─────────────────────────────────────────────────────────────────────
# Fallback: text-based package pin extraction
# ─────────────────────────────────────────────────────────────────────

def _text_fallback_packages(pdf: pdfplumber.PDF) -> list[PackageInfo]:
    """
    Scan raw page text for simple 'pin_number  pin_name' patterns near
    known package headings.
    """
    packages: list[PackageInfo] = []
    current_pkg: Optional[str] = None
    current_pins: list[PackagePin] = []
    current_count = 0

    pin_line = re.compile(r'^\s*(\d+)\s+(P[AB]\d+|VDD|GND|AVDD|AVSS|DVDD|DVSS|NRST|XIN|XOUT|VCORE)',
                          re.IGNORECASE)

    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.split('\n'):
            # Check for package heading
            m = _RE_PKG_HEADER.search(line)
            if m:
                # Save previous
                if current_pkg and current_pins:
                    packages.append(PackageInfo(
                        name=current_pkg,
                        pin_count=current_count or len(current_pins),
                        pins=sorted(current_pins, key=lambda p: p.number),
                    ))
                count = int(m.group(1))
                ptype = m.group(2).upper()
                current_pkg = f"{ptype}-{count}"
                current_count = count
                current_pins = []
                continue

            pm = pin_line.match(line)
            if pm and current_pkg:
                num = int(pm.group(1))
                name = pm.group(2).upper()
                kind = _classify_pin(name)
                port, gpio = _parse_port_gpio(name)
                current_pins.append(PackagePin(
                    number=num, name=name, port=port,
                    gpio_num=gpio, kind=kind,
                ))

    # Save last
    if current_pkg and current_pins:
        packages.append(PackageInfo(
            name=current_pkg,
            pin_count=current_count or len(current_pins),
            pins=sorted(current_pins, key=lambda p: p.number),
        ))

    return packages


# ─────────────────────────────────────────────────────────────────────
# Vendor auto-detection
# ─────────────────────────────────────────────────────────────────────

def _detect_vendor(pdf: pdfplumber.PDF) -> str:
    """
    Scan the first few pages of the PDF to determine the MCU vendor.

    Returns one of: 'ti', 'st', 'nordic', 'nxp', 'microchip', 'unknown'.
    """
    sample = ""
    for page in pdf.pages[:5]:
        sample += (page.extract_text() or "") + "\n"
    sample_upper = sample.upper()

    if _RE_SOC.search(sample):
        return "ti"
    if _RE_STM32_SOC.search(sample) or "STMICROELECTRONICS" in sample_upper:
        return "st"
    if re.search(r'NRF\d{4}', sample, re.IGNORECASE) or "NORDIC SEMICONDUCTOR" in sample_upper:
        return "nordic"
    if re.search(r'LPC\d{4}|MIMXRT|MK[A-Z]\d', sample, re.IGNORECASE) or "NXP" in sample_upper:
        return "nxp"
    if re.search(r'PIC\d{2}|SAM[A-Z]\d|ATSAMD|ATSAM', sample, re.IGNORECASE):
        return "microchip"
    return "unknown"


# ─────────────────────────────────────────────────────────────────────
# STM32: Device summary extraction
# ─────────────────────────────────────────────────────────────────────

def _stm32_extract_device_summary(pdf: pdfplumber.PDF) -> DeviceSummary:
    """Extract SOC name, flash/SRAM size, and clock from an STM32 datasheet."""
    summary = DeviceSummary(vendor="st")

    for page in pdf.pages[:15]:
        text = page.extract_text() or ""

        # SOC name – e.g. "STM32L476xx" or "STM32L476RG"
        if not summary.soc:
            m = _RE_STM32_SOC.search(text)
            if m:
                summary.soc = m.group(0).upper()

        # Flash: "up to 1MB flash" or "1 Mbyte of Flash" or "128 KB Flash"
        if not summary.flash_size_kb:
            # "up to 1 MB Flash" or "1-Mbyte Flash"
            m = re.search(
                r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:MB|Mbyte)\s+(?:of\s+)?(?:Flash|program)',
                text, re.IGNORECASE)
            if m:
                summary.flash_size_kb = int(m.group(1)) * 1024
            else:
                m = re.search(
                    r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|Kbyte)\s+(?:of\s+)?(?:Flash|program)',
                    text, re.IGNORECASE)
                if m:
                    summary.flash_size_kb = int(m.group(1))

        # SRAM: "128 KB SRAM" or "320-Kbyte SRAM"
        if not summary.sram_size_kb:
            m = re.search(
                r'(\d+)\s*[-]?\s*(?:KB|Kbyte)\s+(?:of\s+)?(?:SRAM|RAM)',
                text, re.IGNORECASE)
            if m:
                summary.sram_size_kb = int(m.group(1))

        # Clock: "80 MHz" — prefer the one in "up to 80 MHz" or "CPU frequency"
        if not summary.clock_hz:
            m = re.search(
                r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*MHz\s+(?:CPU|system|clock|frequency)',
                text, re.IGNORECASE)
            if not m:
                m = re.search(
                    r'(?:CPU|System|Core)\s*(?:Frequency|Speed|Clock)?[:\s]+(?:up\s+to\s+)?(\d+)\s*MHz',
                    text, re.IGNORECASE)
            if m:
                summary.clock_hz = int(m.group(1)) * 1_000_000

    # STM32 SOC names often end in "xx" in the datasheet, try to get a
    # more specific variant from the title page "Device summary" table.
    if summary.soc.endswith("XX") or summary.soc.endswith("X"):
        # Keep the family name; the actual variant is determined at build time.
        pass

    return summary


# ─────────────────────────────────────────────────────────────────────
# STM32: Alternate-function (AF0–AF15) table parsing
# ─────────────────────────────────────────────────────────────────────

def _stm32_find_af_tables(pdf: pdfplumber.PDF) -> list[list[list[str]]]:
    """
    Find STM32 alternate-function mapping tables.

    These have headers like: Port | <pin> | AF0 | AF1 | … | AF7
    and a second set: Port | <pin> | AF8 | AF9 | … | AF15.

    Returns a list of extracted tables.
    """
    tables = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        # Quick filter: page must mention AF column headers
        if not re.search(r'\bAF\d+\b', text):
            continue

        page_tables = page.extract_tables()
        for tbl in page_tables:
            if not tbl or len(tbl) < 3:
                continue
            header = [str(c).strip() if c else "" for c in tbl[0]]
            header_text = " ".join(header).upper()

            # Must have 'Port' and at least one 'AFn' column
            if "PORT" not in header_text:
                continue
            af_cols = [h for h in header if re.match(r'^AF\d+$', h.strip(), re.IGNORECASE)]
            if len(af_cols) < 2:
                continue

            tables.append(tbl)
            log.debug("Found STM32 AF table on page %d: %d rows, cols=%s",
                      page.page_number, len(tbl),
                      [h[:10] for h in header])

    return tables


def _stm32_parse_af_tables(
    tables: list[list[list[str]]]
) -> dict[str, list[PinMuxEntry]]:
    """
    Parse STM32 AF tables into PinMuxEntry records.

    Each table row: Port (e.g. "Port A") | Pin (e.g. "PA0") | AF0_func | AF1_func | … | AF7_func
    The Port column may be empty for continuation rows (same port).
    Row 1 is a sub-header with peripheral group names — skip it.
    """
    result: dict[str, list[PinMuxEntry]] = {}

    for tbl in tables:
        if len(tbl) < 3:
            continue

        # Determine column layout
        header = [str(c).strip() if c else "" for c in tbl[0]]
        header_upper = [h.upper() for h in header]

        # Find pin-name column (usually index 1)
        pin_col = -1
        for ci, h in enumerate(header_upper):
            if h == "" and ci == 1:
                # STM32 AF tables: col 0 = "Port", col 1 = pin name (no header)
                pin_col = ci
                break

        if pin_col < 0:
            # Fallback: look for a column that has pin-name-like data
            pin_col = 1

        # Find AF columns
        af_map: list[tuple[int, int]] = []   # (col_index, af_number)
        for ci, h in enumerate(header_upper):
            m = re.match(r'^AF(\d+)$', h.strip())
            if m:
                af_map.append((ci, int(m.group(1))))

        if not af_map:
            continue

        # Parse data rows (skip row 0 = header, row 1 = sub-header)
        for row in tbl[2:]:
            if not row or len(row) <= pin_col:
                continue

            raw_pin = str(row[pin_col]).strip() if row[pin_col] else ""
            if not raw_pin:
                continue

            # Normalise pin name: "PA0" or "PB15"
            pin_name = raw_pin.upper().strip()
            if not _RE_STM32_PIN.match(pin_name):
                continue

            port, gpio_num = _parse_port_gpio(pin_name)
            gpio_periph = f"gpio{port.lower()}"

            for col_idx, af_num in af_map:
                if col_idx >= len(row):
                    continue
                cell = str(row[col_idx]).strip() if row[col_idx] else ""
                if not cell or cell in ("—", "-", "–", ""):
                    continue

                # A cell may contain multiple functions separated by /
                for fn_raw in re.split(r'[/\n]', cell):
                    fn = fn_raw.strip()
                    if not fn or fn in ("—", "-", "–"):
                        continue

                    # Extract peripheral and signal
                    periph, sig = _normalise_peripheral(fn)
                    direction = _guess_direction(fn, sig)

                    result.setdefault(pin_name, []).append(PinMuxEntry(
                        pin_name=pin_name,
                        pincm=af_num,            # repurpose pincm as AF number
                        function_id=af_num,
                        function_name=fn.upper().replace(".", "_"),
                        peripheral=periph,
                        signal=sig,
                        direction=direction,
                    ))

            # Also add a GPIO entry (always available)
            result.setdefault(pin_name, []).append(PinMuxEntry(
                pin_name=pin_name,
                pincm=-1,
                function_id=-1,
                function_name=f"GPIO{port}{gpio_num}",
                peripheral=gpio_periph,
                signal=str(gpio_num),
                direction="io",
            ))

    return result


# ─────────────────────────────────────────────────────────────────────
# STM32: Pin definition / package table parsing
# ─────────────────────────────────────────────────────────────────────

def _stm32_find_pin_def_tables(pdf: pdfplumber.PDF) -> list[list[list[str]]]:
    """
    Find STM32 "pin definitions" tables (Table 16 style).

    These have a wide header row with "Pin Number" spanning multiple
    package sub-columns, followed by Pin name, Type, I/O Structure,
    Notes, Alternate functions, Additional functions.
    """
    tables = []
    in_pin_table = False

    for page in pdf.pages:
        text = page.extract_text() or ""

        page_tables = page.extract_tables()
        for tbl in page_tables:
            if not tbl or len(tbl) < 2:
                continue

            header = [str(c).strip() if c else "" for c in tbl[0]]
            header_text = " ".join(header).upper()

            # Detect the pin-definition table header
            if "PIN NUMBER" in header_text and (
                "PIN NAME" in header_text or
                "PIN FUNCTIONS" in header_text or
                any("FUNCTION" in h.upper() for h in header)
            ):
                in_pin_table = True
                tables.append(tbl)
                log.debug("Found STM32 pin-def table on page %d: %d rows",
                          page.page_number, len(tbl))
                continue

            # Continuation pages: same structure (re-check sub-header row)
            if in_pin_table and len(tbl) > 2:
                # Check if row 1 looks like package sub-headers
                # (package names reversed like "46PFQL" or actual pin number)
                row1 = [str(c).strip() if c else "" for c in tbl[1]]
                # Does it have LQFP/UFBGA/WLCSP keywords or look like the
                # same table structure?
                row1_text = " ".join(row1).upper()
                has_pkg = any(k in row1_text for k in
                              ("LQFP", "UFBGA", "WLCSP", "QFP", "BGA",
                               "PFQL", "AGBFU", "PSCLW"))  # reversed too
                has_alt = any("ALTERNATE" in str(c).upper() for c in row1
                              if c)

                if has_pkg or has_alt or "PIN NUMBER" in header_text:
                    tables.append(tbl)
                    log.debug("Found STM32 pin-def continuation on page %d",
                              page.page_number)
                else:
                    in_pin_table = False

    return tables


def _stm32_parse_pin_def_tables(
    tables: list[list[list[str]]]
) -> tuple[list[PackageInfo], dict[str, list[PinMuxEntry]]]:
    """
    Parse STM32 pin-definition tables.

    Returns (packages, extra_pin_mux).

    The table has columns for pin numbers per package variant, the pin
    name, pin type, I/O structure, notes, alternate functions list, and
    additional functions.

    Column layout (typical STM32L476xx):
      0-11: Pin numbers for various packages (LQFP64, WLCSP72, LQFP100, …)
      12: Pin name (with function after reset)
      13: Pin type (I/O, S, etc.)
      14: I/O structure
      15: Notes
      16: Alternate functions (comma-separated list)
      17: Additional functions
    """
    # We need to decode which columns correspond to which packages.
    # Row 1 in each table has the package names (possibly reversed text
    # due to PDF column orientation).

    # Package name mapping: reversed text → real name
    _PKG_DECODE = {
        "LQFP": "LQFP",   "PFQL": "LQFP",
        "UFBGA": "UFBGA",  "AGBFU": "UFBGA",
        "WLCSP": "WLCSP",  "PSCLW": "WLCSP",
        "QFN": "QFN",      "NFQ": "QFN",
        "TSSOP": "TSSOP",  "POSST": "TSSOP",
        "UFQFPN": "UFQFPN", "NPFQFU": "UFQFPN",
    }

    # Collect raw pin data per package
    pkg_pins: dict[str, list[PackagePin]] = {}  # pkg_name → pins
    extra_mux: dict[str, list[PinMuxEntry]] = {}

    for tbl in tables:
        if len(tbl) < 3:
            continue

        # Detect package columns from sub-header row (row 1)
        sub_header = [str(c).strip() if c else "" for c in tbl[1]]

        # Detect the pin-name column and alt-functions column
        header = [str(c).strip() if c else "" for c in tbl[0]]
        header_upper = [h.upper() for h in header]

        name_col = -1
        alt_col = -1
        addl_col = -1

        for ci, h in enumerate(header_upper):
            if "PIN NAME" in h or "PIN FUNCTION" in h.replace("S", ""):
                name_col = ci
            if "FUNCTION AFTER" in h or ("PIN NAME" in h and "FUNCTION" in h):
                name_col = ci

        # In STM32 pin-def tables, the "Pin name" column header may span
        # row 0 as "Pin name\n(function\nafter\nreset)" — typically col 12.
        # The "Alternate functions" and "Additional functions" are in the
        # "Pin functions" merged header, with sub-cols in row 1.
        if name_col < 0:
            for ci, h in enumerate(header):
                if h and re.search(r'Pin\s*name', h, re.IGNORECASE):
                    name_col = ci
                    break

        # Find Alt/Additional in sub-header
        for ci, sh in enumerate(sub_header):
            sh_up = sh.upper() if sh else ""
            if "ALTERNATE" in sh_up:
                alt_col = ci
            elif "ADDITIONAL" in sh_up:
                addl_col = ci

        if name_col < 0:
            # Fallback: assume column 12 is pin name for typical STM32 layout
            if len(header) >= 18:
                name_col = 12
                alt_col = 16
                addl_col = 17
            else:
                continue

        # Identify package columns by matching sub-header text
        pkg_col_map: dict[str, int] = {}  # pkg_name → column index
        for ci, sh in enumerate(sub_header):
            if ci >= name_col:
                break  # package columns are before the name column
            if not sh:
                continue
            sh_up = sh.upper().replace("_", "").replace("-", "").replace(" ", "")
            # Try to match a package type and extract pin count
            for key, real_name in _PKG_DECODE.items():
                if key in sh_up:
                    # Extract pin count from the column name
                    nums = re.findall(r'\d+', sh_up)
                    if nums:
                        count = int(nums[0])
                        # The reversed text may have digits reversed too
                        # e.g. "46PFQL" → LQFP64, "001PFQL" → LQFP100
                        # digits: "46" reversed → "64", "001" → "100"
                        rev_count = int(str(count)[::-1])
                        pkg_label = f"{real_name}{rev_count}"
                    else:
                        pkg_label = real_name
                    if pkg_label not in pkg_col_map:
                        pkg_col_map[pkg_label] = ci
                    break

        log.debug("STM32 pin-def: name_col=%d, alt_col=%d, addl_col=%d, pkgs=%s",
                  name_col, alt_col, addl_col, list(pkg_col_map.keys()))

        # Parse data rows
        for row in tbl[2:]:
            if not row or len(row) <= name_col:
                continue

            raw_name = str(row[name_col]).strip() if row[name_col] else ""
            if not raw_name:
                continue

            # Clean pin name: may be multi-line like "PC14-\nOSC32_\nIN\n(PC14)"
            clean = re.sub(r'\s+', ' ', raw_name).strip()
            # Extract the core pin name: first P[A-I]\d+ match
            m = re.search(r'(P[A-I]\d+)', clean, re.IGNORECASE)
            if m:
                pin_name = m.group(1).upper()
            else:
                # Could be a power/special pin like "VBAT", "NRST"
                pin_name = re.sub(r'\(.*?\)', '', clean).strip().split()[0].upper()
                pin_name = pin_name.rstrip("-")

            kind = _classify_pin(pin_name)
            port, gpio_num = _parse_port_gpio(pin_name)

            # Collect pin numbers per package
            for pkg_name, col_idx in pkg_col_map.items():
                if col_idx >= len(row):
                    continue
                cell = str(row[col_idx]).strip() if row[col_idx] else ""
                if not cell or cell == "-" or cell == "–":
                    continue
                try:
                    pin_num = int(re.sub(r'[^\d]', '', cell))
                except (ValueError, TypeError):
                    # BGA-style: "A1", "B2", etc. — keep as string-based
                    # We store it as a negative hash for now, handle BGA later
                    pin_num = -1
                    # Try BGA coordinate: letter + digit
                    bga_m = re.match(r'^([A-Z])(\d+)$', cell.upper())
                    if bga_m:
                        # Encode: A=1, B=2, ... row * 100 + col
                        pin_num = (ord(bga_m.group(1)) - ord('A') + 1) * 100 + int(bga_m.group(2))

                if pin_num > 0:
                    pkg_pins.setdefault(pkg_name, []).append(PackagePin(
                        number=pin_num,
                        name=pin_name,
                        port=port,
                        gpio_num=gpio_num,
                        kind=kind,
                    ))

            # Parse alternate functions from the "Alternate functions" column
            if alt_col >= 0 and alt_col < len(row):
                alt_text = str(row[alt_col]).strip() if row[alt_col] else ""
                if alt_text and alt_text not in ("-", "–", "—"):
                    for fn_raw in re.split(r'[,\n]', alt_text):
                        fn = fn_raw.strip()
                        if not fn or fn in ("-", "–", "—"):
                            continue
                        # Remove any trailing whitespace artifacts
                        fn = re.sub(r'\s+', '_', fn)
                        periph, sig = _normalise_peripheral(fn)
                        direction = _guess_direction(fn, sig)
                        extra_mux.setdefault(pin_name, []).append(PinMuxEntry(
                            pin_name=pin_name,
                            pincm=-1,
                            function_id=-1,
                            function_name=fn.upper(),
                            peripheral=periph,
                            signal=sig,
                            direction=direction,
                        ))

    # Build PackageInfo list
    packages = []
    for pkg_name, pins in pkg_pins.items():
        # Deduplicate pins by number
        seen = set()
        unique_pins = []
        for p in pins:
            if p.number not in seen:
                seen.add(p.number)
                unique_pins.append(p)
        unique_pins.sort(key=lambda p: p.number)

        # Extract pin count from name
        m = re.search(r'(\d+)', pkg_name)
        count = int(m.group(1)) if m else len(unique_pins)

        packages.append(PackageInfo(
            name=pkg_name,
            pin_count=count,
            pins=unique_pins,
        ))

    packages.sort(key=lambda p: p.pin_count)
    return packages, extra_mux


# ─────────────────────────────────────────────────────────────────────
# STM32: Combined parsing entry point
# ─────────────────────────────────────────────────────────────────────

def _parse_stm32_datasheet(pdf: pdfplumber.PDF) -> DatasheetInfo:
    """Full parse pipeline for an STM32 datasheet."""
    info = DatasheetInfo()

    # 1) Device summary
    info.device = _stm32_extract_device_summary(pdf)
    log.info("STM32 Device: %s  Flash=%dKB  SRAM=%dKB  Clock=%dMHz",
             info.device.soc, info.device.flash_size_kb,
             info.device.sram_size_kb,
             info.device.clock_hz // 1_000_000 if info.device.clock_hz else 0)

    # 2) AF tables (AF0–AF15) — the precise alternate function mapping
    af_tables = _stm32_find_af_tables(pdf)
    if af_tables:
        info.pin_mux = _stm32_parse_af_tables(af_tables)
        log.info("STM32 AF tables: %d pins extracted from %d table(s)",
                 len(info.pin_mux), len(af_tables))
    else:
        log.warning("No STM32 AF tables found")

    # 3) Pin-definition tables — package pin-outs + extra alt-func list
    pin_def_tables = _stm32_find_pin_def_tables(pdf)
    if pin_def_tables:
        packages, extra_mux = _stm32_parse_pin_def_tables(pin_def_tables)
        info.packages = packages
        log.info("STM32 packages: %s",
                 ", ".join(f"{p.name} ({len(p.pins)} pins)"
                           for p in info.packages))

        # Merge extra_mux into pin_mux (pin-def table has a less structured
        # list of alt functions; the AF table is more authoritative, but the
        # pin-def table may have "additional functions" like ADC channels).
        for pin, entries in extra_mux.items():
            existing_funcs = {e.function_name for e in info.pin_mux.get(pin, [])}
            for e in entries:
                if e.function_name not in existing_funcs:
                    info.pin_mux.setdefault(pin, []).append(e)
    else:
        log.warning("No STM32 pin-definition tables found")

    return info


# ─────────────────────────────────────────────────────────────────────
# TI MSPM0: Combined parsing entry point
# ─────────────────────────────────────────────────────────────────────

def _parse_ti_datasheet(pdf: pdfplumber.PDF) -> DatasheetInfo:
    """Full parse pipeline for a TI MSPM0 datasheet."""
    info = DatasheetInfo()

    # 1) Device summary
    info.device = _extract_device_summary(pdf)
    log.info("TI Device: %s  Flash=%dKB  SRAM=%dKB  Clock=%dMHz",
             info.device.soc, info.device.flash_size_kb,
             info.device.sram_size_kb,
             info.device.clock_hz // 1_000_000 if info.device.clock_hz else 0)

    # 2) Pin-mux tables (PINCM)
    pincm_tables = _find_pin_mux_tables(pdf)
    if pincm_tables:
        info.pin_mux = _parse_pincm_table(pincm_tables)
        log.info("Pin-mux: %d pins extracted from %d table(s)",
                 len(info.pin_mux), len(pincm_tables))
    else:
        log.warning("No PINCM tables found via table extraction, "
                    "trying text fallback…")
        info.pin_mux = _text_fallback_pin_mux(pdf)
        log.info("Pin-mux (text fallback): %d pins", len(info.pin_mux))

    # 3) Package pin-out tables
    raw_pkgs = _find_package_tables(pdf)
    if raw_pkgs:
        info.packages = _parse_package_tables(raw_pkgs)
        log.info("Packages: %s",
                 ", ".join(f"{p.name} ({len(p.pins)} pins)"
                           for p in info.packages))
    else:
        log.warning("No package tables found via table extraction, "
                    "trying text fallback…")
        info.packages = _text_fallback_packages(pdf)
        log.info("Packages (text fallback): %s",
                 ", ".join(f"{p.name} ({len(p.pins)} pins)"
                           for p in info.packages) or "none")

    return info


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def parse_datasheet(pdf_path: str, verbose: bool = False) -> DatasheetInfo:
    """
    Parse an MCU datasheet PDF and return structured pin/package data.

    Automatically detects the vendor (TI, ST, Nordic, NXP, …) and uses
    the appropriate parsing strategy.

    Parameters
    ----------
    pdf_path : str
        Path to the manufacturer PDF file.
    verbose : bool
        If True, enable debug logging.

    Returns
    -------
    DatasheetInfo
        Extracted device summary, packages, and pin-mux entries.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    log.info("Parsing datasheet: %s", pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        vendor = _detect_vendor(pdf)
        log.info("Detected vendor: %s", vendor)

        if vendor == "st":
            return _parse_stm32_datasheet(pdf)
        elif vendor == "ti":
            return _parse_ti_datasheet(pdf)
        else:
            # Try STM32 first (wider pin-name alphabet), then TI
            log.info("Unknown vendor, trying STM32 parser first…")
            info = _parse_stm32_datasheet(pdf)
            if info.pin_mux or info.packages:
                return info
            log.info("STM32 parser found nothing, trying TI parser…")
            return _parse_ti_datasheet(pdf)
