// ═══════════════════════════════════════════════════════════════════
//  Pyontrust — Integration & Workflow Tutorial
//  A concrete guide to the embedded test & measurement platform
// ═══════════════════════════════════════════════════════════════════

// ─── Page & Theme Setup ──────────────────────────────────────────
#set page(
  width: 254mm,
  height: 190.5mm,
  margin: (x: 24mm, y: 18mm),
  fill: rgb("#1e1e2e"),          // Catppuccin Mocha base
)

#set text(
  font: "Segoe UI",
  size: 14pt,
  fill: rgb("#cdd6f4"),          // Catppuccin text
)

#set heading(numbering: none)
#show heading.where(level: 1): set text(
  size: 28pt, weight: "bold", fill: rgb("#89b4fa"),   // blue
)
#show heading.where(level: 2): set text(
  size: 22pt, weight: "bold", fill: rgb("#a6e3a1"),   // green
)
#show heading.where(level: 3): set text(
  size: 18pt, weight: "bold", fill: rgb("#f9e2af"),   // yellow
)

// Inline code
#show raw.where(block: false): box.with(
  fill: rgb("#313244"),
  inset: (x: 4pt, y: 2pt),
  outset: (y: 2pt),
  radius: 3pt,
)

// Code blocks
#show raw.where(block: true): block.with(
  fill: rgb("#181825"),
  inset: 10pt,
  radius: 6pt,
  width: 100%,
  stroke: 1pt + rgb("#45475a"),
)
#set raw(theme: none)
#show raw: set text(font: "Consolas", size: 11pt, fill: rgb("#a6e3a1"))

// ─── Helper functions ────────────────────────────────────────────
#let accent   = rgb("#89b4fa")   // blue
#let green    = rgb("#a6e3a1")
#let peach    = rgb("#fab387")
#let mauve    = rgb("#cba6f7")
#let red      = rgb("#f38ba8")
#let yellow   = rgb("#f9e2af")
#let surface0 = rgb("#313244")
#let surface1 = rgb("#45475a")

#let slide-rule() = line(length: 100%, stroke: 0.5pt + surface1)

#let note-box(body) = block(
  width: 100%,
  fill: rgb("#1e1e2e"),
  stroke: 1pt + accent,
  radius: 6pt,
  inset: 12pt,
  body
)

#let warn-box(body) = block(
  width: 100%,
  fill: rgb("#1e1e2e"),
  stroke: 1pt + yellow,
  radius: 6pt,
  inset: 12pt,
  body
)

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 1 — Title
// ═══════════════════════════════════════════════════════════════════
#page[
  #v(1fr)
  #align(center)[
    #text(size: 40pt, weight: "bold", fill: accent)[Pyontrust]
    #v(6pt)
    #text(size: 20pt, fill: rgb("#cdd6f4"))[
      Integration & Workflow Tutorial
    ]
    #v(12pt)
    #slide-rule()
    #v(12pt)
    #text(size: 14pt, fill: surface1)[
      Embedded Test & Measurement Platform \
      v2026.3.0 — CalVer
    ]
  ]
  #v(1fr)
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 2 — What is Pyontrust?
// ═══════════════════════════════════════════════════════════════════
#page[
  = What is Pyontrust?

  #v(8pt)
  A *pure-Python* platform for automated hardware testing:

  #v(6pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === Measure
      - Power / current profiling
      - Thermal camera imaging
      - CAN bus diagnostics
      - Analog waveform capture
    ],
    note-box[
      === Automate
      - FlowLab visual block graph
      - Lab bench orchestration
      - Pass / fail limit checking
      - PDF / CSV / HTML reports
    ],
  )

  #v(12pt)
  #note-box[
    *Key idea* — Every instrument, recorder, and analysis module plugs into a
    common `EventBus` so you can compose arbitrary test flows.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 3 — Architecture Overview
// ═══════════════════════════════════════════════════════════════════
#page[
  = Architecture Overview

  #v(8pt)
  ```
  +---------------------------------------------------+
  |              Flask Gateway  :5200                  |
  |  blueprints: shell, diag, flowlab, thermal ...    |
  +---------------+-----------------+-----------------+
  |  Analysis     |   Services      |    Recorders    |
  |  - power      |   - event_bus   |    - csv        |
  |  - thermal    |   - config      |    - plot       |
  |  - limits     |   - hw_disc     |    - pdf        |
  +---------------+-----------------+-----------------+
  |           HAL  (Hardware Abstraction)              |
  |   AD3 / DMM / Thermal / PCAN / GPIO / Relay       |
  +---------------------------------------------------+
  ```

  #v(8pt)
  #text(fill: peach)[
    Every layer is importable on its own — no gateway required for scripting.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 4 — Installation
