"""
MCU Datasheet PDF Parser  –  multi-vendor, speed-optimised.

Extracts **pin-mux / alternate-function tables**, **package pin-outs**,
and a **device summary** (SOC name, flash, SRAM, clock) from the PDF
datasheets of all major MCU manufacturers.

Supported vendor families (auto-detected)
-----------------------------------------
  TI          MSPM0, MSP430, TMS320, CC13xx/CC26xx, AM243x, AM335x
  ST          STM32 (F0/F1/F2/F3/F4/F7/G0/G4/H5/H7/L0/L1/L4/L5/U0/U5/WB/WL/C0)
  NXP         LPC, i.MX RT, Kinetis (MKxx), S32K
  Microchip   PIC16/PIC18/PIC24/dsPIC33, SAM (SAMD/SAML/SAME/SAMV), AVR
  Nordic      nRF52, nRF53, nRF54, nRF91
  Infineon    PSoC4/PSoC6, CY8C, XMC1000/XMC4000, TRAVEO
  Renesas     RA (R7FA), RX, RL78, R5F
  Espressif   ESP32, ESP32-S2/S3/C2/C3/C6/H2
  Silicon Labs EFM32, EFR32, BGM/MGM
  GigaDevice  GD32 (F/E/L/W/C/H/VF series)
  WCH         CH32V, CH32X, CH57x, CH58x
  Nuvoton     M031/M051/M261/M480, NUC series
  Bouffalo Lab BL602, BL616, BL702, BL808
  HPMicro     HPM5300, HPM6200, HPM6700
  Puya        PY32F0, PY32F4
  Artery      AT32F403, AT32F413, AT32F415, AT32F435
  MindMotion  MM32F, MM32L
  Air/Luat    Air001, Air32F103, Air105

Usage
-----
    from pdf_parser import parse_datasheet
    info = parse_datasheet("MSPM0G3507.pdf")
    info = parse_datasheet("stm32l476rg.pdf")
    info = parse_datasheet("nrf52840.pdf")
"""

from __future__ import annotations

import re
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

log = logging.getLogger(__name__)

# ─────────────────────────── data model ──────────────────────────────

@dataclass
class PinMuxEntry:
    """One alternate-function slot for a pin."""
    pin_name: str          # e.g. "PA0"
    pincm: int             # TI PINCM index, or AF number for STM32, or -1
    function_id: int       # function code / AF number
    function_name: str     # e.g. "TIMA0_CCP0", "TIM2_CH1", "GPIO"
    peripheral: str        # e.g. "tima0", "uart0", "gpioa"
    signal: str            # e.g. "ccp0", "tx", "0"
    direction: str = "io"  # "in" / "out" / "io" / "analog"


@dataclass
class PackagePin:
    """One pin in a specific package."""
    number: int            # physical pin number (BGA encoded as row*100+col)
    name: str              # e.g. "PA0", "VDD", "GND", "NRST"
    port: str = ""         # port letter (empty for power/special)
    gpio_num: int = -1     # GPIO bit number (-1 for non-GPIO)
    kind: str = "io"       # "io" / "power" / "ground" / "special"


@dataclass
class PackageInfo:
    """Describes one physical package variant."""
    name: str              # e.g. "QFP-48", "LQFP64"
    pin_count: int
    pins: list[PackagePin] = field(default_factory=list)


@dataclass
class DeviceSummary:
    """Top-level device info extracted from the datasheet."""
    soc: str = ""
    vendor: str = ""
    flash_size_kb: int = 0
    sram_size_kb: int = 0
    clock_hz: int = 0


@dataclass
class DatasheetInfo:
    """Everything extracted from one datasheet PDF."""
    device: DeviceSummary = field(default_factory=DeviceSummary)
    packages: list[PackageInfo] = field(default_factory=list)
    pin_mux: dict[str, list[PinMuxEntry]] = field(default_factory=dict)


# ────────────────────── compiled regex cache ─────────────────────────

_RE_GPIO_PIN = re.compile(r'^P([A-K])(\d{1,2})$')
_RE_TI_PIN   = re.compile(r'^P([AB])(\d+)$')
_RE_STM32_SOC = re.compile(r'STM32[A-Z]\d{3}[A-Z0-9]*', re.I)
_RE_TI_SOC    = re.compile(r'MSPM0[A-Z]\d{4}', re.I)
_RE_PKG_NxPIN = re.compile(r'(\d+)[\s-]*[Pp]in\s+([A-Z]{2,8})', re.I)
_RE_PKG_TYPE  = re.compile(
    r'(LQFP|UFBGA|WLCSP|BGA|TFBGA|TSSOP|UFQFPN|QFN|QFP|TQFP|VFQFPN|HVQFN|'
    r'MAPBGA|EWLCSP|SO|SOIC|SSOP|CSP|MLF|TFLGA|FBGA)\s*[-]?\s*(\d+)', re.I)
_RE_FUNC_SPLIT = re.compile(r'([A-Za-z]+\d*)(?:_(.+))?')
_RE_BGA_COORD  = re.compile(r'^([A-Z])(\d+)$')

# ── broad SOC-detection patterns (most specific first) ──
_VENDOR_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ti",         re.compile(r'MSPM0[A-Z]\d|MSP430|TMS320|CC[12][36]\d{2}|AM[23]\d{2}', re.I)),
    ("st",         re.compile(r'STM32[A-Z]\d{3}|STM8[SLA]', re.I)),
    ("nxp",        re.compile(r'LPC\d{3,4}|MIMXRT\d|MK[LEVW]\d|S32K|MCX[A-Z]\d', re.I)),
    ("microchip",  re.compile(r'PIC\d{2}|dsPIC|SAM[DLEVC]\d|AT(?:mega|tiny|SAM)|AVR\d', re.I)),
    ("nordic",     re.compile(r'nRF\d{4,5}', re.I)),
    ("infineon",   re.compile(r'PSoC\s*[46]|CY8C|XMC[14]\d{3}|TRAVEO', re.I)),
    ("renesas",    re.compile(r'R[57]F\w{5,}|RA\d[A-Z]\d|RX\d{3}|RL78', re.I)),
    ("espressif",  re.compile(r'ESP32[-]?[A-Z0-9]*', re.I)),
    ("silabs",     re.compile(r'EF[MR]32[A-Z]{2}\d|BGM\d|MGM\d', re.I)),
    ("gigadevice", re.compile(r'GD32[A-Z]\d{3}', re.I)),
    ("wch",        re.compile(r'CH32[VX]\d{3}|CH5[78]\d', re.I)),
    ("nuvoton",    re.compile(r'M\d{3}[A-Z]|NUC\d{3}', re.I)),
    ("bouffalo",   re.compile(r'BL[6-8]\d{2}', re.I)),
    ("hpmicro",    re.compile(r'HPM\d{4}', re.I)),
    ("puya",       re.compile(r'PY32[A-Z]\d', re.I)),
    ("artery",     re.compile(r'AT32[A-Z]\d{3}', re.I)),
    ("mindmotion", re.compile(r'MM32[A-Z]', re.I)),
    ("luat",       re.compile(r'Air\d{3}', re.I)),
]

