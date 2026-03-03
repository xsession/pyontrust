"""
MCU Package Generator – produces board definition .py files from parsed PDF data.

Takes DatasheetInfo (from pdf_parser) and generates Python source files matching
the format used by the pin_configurator (see boards/mspm0g3507_48qfp.py).

Usage
-----
    from pdf_parser import parse_datasheet
    from package_generator import generate_board_files

    info = parse_datasheet("MSPM0G3507.pdf")
    generate_board_files(info, output_dir="boards")
"""

from __future__ import annotations

import os
import re
import pathlib
import textwrap
from typing import Optional

from pdf_parser import (
    DatasheetInfo, PackageInfo, PackagePin, PinMuxEntry, DeviceSummary,
)


# ─────────────────────────────────────────────────────────────────────
# Known TI MSPM0 peripherals → DTS compatible + base addresses
# ─────────────────────────────────────────────────────────────────────

# This mapping is used to fill in Peripheral() entries.
# Extend as needed for other MCU families.
_TI_PERIPH_MAP = {
    "gpioa":  ("ti,mspm0-gpio",      "0x400a0000", "&gpioa"),
    "gpiob":  ("ti,mspm0-gpio",      "0x400a2000", "&gpiob"),
    "uart0":  ("ti,mspm0-uart",      "0x40108000", "&uart0"),
    "uart1":  ("ti,mspm0-uart",      "0x40100000", "&uart1"),
    "uart2":  ("ti,mspm0-uart",      "0x40102000", "&uart2"),
    "uart3":  ("ti,mspm0-uart",      "0x40500000", "&uart3"),
    "spi0":   ("ti,mspm0-spi",       "",           "&spi0"),
    "spi1":   ("ti,mspm0-spi",       "",           "&spi1"),
    "i2c0":   ("ti,mspm0-i2c",       "",           "&i2c0"),
    "i2c1":   ("ti,mspm0-i2c",       "",           "&i2c1"),
    "can0":   ("ti,mspm0-can",       "",           "&can0"),
    "tima0":  ("ti,mspm0-timer-pwm", "0x40860000", "&tima0"),
    "tima1":  ("ti,mspm0-timer-pwm", "0x40862000", "&tima1"),
    "timg0":  ("ti,mspm0-timer",     "0x40084000", "&timg0"),
    "timg6":  ("ti,mspm0-timer",     "0x40868000", "&timg6"),
    "timg7":  ("ti,mspm0-timer",     "0x4086a000", "&timg7"),
    "timg8":  ("ti,mspm0-timer",     "0x40090000", "&timg8"),
    "timg12": ("ti,mspm0-timer",     "0x40870000", "&timg12"),
    "adc0":   ("ti,mspm0-adc",       "",           "&adc0"),
    "dac0":   ("ti,mspm0-dac",       "",           "&dac0"),
    "comp0":  ("ti,mspm0-comp",      "",           "&comp0"),
    "comp1":  ("ti,mspm0-comp",      "",           "&comp1"),
}

# Peripheral display names
_PERIPH_DISPLAY = {
    "gpioa": "GPIO A", "gpiob": "GPIO B",
    "uart0": "UART 0", "uart1": "UART 1", "uart2": "UART 2", "uart3": "UART 3",
    "spi0": "SPI 0", "spi1": "SPI 1",
    "i2c0": "I2C 0", "i2c1": "I2C 1",
    "can0": "CAN 0",
    "tima0": "Timer A0 (PWM)", "tima1": "Timer A1 (PWM)",
    "timg0": "Timer G0", "timg6": "Timer G6", "timg7": "Timer G7",
    "timg8": "Timer G8", "timg12": "Timer G12",
    "adc0": "ADC 0", "dac0": "DAC 0",
    "comp0": "Comp 0", "comp1": "Comp 1",
}

