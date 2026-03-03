"""
Zephyr DTS overlay & prj.conf generator from pin configurator state.

Takes the current pin assignments and generates:
  1. A ``<board>.overlay``  – pinctrl nodes + peripheral enables
  2. A ``prj.conf`` fragment – Kconfig enables for used peripherals

Output is valid Zephyr DTS that can be dropped into any application folder.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PinAssignment:
    """One pin ↔ function binding from the UI."""
    pin_name: str       # e.g. "PA10"
    pincm: int          # PINCMx index (1-based)
    function_id: int    # MSPM0_PIN_FUNCTION_x
    af_name: str        # e.g. "UART0_TX"
    peripheral: str     # e.g. "uart0"
    signal: str         # e.g. "tx"
    direction: str      # "in", "out", "io", "analog"
    # Optional pin properties
    bias_pull_up: bool = False
    bias_pull_down: bool = False
    drive_open_drain: bool = False
    input_enable: bool = False


@dataclass
class PeripheralConfig:
    """Peripheral enable state from the UI."""
    name: str           # e.g. "uart0"
    dts_node: str       # e.g. "&uart0"
    compatible: str     # e.g. "ti,mspm0-uart"
    enabled: bool = False


@dataclass
class GeneratedOutput:
    overlay: str
    prj_conf: str


# ── Kconfig mapping ───────────────────────────────────────────────────

_KCONFIG_MAP = {
    "ti,mspm0-uart":      ["CONFIG_SERIAL=y", "CONFIG_UART_CONSOLE=y"],
    "ti,mspm0-spi":       ["CONFIG_SPI=y"],
    "ti,mspm0-i2c":       ["CONFIG_I2C=y"],
    "ti,mspm0-can":       ["CONFIG_CAN=y"],
    "ti,mspm0-gpio":      ["CONFIG_GPIO=y"],
    "ti,mspm0-timer":     ["CONFIG_COUNTER=y"],
    "ti,mspm0-timer-pwm": ["CONFIG_PWM=y"],
    "ti,mspm0-adc":       ["CONFIG_ADC=y"],
    "ti,mspm0-dac":       [],
    "ti,mspm0-comp":      [],
}


def _function_macro(function_id: int) -> str:
    """Return the DTS macro name for a function id."""
    names = {
        0: "MSPM0_PIN_FUNCTION_ANALOG",
        1: "MSPM0_PIN_FUNCTION_GPIO",
    }
    return names.get(function_id, f"MSPM0_PIN_FUNCTION_{function_id}")


def _pinctrl_node_name(assignment: PinAssignment) -> str:
    """
    Generate a DTS node label like ``uart0_tx_pa10``.
    """
    periph = assignment.peripheral
    sig = assignment.signal
    pin = assignment.pin_name.lower()
    return f"{periph}_{sig}_{pin}"


def generate(
    assignments: list[PinAssignment],
    peripherals: list[PeripheralConfig],
    board_name: str = "custom_board",
) -> GeneratedOutput:
    """
    Generate a Zephyr DTS overlay and prj.conf fragment.

    Parameters
    ----------
    assignments : list[PinAssignment]
        All pins that the user has assigned to a function.
    peripherals : list[PeripheralConfig]
        Peripheral enable / disable state.
    board_name : str
        Used in the comment header.

    Returns
    -------
    GeneratedOutput
        .overlay and .prj_conf as strings.
    """

    # ── Group assignments by peripheral ──────────────────────────────
    periph_pins: dict[str, list[PinAssignment]] = {}
    for a in assignments:
        periph_pins.setdefault(a.peripheral, []).append(a)

    # ── Build the pinctrl block ──────────────────────────────────────
    pinctrl_nodes: list[str] = []

    for a in sorted(assignments, key=lambda x: x.pincm):
        label = _pinctrl_node_name(a)
        props = [f"\t\tpinmux = <MSP_PINMUX({a.pincm},{_function_macro(a.function_id)})>;"]
        if a.input_enable or a.direction == "in" or a.direction == "io":
            props.append("\t\tinput-enable;")
        if a.bias_pull_up:
            props.append("\t\tbias-pull-up;")
        if a.bias_pull_down:
            props.append("\t\tbias-pull-down;")
        if a.drive_open_drain:
            props.append("\t\tdrive-open-drain;")

        node_text = f"\t{label}: {label} {{\n"
        node_text += "\n".join(props) + "\n"
        node_text += "\t};\n"
        pinctrl_nodes.append(node_text)

    # ── Build the peripheral enable blocks ───────────────────────────
    periph_blocks: list[str] = []

    enabled_periphs = {p.name: p for p in peripherals if p.enabled}

    # GPIO ports – just enable them
    for name in ("gpioa", "gpiob"):
        if name in enabled_periphs:
            periph_blocks.append(f"{enabled_periphs[name].dts_node} {{\n\tstatus = \"okay\";\n}};\n")

    # UART / SPI / I2C / CAN – add pinctrl references
    for pname, pconf in sorted(enabled_periphs.items()):
        if pname.startswith("gpio"):
            continue  # already handled

        pins_for = periph_pins.get(pname, [])
        if not pins_for and pname not in ("adc0", "dac0", "comp0", "comp1"):
            continue  # no pins assigned, skip

        block = f"{pconf.dts_node} {{\n"
        block += '\tstatus = "okay";\n'

        if pins_for:
            labels = " ".join(
                f"&{_pinctrl_node_name(a)}"
                for a in sorted(pins_for, key=lambda x: x.pincm)
            )
            block += f"\tpinctrl-0 = <{labels}>;\n"
            block += '\tpinctrl-names = "default";\n'

        # Add peripheral-specific defaults
        if pname.startswith("uart"):
            block += "\tcurrent-speed = <115200>;\n"
        if pname.startswith("i2c"):
            block += "\tclock-frequency = <I2C_BITRATE_STANDARD>;\n"

        block += "};\n"
        periph_blocks.append(block)

    # ── Assemble the overlay ─────────────────────────────────────────
    header = textwrap.dedent(f"""\
        /*
         * Auto-generated DTS overlay for {board_name}
         * Created by Zephyr Pin Configurator
         *
         * SPDX-License-Identifier: Apache-2.0
         */

        #include <zephyr/dt-bindings/pinctrl/mspm0-pinctrl.h>

    """)

    overlay = header

    if pinctrl_nodes:
        overlay += "&pinctrl {\n"
        overlay += "\n".join(pinctrl_nodes)
        overlay += "};\n\n"

    for b in periph_blocks:
        overlay += b + "\n"

    # ── Build prj.conf ───────────────────────────────────────────────
    kconfigs: set[str] = set()
    kconfigs.add("CONFIG_CLOCK_CONTROL=y")

    for pconf in peripherals:
        if pconf.enabled:
            for line in _KCONFIG_MAP.get(pconf.compatible, []):
                kconfigs.add(line)

    prj_conf = "# Auto-generated by Zephyr Pin Configurator\n\n"
    prj_conf += "\n".join(sorted(kconfigs)) + "\n"

    return GeneratedOutput(overlay=overlay.rstrip() + "\n", prj_conf=prj_conf)