# power / ground / special keywords (union across vendors)
_PWR = frozenset({
    'VDD', 'AVDD', 'DVDD', 'VCORE', 'VDDA', 'VDDIO2', 'VDDIO',
    'VDDUSB', 'VDD12', 'VBAT', 'VREF+', 'VREF-', 'VCAP1', 'VCAP2',
    'VLCD', 'VDDSMPS', 'VDD_SMPS', 'SMPS', 'VBUS', 'VDDQ', 'V33',
    'VCC', 'AVCC', 'VDDANA', 'VDD_IO', 'VDDIOP', 'VDDIOA', 'VDDIOB',
    'DECOUPLE', 'DEC1', 'DEC4', 'DEC6',
})
_GND = frozenset({
    'GND', 'VSS', 'AVSS', 'DVSS', 'VSSA', 'VSSSMPS', 'VSS_SMPS',
    'AGND', 'DGND', 'EPAD', 'EP', 'EXPOSED',
})
_SPEC = frozenset({
    'NRST', 'RESET', 'RSTN', '/RESET', 'XIN', 'XOUT', 'XIN32', 'XOUT32',
    'SWDIO', 'SWCLK', 'SWDCLK', 'SWO', 'JTMS', 'JTCK', 'JTDI', 'JTDO',
    'NJTRST', 'BOOT0', 'PDR_ON', 'BYPASS_REG', 'TEST', 'TCK', 'TMS',
    'TDI', 'TDO', 'OSC_IN', 'OSC_OUT', 'OSC32_IN', 'OSC32_OUT',
    'NC', 'DNC', 'N/C', 'RFU',
})

# STM32-like vendors (GD32, AT32, PY32, MM32 share STM32 table format)
_STM32_LIKE = frozenset({"st", "gigadevice", "artery", "puya", "mindmotion"})

# Package-name decode (handles reversed text from rotated PDF columns)
_PKG_DECODE = {
    "LQFP": "LQFP",    "PFQL": "LQFP",
    "UFBGA": "UFBGA",  "AGBFU": "UFBGA",
    "TFBGA": "TFBGA",  "AGBFT": "TFBGA",
    "WLCSP": "WLCSP",  "PSCLW": "WLCSP",
    "QFN": "QFN",       "NFQ": "QFN",
    "TSSOP": "TSSOP",   "POSST": "TSSOP",
    "UFQFPN": "UFQFPN", "NPFQFU": "UFQFPN",
    "TQFP": "TQFP",     "PFQT": "TQFP",
    "VFQFPN": "VFQFPN", "NPFQFV": "VFQFPN",
    "HVQFN": "HVQFN",   "NFQVH": "HVQFN",
    "BGA": "BGA",        "AGB": "BGA",
}


# ──────────────────────── tiny helpers ───────────────────────────────

def _classify(name: str) -> str:
    u = name.upper().strip().replace("/", "")
    if u in _PWR or any(k in u for k in ("VDD", "VCC", "VREF", "VBAT", "VBUS", "DECOUPLE")):
        return "power"
    if u in _GND or any(k in u for k in ("VSS", "GND", "AGND", "EPAD")):
        return "ground"
    if u in _SPEC:
        return "special"
    if _RE_GPIO_PIN.match(u):
        return "io"
    return "special"


def _port_gpio(name: str) -> tuple[str, int]:
    m = _RE_GPIO_PIN.match(name.upper().strip())
    return (m.group(1), int(m.group(2))) if m else ("", -1)


def _norm_periph(func_name: str) -> tuple[str, str]:
    fn = func_name.strip()
    if not fn:
        return "", ""
    m = _RE_FUNC_SPLIT.match(fn)
    if not m:
        return fn.lower(), ""
    return m.group(1).lower(), (m.group(2) or "").lower()


def _guess_dir(fn: str, sig: str) -> str:
    f, s = fn.upper(), sig.upper()
    if any(k in s for k in ("RX", "POCI", "CTS", "IDX", "MISO")):
        return "in"
    if any(k in f for k in ("_RX", "_POCI", "_CTS", "_IDX", "_MISO")):
        return "in"
    if any(k in s for k in ("TX", "PICO", "RTS", "OUT", "MOSI")):
        return "out"
    if any(k in f for k in ("_TX", "_PICO", "_RTS", "_MOSI", "COMP")):
        return "out"
    if "CCP" in f or "PWM" in f or "OC" in s:
        return "out"
    if any(k in s for k in ("SCL", "SDA", "SCK", "CLK")):
        return "io"
    if any(k in f for k in ("ADC", "DAC", "COMP", "AIN", "AOUT")):
        return "analog"
    return "io"


def _clean_table_rows(tbl: list[list[object]]) -> list[list[str]]:
    rows = [[str(cell).strip() if cell else "" for cell in row] for row in tbl if row]
    while rows and re.search(r'continued', ' '.join(rows[0]), re.I):
        rows.pop(0)
    return rows


