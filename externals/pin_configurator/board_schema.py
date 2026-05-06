"""
Board definition schema for the Zephyr Pin Configurator.

Each board JSON describes:
  - Package outline (QFP-48, LQFP-64, etc.)
  - Physical pins and their locations
  - Alternate-function mux table (PINCM-based for MSPM0)
  - Peripheral instances and their required signals
  - Power / ground / special pins
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ── Pin types ──────────────────────────────────────────────────────────

class PinKind(str, Enum):
    IO   = "io"       # Configurable I/O pin
    PWR  = "power"    # VDD / DVDD / AVDD
    GND  = "ground"   # VSS / DVSS
    SPEC = "special"  # NRST, TEST, XIN, XOUT, etc.


class PinSide(str, Enum):
    LEFT   = "left"
    BOTTOM = "bottom"
    RIGHT  = "right"
    TOP    = "top"


class OutputKind(str, Enum):
    ZEPHYR = "zephyr"
    ARDUINO = "arduino"
    BAREMETAL = "baremetal"


# ── Data classes ───────────────────────────────────────────────────────

@dataclass
class AltFunction:
    """One alternate function entry for a pin."""
    function_id: int          # MSPM0_PIN_FUNCTION_x  (0-15)
    pincm: int                # PINCMx register index (1-based)
    name: str                 # Human-readable, e.g. "UART0_TX"
    peripheral: str           # e.g. "uart0", "spi1", "gpio"
    signal: str               # e.g. "tx", "rx", "scl", "mosi", "ccp0"
    direction: str = "io"     # "in", "out", "io", "analog"
    zephyr_pinmux: str = ""    # Raw Zephyr pinmux macro/value when not MSPM0


@dataclass
class Pin:
    """A single physical pin."""
    number: int               # 1-based package pin number
    name: str                 # Pad name, e.g. "PA10", "PB22", "VDD"
    port: str = ""            # "A", "B", "C" or "" for non-IO
    gpio_num: int = -1        # GPIO bit within port (-1 = N/A)
    kind: PinKind = PinKind.IO
    side: PinSide = PinSide.LEFT
    alt_functions: list[AltFunction] = field(default_factory=list)
    default_function: str = "Reset"  # label shown when unassigned

    # Current user selection (runtime, not serialised to board JSON)
    selected_af: Optional[int] = None
    selected_label: str = ""
    properties: dict = field(default_factory=dict)  # bias, drive, etc.


@dataclass
class Peripheral:
    """A peripheral instance that requires pins to be assigned."""
    name: str                 # Node label, e.g. "uart0", "spi1"
    display: str              # e.g. "UART 0"
    compatible: str           # Zephyr compatible, e.g. "ti,mspm0-uart"
    signals: list[str]        # Required signal names, e.g. ["tx", "rx"]
    reg_address: str = ""     # e.g. "0x40108000"
    dts_node: str = ""        # e.g. "&uart0"
    enabled: bool = False
    core_id: str = ""         # Owning CPU core for multicore devices
    available_cores: list[str] = field(default_factory=list)


@dataclass
class Core:
    """CPU core metadata for multicore devices."""
    id: str
    name: str
    arch: str
    role: str = "application"
    clock_hz: int = 0
    default: bool = False


@dataclass
class OutputTarget:
    """Supported output target for generated project files."""
    kind: OutputKind
    label: str
    file_suffixes: list[str] = field(default_factory=list)


@dataclass
class ExternalDevice:
    """Optional off-board device wired to this board."""
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
class BoardDef:
    """Complete board / SoC definition."""
    soc: str                  # e.g. "MSPM0G3507"
    board: str                # e.g. "lp_mspm0g3507"
    vendor: str = "ti"
    package: str = "QFP-48"
    pin_count: int = 48
    pins: list[Pin] = field(default_factory=list)
    peripherals: list[Peripheral] = field(default_factory=list)
    external_devices: list[ExternalDevice] = field(default_factory=list)
    cores: list[Core] = field(default_factory=list)
    output_targets: list[OutputTarget] = field(default_factory=list)

    # DTS generation metadata
    dts_soc_include: str = ""    # e.g. "<ti/mspm0/g/mspm0g3507.dtsi>"
    dts_pinctrl_include: str = "" # e.g. "<ti/mspm0g1x0x_g3x0x/mspm0g350x-pinctrl.dtsi>"
    pinctrl_header: str = ""     # e.g. "mspm0-pinctrl.h"
    flash_size_kb: int = 128
    sram_size_kb: int = 32
    clock_hz: int = 80_000_000


# ── I/O helpers ────────────────────────────────────────────────────────

def _enum_serialiser(obj):
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Not serialisable: {type(obj)}")


def save_board(board: BoardDef, path: str | pathlib.Path) -> None:
    """Persist a board definition to JSON."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(asdict(board), f, indent=2, default=_enum_serialiser)


