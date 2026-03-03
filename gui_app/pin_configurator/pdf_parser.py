"""
MCU Datasheet PDF Parser – extracts pin-mux and package information.

Currently supports Texas Instruments MSPM0 family datasheets.

The parser looks for:
  1. **Package pin-out tables** – mapping physical pin number → pin name
     for each package variant (e.g. 48-QFP, 64-QFP, 32-QFN …).
  2. **PINCM pin-mux table** – lists every I/O pin's multiplexed functions
     (function codes, peripheral, signal names).
  3. **Device summary** – SOC name, flash/SRAM sizes, max clock frequency.

Usage
-----
    from pdf_parser import parse_datasheet
    result = parse_datasheet("path/to/MSPM0G3507.pdf")
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
    soc: str = ""                  # e.g. "MSPM0G3507"
    vendor: str = "ti"
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
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _classify_pin(name: str) -> str:
    """Return pin kind: 'io', 'power', 'ground', or 'special'."""
    upper = name.upper().replace("/", "").strip()
    if upper in _PWR_NAMES:
        return "power"
    if upper in _GND_NAMES:
        return "ground"
    if upper in _SPEC_NAMES:
        return "special"
    if _RE_PIN_NAME.match(upper):
        return "io"
    # Heuristic: if it contains VDD/VCC → power, VSS/GND → ground
    if any(v in upper for v in ("VDD", "VCC", "VCORE")):
        return "power"
    if any(v in upper for v in ("VSS", "GND")):
        return "ground"
    return "special"


def _parse_port_gpio(name: str) -> tuple[str, int]:
    """Extract (port_letter, gpio_num) from pin name, e.g. 'PA12' → ('A', 12)."""
    m = _RE_PIN_NAME.match(name.upper().strip())
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
# Public API
# ─────────────────────────────────────────────────────────────────────

def parse_datasheet(pdf_path: str, verbose: bool = False) -> DatasheetInfo:
    """
    Parse an MCU datasheet PDF and return structured pin/package data.

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

    info = DatasheetInfo()

    with pdfplumber.open(pdf_path) as pdf:
        # 1) Device summary
        info.device = _extract_device_summary(pdf)
        log.info("Device: %s  Flash=%dKB  SRAM=%dKB  Clock=%dMHz",
                 info.device.soc, info.device.flash_size_kb,
                 info.device.sram_size_kb, info.device.clock_hz // 1_000_000
                 if info.device.clock_hz else 0)

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