def _combine_table_headers(rows: list[list[str]], header_rows: int) -> list[str]:
    width = max((len(row) for row in rows[:header_rows]), default=0)
    headers: list[str] = []
    for ci in range(width):
        parts: list[str] = []
        for row in rows[:header_rows]:
            cell = row[ci].replace("\n", " ").strip() if ci < len(row) else ""
            if cell and cell not in parts:
                parts.append(cell)
        headers.append(" ".join(parts).strip())
    return headers


def _looks_like_pin_name(value: str) -> bool:
    return bool(re.search(r'(P[A-K]\d+|GPIO_?\d+|IO\d+)', value or '', re.I))


def _looks_like_pin_number(value: str) -> bool:
    text = (value or '').strip().upper()
    return bool(_RE_BGA_COORD.match(text) or re.fullmatch(r'[\d\s/,-]+', text))


def _table_data_start(rows: list[list[str]], name_col: int) -> int:
    for idx, row in enumerate(rows):
        if name_col < len(row) and _looks_like_pin_name(row[name_col]):
            return idx
    return len(rows)


def _mux_index_from_header(header: str) -> int:
    am = re.search(r'AF(\d+)|ALT\s*(\d+)', header, re.I)
    if am:
        return int(am.group(1) or am.group(2))
    lm = re.match(r'\s*([A-I])(?:\b|\()', header, re.I)
    if lm:
        return ord(lm.group(1).upper()) - ord('A')
    return -1


def _generic_parse_pinmux_table(tbl: list[list[object]]) -> dict[str, list[PinMuxEntry]]:
    result: dict[str, list[PinMuxEntry]] = {}
    rows = _clean_table_rows(tbl)
    if len(rows) < 2:
        return result

    probe_headers = _combine_table_headers(rows, min(3, len(rows)))
    pin_col = -1
    for ci, header in enumerate(probe_headers):
        if re.search(r'PIN\s*NAME|GPIO|PORT\s*PIN|PAD\s*NAME|BALL\s*NAME|IO\s*NAME|I/O\s*PIN', header, re.I):
            pin_col = ci
            break
    if pin_col < 0:
        return result

    data_start = _table_data_start(rows, pin_col)
    if data_start >= len(rows):
        return result

    headers = _combine_table_headers(rows, data_start)
    func_cols: list[tuple[int, str]] = []
    for ci, header in enumerate(headers):
        if ci == pin_col:
            continue
        hu = header.upper()
        if not hu or re.search(r'SUPPLY|VDD|VSS|POWER|PIN\(|^PIN$', hu):
            continue
        if re.search(r'AF\d+|ALT\s*\d|FUNC|MUX|PERIPH|SIGNAL|ALTERNATE|SERCOM|TC\b|TCC|EIC|ADC|DAC|PTC|COM\b|CCL|GCLK|REF|AC\b', hu) or re.match(r'\s*[A-I](?:\b|\()', hu):
            func_cols.append((ci, hu))

    if not func_cols:
        return result

    for row in rows[data_start:]:
        if not row or len(row) <= pin_col:
            continue
        raw_pin = row[pin_col].strip().upper() if row[pin_col] else ""
        if not _looks_like_pin_name(raw_pin):
            continue
        m2 = re.search(r'(P[A-K]\d+|GPIO_?\d+|IO\d+)', raw_pin, re.I)
        if not m2:
            continue
        pin_name = m2.group(1).upper()

        for ci, cname in func_cols:
            if ci >= len(row):
                continue
            cell = str(row[ci]).strip() if row[ci] else ""
            if not cell or cell in ("—", "-", "–", "Reserved"):
                continue
            af = _mux_index_from_header(cname)

            for fn in re.split(r'[,\n;]', cell):
                fn = fn.strip()
                if not fn or fn in ("—", "-", "–"):
                    continue
                fn_norm = fn.upper().replace('.', '_').replace('/', '_')
                p, s = _norm_periph(fn_norm)
                result.setdefault(pin_name, []).append(PinMuxEntry(
                    pin_name, af, af,
                    fn_norm, p, s,
                    _guess_dir(fn_norm, s)))

    return result


def _split_stm32_af_cell(cell: str) -> list[str]:
    tokens: list[str] = []
    compact_cell = re.sub(r'\s+', '', cell)
    for chunk in re.split(r'[,;]+', compact_cell):
        if not chunk or chunk in ("—", "-", "–"):
            continue
        if "/" not in chunk:
            tokens.append(chunk)
            continue

        parts = [part.strip() for part in chunk.split("/") if part.strip()]
        if not parts:
            continue

        expanded = [parts[0]]
        prefix = parts[0].rsplit("_", 1)[0] if "_" in parts[0] else ""
        for part in parts[1:]:
            if "_" in part or not prefix:
                expanded.append(part)
            else:
                expanded.append(f"{prefix}_{part}")
        tokens.extend(expanded)
    return tokens


def _decode_stm32_package_label(header: str) -> str | None:
    normalized = header.upper().replace("_", "").replace("-", "").replace(" ", "")
    if not normalized or normalized.startswith("SPMS"):
        return None

    for key, real in _PKG_DECODE.items():
        if key not in normalized:
            continue
        nums = re.findall(r'\d+', normalized)
        if nums:
            count = int(max(nums, key=len)[::-1])
            return f"{real}{count}"
        return real
    return None


def _package_name_from_header(header: str, page_text: str, fallback: str) -> str:
    cleaned = re.sub(r'PIN\s*\(?\d*\)?', '', header, flags=re.I)
    cleaned = re.sub(r'[^A-Za-z0-9]+', '', cleaned).upper()
    if cleaned and re.search(r'[A-Z]', cleaned):
        return cleaned
    pm = _RE_PKG_TYPE.search(page_text)
    if pm:
        return f"{pm.group(1).upper()}{pm.group(2)}"
    return fallback


def _package_pin_count(name: str, pins: list[PackagePin]) -> int:
    if _RE_PKG_TYPE.search(name) or _RE_PKG_NxPIN.search(name):
        m = re.search(r'(\d+)', name)
        if m:
            return int(m.group(1))
    return len(pins)


def _is_reasonable_package_pin(name: str) -> bool:
    cleaned = (name or '').strip().upper()
    if not cleaned or ' ' in cleaned:
        return False
    if _looks_like_pin_name(cleaned):
        return True
    return _classify(cleaned) in {"power", "ground", "special"}


