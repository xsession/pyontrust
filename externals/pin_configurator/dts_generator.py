"""
Zephyr DTS overlay & prj.conf generator from pin configurator state.

Takes the current pin assignments and generates:
  1. A ``<board>.overlay``  – pinctrl nodes + peripheral enables
  2. A ``prj.conf`` fragment – Kconfig enables for used peripherals

Output is valid Zephyr DTS that can be dropped into any application folder.
"""

from __future__ import annotations

import re
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
    zephyr_pinmux: str = ""
    custom_name: str = ""
    # Optional pin properties
    bias_pull_up: bool = False
    bias_pull_down: bool = False
    drive_open_drain: bool = False
    input_enable: bool = False

    @property
    def display_name(self) -> str:
        return self.custom_name.strip() or self.pin_name


@dataclass
class PeripheralConfig:
    """Peripheral enable state from the UI."""
    name: str           # e.g. "uart0"
    dts_node: str       # e.g. "&uart0"
    compatible: str     # e.g. "ti,mspm0-uart"
    enabled: bool = False
    core_id: str = ""


@dataclass
class ExternalDeviceConfig:
    id: str
    display: str
    category: str = "device"
    bus: str = ""
    compatible: str = ""
    address: str = ""
    required_signals: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class GeneratedOutput:
    overlay: str
    prj_conf: str
    targets: dict[str, dict[str, str]] = field(default_factory=dict)


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
    "raspberrypi,rp2040-uart": ["CONFIG_SERIAL=y", "CONFIG_UART_CONSOLE=y"],
    "raspberrypi,rp2040-spi": ["CONFIG_SPI=y"],
    "raspberrypi,rp2040-i2c": ["CONFIG_I2C=y"],
    "raspberrypi,rp2040-pwm": ["CONFIG_PWM=y"],
    "raspberrypi,rp2040-adc": ["CONFIG_ADC=y"],
    "raspberrypi,rp2040-gpio": ["CONFIG_GPIO=y"],
}

_DEVICE_KCONFIG_MAP = {
    "bosch,bme280": ["CONFIG_SENSOR=y", "CONFIG_BME280=y"],
    "st,lis2dh": ["CONFIG_SENSOR=y", "CONFIG_LIS2DH=y"],
    "solomon,ssd1306fb": ["CONFIG_DISPLAY=y", "CONFIG_SSD1306=y"],
    "sitronix,st7789v": ["CONFIG_DISPLAY=y", "CONFIG_ST7789V=y"],
}

_DEVICE_CATEGORY_KCONFIG = {
    "sensor": ["CONFIG_SENSOR=y"],
    "display": ["CONFIG_DISPLAY=y"],
}

_ARDUINO_DEVICE_SNIPPETS = {
    "bosch,bme280": [
        "  // Example: Adafruit_BME280 bme280;",
        "  // bme280.begin(0x76);",
    ],
    "solomon,ssd1306fb": [
        "  // Example: Adafruit_SSD1306 display(128, 64, &Wire);",
        "  // display.begin(SSD1306_SWITCHCAPVCC, 0x3C);",
    ],
    "sitronix,st7789v": [
        "  // Example: Adafruit_ST7789 display(TFT_CS, TFT_DC, TFT_RST);",
        "  // display.init(240, 320);",
    ],
}


def _sanitize_node_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_") or "device"


def _parse_address(address: str) -> Optional[int]:
    text = address.strip().lower()
    if not text:
        return None
    try:
        return int(text, 16) if text.startswith("0x") else int(text, 10)
    except ValueError:
        return None


def _bus_kind(bus: str) -> str:
    lowered = bus.lower()
    for prefix in ("i2c", "spi", "uart"):
        if lowered.startswith(prefix):
            return prefix
    return lowered


def _generate_external_device_zephyr(devices: list[ExternalDeviceConfig]) -> tuple[list[str], set[str]]:
    blocks: list[str] = []
    kconfigs: set[str] = set()

    for device in devices:
        if "zephyr" not in device.frameworks:
            continue
        if not device.bus or not device.compatible:
            continue

        node_id = _sanitize_node_name(device.id)
        compat_tail = _sanitize_node_name(device.compatible.split(",", 1)[-1])
        address_value = _parse_address(device.address)
        unit_addr = f"@{address_value:x}" if address_value is not None else ""
        block = f"&{device.bus} {{\n"
        block += f"\t{node_id}: {compat_tail}{unit_addr} {{\n"
        block += f"\t\tcompatible = \"{device.compatible}\";\n"
        if address_value is not None:
            block += f"\t\treg = <0x{address_value:x}>;\n"
        block += f"\t\tlabel = \"{device.display}\";\n"
        if device.notes:
            block += f"\t\t/* {device.notes} */\n"
        block += "\t\tstatus = \"okay\";\n"
        block += "\t};\n};\n"
        blocks.append(block)

        for line in _DEVICE_CATEGORY_KCONFIG.get(device.category, []):
            kconfigs.add(line)
        for line in _DEVICE_KCONFIG_MAP.get(device.compatible, []):
            kconfigs.add(line)

    return blocks, kconfigs