# Peripheral → signal list (used to build Peripheral objects)
_PERIPH_SIGNALS = {
    "gpioa": [], "gpiob": [],
    "uart0": ["tx", "rx"], "uart1": ["tx", "rx"],
    "uart2": ["tx", "rx"], "uart3": ["tx", "rx"],
    "spi0": ["sclk", "pico", "poci", "cs0"],
    "spi1": ["sclk", "pico", "poci", "cs0"],
    "i2c0": ["scl", "sda"], "i2c1": ["scl", "sda"],
    "can0": ["tx", "rx"],
}


# ─────────────────────────────────────────────────────────────────────
# Side assignment for QFP / LQFP / QFN packages
# ─────────────────────────────────────────────────────────────────────

def _assign_sides(pin_count: int, pin_num: int) -> str:
    """
    Assign a pin to a package side based on standard QFP numbering.

    QFP/LQFP convention (counter-clockwise from top-left):
      Left   (top→bottom): 1  … N/4
      Bottom (left→right): N/4+1 … N/2
      Right  (bottom→top): N/2+1 … 3N/4
      Top    (right→left): 3N/4+1 … N
    """
    q = pin_count // 4
    if pin_num <= q:
        return "left"
    elif pin_num <= 2 * q:
        return "bottom"
    elif pin_num <= 3 * q:
        return "right"
    else:
        return "top"


# ─────────────────────────────────────────────────────────────────────
# Python source-code generation
# ─────────────────────────────────────────────────────────────────────