def _rename_fallback_packages(packages: list[PackageInfo]) -> list[PackageInfo]:
    counts: dict[int, int] = {}
    renamed: list[PackageInfo] = []
    for pkg in packages:
        if not pkg.name.startswith("PKG_p"):
            renamed.append(pkg)
            continue

        counts[pkg.pin_count] = counts.get(pkg.pin_count, 0) + 1
        suffix = "" if counts[pkg.pin_count] == 1 else f"_{counts[pkg.pin_count]}"
        renamed.append(PackageInfo(f"PACKAGE{pkg.pin_count}{suffix}", pkg.pin_count, pkg.pins))
    return renamed


def _finalize_packages(raw: dict[str, list[PackagePin]]) -> list[PackageInfo]:
    packages: list[PackageInfo] = []
    for name, pins in raw.items():
        seen: set[int] = set()
        uniq: list[PackagePin] = []
        for pin in pins:
            if pin.number not in seen:
                seen.add(pin.number)
                uniq.append(pin)
        uniq.sort(key=lambda pin: pin.number)
        if not uniq:
            continue

        valid_pin_names = sum(1 for pin in uniq if _is_reasonable_package_pin(pin.name))
        if valid_pin_names < max(4, len(uniq) // 2):
            continue

        packages.append(PackageInfo(name, _package_pin_count(name, uniq), uniq))

    named = [pkg for pkg in packages if not pkg.name.startswith("PKG_p")]
    named_sets = [set(pin.name for pin in pkg.pins) for pkg in named]
    filtered: list[PackageInfo] = []
    for pkg in packages:
        if pkg.name.startswith("PKG_p"):
            pkg_set = set(pin.name for pin in pkg.pins)
            for named_pkg, named_set in zip(named, named_sets):
                if not pkg_set or not named_set:
                    continue
                overlap = len(pkg_set & named_set) / min(len(pkg_set), len(named_set))
                if pkg_set.issubset(named_set) or (
                    overlap >= 0.85 and abs(len(pkg_set) - len(named_set)) <= 8
                ):
                    break
            else:
                filtered.append(pkg)
                continue
            continue
        filtered.append(pkg)

    filtered = _rename_fallback_packages(filtered)
    filtered.sort(key=lambda pkg: (pkg.pin_count, pkg.name))
    return filtered


def _generic_parse_package_table(tbl: list[list[object]], page_text: str, fallback: str) -> dict[str, list[PackagePin]]:
    rows = _clean_table_rows(tbl)
    if len(rows) < 2:
        return {}

    probe_headers = _combine_table_headers(rows, min(3, len(rows)))
    name_col = -1
    for ci, header in enumerate(probe_headers):
        if re.search(r'PIN\s*NAME|SIGNAL|NAME|GPIO|PAD|FUNCTION|I/O\s*PIN', header, re.I):
            name_col = ci
            break
    if name_col < 0:
        return {}

    data_start = _table_data_start(rows, name_col)
    if data_start >= len(rows):
        return {}

    headers = _combine_table_headers(rows, data_start)
    pin_cols = [
        ci for ci in range(name_col)
        if any(ci < len(row) and _looks_like_pin_number(row[ci]) for row in rows[data_start:data_start + 8])
    ]
    if not pin_cols:
        return {}

    packages: dict[str, list[PackagePin]] = {}
    for ci in pin_cols:
        header = headers[ci] if ci < len(headers) else ""
        pkg_name = _package_name_from_header(header, page_text, f"{fallback}_{ci}")
        for row in rows[data_start:]:
            if len(row) <= max(ci, name_col):
                continue
            ns = row[ci].strip() if row[ci] else ""
            nm = row[name_col].strip().upper() if row[name_col] else ""
            if not ns or not _looks_like_pin_name(nm):
                continue
            bm = _RE_BGA_COORD.match(ns.upper())
            if bm:
                pnum = (ord(bm.group(1)) - 64) * 100 + int(bm.group(2))
            else:
                digits = re.sub(r'[^\d]', '', ns)
                if not digits:
                    continue
                pnum = int(digits)
            port, gn = _port_gpio(nm)
            packages.setdefault(pkg_name, []).append(
                PackagePin(pnum, nm, port, gn, _classify(nm)))

    return packages


# ──────────────────── speed: batch page text ─────────────────────────

def _extract_all_text(pdf: pdfplumber.PDF, max_workers: int = 1) -> list[str]:
    """Extract text from all pages.
    
    Note: pdfplumber is NOT thread-safe (shared internal state), so we
    default to sequential extraction with per-page error handling.
    """
    n = len(pdf.pages)
    texts: list[str] = [""] * n
    for idx in range(n):
        try:
            texts[idx] = pdf.pages[idx].extract_text() or ""
        except Exception as exc:
            log.warning("Page %d text extraction failed: %s", idx + 1, exc)
            texts[idx] = ""
    return texts


def _pages_matching(texts: list[str], pattern: re.Pattern) -> list[int]:
    """Return 0-based page indices whose text matches *pattern*."""
    return [i for i, t in enumerate(texts) if pattern.search(t)]


# ─────────────────── vendor auto-detection ───────────────────────────

def _detect_vendor(texts: list[str]) -> str:
    sample = "\n".join(texts[:6]).upper()
    for vendor, pat in _VENDOR_PATTERNS:
        if pat.search(sample):
            return vendor
    kw = {
        "st": "STMICROELECTRONICS", "nxp": "NXP SEMICONDUCTORS",
        "nordic": "NORDIC SEMICONDUCTOR", "microchip": "MICROCHIP TECHNOLOGY",
        "infineon": "INFINEON TECHNOLOGIES", "renesas": "RENESAS ELECTRONICS",
        "espressif": "ESPRESSIF SYSTEMS", "silabs": "SILICON LABORATORIES",
        "gigadevice": "GIGADEVICE", "wch": "NANJING QINHENG",
        "nuvoton": "NUVOTON", "bouffalo": "BOUFFALO",
        "hpmicro": "HPMICRO", "puya": "PUYA SEMICONDUCTOR",
        "artery": "ARTERY TECHNOLOGY", "mindmotion": "MINDMOTION",
        "luat": "LUAT",
    }
    for v, kword in kw.items():
        if kword in sample:
            return v
    return "unknown"


# ────────────── generic device-summary extraction ────────────────────

def _extract_summary(texts: list[str], vendor: str) -> DeviceSummary:
    """Generic device-summary extractor — works across many vendors."""
    summary = DeviceSummary(vendor=vendor)
    scan = "\n".join(texts[:12])

    # SOC name
    for _, pat in _VENDOR_PATTERNS:
        m = pat.search(scan)
        if m:
            summary.soc = m.group(0).upper()
            break

    # Flash (KB or MB)
    for pat in [
        r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:MB|Mbyte)\s+(?:of\s+)?(?:Flash|program|code)',
        r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|Kbyte|KiB)\s+(?:of\s+)?(?:Flash|program|code)',
        r'Flash\s*(?:Memory|ROM)?[:\s]+(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|MB)',
        r'(\d+)\s*[-]?\s*(?:KB|Kbyte)\s+Flash',
    ]:
        m = re.search(pat, scan, re.I)
        if m:
            v = int(m.group(1))
            # check if the unit in the matched text is MB
            matched_text = m.group(0).upper()
            if "MB" in matched_text or "MBYTE" in matched_text:
                v *= 1024
            summary.flash_size_kb = v
            break

    # SRAM (KB or MB)
    for pat in [
        r'(\d+)\s*[-]?\s*(?:KB|Kbyte|KiB)\s+(?:of\s+)?(?:SRAM|RAM|data\s+memory)',
        r'(?:SRAM|RAM)[:\s]+(?:up\s+to\s+)?(\d+)\s*[-]?\s*(?:KB|MB)',
        r'(\d+)\s*[-]?\s*(?:MB|Mbyte)\s+(?:of\s+)?(?:SRAM|RAM)',
    ]:
        m = re.search(pat, scan, re.I)
        if m:
            v = int(m.group(1))
            matched_text = m.group(0).upper()
            if ("MB" in matched_text or "MBYTE" in matched_text) and v < 32:
                v *= 1024
            summary.sram_size_kb = v
            break

    # Clock (MHz) — prefer qualified "up to N MHz CPU/system"
    for pat in [
        r'(?:up\s+to\s+)?(\d+)\s*[-]?\s*MHz\s+(?:Arm|CPU|system|core|clock|frequency)',
        r'(?:CPU|System|Core|Arm)\s*(?:Frequency|Speed|Clock)?[:\s]+(?:up\s+to\s+)?(\d+)\s*MHz',
        r'(?:frequency|freq|clock)\s+(?:up\s+to\s+)(\d+)\s*MHz',
    ]:
        m = re.search(pat, scan, re.I)
        if m:
            val = int(m.group(1) if m.group(1) else m.group(2))
            summary.clock_hz = val * 1_000_000
            break
    if not summary.clock_hz:
        for m in re.finditer(r'(\d+)\s*[-]?\s*MHz', scan, re.I):
            v = int(m.group(1))
            if 16 <= v <= 1200:
                summary.clock_hz = v * 1_000_000
                break

    return summary