// ═══════════════════════════════════════════════════════════════════
#page[
  = Installation

  #v(8pt)
  === 1. Clone & install (editable)
  ```bash
  git clone https://github.com/your-org/pyontrust.git
  cd pyontrust
  pip install -e ".[dev]"
  ```

  #v(8pt)
  === 2. Hardware drivers (optional)
  ```bash
  # Digilent WaveForms runtime  -> AD3
  # PEAK PCAN-Basic             -> CAN bus
  # libusb + pyusb              -> Seek Thermal
  python scripts/discover_hardware.py   # verify
  ```

  #v(8pt)
  === 3. Start the gateway
  ```bash
  python -m pyontrust.gateway.app   # http://localhost:5200
  ```

  #note-box[
    *Tip* — Run `discover_hardware.py` first. It prints a table of every
    detected instrument so you know what is available before writing tests.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 5 — Project Structure
// ═══════════════════════════════════════════════════════════════════
#page[
  = Project Structure

  #v(6pt)
  ```
  pyontrust/
  +-- src/pyontrust/
  |   +-- core/          # models, event bus, config
  |   +-- hal/           # hardware abstraction drivers
  |   +-- instruments/   # high-level instrument wrappers
  |   +-- recorders/     # CSV, plot, PDF recorders
  |   +-- analysis/      # power, thermal, limits
  |   +-- services/      # hardware discovery, utilities
  |   +-- gateway/       # Flask app + blueprints + web UI
  +-- tests/             # 665+ unit tests (pytest)
  +-- profiles/          # JSON test profiles
  +-- limits/            # JSON pass/fail limits
  +-- benches/           # board definition files
  +-- scripts/           # CLI helpers
  ```

  #v(6pt)
  #text(fill: peach)[
    Each folder maps 1-to-1 with an architecture layer.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 6 — Core Models
// ═══════════════════════════════════════════════════════════════════
#page[
  = Core Models

  #v(6pt)
  All data flows through *dataclasses*:

  #v(6pt)
  ```python
  @dataclass
  class Sample:
      timestamp: float
      value: float
      unit: str = "A"

  @dataclass
  class PowerTrace:
      samples: list[Sample]
      metadata: dict
  ```

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === Domain Objects
      - `Sample` — single reading
      - `PowerTrace` — ordered samples
      - `ThermalFrame` — pixel matrix
      - `LimitSpec` — pass/fail rule
    ],
    note-box[
      === Why dataclasses?
      - Immutable-friendly
      - Free `__repr__` / `__eq__`
      - Easy JSON serialization
      - Type-checker friendly
    ],
  )
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7 — HAL Protocol
// ═══════════════════════════════════════════════════════════════════
#page[
  = HAL — Hardware Abstraction

  #v(6pt)
  Every driver implements a thin *protocol*:

  #v(4pt)
  ```python
  class PowerMeterProtocol(Protocol):
      def open(self) -> None: ...
      def read_current(self) -> float: ...
      def close(self) -> None: ...
  ```

  #v(8pt)
  Concrete drivers:

  #grid(
    columns: (1fr, 1fr, 1fr),
    gutter: 12pt,
    note-box[
      *AD3 Power*\
      Analog Discovery 3\
      via DWF C library
    ],
    note-box[
      *Seek Thermal*\
      Pure-Python USB\
      libseek driver
    ],
    note-box[
      *PCAN*\
      CAN bus diag\
      via PCAN-Basic
    ],
  )

  #v(8pt)
  #warn-box[
    *Swap rule* — Any driver can be replaced with a simulated stub by
    setting `simulated: true` in the bench file. Tests run everywhere.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7b — Communication Interface Description (YAML)
// ═══════════════════════════════════════════════════════════════════
#page[
  = Communication Interface Description

  #v(6pt)
  Interfaces are defined in *YAML* — single source of truth for docs, C headers, and Python drivers:

  #v(4pt)
  ```yaml
  interface:
    title: Locator Base MCU Interface
    version history:
      - fw-version: "1.0"
        date: '2026.03.09'
        author: dev
        changes: >
          - Initial CANopen object dictionary.

    canopen:
      nodes:
        - id: 0x10
          name: Locator Base Node
          doc: >
            Main control & monitor node for the
            locator base board.

      object dictionary:
        info:
          device_name:
            mlx: 0x100800
            flags: [read]
            type: string
            doc: >
              Device name. E.g.: "Locator Base"
          fw_version:
            mlx: 0x100a00
            flags: [read]
            type: string
            doc: >
              Firmware version. Format: "FW vX.Y"
  ```

  #text(fill: peach)[
    One YAML file → C header + Python driver + HTML docs + XML.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7c — Object Dictionary & Types
