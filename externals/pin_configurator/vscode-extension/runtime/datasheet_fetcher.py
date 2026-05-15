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
import urllib.parse
import urllib.error
import urllib.request
from html import unescape
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger(__name__)

_SEARCH_RESULT_LIMIT = 8
_SEARCH_QUERY_LIMIT = 6
_SEARCH_CANDIDATE_CACHE: dict[tuple[str, str], list[dict[str, str]]] = {}


# ── Vendor detection patterns ─────────────────────────────────────────

@dataclass
class VendorMatch:
    """Result of vendor identification from a part number."""
    vendor: str           # Canonical vendor id
    vendor_name: str      # Human-readable vendor name
    family: str           # MCU family (e.g. "MSPM0", "STM32F4")
    part_number: str      # Normalised part number
    datasheet_urls: list[str] = field(default_factory=list)  # Candidate URLs


@dataclass
class DatasheetCatalogTerms:
    aliases: list[str] = field(default_factory=list)
    title_tokens: list[str] = field(default_factory=list)
    preferred_queries: list[str] = field(default_factory=list)


@dataclass
class DatasheetCatalogProfile:
    pattern: re.Pattern
    build_terms: Callable[[str, VendorMatch | None, re.Match], DatasheetCatalogTerms]
    vendor: str | None = None


_VENDOR_PATTERNS: list[tuple[re.Pattern, str, str, callable]] = []
_CATALOG_PROFILES: list[DatasheetCatalogProfile] = []


def _register_vendor(pattern: str, vendor: str, vendor_name: str, url_builder):
    """Register a vendor detection pattern."""
    _VENDOR_PATTERNS.append((
        re.compile(pattern, re.IGNORECASE),
        vendor,
        vendor_name,
        url_builder,
    ))