# ═══════════════════════════════════════════════════════════════════════
#  TI MSPM0 parsing
# ═══════════════════════════════════════════════════════════════════════

def _ti_find_pincm(pdf: pdfplumber.PDF, texts: list[str]) -> list[list[list[str]]]:
    pages = _pages_matching(texts,
        re.compile(r'PINCM|Pin\s*Attributes|Pin\s*Function|Digital\s*I/O\s*Features', re.I))
    tables: list[list[list[str]]] = []
    for idx in pages:
        for tbl in pdf.pages[idx].extract_tables():
            if not tbl or len(tbl) < 2:
                continue
            hdr = " ".join(str(c) for c in tbl[0] if c).upper()
            if "PINCM" in hdr or ("PIN" in hdr and "FUNCTION" in hdr):
                tables.append(tbl)
    return tables


def _ti_parse_pincm(tables: list[list[list[str]]]) -> dict[str, list[PinMuxEntry]]:
    result: dict[str, list[PinMuxEntry]] = {}
    for tbl in tables:
        if len(tbl) < 2:
            continue
        header = [str(c).strip() if c else "" for c in tbl[0]]
        hu = [h.upper() for h in header]
        name_col = pincm_col = -1
        func_cols: list[tuple[int, int]] = []
        for ci, h in enumerate(hu):
            if re.search(r'PIN\s*NAME|SIGNAL\s*NAME|NAME', h) and name_col < 0:
                name_col = ci
            elif "PINCM" in h:
                pincm_col = ci
            else:
                m2 = re.search(r'FUNCTION\s*(\d+)|^F(\d+)$', h.strip())
                if m2:
                    func_cols.append((ci, int(m2.group(1) or m2.group(2))))
        if name_col < 0 or pincm_col < 0:
            continue
        if not func_cols:
            start = max(name_col, pincm_col) + 1
            func_cols = [(ci, ci - start) for ci in range(start, len(header))]

        for row in tbl[1:]:
            if not row or len(row) <= max(name_col, pincm_col):
                continue
            pn = str(row[name_col]).strip().upper() if row[name_col] else ""
            ps = str(row[pincm_col]).strip() if row[pincm_col] else ""
            if not pn or not _RE_TI_PIN.match(pn):
                continue
            try:
                pincm = int(re.sub(r'[^\d]', '', ps))
            except (ValueError, TypeError):
                continue
            port, gnum = _port_gpio(pn)
            gperiph = f"gpio{port.lower()}" if port else "gpio"
            for ci, fid in func_cols:
                if ci >= len(row):
                    continue
                cell = str(row[ci]).strip() if row[ci] else ""
                if not cell or cell in ("—", "-", "–"):
                    continue
                for fn in re.split(r'[,\n/]', cell):
                    fn = fn.strip()
                    if not fn or fn in ("—", "-", "–"):
                        continue
                    if fn.upper().startswith("GPIO"):
                        result.setdefault(pn, []).append(PinMuxEntry(
                            pn, pincm, fid, f"GPIO{port}{gnum}",
                            gperiph, str(gnum), "io"))
                    else:
                        p, s = _norm_periph(fn)
                        result.setdefault(pn, []).append(PinMuxEntry(
                            pn, pincm, fid,
                            fn.upper().replace(".", "_"), p, s,
                            _guess_dir(fn, s)))
    return result