// ═══════════════════════════════════════════════════════════════════
#page[
  = Object Dictionary & Types

  #v(6pt)
  === SDO Object Dictionary

  #table(
    columns: (1.4fr, 0.8fr, 0.8fr, 0.5fr, 2fr),
    stroke: 0.5pt + surface1,
    inset: 8pt,
    fill: (_, row) => if calc.odd(row) { surface0 } else { rgb("#1e1e2e") },
    table.header(
      [*Object Name*], [*MLX*], [*Type*], [*R/W*], [*Description*],
    ),
    [`device_name`],       [`0x100800`], [`string`],   [R],   [Device name of the node],
    [`hw_version`],        [`0x100900`], [`string`],   [RW],  [Hardware version (PCB article ID)],
    [`fw_version`],        [`0x100a00`], [`string`],   [R],   [Firmware version "FW vX.Y"],
    [`stored_node_id`],    [`0x100b00`], [`uint16`],   [RW],  [CAN node ID stored in flash],
    [`stored_can_speed`],  [`0x314420`], [`uint16`],   [RW],  [CAN baud rate stored in flash],
    [`serial_num`],        [`0x312301`], [`string`],   [RW],  [Manufacturer serial number],
  )

  #v(6pt)
  === Bitfield Types (separate `_types.yaml`)

  ```yaml
  types:
    status_tun:
      size: 32
      format: union
      fields:
        all:  { size: 32, format: uint }
        bits: EXT__status_tst

    status_tst:
      size: 32
      format: bitfield
      fields:
        ACTIVE:   { size: 1, doc: "Node active flag" }
        ERROR:    { size: 1, doc: "Error present" }
        RESERVED: { size: 30, doc: "Reserved bits" }
  ```
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7d — Code Generation Pipeline
// ═══════════════════════════════════════════════════════════════════
#page[
  = Code Generation Pipeline

  #v(6pt)
  ```
  +------------------+     +----------------+     +-------------------+
  |  mcu.yaml        |---->|                |---->|  generated/c/     |
  |  mcu_types.yaml  |     |  yaml_doc.py   |     |    mcu_can_if.h   |
  |  mcu_pdo.yaml    |     |  (batch: mp.y) |     |    mcu_types.h    |
  +------------------+     +----------------+     |    mcu_pdo.h      |
                                  |               +-------------------+
                                  |               +-------------------+
                                  +-------------->|  generated/py/    |
                                  |               |    generated.py   |
                                  |               +-------------------+
                                  |               +-------------------+
                                  +-------------->|  generated/html/  |
                                                  |    html_chunk.html|
                                                  +-------------------+
  ```

  #v(6pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    gutter: 12pt,
    note-box[
      *C Header*\
      `#define` MLX addresses\
      `MLX_DEF_MACRO` structs\
      Type-safe SDO access
    ],
    note-box[
      *Python Driver*\
      Typed SDO read/write\
      Enum/bitfield decode\
      Integrates with `can_service`
    ],
    note-box[
      *HTML / Confluence*\
      Version history table\
      Node list & OD tables\
      Auto-upload to wiki
    ],
  )

  #v(8pt)
  #note-box[
    *Batch file* (`mp.yaml`) — lists all generation targets, dependencies, and
    output paths. Run `yaml_doc.py mp.yaml` to regenerate everything.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7e — UART Interface Description