def _register_catalog_profile(
    pattern: str,
    build_terms: Callable[[str, VendorMatch | None, re.Match], DatasheetCatalogTerms],
    vendor: str | None = None,
):
    _CATALOG_PROFILES.append(DatasheetCatalogProfile(
        pattern=re.compile(pattern, re.IGNORECASE),
        build_terms=build_terms,
        vendor=vendor,
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
    pn_low = pn.lower()
    # ST datasheets: try multiple URL patterns
    # Pattern 1: exact part (e.g. stm32l476rg)
    # Pattern 2: base part without package suffix (e.g. stm32l476xx)
    # Pattern 3: just family+density (e.g. stm32l476)
    base = re.match(r'(STM32(?:MP\d{2,3}|[A-Z]\d{3}))', pn, re.IGNORECASE)
    base_pn = base.group(1).lower() if base else pn_low
    urls: list[str] = []
    if pn_low == base_pn and not pn_low.endswith("xx"):
        urls.append(f"https://www.st.com/resource/en/datasheet/{base_pn}xx.pdf")
    urls.append(f"https://www.st.com/resource/en/datasheet/{pn_low}.pdf")
    if len(pn) > len(base_pn):
        # Try with 'xx' suffix (common ST pattern)
        urls.append(f"https://www.st.com/resource/en/datasheet/{base_pn}xx.pdf")
    if pn_low != base_pn:
        urls.append(f"https://www.st.com/resource/en/datasheet/{base_pn}.pdf")
    return list(dict.fromkeys(urls))

_register_vendor(
    r'^(STM32(?:MP\d{2,3}\w*|([A-Z])\d{3}\w*))',
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
_register_vendor(r'^(ATSAMC\d+\w*)', "microchip", "Microchip Technology", _microchip_urls)
_register_vendor(r'^(SAMC\d+\w*)', "microchip", "Microchip Technology", _microchip_urls)


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


# ── Infineon (PSoC, XMC, AIROC) ───────────────────────────────────────

def _infineon_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    return [
        f"https://www.infineon.com/dgdl/{pn}-datasheet.pdf",
    ]

_register_vendor(r'^(CY8C\w+)', "infineon", "Infineon Technologies", _infineon_urls)
_register_vendor(r'^(PSOC\d\w*)', "infineon", "Infineon Technologies", _infineon_urls)
_register_vendor(r'^(XMC\d{4}\w*)', "infineon", "Infineon Technologies", _infineon_urls)


# ── Renesas (RA, RX, RL78) ────────────────────────────────────────────

def _renesas_urls(part: str, m: re.Match) -> list[str]:
    pn = part.upper()
    pn_low = pn.lower()
    return [
        f"https://www.renesas.com/document/dst/{pn_low}-group-datasheet",
    ]

_register_vendor(r'^(R7FA\w+)', "renesas", "Renesas Electronics", _renesas_urls)
_register_vendor(r'^(R5F\w+)', "renesas", "Renesas Electronics", _renesas_urls)
_register_vendor(r'^(RA\d[A-Z]\d\w*)', "renesas", "Renesas Electronics", _renesas_urls)


def _stm32_catalog_terms(compact: str, vendor_info: VendorMatch | None, match: re.Match) -> DatasheetCatalogTerms:
    del vendor_info
    base = match.group(1).upper()
    return DatasheetCatalogTerms(
        aliases=[base, f"{base}XX"],
        title_tokens=[base],
    )


def _microchip_sam_catalog_terms(compact: str, vendor_info: VendorMatch | None, match: re.Match) -> DatasheetCatalogTerms:
    del vendor_info
    family_letter = match.group(1).upper()
    family_num = match.group(2)
    aliases = []
    if compact.startswith("SAM") and not compact.startswith("ATSAM"):
        aliases.append(f"AT{compact}")
    if compact.startswith("ATSAM"):
        aliases.append(compact[2:])
    family_label = f"SAM {family_letter}20/{family_letter}21"
    family_sheet = f"{family_label} Family Data Sheet"
    aliases.extend([
        f"SAM {family_letter}{family_num}",
        family_label,
        family_sheet,
    ])
    return DatasheetCatalogTerms(
        aliases=aliases,
        title_tokens=[family_label, family_sheet],
        preferred_queries=[
            f"{family_sheet} pdf",
            f"{family_sheet} Microchip Technology pdf",
        ],
    )


_register_catalog_profile(r'^(STM32(?:MP\d{2,3}|[A-Z]\d{3}))', _stm32_catalog_terms, vendor="st")
_register_catalog_profile(r'^(?:AT)?SAM([A-Z])(20|21)\w*', _microchip_sam_catalog_terms, vendor="microchip")


# ── Identification ────────────────────────────────────────────────────

def _extract_family(match: str, vendor: str) -> str:
    """Extract a short family name from a matched part number."""
    up = match.upper()
    if vendor == "st":
        # STM32L476RET6 → STM32L4, STM32MP135FXX → STM32MP1
        fm = re.match(r'^(STM32MP\d|STM32[A-Z]\d)', up)
        return fm.group(1) if fm else up
    if vendor == "ti":
        # MSPM0G3507 → MSPM0
        fm = re.match(r'^(MSPM0|MSP430|CC\d{2})', up)
        return fm.group(1) if fm else up
    if vendor == "nordic":
        # nRF52840 → nRF52
        fm = re.match(r'^(NRF\d{2})', up)
        return fm.group(1) if fm else up
    if vendor == "nxp":
        fm = re.match(r'^(LPC\d{2}|MIMXRT\d{3}|MK[A-Z]\d)', up)
        return fm.group(1) if fm else up
    if vendor == "espressif":
        fm = re.match(r'^(ESP32\w?\d?)', up)
        return fm.group(1) if fm else up
    if vendor == "microchip":
        fm = re.match(r'^((?:AT)?SAM[CD]\d{2}|ATSAMD?\d+|SAMD?\d+|PIC\d+)', up)
        return fm.group(1) if fm else up
    if vendor == "infineon":
        fm = re.match(r'^(CY8C\d|PSOC\d|XMC\d{4})', up)
        return fm.group(1) if fm else up
    if vendor == "renesas":
        fm = re.match(r'^(RA\d[A-Z]|R7FA|R5F)', up)
        return fm.group(1) if fm else up
    return up


def identify_vendor(part_number: str) -> Optional[VendorMatch]:
    """
    Identify vendor and generate candidate datasheet URLs from a part number.

    Returns None if the part number doesn't match any known vendor pattern.
    """
    pn = part_number.strip()
    for pattern, vendor, vendor_name, url_builder in _VENDOR_PATTERNS:
        m = pattern.match(pn)
        if m:
            full_match = m.group(1) if m.lastindex else pn
            # Extract a short family name from the match
            family = _extract_family(full_match, vendor)
            urls = url_builder(pn, m)
            return VendorMatch(
                vendor=vendor,
                vendor_name=vendor_name,
                family=family,
                part_number=pn,
                datasheet_urls=urls,
            )
    return None


def _vendor_domains(vendor: str) -> list[str]:
    return {
        "st": ["www.st.com", "st.com"],
        "ti": ["www.ti.com", "ti.com"],
        "nordic": ["www.nordicsemi.com", "docs.nordicsemi.com", "infocenter.nordicsemi.com"],
        "nxp": ["www.nxp.com", "nxp.com"],
        "microchip": ["ww1.microchip.com", "www.microchip.com", "microchip.com"],
        "espressif": ["www.espressif.com", "espressif.com"],
        "infineon": ["www.infineon.com", "infineon.com"],
        "renesas": ["www.renesas.com", "renesas.com"],
    }.get(vendor, [])


def _known_vendor_hosts() -> list[str]:
    hosts = []
    for domains in (
        ["www.st.com", "st.com"],
        ["www.ti.com", "ti.com"],
        ["www.nordicsemi.com", "docs.nordicsemi.com", "infocenter.nordicsemi.com"],
        ["www.nxp.com", "nxp.com"],
        ["ww1.microchip.com", "www.microchip.com", "microchip.com"],
        ["www.espressif.com", "espressif.com"],
        ["www.infineon.com", "infineon.com"],
        ["www.renesas.com", "renesas.com"],
    ):
        hosts.extend(domains)
    return list(dict.fromkeys(hosts))


def _merge_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _catalog_terms(part_number: str, vendor_info: VendorMatch | None) -> DatasheetCatalogTerms:
    compact = re.sub(r'[^A-Z0-9]', '', part_number.strip().upper())
    terms = DatasheetCatalogTerms()

    for profile in _CATALOG_PROFILES:
        if profile.vendor and (vendor_info is None or vendor_info.vendor != profile.vendor):
            continue
        match = profile.pattern.match(compact)
        if not match:
            continue
        resolved = profile.build_terms(compact, vendor_info, match)
        terms.aliases.extend(resolved.aliases)
        terms.title_tokens.extend(resolved.title_tokens)
        terms.preferred_queries.extend(resolved.preferred_queries)

    terms.aliases = _merge_unique(terms.aliases)
    terms.title_tokens = _merge_unique(terms.title_tokens)
    terms.preferred_queries = _merge_unique(terms.preferred_queries)
    return terms


def _part_search_variants(part_number: str, vendor_info: VendorMatch | None) -> list[str]:
    pn = part_number.strip().upper()
    variants = [pn]
    compact = re.sub(r'[^A-Z0-9]', '', pn)
    if compact and compact != pn:
        variants.append(compact)

    trimmed_alpha = re.sub(r'[A-Z]+$', '', compact)
    if trimmed_alpha and trimmed_alpha != compact and len(trimmed_alpha) >= 6:
        variants.append(trimmed_alpha)

    if vendor_info and vendor_info.family:
        variants.append(vendor_info.family.upper())

    variants.extend(_catalog_terms(part_number, vendor_info).aliases)

    return _merge_unique(variants)


def _build_search_queries(part_number: str, vendor_info: VendorMatch | None) -> list[str]:
    variants = _part_search_variants(part_number, vendor_info)
    terms = _catalog_terms(part_number, vendor_info)
    queries = []

    queries.extend(terms.preferred_queries)

    query_variants = _merge_unique(([variants[0]] if variants else []) + terms.aliases + variants[1:])

    for variant in query_variants[:3]:
        queries.append(f'{variant} datasheet pdf')
        if vendor_info:
            queries.append(f'{variant} {vendor_info.vendor_name} datasheet pdf')
            domains = _vendor_domains(vendor_info.vendor)
            if domains:
                queries.append(f'site:{domains[0]} {variant} datasheet pdf')
        else:
            queries.append(f'{variant} mcu datasheet pdf')

    deduped = []
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:_SEARCH_QUERY_LIMIT]


def _extract_search_urls(html: str) -> list[str]:
    urls = []
    patterns = [
        r"uddg=([^&\"'>]+)",
        r"href=[\"'](https?://[^\"']+)[\"']",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            candidate = urllib.parse.unquote(match)
            if candidate.startswith("http://") or candidate.startswith("https://"):
                urls.append(candidate)
    # Preserve order while deduplicating.
    return list(dict.fromkeys(urls))


def _extract_search_candidates(html: str) -> list[dict[str, str]]:
    candidates = []
    seen = set()
    for href, title_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL):
        candidate_url = urllib.parse.unquote(href)
        uddg_match = re.search(r'uddg=([^&"\']+)', href, flags=re.IGNORECASE)
        if uddg_match:
            candidate_url = urllib.parse.unquote(uddg_match.group(1))
        if not (candidate_url.startswith("http://") or candidate_url.startswith("https://")):
            continue
        if candidate_url in seen:
            continue
        title = unescape(re.sub(r'<[^>]+>', ' ', title_html))
        title = " ".join(title.split())
        candidates.append({"url": candidate_url, "title": title})
        seen.add(candidate_url)
    return candidates


def _classify_search_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    full = urllib.parse.unquote(url).lower()
    if "/datasheet/" in path or "datasheet" in full or "data-sheet" in full or "data_sheet" in full:
        return "datasheet"
    if "reference_manual" in path or "reference-manual" in full:
        return "reference-manual"
    if path.endswith(".pdf"):
        return "pdf"
    if "documentation" in full or "/document/" in path:
        return "documentation"
    return "other"


def _host_matches_domain(host: str, domain: str) -> bool:
    normalized_host = host.lower().strip('.')
    normalized_domain = domain.lower().strip('.')
    return normalized_host == normalized_domain or normalized_host.endswith(f".{normalized_domain}")


def _candidate_matches_part(url: str, title: str, part_number: str, vendor_info: VendorMatch | None) -> bool:
    haystack = f"{urllib.parse.unquote(url)} {title}".lower()
    for variant in _part_search_variants(part_number, vendor_info):
        normalized = variant.lower()
        compact = normalized.replace("xx", "")
        if normalized and normalized in haystack:
            return True
        if compact and len(compact) >= 6 and compact in haystack:
            return True
    for token in _catalog_terms(part_number, vendor_info).title_tokens:
        if token.lower() in haystack:
            return True
    return False


def _score_search_url(url: str, vendor: str, part_number: str) -> tuple[int, int, int, str]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    pn = part_number.lower()
    vendor_domains = _vendor_domains(vendor)
    if vendor_domains:
        vendor_bonus = 0 if any(_host_matches_domain(host, domain) for domain in vendor_domains) else 1
    else:
        vendor_bonus = 0 if any(_host_matches_domain(host, domain) for domain in _known_vendor_hosts()) else 1

    locale_bonus = 0
    if vendor == "st":
        locale_bonus = 0 if "/resource/en/" in path else 1 if re.search(r'/resource/[a-z]{2}/', path) else 0

    kind = _classify_search_url(url)
    if kind == "datasheet":
        kind_bonus = 0
    elif kind == "pdf":
        kind_bonus = 1
    elif kind == "documentation":
        kind_bonus = 2
    elif kind == "reference-manual":
        kind_bonus = 3
    else:
        kind_bonus = 4
    part_bonus = 0 if pn in path or pn in urllib.parse.unquote(url).lower() else 1
    return (vendor_bonus, locale_bonus, kind_bonus, part_bonus, url)


def search_datasheet_candidates(
    part_number: str,
    vendor_info: VendorMatch | None = None,
    max_results: int = _SEARCH_RESULT_LIMIT,
) -> list[dict[str, str]]:
    cache_key = (part_number.strip().lower(), vendor_info.vendor if vendor_info else "")
    cached = _SEARCH_CANDIDATE_CACHE.get(cache_key)
    if cached:
        return cached[:max_results]

    candidates: dict[str, dict[str, object]] = {}

    for query_index, query in enumerate(_build_search_queries(part_number, vendor_info), start=1):
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", "ignore")

        for rank, candidate in enumerate(_extract_search_candidates(html), start=1):
            url = candidate["url"]
            title = candidate["title"]
            kind = _classify_search_url(url)
            if kind == "other":
                continue
            if not _candidate_matches_part(url, title, part_number, vendor_info):
                continue
            score = _score_search_url(url, vendor_info.vendor if vendor_info else "", part_number)
            score = score + (query_index, rank)
            existing = candidates.get(url)
            if existing is None or score < existing["score"]:
                candidates[url] = {
                    "url": url,
                    "title": title,
                    "kind": kind,
                    "query": query,
                    "score": score,
                }

    ordered = sorted(candidates.values(), key=lambda item: item["score"])
    results = [
        {
            "url": str(item["url"]),
            "kind": str(item["kind"]),
            "query": str(item["query"]),
        }
        for item in ordered[:max_results]
    ]
    if results:
        _SEARCH_CANDIDATE_CACHE[cache_key] = results
    return results


def _search_fallback_urls(part_number: str, vendor_info: VendorMatch | None) -> list[str]:
    return [
        candidate["url"]
        for candidate in search_datasheet_candidates(part_number, vendor_info, max_results=_SEARCH_RESULT_LIMIT)
    ]


def _prefer_search_before_direct(part_number: str, vendor_info: VendorMatch | None) -> bool:
    if not vendor_info or vendor_info.vendor != "st":
        return False
    compact = re.sub(r'[^A-Z0-9]', '', part_number.strip().upper())
    return bool(re.fullmatch(r'STM32(?:MP\d{2,3}|[A-Z]\d{3})', compact))


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
        urls_to_try = vendor_info.datasheet_urls if vendor_info else []
        if _prefer_search_before_direct(part_number, vendor_info):
            try:
                search_first = _search_fallback_urls(part_number, vendor_info)
            except Exception as exc:
                log.warning("Search-first fallback failed for %s: %s", part_number, exc)
                search_first = []
            urls_to_try = list(dict.fromkeys(search_first + urls_to_try))

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

    if not url:
        try:
            fallback_urls = _search_fallback_urls(part_number, vendor_info)
        except Exception as exc:
            log.warning("Fallback search failed for %s: %s", part_number, exc)
            fallback_urls = []

        for u in fallback_urls:
            if u in urls_to_try:
                continue
            log.info("Trying fallback datasheet URL: %s", u)
            try:
                req = urllib.request.Request(u, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    data = resp.read()
                    if data[:5] == b'%PDF-' or "pdf" in content_type.lower():
                        pdf_path.write_bytes(data)
                        size_kb = len(data) / 1024
                        vendor_msg = f" ({vendor_info.vendor_name})" if vendor_info else ""
                        return str(pdf_path), (
                            f"Downloaded {size_kb:.0f} KB from {u}{vendor_msg}"
                        )
            except Exception as exc:
                log.warning("Fallback URL failed for %s: %s", u, exc)
                continue

    attempted = urls_to_try + fallback_urls if not url else urls_to_try
    return None, f"Could not download datasheet for '{part_number}'. Tried: {attempted}"


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