def _ti_find_packages(pdf: pdfplumber.PDF, texts: list[str]) -> dict[str, list[list[str]]]:
    pages = _pages_matching(texts,
        re.compile(r'Signal\s*Descriptions?|Pin\s*Diagram|Pin\s*(Out|Assignment)|'
                   r'Package\s*Pin|Terminal\s*Functions', re.I))
    raw: dict[str, list[list[str]]] = {}
    for idx in pages:
        for tbl in pdf.pages[idx].extract_tables():
            if not tbl or len(tbl) < 2:
                continue
            header = [str(c).strip() if c else "" for c in tbl[0]]
            pkg_cols: dict[str, int] = {}
            name_col = -1
            for ci, h in enumerate(header):
                hup = h.upper().strip()
                m2 = _RE_PKG_NxPIN.search(hup)
                if m2:
                    pkg_cols[f"{m2.group(2).upper()}-{m2.group(1)}"] = ci
                if re.search(r'SIGNAL|PIN\s*NAME|NAME|FUNCTION', hup):
                    name_col = ci
            if not pkg_cols:
                for ci, h in enumerate(header):
                    if h.upper().strip() in ("PIN", "PIN NO", "PIN NO.", "PIN NUMBER", "#"):
                        pm = _RE_PKG_NxPIN.search(texts[idx])
                        if pm:
                            pkg_cols[f"{pm.group(2).upper()}-{pm.group(1)}"] = ci
            if pkg_cols and name_col >= 0:
                for pn, pc in pkg_cols.items():
                    for row in tbl[1:]:
                        if len(row) > max(pc, name_col):
                            ns = str(row[pc]).strip() if row[pc] else ""
                            nm = str(row[name_col]).strip() if row[name_col] else ""
                            if ns and nm:
                                raw.setdefault(pn, []).append([ns, nm])
    return raw


def _ti_build_packages(raw: dict[str, list[list[str]]]) -> list[PackageInfo]:
    pkgs: list[PackageInfo] = []
    for name, rows in raw.items():
        m = re.search(r'(\d+)', name)
        cnt = int(m.group(1)) if m else 0
        pins: list[PackagePin] = []
        for r in rows:
            if len(r) < 2:
                continue
            pname = re.sub(r'\s+', '', r[1]).upper()
            try:
                pnum = int(re.sub(r'[^\d]', '', r[0]))
            except (ValueError, TypeError):
                continue
            port, gn = _port_gpio(pname)
            pins.append(PackagePin(pnum, pname, port, gn, _classify(pname)))
        pins.sort(key=lambda p: p.number)
        pkgs.append(PackageInfo(name, cnt or len(pins), pins))
    return pkgs


def _ti_text_fallback_mux(texts: list[str]) -> dict[str, list[PinMuxEntry]]:
    result: dict[str, list[PinMuxEntry]] = {}
    pat = re.compile(r'(P[AB]\d+)\s+(\d+)\s+(.*)', re.I)
    in_tbl = False
    for txt in texts:
        for line in txt.split('\n'):
            line = line.strip()
            if re.search(r'PINCM|Pin\s*Name.*Function', line, re.I):
                in_tbl = True
                continue
            if not in_tbl:
                continue
            if not line or re.match(r'^(Table|Note|Copyright|\d+\s+of\s+\d+)', line, re.I):
                if result:
                    in_tbl = False
                continue
            m = pat.match(line)
            if not m:
                continue
            pn = m.group(1).upper()
            pincm = int(m.group(2))
            port, gnum = _port_gpio(pn)
            gp = f"gpio{port.lower()}" if port else "gpio"
            for fid, fn in enumerate(re.split(r'\s{2,}|\t', m.group(3))):
                fn = fn.strip()
                if not fn or fn in ("—", "-", "–", "N/A"):
                    continue
                if fn.upper().startswith("GPIO"):
                    result.setdefault(pn, []).append(PinMuxEntry(
                        pn, pincm, fid, f"GPIO{port}{gnum}", gp, str(gnum), "io"))
                elif fn.upper() not in ("ANALOG", "ANA"):
                    p, s = _norm_periph(fn)
                    result.setdefault(pn, []).append(PinMuxEntry(
                        pn, pincm, fid, fn.upper().replace(".", "_"), p, s, _guess_dir(fn, s)))
    return result


# ═══════════════════════════════════════════════════════════════════════
#  STM32 parsing (also works for GD32, AT32, PY32, MM32 clones)
# ═══════════════════════════════════════════════════════════════════════

def _stm32_find_af_tables(pdf: pdfplumber.PDF, texts: list[str]) -> list[list[list[str]]]:
    """Locate AF0-AF15 alternate-function tables (fast pre-filter)."""
    pages = _pages_matching(texts, re.compile(r'\bAF\d+\b'))
    tables: list[list[list[str]]] = []
    for idx in pages:
        for tbl in pdf.pages[idx].extract_tables():
            if not tbl or len(tbl) < 3:
                continue
            hdr = [str(c).strip() if c else "" for c in tbl[0]]
            hdr_up = " ".join(hdr).upper()
            if "PORT" not in hdr_up:
                continue
            af_count = sum(1 for h in hdr if re.match(r'^AF\d+$', h.strip(), re.I))
            if af_count >= 2:
                tables.append(tbl)
    return tables