// ═══════════════════════════════════════════════════════════════════
#page[
  = UART Interface Description

  #v(4pt)
  ```yaml
  interface:
    title: Locator Base UART Debug Interface
    transport: uart
    version history:
      - fw-version: "1.0"
        date: '2026.03.09'
        author: dev
        changes: "Initial UART command set."

    uart:
      physical:
        tx_pin: PA10
        rx_pin: PA11
        baud_rate: 115200
        data_bits: 8
        parity: none
        stop_bits: 1
        flow_control: none

      framing:
        start_byte: 0xAA
        end_byte: 0x55
        crc: crc16-ccitt
        max_payload: 256
        byte_order: little-endian

      commands:
        get_version:
          id: 0x01
          direction: request-response
          request:  { fields: [] }
          response: { fields: [
            { name: major, type: uint8 },
            { name: minor, type: uint8 } ] }
          doc: "Query firmware version."

        set_led:
          id: 0x02
          direction: request-response
          request:  { fields: [
            { name: led_id, type: uint8 },
            { name: state,  type: uint8 } ] }
          response: { fields: [
            { name: ack, type: uint8 } ] }
          doc: "Set LED on/off state."
  ```
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7f — RS-485 Interface Description
// ═══════════════════════════════════════════════════════════════════
#page[
  = RS-485 Interface Description

  #v(4pt)
  ```yaml
  interface:
    title: Locator Base RS-485 Bus
    transport: rs485
    version history:
      - fw-version: "1.0"
        date: '2026.03.09'
        author: dev
        changes: "Initial Modbus register map."

    rs485:
      physical:
        a_pin: PA5        # D+ / non-inverting
        b_pin: PA6        # D- / inverting
        de_pin: PA7       # driver-enable (auto)
        baud_rate: 9600
        data_bits: 8
        parity: even
        stop_bits: 1
        termination: true  # 120 Ω on-board

      modbus:
        mode: rtu          # rtu | ascii
        slave_id: 0x10
        registers:
          holding:
            - addr: 0x0000
              name: device_status
              type: uint16
              flags: [read]
              doc: "Bit-mapped device status word."
            - addr: 0x0001
              name: led_control
              type: uint16
              flags: [read, write]
              doc: "LED on/off bitmask (bit 0 = LED0)."
            - addr: 0x0002
              name: fw_version_major
              type: uint16
              flags: [read]
              doc: "Firmware major version."
            - addr: 0x0003
              name: fw_version_minor
              type: uint16
              flags: [read]
              doc: "Firmware minor version."
          input:
            - addr: 0x0000
              name: temperature
              type: int16
              unit: "0.1 °C"
              flags: [read]
              doc: "Board temperature × 10."
            - addr: 0x0001
              name: supply_voltage
              type: uint16
              unit: mV
              flags: [read]
              doc: "Supply rail voltage in mV."
  ```
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7g — TCP / UDP Interface Description
// ═══════════════════════════════════════════════════════════════════
#page[
  = TCP / UDP Interface Description

  #v(4pt)
  ```yaml
  interface:
    title: Locator Base Ethernet Control
    transport: tcp/udp
    version history:
      - fw-version: "1.0"
        date: '2026.03.09'
        author: dev
        changes: "Initial TCP command + UDP telemetry."

    tcp:
      port: 5200
      framing:
        header: { length: 4, fields: [
          { name: msg_id,  type: uint16 },
          { name: payload_len, type: uint16 } ] }
        crc: crc32
        byte_order: big-endian

      commands:
        get_status:
          id: 0x0001
          direction: request-response
          request:  { fields: [] }
          response: { fields: [
            { name: state,   type: uint8 },
            { name: uptime_s, type: uint32 } ] }
          doc: "Query device operating status."
        start_measurement:
          id: 0x0010
          direction: request-response
          request:  { fields: [
            { name: channel,    type: uint8 },
            { name: duration_ms, type: uint32 } ] }
          response: { fields: [
            { name: ack, type: uint8 } ] }
          doc: "Start a measurement on given channel."

    udp:
      port: 5201
      messages:
        telemetry:
          id: 0x0100
          direction: publish
          rate_hz: 10
          fields:
            - { name: timestamp_ms, type: uint32 }
            - { name: current_uA,   type: float32 }
            - { name: temperature,   type: int16 }
          doc: "Periodic telemetry broadcast."
  ```
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7h — I²C Interface Description
// ═══════════════════════════════════════════════════════════════════
#page[
  = I²C Interface Description

  #v(4pt)
  ```yaml
  interface:
    title: Locator Base I2C Sensor Bus
    transport: i2c
    version history:
      - fw-version: "1.0"
        date: '2026.03.09'
        author: dev
        changes: "Initial I2C register map."

    i2c:
      physical:
        sda_pin: PA0
        scl_pin: PA1
        speed: 400kHz       # standard | fast | fast-plus
        pull_ups: "4.7 kΩ external"
        address_bits: 7

      devices:
        - address: 0x48
          name: temp_sensor
          doc: "On-board temperature sensor (TMP117 compatible)."
          registers:
            - addr: 0x00
              name: temperature
              type: int16
              flags: [read]
              unit: "0.0078125 °C / LSB"
              doc: "Temperature result register."
            - addr: 0x01
              name: config
              type: uint16
              flags: [read, write]
              doc: "Configuration register."
            - addr: 0x02
              name: t_high_limit
              type: int16
              flags: [read, write]
              doc: "High-temperature alert threshold."
            - addr: 0x03
              name: t_low_limit
              type: int16
              flags: [read, write]
              doc: "Low-temperature alert threshold."

        - address: 0x50
          name: eeprom
          doc: "256-byte calibration EEPROM."
          registers:
            - addr: 0x00
              name: cal_data
              type: bytes
              length: 256
              flags: [read, write]
              page_size: 16
              doc: "Calibration data block (page-write)."
  ```
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7i — SPI Interface Description
// ═══════════════════════════════════════════════════════════════════
#page[
  = SPI Interface Description

  #v(4pt)
  ```yaml
  interface:
    title: Locator Base SPI Peripheral Bus
    transport: spi
    version history:
      - fw-version: "1.0"
        date: '2026.03.09'
        author: dev
        changes: "Initial SPI register map."

    spi:
      physical:
        sck_pin:  PA12
        mosi_pin: PA14      # PICO
        miso_pin: PA13      # POCI
        cs_pins:
          - { pin: PA8,  device: dac }
          - { pin: PA3,  device: adc_ext }
          - { pin: PA24, device: flash }
        clock_hz: 10_000_000
        mode: 0              # CPOL=0, CPHA=0
        bit_order: msb-first
        word_size: 8

      devices:
        - cs: dac
          name: dac_output
          doc: "12-bit DAC (MCP4921 compatible)."
          transactions:
            write_dac:
              type: write
              frame: { fields: [
                { name: control, type: uint4,
                  bits: "SHDN:1 GA:1 BUF:1 RSVD:1" },
                { name: value,   type: uint12 } ] }
              doc: "Write 12-bit output value."

        - cs: adc_ext
          name: adc_input
          doc: "16-bit external ADC (ADS8681 compatible)."
          transactions:
            read_sample:
              type: read
              frame: { fields: [
                { name: status, type: uint4 },
                { name: value,  type: uint16 },
                { name: pad,    type: uint4 } ] }
              doc: "Read single conversion result."
            write_config:
              type: write
              frame: { fields: [
                { name: reg_addr, type: uint8 },
                { name: data,     type: uint16 } ] }
              doc: "Write configuration register."

        - cs: flash
          name: nor_flash
          doc: "SPI NOR flash (W25Q128 compatible)."
          commands:
            read_id:    { opcode: 0x9F, response_len: 3,
                          doc: "Read JEDEC manufacturer ID." }
            read_data:  { opcode: 0x03, addr_bytes: 3,
                          doc: "Read data from address." }
            page_prog:  { opcode: 0x02, addr_bytes: 3,
                          max_payload: 256,
                          doc: "Program up to 256-byte page." }
            chip_erase: { opcode: 0xC7,
                          doc: "Erase entire flash chip." }
  ```
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 7j — Interface Description Summary
// ═══════════════════════════════════════════════════════════════════
#page[
  = Interface Description — Summary

  #v(6pt)
  #table(
    columns: (0.8fr, 1fr, 1.2fr, 1.2fr),
    stroke: 0.5pt + surface1,
    inset: 8pt,
    fill: (_, row) => if calc.odd(row) { surface0 } else { rgb("#1e1e2e") },
    table.header(
      [*Transport*], [*Key Section*], [*Addressing*], [*Data Model*],
    ),
    [CANopen],  [`canopen.object dictionary`], [MLX index `0xNNNNNN`], [SDO/PDO + bitfield types],
    [UART],     [`uart.commands`],             [Command ID `0xNN`],    [Request/response frames],
    [RS-485],   [`rs485.modbus.registers`],    [Modbus addr `0xNNNN`], [Holding / input registers],
    [TCP/UDP],  [`tcp.commands` / `udp.messages`], [Message ID `0xNNNN`], [Framed commands / datagrams],
    [I²C],      [`i2c.devices[].registers`],   [Device addr + reg],    [Register read/write],
    [SPI],      [`spi.devices[].transactions`], [CS line + opcode],    [Frame fields / commands],
  )

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === Common structure
      - `interface.title`
      - `transport` discriminator
      - `version history` changelog
      - `physical` pin & electrical config
      - Protocol-specific data model
    ],
    note-box[
      === Code generation targets
      - *C* — register maps, frame packers
      - *Python* — typed driver classes
      - *HTML* — documentation tables
      - *XML* — tool-chain interchange
      - *Batch* — `mp.yaml` orchestration
    ],
  )
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 8 — Tutorial 1: Power Measurement
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 1 — Power Measurement

  #v(6pt)
  ```python
  from pyontrust.instruments import AD3PowerMeter

  meter = AD3PowerMeter(shunt_ohm=0.1)
  meter.open()

  trace = meter.record(duration_s=5.0, rate_hz=1000)
  avg   = sum(s.value for s in trace.samples) / len(trace.samples)
  print(f"Average current: {avg*1e6:.1f} uA")

  meter.close()
  ```

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === What happens
      + `open()` — loads DWF, configures ADC
      + `record()` — streams samples
      + Returns `PowerTrace` dataclass
    ],
    note-box[
      === Typical use-cases
      - Sleep-current profiling
      - TX burst energy calc
      - Battery-life estimation
    ],
  )
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 9 — Tutorial 2: Thermal Camera
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 2 — Thermal Camera

  #v(6pt)
  ```python
  from pyontrust.hal.seek_thermal import SeekThermalDriver

  cam = SeekThermalDriver()
  cam.open()
  frame = cam.grab_frame()          # ThermalFrame
  print(f"Hot-spot: {frame.max_temp:.1f} C")
  cam.close()
  ```

  #v(8pt)
  === Four measurement modes

  #grid(
    columns: (1fr, 1fr),
    gutter: 12pt,
    note-box[
      *Continuous* — stream N frames \
      *Soak* — record until temperature stabilises
    ],
    note-box[
      *Delta* — measure temperature change \
      *Gradient* — spatial gradient across zone
    ],
  )

  #v(8pt)
  #text(fill: peach)[
    The `thermal_measurement` blueprint exposes all four modes via REST
    and the dashboard auto-plots live data.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 10 — Tutorial 3: Lab Bench
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 3 — Lab Bench Definition

  #v(6pt)
  Define your bench in JSON:

  ```json
  {
    "name": "nrf9160dk",
    "instruments": {
      "power": {
        "type": "ad3",
        "shunt_ohm": 0.1,
        "simulated": false
      },
      "thermal": {
        "type": "seek_compact_pro",
        "simulated": true
      }
    }
  }
  ```

  #v(6pt)
  ```python
  from pyontrust.core import LabBench
  bench = LabBench.from_file("benches/nrf9160dk.json")
  bench.open_all()          # opens every instrument
  ```

  #note-box[
    *Simulated mode* lets your CI run the same profiles without hardware.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 11 — Tutorial 4: Dashboard
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 4 — Web Dashboard

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === Shell (landing page)
      - Links to every blueprint
      - System status at a glance
      - Quick-launch buttons
    ],
    note-box[
      === Thermal Dashboard
      - 4 tabs: Measure, Live, Results, Reports
      - Real-time frame display
      - Zone-of-interest selection
    ],
  )

  #v(12pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === FlowLab
      - Drag & drop block editor
      - 90+ blocks in registry
      - One-click code generation
    ],
    note-box[
      === CAN Diagnostics
      - DTC scanner
      - Live frame monitor
      - UDS service calls
    ],
  )

  #v(12pt)
  #text(fill: green)[
    All dashboards are single-page apps served by the Flask gateway.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 12 — Tutorial 5: FlowLab Basics
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 5 — FlowLab Visual Editor

  #v(6pt)
  FlowLab is a *node-graph* editor for test flows:

  #v(6pt)
  ```json
  {
    "blocks": [
      { "id": "b1", "type": "open_instrument",
        "params": { "bench": "nrf9160dk" } },
      { "id": "b2", "type": "power_record",
        "params": { "duration_s": 5, "rate_hz": 1000 } },
      { "id": "b3", "type": "check_limits",
        "params": { "limit_file": "limits/sleep_current.json" } },
      { "id": "b4", "type": "plot_trace",
        "params": { "title": "Sleep Current" } }
    ],
    "edges": [
      ["b1","b2"], ["b2","b3"], ["b2","b4"]
    ]
  }
  ```

  #v(6pt)
  #text(fill: peach)[
    Each block is a Python function — the engine topologically sorts the
    graph and runs blocks in dependency order.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 13 — Tutorial 5b: FlowLab Block Categories