def load_board(path: str | pathlib.Path) -> BoardDef:
    """Load a board definition from JSON."""
    p = pathlib.Path(path)
    with open(p, "r", encoding="utf-8") as f:
        d = json.load(f)

    pins = []
    for pd in d.pop("pins", []):
        afs = [AltFunction(**a) for a in pd.pop("alt_functions", [])]
        pd["kind"] = PinKind(pd.get("kind", "io"))
        pd["side"] = PinSide(pd.get("side", "left"))
        pins.append(Pin(**pd, alt_functions=afs))

    periphs = [Peripheral(**p) for p in d.pop("peripherals", [])]
    external_devices = [ExternalDevice(**device) for device in d.pop("external_devices", [])]
    cores = [Core(**core) for core in d.pop("cores", [])]

    output_targets = []
    for target in d.pop("output_targets", []):
        output_targets.append(
            OutputTarget(
                **target,
                kind=OutputKind(target.get("kind", "zephyr")),
            )
        )

    return BoardDef(
        **d,
        pins=pins,
        peripherals=periphs,
        external_devices=external_devices,
        cores=cores,
        output_targets=output_targets,
    )


def board_to_frontend(board: BoardDef) -> dict:
    """Convert board to the JSON payload expected by the web UI."""
    return {
        "soc": board.soc,
        "board": board.board,
        "vendor": board.vendor,
        "package": board.package,
        "pin_count": board.pin_count,
        "flash_size_kb": board.flash_size_kb,
        "sram_size_kb": board.sram_size_kb,
        "clock_hz": board.clock_hz,
        "cores": [
            {
                "id": core.id,
                "name": core.name,
                "arch": core.arch,
                "role": core.role,
                "clock_hz": core.clock_hz,
                "default": core.default,
            }
            for core in board.cores
        ],
        "output_targets": [
            {
                "kind": target.kind.value,
                "label": target.label,
                "file_suffixes": target.file_suffixes,
            }
            for target in board.output_targets
        ],
        "pins": [
            {
                "number": p.number,
                "name": p.name,
                "port": p.port,
                "gpio_num": p.gpio_num,
                "kind": p.kind.value,
                "side": p.side.value,
                "default_function": p.default_function,
                "alt_functions": [
                    {
                        "function_id": a.function_id,
                        "pincm": a.pincm,
                        "name": a.name,
                        "peripheral": a.peripheral,
                        "signal": a.signal,
                        "direction": a.direction,
                        "zephyr_pinmux": a.zephyr_pinmux,
                    }
                    for a in p.alt_functions
                ],
            }
            for p in board.pins
        ],
        "peripherals": [
            {
                "name": pe.name,
                "display": pe.display,
                "compatible": pe.compatible,
                "signals": pe.signals,
                "dts_node": pe.dts_node,
                "enabled": pe.enabled,
                "core_id": pe.core_id,
                "available_cores": pe.available_cores,
            }
            for pe in board.peripherals
        ],
        "external_devices": [
            {
                "id": device.id,
                "display": device.display,
                "category": device.category,
                "bus": device.bus,
                "compatible": device.compatible,
                "address": device.address,
                "required_signals": device.required_signals,
                "frameworks": device.frameworks,
                "notes": device.notes,
            }
            for device in board.external_devices
        ],
    }