def _stm32_parse_af(tables: list[list[list[str]]]) -> dict[str, list[PinMuxEntry]]:
    result: dict[str, list[PinMuxEntry]] = {}
    for tbl in tables:
        if len(tbl) < 3:
            continue
        hdr = [str(c).strip() if c else "" for c in tbl[0]]
        af_map: list[tuple[int, int]] = []
        for ci, h in enumerate(hdr):
            m2 = re.match(r'^AF(\d+)$', h.strip(), re.I)
            if m2:
                af_map.append((ci, int(m2.group(1))))
        if not af_map:
            continue
        for row in tbl[2:]:  # skip header + peripheral sub-header
            if not row:
                continue
            raw_pin = str(row[1]).strip().upper() if len(row) > 1 and row[1] else ""
            if not raw_pin or not _RE_GPIO_PIN.match(raw_pin):
                continue
            port, gnum = _port_gpio(raw_pin)
            for ci, af in af_map:
                if ci >= len(row):
                    continue
                cell = str(row[ci]).strip() if row[ci] else ""
                if not cell or cell in ("—", "-", "–"):
                    continue
                for fn in _split_stm32_af_cell(cell):
                    p, s = _norm_periph(fn)
                    result.setdefault(raw_pin, []).append(PinMuxEntry(
                        raw_pin, af, af,
                        fn.upper().replace(".", "_"), p, s, _guess_dir(fn, s)))
            # GPIO always available
            result.setdefault(raw_pin, []).append(PinMuxEntry(
                raw_pin, -1, -1,
                f"GPIO{port}{gnum}",
                f"gpio{port.lower()}", str(gnum), "io"))
    return result


def _stm32_find_pindef(pdf: pdfplumber.PDF, texts: list[str]) -> list[list[list[str]]]:
    """Locate the wide 'pin definitions' table (Table 16 style)."""
    pages = _pages_matching(texts,
        re.compile(r'Pin\s*Number|pin\s+definitions?|Pin\s*name.*function\s*after\s*reset', re.I))
    tables: list[list[list[str]]] = []
    active = False
    for idx in sorted(set(pages)):
        for tbl in pdf.pages[idx].extract_tables():
            if not tbl or len(tbl) < 2:
                continue
            hdr = " ".join(str(c) for c in tbl[0] if c).upper()
            if "PIN NUMBER" in hdr:
                active = True
                tables.append(tbl)
                continue
            if active and len(tbl) > 2:
                sub = " ".join(str(c) for c in tbl[1] if c).upper()
                if any(k in sub for k in ("LQFP", "UFBGA", "WLCSP", "QFP", "BGA",
                                           "PFQL", "AGBFU", "PSCLW", "ALTERNATE")):
                    tables.append(tbl)
                elif "PIN NUMBER" in hdr:
                    tables.append(tbl)
                else:
                    active = False
    return tables


def _stm32_parse_pindef(tables: list[list[list[str]]]) -> tuple[list[PackageInfo], dict[str, list[PinMuxEntry]]]:
    pkg_pins: dict[str, list[PackagePin]] = {}
    extra_mux: dict[str, list[PinMuxEntry]] = {}

    for tbl in tables:
        if len(tbl) < 3:
            continue
        header = [str(c).strip() if c else "" for c in tbl[0]]
        sub = [str(c).strip() if c else "" for c in tbl[1]]

        name_col = alt_col = addl_col = -1
        for ci, h in enumerate(header):
            if h and re.search(r'Pin\s*name', h, re.I):
                name_col = ci
        for ci, s in enumerate(sub):
            su = s.upper() if s else ""
            if "ALTERNATE" in su:
                alt_col = ci
            elif "ADDITIONAL" in su:
                addl_col = ci
        if name_col < 0 and len(header) >= 18:
            name_col, alt_col, addl_col = 12, 16, 17
        if name_col < 0:
            continue

        pkg_col: dict[str, int] = {}
        for ci, s in enumerate(sub):
            if ci >= name_col:
                break
            if not s:
                continue
            label = _decode_stm32_package_label(s)
            if label and label not in pkg_col:
                pkg_col[label] = ci

        for row in tbl[2:]:
            if not row or len(row) <= name_col:
                continue
            raw = str(row[name_col]).strip() if row[name_col] else ""
            if not raw:
                continue
            clean = re.sub(r'\s+', ' ', raw)
            m2 = re.search(r'(P[A-I]\d+)', clean, re.I)
            pin_name = m2.group(1).upper() if m2 else re.sub(r'\(.*?\)', '', clean).split()[0].upper().rstrip("-")
            kind = _classify(pin_name)
            port, gn = _port_gpio(pin_name)

            for pkg, ci in pkg_col.items():
                if ci >= len(row):
                    continue
                cell = str(row[ci]).strip() if row[ci] else ""
                if not cell or cell in ("-", "–"):
                    continue
                bm = _RE_BGA_COORD.match(cell.upper())
                if bm:
                    pnum = (ord(bm.group(1)) - 64) * 100 + int(bm.group(2))
                else:
                    try:
                        pnum = int(re.sub(r'[^\d]', '', cell))
                    except (ValueError, TypeError):
                        continue
                if pnum > 0:
                    pkg_pins.setdefault(pkg, []).append(
                        PackagePin(pnum, pin_name, port, gn, kind))

            if alt_col >= 0 and alt_col < len(row):
                at = str(row[alt_col]).strip() if row[alt_col] else ""
                if at and at not in ("-", "–", "—"):
                    for fn in re.split(r'[,\n]', at):
                        fn = re.sub(r'\s+', '_', fn.strip())
                        if not fn or fn in ("-", "–", "—"):
                            continue
                        p, s = _norm_periph(fn)
                        extra_mux.setdefault(pin_name, []).append(PinMuxEntry(
                            pin_name, -1, -1, fn.upper(), p, s, _guess_dir(fn, s)))

    pkgs: list[PackageInfo] = []
    for name, pins in pkg_pins.items():
        seen: set[int] = set()
        uniq: list[PackagePin] = []
        for p in pins:
            if p.number not in seen:
                seen.add(p.number)
                uniq.append(p)
        uniq.sort(key=lambda p: p.number)
        m2 = re.search(r'(\d+)', name)
        pkgs.append(PackageInfo(name, int(m2.group(1)) if m2 else len(uniq), uniq))
    pkgs.sort(key=lambda p: p.pin_count)
    return pkgs, extra_mux


# ═══════════════════════════════════════════════════════════════════════
#  Generic / NXP / Microchip / Nordic / Renesas / Infineon / Espressif
#  → universal table-scanner heuristic
# ═══════════════════════════════════════════════════════════════════════