def _generate_external_device_arduino(devices: list[ExternalDeviceConfig]) -> tuple[list[str], list[str]]:
    include_lines: list[str] = []
    setup_lines: list[str] = []
    started_buses: set[str] = set()

    for device in devices:
        if "arduino" not in device.frameworks:
            continue

        kind = _bus_kind(device.bus)
        if kind == "i2c":
            if "#include <Wire.h>" not in include_lines:
                include_lines.append("#include <Wire.h>")
            if device.bus not in started_buses:
                setup_lines.append(f"  // {device.bus} for external devices")
                setup_lines.append("  Wire.begin();")
                started_buses.add(device.bus)
        elif kind == "spi":
            if "#include <SPI.h>" not in include_lines:
                include_lines.append("#include <SPI.h>")
            if device.bus not in started_buses:
                setup_lines.append(f"  // {device.bus} for external devices")
                setup_lines.append("  SPI.begin();")
                started_buses.add(device.bus)

        setup_lines.append(
            f"  // Device: {device.display} on {device.bus or 'unassigned bus'}"
            + (f" ({device.address})" if device.address else "")
        )
        if device.notes:
            setup_lines.append(f"  // {device.notes}")
        setup_lines.extend(_ARDUINO_DEVICE_SNIPPETS.get(device.compatible, [
            f"  // Compatible: {device.compatible}",
        ]))

    return include_lines, setup_lines


def _function_macro(function_id: int) -> str:
    """Return the DTS macro name for a function id."""
    names = {
        0: "MSPM0_PIN_FUNCTION_ANALOG",
        1: "MSPM0_PIN_FUNCTION_GPIO",
    }
    return names.get(function_id, f"MSPM0_PIN_FUNCTION_{function_id}")


def _sanitize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_") or "PIN"


def _pin_numeric_value(pin_name: str, fallback: int) -> int:
    match = re.search(r"(\d+)$", pin_name)
    if match:
        return int(match.group(1))
    return fallback


def _baremetal_mode(direction: str) -> str:
    if direction == "analog":
        return "PIN_MODE_ANALOG"
    if direction == "out":
        return "PIN_MODE_OUTPUT"
    return "PIN_MODE_INPUT"


def _arduino_mode(assignment: PinAssignment) -> str:
    if assignment.direction == "analog":
        return "INPUT"
    if assignment.direction == "out":
        return "OUTPUT"
    if assignment.bias_pull_up:
        return "INPUT_PULLUP"
    return "INPUT"


def _pinctrl_node_name(assignment: PinAssignment) -> str:
    """
    Generate a DTS node label like ``uart0_tx_pa10``.
    """
    periph = assignment.peripheral
    sig = assignment.signal
    pin = assignment.pin_name.lower()
    return f"{periph}_{sig}_{pin}"


def _zephyr_pinmux_expr(assignment: PinAssignment) -> str:
    if assignment.zephyr_pinmux:
        return assignment.zephyr_pinmux
    return f"MSP_PINMUX({assignment.pincm},{_function_macro(assignment.function_id)})"


def _zephyr_header(assignments: list[PinAssignment], board_name: str) -> str:
    uses_explicit_macros = any(assignment.zephyr_pinmux for assignment in assignments)
    include = "#include <zephyr/dt-bindings/pinctrl/rpi-pico-pinctrl.h>" if uses_explicit_macros else "#include <zephyr/dt-bindings/pinctrl/mspm0-pinctrl.h>"
    return textwrap.dedent(f"""\
        /*
         * Auto-generated DTS overlay for {board_name}
         * Created by Zephyr Pin Configurator
         *
         * SPDX-License-Identifier: Apache-2.0
         */

        {include}

    """)