// ═══════════════════════════════════════════════════════════════════
#page[
  = FlowLab — Block Categories

  #v(8pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    gutter: 12pt,
    note-box[
      === Instruments
      `open_instrument`\
      `power_record`\
      `dmm_read`\
      `thermal_grab`
    ],
    note-box[
      === Analysis
      `check_limits`\
      `calc_energy`\
      `thermal_delta`\
      `statistics`
    ],
    note-box[
      === Output
      `plot_trace`\
      `csv_export`\
      `pdf_report`\
      `mqtt_publish`
    ],
  )

  #v(12pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    gutter: 12pt,
    note-box[
      === Flow Control
      `if_else`\
      `loop`\
      `delay`\
      `parallel`
    ],
    note-box[
      === CAN Bus
      `can_open`\
      `can_send`\
      `can_scan_dtc`\
      `can_uds`
    ],
    note-box[
      === Thermal
      `thermal_measure`\
      `thermal_soak`\
      `thermal_delta`\
      `thermal_gradient`
    ],
  )

  #v(8pt)
  #text(fill: green)[90+ blocks — all discoverable via `/flowlab/blocks` API.]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 14 — Tutorial 6: Custom Block
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 6 — Writing a Custom Block

  #v(6pt)
  ```python
  # In flowlab_engine.py — register a new block

  def _blk_voltage_divider(inputs, params, ctx):
      """Calculate divided voltage from two resistor values."""
      v_in = inputs["voltage"]
      r1   = params.get("r1", 10_000)
      r2   = params.get("r2", 10_000)
      v_out = v_in * r2 / (r1 + r2)
      return {"voltage_out": round(v_out, 6)}

  BLOCK_REGISTRY["voltage_divider"] = {
      "fn":          _blk_voltage_divider,
      "label":       "Voltage Divider",
      "category":    "analysis",
      "inputs":      ["voltage"],
      "outputs":     ["voltage_out"],
      "params":      {"r1": 10000, "r2": 10000},
      "description": "Resistive voltage divider calculation",
  }
  ```

  #v(6pt)
  #note-box[
    *Convention* — prefix with `_blk_`, return a dict of named outputs,
    register in `BLOCK_REGISTRY`.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 15 — Tutorial 7: Event Bus
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 7 — Event Bus

  #v(6pt)
  The `EventBus` decouples producers from consumers:

  #v(4pt)
  ```python
  from pyontrust.core.event_bus import EventBus

  bus = EventBus()

  # Subscribe
  bus.subscribe("sample", lambda evt: print(evt))

  # Publish
  bus.publish("sample", {"value": 3.3, "unit": "V"})
  ```

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === Built-in topics
      - `sample` — new measurement
      - `frame` — thermal frame
      - `limit_result` — pass / fail
      - `profile_done` — run finished
    ],
    note-box[
      === Architecture benefit
      - Instruments publish data
      - Recorders subscribe
      - Zero coupling between layers
      - Easy to add new consumers
    ],
  )
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 16 — Tutorial 8: Testing
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 8 — Writing & Running Tests

  #v(6pt)
  ```python
  # tests/power_framework_tests/test_limits.py
  import pytest
  from pyontrust.analysis.limits import check_limits

  def test_sleep_current_pass():
      trace = make_trace(avg_uA=4.2)
      result = check_limits(trace, "limits/sleep_current.json")
      assert result.passed is True

  def test_sleep_current_fail():
      trace = make_trace(avg_uA=150.0)
      result = check_limits(trace, "limits/sleep_current.json")
      assert result.passed is False
  ```

  #v(6pt)
  ```bash
  pytest tests/ -v --tb=short      # 665+ tests, 13 skipped
  ```

  #v(4pt)
  #note-box[
    *Skipped tests* are hardware-dependent — they run only when the real
    instrument is connected. CI always stays green.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 17 — Tutorial 9: Adding a New Driver