def _generic_find_pinmux(pdf: pdfplumber.PDF, texts: list[str]) -> dict[str, list[PinMuxEntry]]:
    """
    Universal heuristic pin-mux extractor.
    Works for NXP (LPC, i.MX RT), Microchip (SAM), Nordic (nRF),
    Infineon, Renesas, Espressif, Silicon Labs, etc.
    """
    result: dict[str, list[PinMuxEntry]] = {}

    pages = _pages_matching(texts, re.compile(
        r'alternate\s+function|pin\s*mux|pin\s*function|signal\s*mux|'
        r'GPIO\s*Mapping|GPIO\s*alternate|'
        r'Pin\s*Name\s.*Function|Port\s*Pin\s*Function|'
        r'IO_MUX|IOMUX|PINMUX|AFR|'
        r'\bAF\d+\b|I/O\s+Multiplex|Pin\s+Multiplexing',
        re.I))

    for idx in pages:
        try:
            page_tables = pdf.pages[idx].extract_tables()
        except Exception:
            continue
        for tbl in page_tables:
            parsed = _generic_parse_pinmux_table(tbl)
            for pin_name, entries in parsed.items():
                result.setdefault(pin_name, []).extend(entries)

    return result


def _generic_find_packages(pdf: pdfplumber.PDF, texts: list[str]) -> list[PackageInfo]:
    """Universal package extractor."""
    pages = _pages_matching(texts, re.compile(
        r'pin\s*(out|diagram|assignment|description|definition)|'
        r'ball\s*map|signal\s*description|package\s*pin|'
        r'terminal\s*function|pin\s*configuration|'
        r'i/o\s+multiplexing|multiplexed\s+signals',
        re.I))

    raw: dict[str, list[PackagePin]] = {}
    for idx in pages:
        text = texts[idx]
        try:
            page_tables = pdf.pages[idx].extract_tables()
        except Exception:
            continue
        for tbl in page_tables:
            parsed = _generic_parse_package_table(tbl, text, f"PKG_p{idx+1}")
            for pkg_name, pins in parsed.items():
                raw.setdefault(pkg_name, []).extend(pins)

    return _finalize_packages(raw)


# ═══════════════════════════════════════════════════════════════════════
#  Vendor-specific parse pipelines
# ═══════════════════════════════════════════════════════════════════════

def _parse_ti(pdf: pdfplumber.PDF, texts: list[str]) -> DatasheetInfo:
    info = DatasheetInfo(device=_extract_summary(texts, "ti"))
    pincm = _ti_find_pincm(pdf, texts)
    info.pin_mux = _ti_parse_pincm(pincm) if pincm else _ti_text_fallback_mux(texts)
    raw = _ti_find_packages(pdf, texts)
    if raw:
        info.packages = _ti_build_packages(raw)
    log.info("TI: %s  flash=%dKB sram=%dKB  pins=%d  pkgs=%d",
             info.device.soc, info.device.flash_size_kb,
             info.device.sram_size_kb, len(info.pin_mux), len(info.packages))
    return info


def _parse_stm32_like(pdf: pdfplumber.PDF, texts: list[str], vendor: str) -> DatasheetInfo:
    info = DatasheetInfo(device=_extract_summary(texts, vendor))
    af = _stm32_find_af_tables(pdf, texts)
    if af:
        info.pin_mux = _stm32_parse_af(af)
    pdt = _stm32_find_pindef(pdf, texts)
    if pdt:
        pkgs, extra = _stm32_parse_pindef(pdt)
        info.packages = pkgs
        for pin, entries in extra.items():
            existing = {e.function_name for e in info.pin_mux.get(pin, [])}
            for e in entries:
                if e.function_name not in existing:
                    info.pin_mux.setdefault(pin, []).append(e)
    if not info.pin_mux:
        info.pin_mux = _generic_find_pinmux(pdf, texts)
    if not info.packages:
        info.packages = _generic_find_packages(pdf, texts)
    log.info("STM32-like(%s): %s  flash=%dKB sram=%dKB  pins=%d  pkgs=%d",
             vendor, info.device.soc, info.device.flash_size_kb,
             info.device.sram_size_kb, len(info.pin_mux), len(info.packages))
    return info


def _parse_generic(pdf: pdfplumber.PDF, texts: list[str], vendor: str) -> DatasheetInfo:
    info = DatasheetInfo(device=_extract_summary(texts, vendor))
    info.pin_mux = _generic_find_pinmux(pdf, texts)
    info.packages = _generic_find_packages(pdf, texts)
    log.info("Generic(%s): %s  flash=%dKB sram=%dKB  pins=%d  pkgs=%d",
             vendor, info.device.soc, info.device.flash_size_kb,
             info.device.sram_size_kb, len(info.pin_mux), len(info.packages))
    return info


# ═══════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════

def parse_datasheet(pdf_path: str, verbose: bool = False) -> DatasheetInfo:
    """
    Parse an MCU datasheet PDF and return structured pin/package data.

    Auto-detects the vendor and dispatches to the best parsing strategy.
    Covers 18+ vendor families with a generic fallback for unknown PDFs.

    Parameters
    ----------
    pdf_path : str
        Path to the manufacturer PDF file.
    verbose : bool
        If True, enable debug logging.

    Returns
    -------
    DatasheetInfo
    """
    # Always suppress pdfminer's extremely verbose per-token debug logging
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    log.info("Parsing datasheet: %s", pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        texts = _extract_all_text(pdf)
        log.info("Extracted text from %d pages", len(texts))

        vendor = _detect_vendor(texts)
        log.info("Detected vendor: %s", vendor)

        if vendor == "ti":
            return _parse_ti(pdf, texts)
        if vendor in _STM32_LIKE:
            return _parse_stm32_like(pdf, texts, vendor)

        # Generic path (Nordic, NXP, Microchip, Infineon, Renesas, …)
        info = _parse_generic(pdf, texts, vendor)
        if not info.pin_mux and not info.packages:
            log.info("Generic found nothing, retrying with STM32-like logic…")
            info2 = _parse_stm32_like(pdf, texts, vendor)
            if info2.pin_mux or info2.packages:
                return info2
        return info