def _generate_zephyr_output(
    assignments: list[PinAssignment],
    peripherals: list[PeripheralConfig],
    external_devices: list[ExternalDeviceConfig],
    board_name: str,
) -> tuple[str, str]:
    # ── Group assignments by peripheral ──────────────────────────────
    periph_pins: dict[str, list[PinAssignment]] = {}
    for a in assignments:
        periph_pins.setdefault(a.peripheral, []).append(a)

    pinctrl_nodes: list[str] = []

    for a in sorted(assignments, key=lambda x: x.pincm):
        label = _pinctrl_node_name(a)
        props = [f"\t\tpinmux = <{_zephyr_pinmux_expr(a)}>;"]
        if a.input_enable or a.direction == "in" or a.direction == "io":
            props.append("\t\tinput-enable;")
        if a.bias_pull_up:
            props.append("\t\tbias-pull-up;")
        if a.bias_pull_down:
            props.append("\t\tbias-pull-down;")
        if a.drive_open_drain:
            props.append("\t\tdrive-open-drain;")

        node_text = f"\t{label}: {label} {{\n"
        if a.custom_name.strip():
            node_text += f"\t\t/* {a.display_name} -> {a.pin_name} */\n"
        node_text += "\n".join(props) + "\n"
        node_text += "\t};\n"
        pinctrl_nodes.append(node_text)

    periph_blocks: list[str] = []
    enabled_periphs = {p.name: p for p in peripherals if p.enabled}

    for name in ("gpioa", "gpiob", "gpio0"):
        if name in enabled_periphs:
            core_comment = f"\t/* assigned-core: {enabled_periphs[name].core_id} */\n" if enabled_periphs[name].core_id else ""
            periph_blocks.append(f"{enabled_periphs[name].dts_node} {{\n{core_comment}\tstatus = \"okay\";\n}};\n")

    for pname, pconf in sorted(enabled_periphs.items()):
        if pname.startswith("gpio"):
            continue

        pins_for = periph_pins.get(pname, [])
        if not pins_for and pname not in ("adc0", "dac0", "comp0", "comp1"):
            continue

        block = f"{pconf.dts_node} {{\n"
        if pconf.core_id:
            block += f"\t/* assigned-core: {pconf.core_id} */\n"
        block += '\tstatus = "okay";\n'

        if pins_for:
            labels = " ".join(
                f"&{_pinctrl_node_name(a)}"
                for a in sorted(pins_for, key=lambda x: x.pincm)
            )
            block += f"\tpinctrl-0 = <{labels}>;\n"
            block += '\tpinctrl-names = "default";\n'

        if pname.startswith("uart"):
            block += "\tcurrent-speed = <115200>;\n"
        if pname.startswith("i2c"):
            block += "\tclock-frequency = <I2C_BITRATE_STANDARD>;\n"

        block += "};\n"
        periph_blocks.append(block)

    overlay = _zephyr_header(assignments, board_name)

    if pinctrl_nodes:
        overlay += "&pinctrl {\n"
        overlay += "\n".join(pinctrl_nodes)
        overlay += "};\n\n"

    for block in periph_blocks:
        overlay += block + "\n"

    device_blocks, device_kconfigs = _generate_external_device_zephyr(external_devices)
    for block in device_blocks:
        overlay += block + "\n"

    kconfigs: set[str] = {"CONFIG_CLOCK_CONTROL=y"}
    for pconf in peripherals:
        if pconf.enabled:
            for line in _KCONFIG_MAP.get(pconf.compatible, []):
                kconfigs.add(line)
    kconfigs.update(device_kconfigs)

    prj_conf = "# Auto-generated by Zephyr Pin Configurator\n\n"
    prj_conf += "\n".join(sorted(kconfigs)) + "\n"
    return overlay.rstrip() + "\n", prj_conf


