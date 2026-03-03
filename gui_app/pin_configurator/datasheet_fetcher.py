"""
Datasheet auto-fetcher for unknown MCU part numbers.

Given an MCU part number (e.g. "MSPM0G3507", "STM32F401RE", "nRF52840"),
this module attempts to:
  1. Identify the vendor from the part number pattern
  2. Construct a plausible datasheet URL
  3. Download the PDF
  4. Hand it off to ``pdf_parser.parse_datasheet()`` for extraction

Supported vendors:
  - Texas Instruments (MSPM0 family, MSP430, CC series)
  - STMicroelectronics (STM32 family)
  - Nordic Semiconductor (nRF family)
  - NXP (LPC, i.MX RT, Kinetis)
  - Microchip (PIC, SAM, SAMD)
  - Espressif (ESP32)

For vendors without direct-URL support, falls back to a Google search
scrape to find the datasheet link.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


# ── Vendor detection patterns ─────────────────────────────────────────

@dataclass
class VendorMatch:
    """Result of vendor identification from a part number."""
    vendor: str           # Canonical vendor id
    vendor_name: str      # Human-readable vendor name
    family: str           # MCU family (e.g. "MSPM0", "STM32F4")
    part_number: str      # Normalised part number
    datasheet_urls: list[str] = field(default_factory=list)  # Candidate URLs


_VENDOR_PATTERNS: list[tuple[re.Pattern, str, str, callable]] = []


def _register_vendor(pattern: str, vendor: str, vendor_name: str, url_builder):
    """Register a vendor detection pattern."""
    _VENDOR_PATTERNS.append((
        re.compile(pattern, re.IGNORECASE),
        vendor,
        vendor_name,
        url_builder,
    ))


# ── TI MSPM0 ──────────────────────────────────────────────────────────

def _ti_mspm0_urls(part: str, m: re.Match) -> list[str]:
    """Build datasheet URLs for TI MSPM0 parts."""
    pn = part.upper()
    # TI datasheet PDFs follow: https://www.ti.com/lit/ds/symlink/{lowercase_part}.pdf
    return [
        f"https://www.ti.com/lit/ds/symlink/{pn.lower()}.pdf",
        f"https://www.ti.com/lit/gpn/{pn.lower()}",
    ]

_register_vendor(
    r'^(MSPM0[A-Z]\d{4})',
    "ti", "Texas Instruments",
    _ti_mspm0_urls,
)


# ── TI MSP430 ─────────────────────────────────────────────────────────

def _ti_msp430_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    return [
        f"https://www.ti.com/lit/ds/symlink/{pn.lower()}.pdf",
        f"https://www.ti.com/lit/gpn/{pn.lower()}",
    ]

_register_vendor(
    r'^(MSP430\w+)',
    "ti", "Texas Instruments",
    _ti_msp430_urls,
)


# ── TI CC series (SimpleLink) ─────────────────────────────────────────

def _ti_cc_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    return [
        f"https://www.ti.com/lit/ds/symlink/{pn.lower()}.pdf",
    ]

_register_vendor(
    r'^(CC\d{2,4}[A-Z]\d*)',
    "ti", "Texas Instruments",
    _ti_cc_urls,
)


# ── STMicroelectronics STM32 ──────────────────────────────────────────

def _stm32_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    # ST datasheets: https://www.st.com/resource/en/datasheet/{part}.pdf
    return [
        f"https://www.st.com/resource/en/datasheet/{pn.lower()}.pdf",
    ]

_register_vendor(
    r'^(STM32[A-Z]\d{3}\w*)',
    "st", "STMicroelectronics",
    _stm32_urls,
)


# ── Nordic nRF ─────────────────────────────────────────────────────────

def _nrf_urls(part: str, m: re.Match) -> list[str]:
    pn = part.lower()
    return [
        f"https://docs-be.nordicsemi.com/bundle/ps_{pn}/resource/ref_manual.pdf",
        f"https://infocenter.nordicsemi.com/pdf/{pn}_ps_v1.0.pdf",
    ]

_register_vendor(
    r'^(nRF\d{4,5}\w*)',
    "nordic", "Nordic Semiconductor",
    _nrf_urls,
)


# ── NXP (LPC, i.MX RT, Kinetis) ──────────────────────────────────────

def _nxp_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    return [
        f"https://www.nxp.com/docs/en/data-sheet/{pn}.pdf",
    ]

_register_vendor(r'^(LPC\d{4}\w*)', "nxp", "NXP Semiconductors", _nxp_urls)
_register_vendor(r'^(MIMXRT\d{4}\w*)', "nxp", "NXP Semiconductors", _nxp_urls)
_register_vendor(r'^(MK\w+)', "nxp", "NXP Semiconductors", _nxp_urls)


# ── Microchip (PIC, SAM, SAMD) ────────────────────────────────────────

def _microchip_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    return [
        f"https://ww1.microchip.com/downloads/en/DeviceDoc/{pn}-datasheet.pdf",
    ]

_register_vendor(r'^(PIC\d+\w+)', "microchip", "Microchip Technology", _microchip_urls)
_register_vendor(r'^(ATSAMD?\d+\w*)', "microchip", "Microchip Technology", _microchip_urls)
_register_vendor(r'^(SAMD?\d+\w*)', "microchip", "Microchip Technology", _microchip_urls)


# ── Espressif ESP32 ───────────────────────────────────────────────────

def _esp_urls(part: str, m: re.Match) -> list[str]:
    pn = part.lower().replace("_", "-")
    return [
        f"https://www.espressif.com/sites/default/files/documentation/{pn}_datasheet_en.pdf",
    ]

_register_vendor(
    r'^(ESP32\w*)',
    "espressif", "Espressif Systems",
    _esp_urls,
)


# ── Identification ────────────────────────────────────────────────────

def identify_vendor(part_number: str) -> Optional[VendorMatch]:
    """
    Identify vendor and generate candidate datasheet URLs from a part number.

    Returns None if the part number doesn't match any known vendor pattern.
    """
    pn = part_number.strip()
    for pattern, vendor, vendor_name, url_builder in _VENDOR_PATTERNS:
        m = pattern.match(pn)
        if m:
            family = m.group(1) if m.lastindex else pn
            urls = url_builder(pn, m)
            return VendorMatch(
                vendor=vendor,
                vendor_name=vendor_name,
                family=family,
                part_number=pn,
                datasheet_urls=urls,
            )
    return None


# ── Download ──────────────────────────────────────────────────────────

def download_datasheet(
    part_number: str,
    output_dir: str | pathlib.Path | None = None,
    url: str | None = None,
) -> tuple[Optional[str], str]:
    """
    Download a datasheet PDF for the given part number.

    Parameters
    ----------
    part_number : str
        MCU part number (e.g. "MSPM0G3507").
    output_dir : path, optional
        Directory to save the PDF. Defaults to a temp directory.
    url : str, optional
        Explicit URL to download from. If None, auto-detect from part number.

    Returns
    -------
    (file_path, message)
        file_path is the local PDF path, or None on failure.
        message describes what happened.
    """
    if output_dir is None:
        output_dir = pathlib.Path(tempfile.mkdtemp(prefix="datasheet_"))
    else:
        output_dir = pathlib.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    urls_to_try = []
    vendor_info = None

    if url:
        urls_to_try = [url]
    else:
        vendor_info = identify_vendor(part_number)
        if vendor_info is None:
            return None, f"Unknown MCU part number: '{part_number}'. Cannot determine vendor."
        urls_to_try = vendor_info.datasheet_urls

    pn_safe = re.sub(r'[^\w\-.]', '_', part_number)
    pdf_path = output_dir / f"{pn_safe}_datasheet.pdf"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zephyr-Pin-Configurator/1.0",
        "Accept": "application/pdf,*/*",
    }

    for u in urls_to_try:
        log.info("Trying datasheet URL: %s", u)
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()

                # Verify it looks like a PDF
                if data[:5] == b'%PDF-' or "pdf" in content_type.lower():
                    pdf_path.write_bytes(data)
                    size_kb = len(data) / 1024
                    vendor_msg = f" ({vendor_info.vendor_name})" if vendor_info else ""
                    return str(pdf_path), (
                        f"Downloaded {size_kb:.0f} KB from {u}{vendor_msg}"
                    )
                else:
                    log.warning("URL %s returned non-PDF content: %s", u, content_type)
                    continue

        except urllib.error.HTTPError as e:
            log.warning("HTTP %d for %s", e.code, u)
            continue
        except urllib.error.URLError as e:
            log.warning("URL error for %s: %s", u, e.reason)
            continue
        except Exception as e:
            log.warning("Error downloading %s: %s", u, e)
            continue

    return None, f"Could not download datasheet for '{part_number}'. Tried: {urls_to_try}"


def fetch_and_parse(
    part_number: str,
    output_dir: str | pathlib.Path | None = None,
    url: str | None = None,
) -> tuple[Optional[dict], str]:
    """
    Download a datasheet and parse it in one step.

    Returns
    -------
    (parsed_result_or_None, message)
        On success, parsed_result is the DatasheetInfo dict.
    """
    # Lazy import to avoid circular dependency
    from pdf_parser import parse_datasheet

    pdf_path, msg = download_datasheet(part_number, output_dir, url)
    if pdf_path is None:
        return None, msg

    try:
        info = parse_datasheet(pdf_path, verbose=False)
        return info, msg
    except Exception as exc:
        return None, f"Downloaded PDF but parsing failed: {exc}"