def _safe_identifier(s: str) -> str:
    """Turn a string into a safe Python identifier."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', s).lower()


def _format_alt_function(entry: PinMuxEntry) -> str:
    """Format one PinMuxEntry as a Python _AF() / _GPIO() / _ANA() call."""
    fn = entry.function_name
    fid = entry.function_id

    # GPIO shorthand
    if fn.upper().startswith("GPIO") and fid == 1:
        port = entry.peripheral.replace("gpio", "").upper()
        bit = entry.signal
        return f'_GPIO("{port}", {bit})'

    # Analog shorthand
    if entry.direction == "analog":
        return f'_ANA("{fn}", "{entry.peripheral}", "{entry.signal}")'

    # General alt-function
    d = entry.direction
    return f'_AF({fid}, "{fn}", "{entry.peripheral}", "{entry.signal}", "{d}")'


def _gen_pin_call(pin: PackagePin, mux_entries: list[PinMuxEntry],
                  pincm: int, side: str) -> str:
    """Generate the Python constructor call for one pin."""

    kind = pin.kind

    if kind == "power":
        return f'        _pwr({pin.number}, "{pin.name}", {side}),'

    if kind == "ground":
        return f'        _gnd({pin.number}, "{pin.name}", {side}),'

    if kind == "special":
        return f'        _spec({pin.number}, "{pin.name}", {side}, "{pin.name}"),'

    # I/O pin
    alts_str = ",\n".join(f"            {_format_alt_function(e)}" for e in mux_entries)
    if alts_str:
        alts_block = f"[\n{alts_str},\n        ]"
    else:
        alts_block = "[]"

    return (
        f'        _io({pin.number}, "{pin.name}", "{pin.port}", '
        f'{pin.gpio_num}, {side}, {pincm}, {alts_block}),'
    )


def _collect_peripherals(mux: dict[str, list[PinMuxEntry]]) -> list[str]:
    """
    Collect unique peripheral ids referenced in the pin-mux table,
    sorted in a sensible order (gpio, uart, spi, i2c, can, timers, adc, dac, comp).
    """
    seen: set[str] = set()
    for entries in mux.values():
        for e in entries:
            p = e.peripheral
            if p and p not in seen:
                seen.add(p)

    # Sort order
    order = [
        "gpioa", "gpiob",
        "uart0", "uart1", "uart2", "uart3",
        "spi0", "spi1",
        "i2c0", "i2c1",
        "can0",
    ]
    # Timers sorted naturally
    timers = sorted([p for p in seen if p.startswith("tim")],
                    key=lambda x: (x[:4], int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))
    # Analog peripherals
    analogs = sorted([p for p in seen if p.startswith(("adc", "dac", "comp"))])

    result = []
    for p in order:
        if p in seen:
            result.append(p)
    for p in timers:
        if p not in result:
            result.append(p)
    for p in analogs:
        if p not in result:
            result.append(p)
    # Anything else we missed
    for p in sorted(seen):
        if p not in result:
            result.append(p)

    return result


def _gen_peripheral_line(periph_id: str,
                         mux: dict[str, list[PinMuxEntry]]) -> str:
    """Generate one Peripheral(...) constructor line."""
    # Look up known info
    if periph_id in _TI_PERIPH_MAP:
        compat, addr, dts_node = _TI_PERIPH_MAP[periph_id]
    else:
        # Guess
        compat = f"ti,mspm0-{periph_id.rstrip('0123456789')}"
        addr = ""
        dts_node = f"&{periph_id}"

    display = _PERIPH_DISPLAY.get(periph_id, periph_id.upper())

    # Collect signals from mux entries
    if periph_id in _PERIPH_SIGNALS:
        signals = _PERIPH_SIGNALS[periph_id]
    else:
        sigs: set[str] = set()
        for entries in mux.values():
            for e in entries:
                if e.peripheral == periph_id and e.signal:
                    sigs.add(e.signal)
        signals = sorted(sigs)

    sigs_str = ", ".join(f'"{s}"' for s in signals)
    return f'        Peripheral("{periph_id}", "{display}", "{compat}", [{sigs_str}], "{addr}", "{dts_node}"),'


def generate_board_file(
    device: DeviceSummary,
    package: PackageInfo,
    pin_mux: dict[str, list[PinMuxEntry]],
    board_name: Optional[str] = None,
    dts_soc_include: Optional[str] = None,
    dts_pinctrl_include: Optional[str] = None,
    pinctrl_header: Optional[str] = None,
) -> str:
    """
    Generate a Python board definition file as a string.

    Parameters
    ----------
    device : DeviceSummary
        SOC name, flash, SRAM, clock.
    package : PackageInfo
        Physical package pins.
    pin_mux : dict
        Pin-mux entries keyed by pin name.
    board_name : str, optional
        Zephyr board name (default: "lp_<soc_lower>").
    dts_soc_include, dts_pinctrl_include, pinctrl_header : str, optional
        Override DTS include strings.

    Returns
    -------
    str
        Python source code for the board definition file.
    """
    soc = device.soc.upper()
    soc_lower = soc.lower()
    pkg_label = package.name.replace("-", "").lower()   # e.g. "qfp48"
    pkg_formal = package.name                            # e.g. "QFP-48"

    if not board_name:
        board_name = f"lp_{soc_lower}"

    func_name = f"build_{soc_lower}_{pkg_label}"
    file_stem = f"{soc_lower}_{pkg_label}"

    # DTS includes – sensible defaults for MSPM0 family
    if not dts_soc_include:
        # e.g. "<ti/mspm0/g/mspm0g3507.dtsi>"
        family_letter = soc[5].lower() if len(soc) > 5 else "g"
        dts_soc_include = f'"<ti/mspm0/{family_letter}/{soc_lower}.dtsi>"'
    else:
        dts_soc_include = f'"{dts_soc_include}"'

    if not dts_pinctrl_include:
        # e.g. "<ti/mspm0g1x0x_g3x0x/mspm0g350x-pinctrl.dtsi>"
        dts_pinctrl_include = '""'
    else:
        dts_pinctrl_include = f'"{dts_pinctrl_include}"'

    if not pinctrl_header:
        pinctrl_header = "mspm0-pinctrl.h"

    # ── Build pin lines ──────────────────────────────────────────────

    side_map = {"left": "L", "bottom": "B", "right": "R", "top": "T"}
    side_comments = {
        "left":   "LEFT SIDE",
        "bottom": "BOTTOM SIDE",
        "right":  "RIGHT SIDE",
        "top":    "TOP SIDE",
    }

    pin_lines: list[str] = []
    current_side = ""
    q = package.pin_count // 4

    for pin in package.pins:
        side = _assign_sides(package.pin_count, pin.number)
        side_var = side_map[side]

        # Section comment
        if side != current_side:
            start = (list(side_map.keys()).index(side)) * q + 1
            end = start + q - 1
            if side == "top":
                end = package.pin_count
            pin_lines.append("")
            pin_lines.append(
                f"        # ═══ {side_comments[side]} "
                f"(pins {start}–{end}) ═══"
            )
            current_side = side

        # Get mux entries for this pin
        entries = pin_mux.get(pin.name, [])
        pincm = 0
        if entries:
            pincm = entries[0].pincm

        pin_lines.append(_gen_pin_call(pin, entries, pincm, side_var))

    pins_block = "\n".join(pin_lines)

    # ── Build peripheral lines ───────────────────────────────────────

    periph_ids = _collect_peripherals(pin_mux)
    periph_lines = [_gen_peripheral_line(pid, pin_mux) for pid in periph_ids]
    periphs_block = "\n".join(periph_lines)

    # ── Assemble the full file ───────────────────────────────────────

    clock_str = f"{device.clock_hz or 0:_}"

    source = textwrap.dedent(f'''\
        """
        {soc} – {package.pin_count}-pin {pkg_formal.split("-")[0]} board definition for the Zephyr Pin Configurator.

        Pin-mux data derived from the {soc} datasheet (PINCM table) and the
        Zephyr ``mspm0-pinctrl.h`` header: MSP_PINMUX(pincm, function).

        *** AUTO-GENERATED by package_generator — do not edit by hand. ***
        """

        from board_schema import (
            BoardDef, Pin, AltFunction, Peripheral,
            PinKind, PinSide,
        )


        def _io(number, name, port, gpio, side, pincm, alts, default="Reset"):
            """Shorthand for an I/O pin with alt-functions."""
            return Pin(
                number=number,
                name=name,
                port=port,
                gpio_num=gpio,
                kind=PinKind.IO,
                side=side,
                default_function=default,
                alt_functions=[
                    AltFunction(
                        function_id=fid,
                        pincm=pincm,
                        name=n,
                        peripheral=per,
                        signal=sig,
                        direction=d,
                    )
                    for fid, n, per, sig, d in alts
                ],
            )


        def _pwr(number, name, side):
            return Pin(number=number, name=name, kind=PinKind.PWR, side=side)


        def _gnd(number, name, side):
            return Pin(number=number, name=name, kind=PinKind.GND, side=side)


        def _spec(number, name, side, default=""):
            return Pin(number=number, name=name, kind=PinKind.SPEC, side=side,
                       default_function=default or name)


        # ── Alt-function tuples: (function_id, label, peripheral, signal, dir) ─

        _AF = lambda fid, label, periph, sig, d="io": (fid, label, periph, sig, d)
        _GPIO = lambda port, bit: _AF(1, f"GPIO{{port}}{{bit}}", f"gpio{{port.lower()}}", f"{{bit}}", "io")
        _ANA  = lambda label, periph, sig: _AF(0, label, periph, sig, "analog")


        def {func_name}() -> BoardDef:
            """
            Return the full {soc} {pkg_formal} board definition.

            Pin numbering follows the {pkg_formal} package:
              Left   (top→bottom): pins 1-{q}
              Bottom (left→right): pins {q+1}-{2*q}
              Right  (bottom→top): pins {2*q+1}-{3*q}
              Top    (right→left): pins {3*q+1}-{package.pin_count}
            """
            L, B, R, T = PinSide.LEFT, PinSide.BOTTOM, PinSide.RIGHT, PinSide.TOP

            pins: list[Pin] = [
        {pins_block}
            ]

            peripherals = [
        {periphs_block}
            ]

            return BoardDef(
                soc="{soc}",
                board="{board_name}",
                vendor="{device.vendor}",
                package="{pkg_formal}",
                pin_count={package.pin_count},
                pins=pins,
                peripherals=peripherals,
                dts_soc_include={dts_soc_include},
                dts_pinctrl_include={dts_pinctrl_include},
                pinctrl_header="{pinctrl_header}",
                flash_size_kb={device.flash_size_kb},
                sram_size_kb={device.sram_size_kb},
                clock_hz={clock_str},
            )
    ''')

    return source


def generate_board_files(
    info: DatasheetInfo,
    output_dir: str | pathlib.Path = "boards",
    board_name: Optional[str] = None,
    dts_soc_include: Optional[str] = None,
    dts_pinctrl_include: Optional[str] = None,
    pinctrl_header: Optional[str] = None,
    register_in_init: bool = True,
) -> list[str]:
    """
    Generate board definition files for every package found in the datasheet.

    Parameters
    ----------
    info : DatasheetInfo
        Parsed datasheet data.
    output_dir : str | Path
        Directory to write the .py files.
    board_name : str, optional
        Override Zephyr board name.
    dts_soc_include, dts_pinctrl_include, pinctrl_header : str, optional
        Override DTS include paths.
    register_in_init : bool
        If True, update boards/__init__.py to register the new board(s).

    Returns
    -------
    list[str]
        Paths of generated files.
    """
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []

    for pkg in info.packages:
        # Filter pin_mux to only pins present in this package
        pkg_pin_names = {p.name for p in pkg.pins}
        pkg_mux = {
            k: v for k, v in info.pin_mux.items()
            if k in pkg_pin_names
        }

        source = generate_board_file(
            device=info.device,
            package=pkg,
            pin_mux=pkg_mux,
            board_name=board_name,
            dts_soc_include=dts_soc_include,
            dts_pinctrl_include=dts_pinctrl_include,
            pinctrl_header=pinctrl_header,
        )

        soc_lower = info.device.soc.lower()
        pkg_label = pkg.name.replace("-", "").lower()
        filename = f"{soc_lower}_{pkg_label}.py"
        filepath = out / filename

        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(source)

        generated.append(str(filepath))
        print(f"  ✓ Generated {filepath}")

    # Update __init__.py
    if register_in_init and generated:
        _update_init(out, info.device.soc, info.packages)

    return generated


def _update_init(boards_dir: pathlib.Path, soc: str,
                 packages: list[PackageInfo]) -> None:
    """
    Update boards/__init__.py to import and register the new board builders.
    Preserves existing entries.
    """
    init_path = boards_dir / "__init__.py"

    # Read existing content
    existing = ""
    if init_path.exists():
        with open(init_path, "r", encoding="utf-8") as f:
            existing = f.read()

    imports: list[str] = []
    entries: list[str] = []

    for pkg in packages:
        soc_lower = soc.lower()
        pkg_label = pkg.name.replace("-", "").lower()
        module_name = f"{soc_lower}_{pkg_label}"
        func_name = f"build_{module_name}"
        board_key = soc_lower

        # If multiple packages, use package-specific key
        if len(packages) > 1:
            board_key = f"{soc_lower}_{pkg_label}"

        import_line = f"from .{module_name} import {func_name}"
        entry_line = f'    "{board_key}": {func_name},'

        # Only add if not already present
        if func_name not in existing:
            imports.append(import_line)
            entries.append(entry_line)

    if not imports:
        return  # Nothing new to add

    if "BOARDS" in existing:
        # Insert new imports before BOARDS dict and new entries inside it
        lines = existing.split("\n")
        new_lines: list[str] = []
        boards_found = False

        for line in lines:
            # Insert imports before the BOARDS = { line
            if re.match(r'^BOARDS\s*=\s*\{', line) and not boards_found:
                for imp in imports:
                    new_lines.append(imp)
                new_lines.append("")
                new_lines.append(line)
                boards_found = True
                continue

            # Insert new entries before the closing }
            if boards_found and line.strip() == "}":
                for ent in entries:
                    new_lines.append(ent)
                new_lines.append(line)
                continue

            new_lines.append(line)

        with open(init_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(new_lines))
    else:
        # Write fresh __init__.py
        with open(init_path, "w", encoding="utf-8", newline="\n") as f:
            for imp in imports:
                f.write(imp + "\n")
            f.write("\nBOARDS = {\n")
            for ent in entries:
                f.write(ent + "\n")
            f.write("}\n")

    print(f"  ✓ Updated {init_path}")