def _generate_arduino_output(
    assignments: list[PinAssignment],
    peripherals: list[PeripheralConfig],
    external_devices: list[ExternalDeviceConfig],
    board_name: str,
) -> dict[str, str]:
    constants: list[str] = []
    setup_lines: list[str] = []
    periph_cores = {peripheral.name: peripheral.core_id for peripheral in peripherals if peripheral.core_id}

    for index, assignment in enumerate(sorted(assignments, key=lambda item: item.pincm), start=1):
        symbol = f"PIN_{_sanitize_symbol(assignment.peripheral)}_{_sanitize_symbol(assignment.signal)}"
        pin_value = _pin_numeric_value(assignment.pin_name, index)
        alias_comment = f" // {assignment.display_name} -> {assignment.pin_name}" if assignment.custom_name.strip() else ""
        constants.append(f"constexpr uint8_t {symbol} = {pin_value};{alias_comment}")
        if assignment.peripheral in periph_cores:
            setup_lines.append(f"  // {assignment.peripheral} owned by {periph_cores[assignment.peripheral]}")
        if assignment.custom_name.strip():
            setup_lines.append(f"  // {assignment.display_name} uses physical pin {assignment.pin_name}")
        setup_lines.append(f"  pinMode({symbol}, {_arduino_mode(assignment)});")

    include_lines, device_setup_lines = _generate_external_device_arduino(external_devices)

    header = textwrap.dedent("""\
        #pragma once
        #include <Arduino.h>

    """) + "\n".join(constants) + ("\n" if constants else "")

    sketch = textwrap.dedent(f"""\
        #include "pin_config.h"
        {chr(10).join(include_lines)}

        // Auto-generated Arduino pin map for {board_name}
        void setup() {{
    """)
    combined_setup = setup_lines + device_setup_lines
    sketch += "\n".join(combined_setup) if combined_setup else "  // No assigned pins"
    sketch += textwrap.dedent("""
        }

        void loop() {
        }
    """)
    return {
        "pin_config.h": header,
        f"{board_name}.ino": sketch,
    }


def _generate_baremetal_output(
    assignments: list[PinAssignment],
    peripherals: list[PeripheralConfig],
    board_name: str,
) -> dict[str, str]:
    entries: list[str] = []
    comments: list[str] = []
    periph_cores = {peripheral.name: peripheral.core_id for peripheral in peripherals if peripheral.core_id}

    for index, assignment in enumerate(sorted(assignments, key=lambda item: item.pincm), start=1):
        pin_value = _pin_numeric_value(assignment.pin_name, index)
        entries.append(
            f'  {{ "{assignment.pin_name}", {pin_value}, {_baremetal_mode(assignment.direction)} }},'
        )
        if assignment.peripheral in periph_cores:
            comments.append(f"  /* {assignment.peripheral} owned by {periph_cores[assignment.peripheral]} */")
        comments.append(
            f"  /* {assignment.peripheral}.{assignment.signal} -> {assignment.display_name} ({assignment.pin_name}) */"
        )

    header = textwrap.dedent("""\
        #pragma once

        typedef enum {
          PIN_MODE_INPUT,
          PIN_MODE_OUTPUT,
          PIN_MODE_ANALOG,
        } pin_mode_t;

        typedef struct {
          const char *name;
          unsigned int pin;
          pin_mode_t mode;
        } pin_config_entry_t;

        void pin_config_apply(void);
    """)

    source = textwrap.dedent(f"""\
        #include "pin_config.h"

        static const pin_config_entry_t board_pin_config[] = {{
    """)
    source += "\n".join(entries) if entries else "  { 0, 0, PIN_MODE_INPUT },"
    source += textwrap.dedent("""
        };

        void pin_config_apply(void) {
    """)
    source += "\n".join(comments) if comments else "  /* No assigned pins */"
    source += (
        "\n\n"
        "  (void)board_pin_config;\n"
        f"  /* Add MCU-specific register writes for {board_name} here. */\n"
        "}\n"
    )
    return {
        "pin_config.h": header,
        "pin_config.c": source,
    }


def generate(
    assignments: list[PinAssignment],
    peripherals: list[PeripheralConfig],
    board_name: str = "custom_board",
    targets: Optional[list[str]] = None,
    external_devices: Optional[list[ExternalDeviceConfig]] = None,
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

    requested_targets = [target.lower() for target in (targets or ["zephyr", "arduino", "baremetal"])]

    device_configs = external_devices or []
    overlay, prj_conf = _generate_zephyr_output(assignments, peripherals, device_configs, board_name)
    generated_targets: dict[str, dict[str, str]] = {
        "zephyr": {
            f"{board_name}.overlay": overlay,
            "prj.conf": prj_conf,
        }
    }

    if "arduino" in requested_targets:
        generated_targets["arduino"] = _generate_arduino_output(assignments, peripherals, device_configs, board_name)

    if "baremetal" in requested_targets:
        generated_targets["baremetal"] = _generate_baremetal_output(assignments, peripherals, board_name)

    return GeneratedOutput(
        overlay=overlay,
        prj_conf=prj_conf,
        targets=generated_targets,
    )
