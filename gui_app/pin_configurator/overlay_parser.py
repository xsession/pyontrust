"""
DTS overlay & prj.conf reverse-parser for the Zephyr Pin Configurator.

Parses existing ``.overlay`` and ``prj.conf`` files back into the
pin-assignment / peripheral-enable structures used by the web UI,
allowing users to import previous configurations for editing.

Supports:
  - ``&pinctrl { ... }`` blocks with ``pinmux = <MSP_PINMUX(...)>;``
  - Per-pin properties: ``input-enable``, ``bias-pull-up``, ``bias-pull-down``,
    ``drive-open-drain``
  - Peripheral enable blocks: ``&uart0 { status = "okay"; ... }``
  - ``pinctrl-0 = <&label1 &label2 ...>;``
  - ``current-speed``, ``clock-frequency`` peripheral properties
  - ``CONFIG_*=y`` / ``CONFIG_*=n`` lines from ``prj.conf``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Result data classes ───────────────────────────────────────────────

@dataclass
class ParsedPinAssignment:
    """One pin assignment extracted from an overlay."""
    node_label: str        # e.g. "uart0_tx_pa10"
    pincm: int             # PINCM register index from MSP_PINMUX(pincm, func)
    function_id: int       # MSPM0_PIN_FUNCTION_x (numeric part)
    function_macro: str    # Full macro text e.g. "MSPM0_PIN_FUNCTION_2"
    # Derived from label:
    peripheral: str = ""   # e.g. "uart0"
    signal: str = ""       # e.g. "tx"
    pin_name: str = ""     # e.g. "PA10"
    # Pin properties:
    input_enable: bool = False
    bias_pull_up: bool = False
    bias_pull_down: bool = False
    drive_open_drain: bool = False


@dataclass
class ParsedPeripheral:
    """One peripheral block extracted from an overlay."""
    dts_node: str           # e.g. "&uart0"
    name: str               # e.g. "uart0"
    enabled: bool = True    # status = "okay"
    pinctrl_refs: list[str] = field(default_factory=list)  # ["uart0_tx_pa10", ...]
    properties: dict = field(default_factory=dict)  # e.g. {"current-speed": "115200"}


@dataclass
class ParsedKconfig:
    """One CONFIG_ line from a prj.conf."""
    key: str                # e.g. "CONFIG_SERIAL"
    value: str              # e.g. "y", "n", "115200"


@dataclass
class ImportResult:
    """Full result of parsing overlay + prj.conf."""
    pins: list[ParsedPinAssignment] = field(default_factory=list)
    peripherals: list[ParsedPeripheral] = field(default_factory=list)
    kconfig: list[ParsedKconfig] = field(default_factory=list)
    board_name: str = ""    # Inferred from filename (e.g. "lp_mspm0g3507")
    warnings: list[str] = field(default_factory=list)


# ── Regex patterns ────────────────────────────────────────────────────

# Match MSP_PINMUX(pincm, MSPM0_PIN_FUNCTION_x) -- handles both named and numeric
_RE_PINMUX = re.compile(
    r'MSP_PINMUX\s*\(\s*(\d+)\s*,\s*(MSPM0_PIN_FUNCTION_(\d+)|\d+)\s*\)',
    re.IGNORECASE
)

# Alternate pinmux macro: PINCM<n>_PF_<PERIPH>_<SIGNAL>
# e.g. <PINCM1_PF_UART0_TX> or <PINCM22_PF_GPIOB_DIO22>
_RE_PINCM_PF = re.compile(
    r'<\s*PINCM(\d+)_PF_(\w+)\s*>',
    re.IGNORECASE
)

# Match node label  e.g.  "uart0_tx_pa10: uart0_tx_pa10 {"
# or                      "uart0_tx_pa10 {"
_RE_NODE_LABEL = re.compile(
    r'^\s*(\w+)\s*:\s*(\w+)\s*\{', re.MULTILINE
)

# Match &node { ... } blocks
_RE_REF_BLOCK = re.compile(
    r'&(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
    re.DOTALL
)

# Match pinctrl-0 references like <&uart0_tx_pa10 &uart0_rx_pa11>
_RE_PINCTRL_REFS = re.compile(
    r'pinctrl-0\s*=\s*<([^>]+)>'
)

# Match status property
_RE_STATUS = re.compile(r'status\s*=\s*"(\w+)"')

# Match current-speed, clock-frequency, etc.
_RE_PROP_INT = re.compile(r'(\w[\w-]*)\s*=\s*<(\d+)>')
_RE_PROP_STR = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')

# Match CONFIG_XXX=value lines in prj.conf
_RE_KCONFIG = re.compile(r'^(CONFIG_\w+)\s*=\s*(.+?)\s*$', re.MULTILINE)

# Match DTS boolean properties (no value, just the property name)
_RE_BOOL_PROP = re.compile(r'^\s*(input-enable|bias-pull-up|bias-pull-down|drive-open-drain)\s*;', re.MULTILINE)

# Derive peripheral/signal/pin from a pinctrl node label
# e.g. "uart0_tx_pa10" -> ("uart0", "tx", "PA10")
# e.g. "spi0_pico_pb5"  -> ("spi0", "pico", "PB5")
# e.g. "tima0_ccp0_pa0" -> ("tima0", "ccp0", "PA0")
_RE_LABEL_PARTS = re.compile(
    r'^([a-z]+\d*)_([a-z0-9_]+?)_(p[ab]\d+)$',
    re.IGNORECASE
)

# Alternate: label may be just peripheral_pin (no signal)
_RE_LABEL_PARTS2 = re.compile(
    r'^([a-z]+\d*)_(p[ab]\d+)$',
    re.IGNORECASE
)


# ── Parser functions ──────────────────────────────────────────────────

def _parse_label(label: str) -> tuple[str, str, str]:
    """
    Derive (peripheral, signal, pin_name) from a pinctrl node label.

    Returns ("", "", "") if the label doesn't match expected patterns.
    """
    m = _RE_LABEL_PARTS.match(label)
    if m:
        return m.group(1).lower(), m.group(2).lower(), m.group(3).upper()

    m2 = _RE_LABEL_PARTS2.match(label)
    if m2:
        return m2.group(1).lower(), "", m2.group(2).upper()

    return "", "", ""


def parse_overlay(text: str) -> tuple[list[ParsedPinAssignment], list[ParsedPeripheral], list[str]]:
    """
    Parse a DTS overlay string into pin assignments and peripheral enables.

    Returns (pins, peripherals, warnings).
    """
    pins: list[ParsedPinAssignment] = []
    peripherals: list[ParsedPeripheral] = []
    warnings: list[str] = []

    # Strip C-style comments
    clean = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    clean = re.sub(r'//[^\n]*', '', clean)

    # Find all &ref { ... } blocks
    for m in _RE_REF_BLOCK.finditer(clean):
        ref_name = m.group(1)   # e.g. "pinctrl", "uart0", "gpioa"
        body = m.group(2)

        if ref_name == "pinctrl":
            # Parse nested pin nodes inside &pinctrl { ... }
            _parse_pinctrl_block(body, pins, warnings)
        else:
            # Parse peripheral enable block
            _parse_peripheral_block(ref_name, body, peripherals, warnings)

    return pins, peripherals, warnings


def _parse_pinctrl_block(
    body: str,
    pins: list[ParsedPinAssignment],
    warnings: list[str],
) -> None:
    """Parse the contents of a &pinctrl { ... } block."""
    # Find sub-nodes:  label: label { ... }  or  label { ... }
    # Use a simple brace-matching approach
    node_re = re.compile(
        r'(\w+)\s*(?::\s*\w+\s*)?\{([^{}]*)\}',
        re.DOTALL
    )

    for nm in node_re.finditer(body):
        label = nm.group(1)
        node_body = nm.group(2)

        # Extract MSP_PINMUX(pincm, func) or PINCM<n>_PF_<PERIPH>_<SIGNAL>
        pm = _RE_PINMUX.search(node_body)
        alt_pm = _RE_PINCM_PF.search(node_body) if not pm else None

        if pm:
            pincm = int(pm.group(1))
            func_macro = pm.group(2)
            if pm.group(3) is not None:
                func_id = int(pm.group(3))
            else:
                try:
                    func_id = int(func_macro)
                    func_macro = f"MSPM0_PIN_FUNCTION_{func_id}"
                except ValueError:
                    func_id = 0
                    warnings.append(f"Could not parse function in '{label}': {func_macro}")
        elif alt_pm:
            # PINCM<n>_PF_<PERIPH>_<SIGNAL> format
            pincm = int(alt_pm.group(1))
            pf_name = alt_pm.group(2)  # e.g. "UART0_TX"
            func_id = -1  # Unknown from this format
            func_macro = f"PINCM{pincm}_PF_{pf_name}"
            # Override peripheral/signal from macro name
            parts = pf_name.split("_", 1)
            if len(parts) == 2:
                periph_override = parts[0].lower()
                signal_override = parts[1].lower()
            else:
                periph_override = pf_name.lower()
                signal_override = ""
        else:
            warnings.append(f"pinctrl node '{label}' has no pinmux macro -- skipped")
            continue

        # Derive peripheral/signal/pin from label
        periph, signal, pin_name = _parse_label(label)

        # If we used the PINCM_PF format, override peripheral/signal from macro
        if alt_pm and not pm:
            if periph_override:
                periph = periph_override
            if signal_override:
                signal = signal_override

        # Boolean pin properties
        input_en = bool(re.search(r'\binput-enable\b', node_body))
        pull_up = bool(re.search(r'\bbias-pull-up\b', node_body))
        pull_down = bool(re.search(r'\bbias-pull-down\b', node_body))
        open_drain = bool(re.search(r'\bdrive-open-drain\b', node_body))

        pins.append(ParsedPinAssignment(
            node_label=label,
            pincm=pincm,
            function_id=func_id,
            function_macro=func_macro,
            peripheral=periph,
            signal=signal,
            pin_name=pin_name,
            input_enable=input_en,
            bias_pull_up=pull_up,
            bias_pull_down=pull_down,
            drive_open_drain=open_drain,
        ))


def _parse_peripheral_block(
    ref_name: str,
    body: str,
    peripherals: list[ParsedPeripheral],
    warnings: list[str],
) -> None:
    """Parse a peripheral block like &uart0 { ... }."""
    # Status
    sm = _RE_STATUS.search(body)
    enabled = True
    if sm:
        enabled = sm.group(1).lower() == "okay"

    # Pinctrl references
    pinctrl_refs = []
    pm = _RE_PINCTRL_REFS.search(body)
    if pm:
        refs_text = pm.group(1)
        pinctrl_refs = [r.strip().lstrip('&') for r in refs_text.split() if r.strip()]

    # Collect other properties
    props = {}
    for pm2 in _RE_PROP_INT.finditer(body):
        key = pm2.group(1)
        if key not in ('status', 'pinctrl-0', 'pinctrl-names'):
            props[key] = pm2.group(2)
    for pm3 in _RE_PROP_STR.finditer(body):
        key = pm3.group(1)
        if key not in ('status', 'pinctrl-names'):
            props[key] = pm3.group(2)

    peripherals.append(ParsedPeripheral(
        dts_node=f"&{ref_name}",
        name=ref_name,
        enabled=enabled,
        pinctrl_refs=pinctrl_refs,
        properties=props,
    ))


def parse_kconfig(text: str) -> list[ParsedKconfig]:
    """Parse a prj.conf / board.conf string into CONFIG entries."""
    results = []
    for m in _RE_KCONFIG.finditer(text):
        results.append(ParsedKconfig(key=m.group(1), value=m.group(2).strip()))
    return results


def parse_import(
    overlay_text: str = "",
    conf_text: str = "",
    board_name: str = "",
) -> ImportResult:
    """
    Parse overlay + prj.conf text and return a unified ImportResult.

    Parameters
    ----------
    overlay_text : str
        Content of a ``.overlay`` file.
    conf_text : str
        Content of a ``prj.conf`` or board ``.conf`` file.
    board_name : str
        Board name (can be auto-detected from filename).

    Returns
    -------
    ImportResult
    """
    warnings: list[str] = []

    pins = []
    peripherals = []
    if overlay_text.strip():
        pins, peripherals, ow = parse_overlay(overlay_text)
        warnings.extend(ow)

    kconfig = []
    if conf_text.strip():
        kconfig = parse_kconfig(conf_text)

    return ImportResult(
        pins=pins,
        peripherals=peripherals,
        kconfig=kconfig,
        board_name=board_name,
        warnings=warnings,
    )


def _dedup_kconfig(kconfig: list[ParsedKconfig]) -> list[dict]:
    """Deduplicate Kconfig entries, keeping the last value for each key."""
    seen: dict[str, str] = {}
    order: list[str] = []
    for kc in kconfig:
        if kc.key not in seen:
            order.append(kc.key)
        seen[kc.key] = kc.value
    return [{"key": k, "value": seen[k]} for k in order]


def import_result_to_json(result: ImportResult) -> dict:
    """Serialise ImportResult to the JSON format expected by the frontend."""
    return {
        "board_name": result.board_name,
        "pins": [
            {
                "node_label": p.node_label,
                "pincm": p.pincm,
                "function_id": p.function_id,
                "function_macro": p.function_macro,
                "peripheral": p.peripheral,
                "signal": p.signal,
                "pin_name": p.pin_name,
                "input_enable": p.input_enable,
                "bias_pull_up": p.bias_pull_up,
                "bias_pull_down": p.bias_pull_down,
                "drive_open_drain": p.drive_open_drain,
            }
            for p in result.pins
        ],
        "peripherals": [
            {
                "dts_node": pe.dts_node,
                "name": pe.name,
                "enabled": pe.enabled,
                "pinctrl_refs": pe.pinctrl_refs,
                "properties": pe.properties,
            }
            for pe in result.peripherals
        ],
        "kconfig": _dedup_kconfig(result.kconfig),
        "warnings": result.warnings,
    }