// ═══════════════════════════════════════════════════════════════════
#page[
  = Tutorial 9 — Adding a New Driver

  #v(6pt)
  ```python
  # src/pyontrust/hal/my_sensor.py
  from pyontrust.hal.protocols import SensorProtocol

  class MySensorDriver(SensorProtocol):
      def open(self):
          self._dev = connect_usb(vid=0x1234, pid=0x5678)

      def read(self) -> float:
          raw = self._dev.bulk_read(64)
          return _parse_temperature(raw)

      def close(self):
          self._dev.close()
  ```

  #v(6pt)
  === Checklist for a new driver

  + Implement the matching `Protocol`
  + Add a simulated stub for CI
  + Register in `hardware_discovery.py`
  + Write tests (real + simulated)
  + Add a FlowLab block if useful

  #text(fill: peach)[
    Following this pattern guarantees the driver works with every
    existing recorder, analysis module, and FlowLab block.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 18 — End-to-End Workflow
// ═══════════════════════════════════════════════════════════════════
#page[
  = End-to-End Workflow

  #v(8pt)
  ```
  +------------+    +------------+    +------------+    +------------+
  |  Define    |--->|  Record    |--->|  Analyze   |--->|  Report    |
  |  Bench     |    |  Data      |    |  & Check   |    |  Output    |
  +------------+    +------------+    +------------+    +------------+
       |                 |                 |                 |
   bench.json       PowerTrace       LimitResult        PDF + CSV
   instruments      ThermalFrame     statistics          plots
  ```

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === Script mode
      ```python
      bench = LabBench.from_file(...)
      bench.open_all()
      trace = bench["power"].record(5)
      result = check_limits(trace, ...)
      generate_report(result)
      ```
    ],
    note-box[
      === FlowLab mode
      + Open dashboard
      + Drag blocks onto canvas
      + Connect edges
      + Click *Run*
      + Download PDF report
    ],
  )
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 19 — Hardware Compatibility
// ═══════════════════════════════════════════════════════════════════
#page[
  = Hardware Compatibility Matrix

  #v(8pt)
  #table(
    columns: (1.4fr, 1fr, 1fr, 1fr),
    stroke: 0.5pt + surface1,
    inset: 8pt,
    fill: (_, row) => if calc.odd(row) { surface0 } else { rgb("#1e1e2e") },
    table.header(
      [*Instrument*], [*Interface*], [*Driver*], [*Simulated*],
    ),
    [Analog Discovery 3],  [USB],      [`ad3_dwf`],        [Yes],
    [Seek Compact Pro],    [USB],      [`libseek`],        [Yes],
    [PCAN-USB],            [USB/CAN],  [`pcan_basic`],     [Yes],
    [Keithley DMM],        [SCPI],     [`scpi_dmm`],       [Yes],
    [GPIO Expander],       [I2C],      [`gpio_i2c`],       [Yes],
    [Relay Board],         [Serial],   [`relay_serial`],   [Yes],
  )

  #v(8pt)
  #note-box[
    Every driver has a `simulated: true` option. CI test runs never
    require physical hardware.
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 20 — Quick Reference
// ═══════════════════════════════════════════════════════════════════
#page[
  = Quick Reference

  #v(6pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === CLI Commands
      ```bash
      # Start gateway
      python -m pyontrust.gateway.app

      # Run all tests
      pytest tests/ -v

      # Discover hardware
      python scripts/discover_hardware.py

      # Run a profile
      python scripts/run_profile_new.py \
        profiles/sleep_current.json
      ```
    ],
    note-box[
      === REST API Endpoints
      ```
      GET  /               shell
      GET  /diag/status     diagnostics
      GET  /flowlab/        editor
      POST /flowlab/run     execute graph
      GET  /flowlab/blocks  block list
      GET  /thermal/        dashboard
      POST /thermal/measure start meas
      GET  /can/            CAN diag
      POST /bench/run       run profile
      ```
    ],
  )
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 21 — Summary
// ═══════════════════════════════════════════════════════════════════
#page[
  = Summary

  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    note-box[
      === What you learned
      + Project structure & layers
      + Core dataclass models
      + HAL protocol pattern
      + Power & thermal measurement
      + Lab bench orchestration
      + FlowLab visual editor
      + Event bus architecture
      + Writing tests & drivers
    ],
    note-box[
      === Key takeaways
      - *Protocol-based HAL* — swap drivers freely
      - *Simulated stubs* — CI runs without hardware
      - *EventBus* — zero coupling between layers
      - *FlowLab* — no-code test composition
      - *CalVer* — `v2026.3.0`
      - *665+ tests* — full coverage
    ],
  )

  #v(12pt)
  #align(center)[
    #text(size: 18pt, fill: accent)[
      Start with `discover_hardware.py`, build from there.
    ]
  ]
]

// ═══════════════════════════════════════════════════════════════════
//  SLIDE 22 — Thank You
// ═══════════════════════════════════════════════════════════════════
#page[
  #v(1fr)
  #align(center)[
    #text(size: 36pt, weight: "bold", fill: accent)[Thank You]
    #v(12pt)
    #text(size: 16pt, fill: rgb("#cdd6f4"))[
      Questions? Open an issue or check the docs.
    ]
    #v(24pt)
    #slide-rule()
    #v(12pt)
    #text(size: 13pt, fill: surface1)[
      Pyontrust v2026.3.0 | Python 3.10+ | Flask 3.x | 665+ Tests
    ]
  ]
  #v(1fr)
]
