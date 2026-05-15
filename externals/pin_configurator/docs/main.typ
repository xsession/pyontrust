// ─────────────────────────────────────────────────────────────────────────────
// Zephyr Pin Configurator — Enterprise Documentation Suite
// Copyright © 2024–2026 Pyontrust Contributors — Apache-2.0
// ─────────────────────────────────────────────────────────────────────────────

// ── Theme & page setup ──────────────────────────────────────────────────────
#let accent    = rgb("#89b4fa")   // Catppuccin Blue
#let surface   = rgb("#1e1e2e")   // Catppuccin Base
#let subtext   = rgb("#a6adc8")   // Catppuccin Subtext0
#let green     = rgb("#a6e3a1")   // Catppuccin Green
#let red       = rgb("#f38ba8")   // Catppuccin Red
#let yellow    = rgb("#f9e2af")   // Catppuccin Yellow

#set document(
  title: "Zephyr Pin Configurator — Technical Documentation",
  author: ("Pyontrust Contributors",),
  date: datetime(year: 2026, month: 3, day: 4),
)

#set page(
  paper: "a4",
  margin: (top: 3cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(8pt, fill: luma(120))
      Zephyr Pin Configurator #h(1fr) v0.1.0
      #line(length: 100%, stroke: 0.4pt + luma(200))
    ]
  },
  footer: context {
    set text(8pt, fill: luma(120))
    line(length: 100%, stroke: 0.4pt + luma(200))
    v(4pt)
    [Pyontrust — Confidential #h(1fr) Page #counter(page).display("1 / 1", both: true)]
  },
)

#set text(font: "New Computer Modern", size: 10.5pt)
#set par(justify: true, leading: 0.65em)
#set heading(numbering: "1.1.1")

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(1.5em)
  block(text(16pt, weight: "bold", fill: accent, it))
  v(0.6em)
}

#show heading.where(level: 2): it => {
  v(1em)
  block(text(13pt, weight: "bold", it))
  v(0.4em)
}

#show heading.where(level: 3): it => {
  v(0.8em)
  block(text(11pt, weight: "bold", it))
  v(0.3em)
}

// Inline code
#show raw.where(block: false): box.with(
  fill: luma(240),
  inset: (x: 3pt, y: 0pt),
  outset: (y: 3pt),
  radius: 2pt,
)

// Code blocks
#show raw.where(block: true): block.with(
  fill: luma(245),
  inset: 10pt,
  radius: 4pt,
  width: 100%,
)

// ═══════════════════════════════════════════════════════════════════════════════
//  TITLE PAGE
// ═══════════════════════════════════════════════════════════════════════════════

#page(header: none, footer: none)[
  #align(center + horizon)[
    #block(width: 80%)[
      #v(2em)
      #text(32pt, weight: "bold", fill: accent)[Zephyr Pin Configurator]
      #v(0.4em)
      #text(14pt, fill: subtext)[
        Enterprise Technical Documentation
      ]
      #v(2em)
      #line(length: 60%, stroke: 1pt + accent)
      #v(2em)

      #text(11pt)[
        *Version* 0.1.0 \
        *Date* #datetime.today().display("[month repr:long] [day], [year]") \
        *License* Apache-2.0 \
        *Python* ≥ 3.10 \
      ]
      #v(3em)

      #block(
        fill: luma(245),
        inset: 16pt,
        radius: 6pt,
        width: 100%,
      )[
        #set text(9.5pt)
        #set par(justify: false)
        A web-based interactive tool for configuring Zephyr RTOS embedded
        projects — from pin-mux assignment and clock-tree tuning through
        peripheral configuration to production-ready DTS overlay, Kconfig,
        and driver code generation. Supports 18+ MCU vendor families.
      ]
      #v(4em)
      #text(9pt, fill: luma(140))[
        © 2024–2026 Pyontrust Contributors \
        This document is confidential and intended for internal use.
      ]
    ]
  ]
]

// ── Table of contents ───────────────────────────────────────────────────────
#page(header: none)[
  #v(2em)
  #text(18pt, weight: "bold", fill: accent)[Contents]
  #v(1em)
  #outline(indent: 1.5em, depth: 3)
]

// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 1 — INTRODUCTION
// ═══════════════════════════════════════════════════════════════════════════════
= Introduction

== Purpose

The *Zephyr Pin Configurator* (hereafter "the Tool") is a Flask-powered,
browser-based application that streamlines the configuration workflow for
Zephyr RTOS embedded projects. It automates the traditionally manual process
of writing DeviceTree Source (DTS) overlays, Kconfig settings, and driver
scaffold code.

The Tool addresses the following pain-points in embedded development:

- *Pin-mux assignment* — interactive SVG chip diagram instead of referencing
  hundred-page datasheets.
- *Clock-tree configuration* — visual frequency computation with vendor-specific
  PLL / divider models.
- *Peripheral setup* — templated configuration for UART, SPI, I²C, CAN, ADC,
  PWM, GPIO, and more.
- *Driver scaffolding* — one-click generation of Zephyr-compliant sensor,
  GPIO, or custom driver boilerplate.
- *Datasheet parsing* — automatic extraction of pin tables and register maps
  from vendor PDFs.

== Scope

This document covers:

#table(
  columns: (1fr, 3fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Section*], [*Content*],
  [Architecture], [System decomposition, module dependency graph, data flow],
  [Installation], [Prerequisites, virtual-env setup, Docker, west extension],
  [User Guide], [Web UI walkthrough, project file management, CLI usage],
  [API Reference], [All 30+ REST endpoints with request / response schemas],
  [Module Reference], [Every Python module — classes, functions, data types],
  [Configuration], [Clock trees, peripheral templates, module registry],
  [Testing], [Test strategy, fixture catalog, running the suite],
  [Deployment], [Docker, release pipeline, SPDX BOM generation],
  [Security], [Threat model, upload handling, CORS, input validation],
)

== Intended Audience

- Firmware engineers configuring Zephyr RTOS targets
- Embedded platform architects evaluating tooling
- DevOps engineers deploying the Tool in CI/CD pipelines
- QA engineers writing integration tests against the API

== Terminology

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Term*],               [*Definition*],
  [DTS],                  [DeviceTree Source — hardware description language used by Zephyr],
  [Overlay],              [DTS fragment that augments the base board `.dts` file],
  [Kconfig],              [Linux-kernel-style build configuration system],
  [`prj.conf`],           [Per-application Kconfig file in Zephyr projects],
  [PINCM],                [Pin Control Multiplexer (TI-specific register index)],
  [AF],                   [Alternate Function — hardware signal routed to a GPIO pin],
  [West],                 [Zephyr's meta-tool for build, flash, and workspace management],
  [`.zpinproj`],          [Pin Configurator project file (JSON, versioned schema)],
  [BoardDef],             [Internal Python dataclass representing one MCU package / board],
  [`compatible`],         [DTS property string identifying a device driver binding],
)


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 2 — ARCHITECTURE
// ═══════════════════════════════════════════════════════════════════════════════
= Architecture

== High-Level Overview

The application follows a classic *single-page application (SPA) + REST API*
pattern, intentionally kept dependency-light:

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (SPA)                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │  index.html│  │  main.js  │  │  CSS      │              │
│  └─────┬─────┘  └─────┬─────┘  └───────────┘              │
│        │               │                                    │
│        └───────┬───────┘                                    │
│                │  fetch() / JSON                            │
└────────────────┼────────────────────────────────────────────┘
                 │  HTTP  (port 5100)
┌────────────────┼────────────────────────────────────────────┐
│                ▼                                            │
│         ┌─────────────┐    Flask Application (server.py)    │
│         │  26+ Routes │                                     │
│         └──────┬──────┘                                     │
│                │                                            │
│   ┌────────────┼────────────┬──────────────┐               │
│   ▼            ▼            ▼              ▼               │
│ board_schema  dts_generator  pdf_parser   driver_generator  │
│ clock_registry  overlay_parser  sensor_parser               │
│ module_registry  peripheral_registry  package_generator     │
│ datasheet_fetcher  zephyr_kconfig_modules                   │
│                                                             │
│         ┌──────────┐   ┌──────────┐                        │
│         │ boards/* │   │ .uploads │                        │
│         └──────────┘   └──────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

*Key design decisions:*

+ *Zero frontend framework* — vanilla HTML / JS / CSS (≈ 5,800 lines total)
  using the Catppuccin Mocha color palette.
+ *No database* — state lives in-memory (`_PARSED_JOBS`, `_SENSOR_JOBS`,
  `_BOARD_CACHE`) and is persisted via `.zpinproj` project files.
+ *Statically typed core* — all domain models are Python `dataclass` objects
  with explicit fields.
+ *Multi-vendor* — 18+ MCU vendor families supported through pattern-based
  vendor detection and vendor-specific parser pipelines.

== Module Dependency Graph

```
run.py
  └─► server.py  (Flask app factory)
        ├─► board_schema.py          Pin / Board / Peripheral dataclasses
        ├─► dts_generator.py         Overlay + prj.conf generation
        ├─► overlay_parser.py        Reverse-parse overlay → UI state
        ├─► pdf_parser.py            MCU datasheet PDF extraction
        ├─► sensor_parser.py         Sensor datasheet / register map
        ├─► driver_generator.py      Zephyr driver scaffolding
        ├─► package_generator.py     Board .py file generation
        ├─► clock_registry.py        Clock-tree definitions + compute
        ├─► module_registry.py       Zephyr module Kconfig catalog
        ├─► peripheral_registry.py   Peripheral config templates
        ├─► zephyr_kconfig_modules.py  Extended Kconfig definitions
        ├─► datasheet_fetcher.py     Auto-download vendor datasheets
        └─► boards/                  Board definition registry
              └─► boards/__init__.py   BOARDS dict → build_*() functions
```

== Data Flow — Pin Configuration

#figure(
  kind: "diagram",
  supplement: [Diagram],
  caption: [End-to-end pin configuration data flow],
)[
```
User assigns pin AF ──► pinStates{} (JS)
       │
       ▼ POST /api/generate
   { assignments, peripherals, board_name }
       │
       ▼ dts_generator.generate()
   ┌──────────────────┐
   │ PinAssignment[]   │──► &pinctrl { … }
   │ PeripheralConfig[]│──► &uart0 { status = "okay"; }
   └──────────────────┘
       │
       ▼ GeneratedOutput
   { overlay: "…", prj_conf: "…" }
       │
       ▼ Rendered in output tabs
```
]

== Data Flow — Datasheet Parsing

```
User uploads .pdf ──► POST /api/parse-pdf (multipart)
       │
       ▼ pdf_parser.parse_datasheet()
   vendor detection ──► _parse_ti() / _parse_stm32_like() / _parse_generic()
       │
       ▼ DatasheetInfo
   { device, packages[], pin_mux[] }
       │
       ▼ POST /api/generate-package
   package_generator.generate_board_files()
       │
       ▼ boards/<soc>_<package>.py  written to disk
       │
       ▼ _reload_boards()  →  available in /api/boards
```

== Technology Stack

#table(
  columns: (auto, 1fr, auto),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Layer*],      [*Technology*],                    [*Version*],
  [Runtime],      [Python],                          [≥ 3.10],
  [Web server],   [Flask],                           [≥ 3.0],
  [WSGI],         [Werkzeug],                        [≥ 3.0],
  [PDF parsing],  [pdfplumber],                      [≥ 0.10],
  [HTTP client],  [requests],                        [≥ 2.31],
  [Frontend],     [Vanilla HTML / JS / CSS],         [ES2020+],
  [Testing],      [pytest + pytest-cov],             [≥ 8.0 / ≥ 5.0],
  [Lint],         [flake8],                          [≥ 7.0],
  [Container],    [Docker (Python 3.12 slim)],       [—],
  [Zephyr SDK],   [Zephyr SDK],                      [0.17.0],
  [Emulator],     [Renode],                          [1.15.3],
)


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 3 — INSTALLATION & SETUP
// ═══════════════════════════════════════════════════════════════════════════════
= Installation & Setup

== Prerequisites

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Requirement*],  [*Details*],
  [Python],         [3.10 or later (3.12 recommended)],
  [pip],            [Bundled with Python ≥ 3.4],
  [Git],            [For cloning the repository],
  [Browser],        [Any modern browser (Chromium-based recommended)],
)

== Quick Start (pip)

```bash
# Clone the repository
git clone https://github.com/pyontrust/pyontrust.git
cd pyontrust/gui_app/pin_configurator

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows PowerShell

# Install in editable mode
pip install -e .

# Launch
pyontrust --port 5100 --open
```

The `--open` flag automatically opens the web UI in the default browser.

== Installation from Requirements

```bash
pip install -r requirements.txt
python run.py --port 5100
```

== Docker Deployment

The included `Dockerfile` builds a development image with the full Zephyr SDK,
Renode emulator, and Robot Framework pre-installed.

```dockerfile
# Build
docker build -t zephyr-pin-configurator .

# Run
docker run -p 5100:5100 zephyr-pin-configurator
```

The image exposes port `5100` and starts the Flask server on container boot.

=== Docker Image Contents

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Component*],   [*Version*], [*Purpose*],
  [Python],        [3.12],      [Application runtime],
  [Zephyr SDK],    [0.17.0],    [Cross-compilation toolchains],
  [Renode],        [1.15.3],    [Hardware-in-the-loop emulation],
  [west],          [latest],    [Zephyr meta-tool],
  [RobotFramework],[latest],    [Integration test harness],
)

== West Extension

For Zephyr workspaces, the Tool ships as a west command extension:

```yaml
# west-commands.yml
west-commands:
  - file: scripts/west/configure.py
    commands:
      - name: configure
        class: Configure
        help: Launch the Pin Configurator web UI
```

*Registration in `west.yml`:*
```yaml
manifest:
  projects:
    - name: pin-configurator
      url: https://github.com/pyontrust/pyontrust
      path: tools/pin-configurator
      west-commands: gui_app/pin_configurator/scripts/west/west-commands.yml
```

*Usage:*
```bash
west configure --port 5100 --board stm32l476_lqfp64
```

The command auto-detects `ZEPHYR_BASE`, imports the Flask application, and
opens the browser.

== CLI Reference

```
usage: pyontrust [-h] [--port PORT] [--host HOST] [--debug] [--open]

Zephyr Pin Configurator – interactive MCU pin & peripheral config tool

options:
  -h, --help    show this help message and exit
  --port PORT   HTTP port (default: 5100)
  --host HOST   Bind address (default: 127.0.0.1)
  --debug       Enable Flask debug mode with auto-reload
  --open        Open browser automatically on start
```


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 4 — USER GUIDE
// ═══════════════════════════════════════════════════════════════════════════════
= User Guide

== Web Interface Overview

The single-page application is organized into five major regions:

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Region*],           [*Purpose*],
  [Header bar],         [Board selector dropdown, project file load / save buttons],
  [Left panel],         [Peripheral list with toggle switches (enable / disable)],
  [Center panel],       [Interactive SVG chip diagram with clickable pins],
  [Right panel],        [Pin configuration detail — AF selection, bias, drive mode],
  [Bottom output bar],  [Generated `.overlay` and `prj.conf` in tabbed code view],
)

The UI uses the *Catppuccin Mocha* dark theme with syntax highlighting in the
output tabs.

== Workflow: Pin-Mux Configuration

+ *Select a board* — choose from the dropdown in the header bar. The chip
  diagram and peripheral list update immediately.
+ *Enable peripherals* — toggle switches in the left panel activate peripheral
  blocks (e.g., UART0, SPI1, I2C0).
+ *Assign pins* — click a pin on the chip diagram. The right panel shows
  available alternate functions. Select the desired AF.
+ *Configure pin properties* — set bias (pull-up / pull-down), drive mode
  (push-pull / open-drain), and input enable as needed.
+ *Generate output* — the bottom bar auto-updates with the DTS overlay and
  `prj.conf`. Click "Copy" to clipboard or "Save to Project" to write
  files directly to a Zephyr project directory.

== Workflow: Datasheet Import

+ Navigate to the *Datasheet Parser* tab.
+ Upload an MCU datasheet PDF (up to 100 MB).
+ The parser auto-detects the vendor and extracts pin tables.
+ Review the parsed pin-mux data.
+ Click "Generate Board Package" to create a new board definition.
+ The new board appears in the board selector.

Alternatively, use the *MCU Lookup* feature: enter a part number (e.g.,
`STM32L476RGT6`) and the Tool will attempt to download the datasheet from
vendor servers automatically.

== Workflow: Sensor Datasheet Parsing

+ Navigate to the *Sensor Parser* tab.
+ Upload a sensor datasheet PDF.
+ The parser extracts the register map, I²C/SPI addresses, and device
  metadata.
+ Review registers and bit-field definitions.
+ Generate:
  - A C register header (`*_regs.h`)
  - A complete Zephyr sensor driver scaffold

== Workflow: Clock Tree Configuration

+ Select a board with a supported clock tree (STM32, MSPM0, nRF52).
+ Open the *Clock Configuration* panel.
+ Adjust PLL multipliers, dividers, and source selections.
+ Computed frequencies update in real-time.
+ Generate clock DTS overlay and Kconfig entries.

== Workflow: Driver Generation

+ Open the *Driver Generator* tab.
+ Select driver type: `sensor`, `gpio`, `i2c`, `spi`, `uart`, `pwm`, `adc`,
  or `custom`.
+ Fill in metadata: name, compatible string, bus, vendor, registers.
+ Enable optional features: interrupt support, multi-channel, SPI variant.
+ Generate a complete driver package:
  - `<name>.c` — driver source
  - `<name>.h` — public header
  - `Kconfig` — build configuration
  - `CMakeLists.txt` — build system integration
  - Sample overlay and `prj.conf`
  - `README.md` — driver documentation
  - `test_<name>.c` — test skeleton

== Workflow: Module Configuration

+ Open the *Module Configuration* panel.
+ Browse 27 Zephyr subsystem modules (Bluetooth, Networking, USB, etc.).
+ Toggle individual configuration options.
+ Generate `prj.conf` lines for all selected modules.

== Project Files

Project state is persisted as `.zpinproj` files (versioned JSON):

```json
{
  "version": 1,
  "board_id": "stm32l476_lqfp64",
  "pin_states": { "PA5": { "af": 5, "periph": "SPI1" } },
  "periph_states": { "SPI1": true, "UART2": false },
  "generated_overlay": "…",
  "generated_conf": "…"
}
```

- *Save*: `POST /api/project-file/save`
- *Load*: `POST /api/project-file/load`
- Auto-appends `.zpinproj` extension if missing.

== Configuration Import

Existing overlay and `prj.conf` files can be reverse-parsed back into the
UI state:

+ *Import Config*: `POST /api/import-config` with overlay and conf text.
+ *Scan Project*: `POST /api/scan-project` with a Zephyr project directory
  path — auto-discovers `.overlay` and `prj.conf` files.


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 5 — REST API REFERENCE
// ═══════════════════════════════════════════════════════════════════════════════
= REST API Reference

== Overview

All endpoints are served by the Flask application on the configured port
(default `5100`). Responses use `application/json` unless otherwise noted.
Error responses follow the pattern:

```json
{ "error": "<description>" }
```

with appropriate HTTP status codes (`400`, `404`, `500`).

== Board Endpoints

=== `GET /api/boards`

Returns an array of available board identifiers.

*Response:*
```json
{
  "boards": [
    "mspm0g3507",
    "stm32l476_lqfp64",
    "stm32f411_lqfp100"
  ]
}
```

=== `GET /api/board/<name>`

Returns the full board definition for the given board ID.

*Parameters:*
#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Param*], [*Type*],   [*Description*],
  [`name`],  [string],   [Board identifier from `/api/boards`],
)

*Response:* Full `BoardDef` serialized as JSON — includes `soc`, `vendor`,
`package`, `pin_count`, `pins[]` (with `alt_functions[]`), `peripherals[]`,
DTS metadata fields, `flash_size_kb`, `sram_size_kb`, `clock_hz`.

*Errors:* `404` if board not found.

== Generation Endpoints

=== `POST /api/generate`

Generates DTS overlay and `prj.conf` from pin assignments.

*Request body:*
```json
{
  "board": "mspm0g3507",
  "assignments": [
    {
      "pin_name": "PA10",
      "pincm": 21,
      "function_id": 3,
      "af_name": "UART0_TX",
      "peripheral": "UART0",
      "signal": "TX",
      "direction": "out"
    }
  ],
  "peripherals": [
    {
      "name": "UART0",
      "dts_node": "uart0",
      "compatible": "ti,mspm0-uart",
      "enabled": true
    }
  ]
}
```

*Response:*
```json
{
  "overlay": "&pinctrl {\n  uart0_tx_default: uart0_tx_default {\n    …\n  };\n};",
  "prj_conf": "CONFIG_SERIAL=y\nCONFIG_CONSOLE=y"
}
```

=== `POST /api/save-project`

Writes the overlay and `prj.conf` to a Zephyr project directory.

*Request body:*
```json
{
  "project_dir": "/home/user/zephyr-app",
  "board": "stm32l476_lqfp64",
  "overlay": "…",
  "prj_conf": "…"
}
```

=== `POST /api/project-file/save`

Saves the entire editor state to a `.zpinproj` file.

*Request body:*
```json
{
  "path": "/home/user/project.zpinproj",
  "state": {
    "board_id": "stm32l476_lqfp64",
    "pin_states": {},
    "periph_states": {},
    "generated_overlay": "",
    "generated_conf": ""
  }
}
```

=== `POST /api/project-file/load`

Loads a `.zpinproj` file and returns the editor state.

*Request body:*
```json
{ "path": "/home/user/project.zpinproj" }
```

*Response:* The full state object as stored.

== Datasheet Parsing Endpoints

=== `POST /api/parse-pdf`

Uploads and parses an MCU datasheet PDF. Accepts `multipart/form-data`.

*Form fields:*
#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Field*],   [*Type*],   [*Description*],
  [`file`],    [file],     [PDF file (max 100 MB)],
  [`verbose`], [string],   [Optional — `"true"` for debug output],
)

*Response:*
```json
{
  "job_id": "abc123",
  "status": "complete",
  "device": "STM32L476xx",
  "vendor": "stm32",
  "packages": ["LQFP64", "LQFP100", "LQFP144"],
  "pin_count": 64,
  "pin_mux_entries": 128
}
```

=== `POST /api/generate-package`

Generates board `.py` files from parsed PDF data.

*Request body:*
```json
{
  "job_id": "abc123",
  "package": "LQFP64",
  "board": "stm32l476",
  "dts_soc": "st/stm32/stm32l476xx",
  "dts_pinctrl": "st,stm32-pinctrl"
}
```

=== `GET /api/parse-jobs`

Lists all active parse jobs with their status.

=== `GET /api/generated-packages`

Lists all board `.py` files in the `boards/` directory.

== MCU Identification

=== `POST /api/identify-mcu`

Identifies vendor family from a part number string.

*Request body:*
```json
{ "part_number": "STM32L476RGT6" }
```

*Response:*
```json
{
  "vendor": "stm32",
  "vendor_name": "STMicroelectronics",
  "family": "STM32",
  "part_number": "STM32L476RGT6",
  "datasheet_urls": ["https://…"]
}
```

=== `POST /api/fetch-datasheet`

Downloads and parses a datasheet by part number.

*Request body:*
```json
{
  "part_number": "STM32L476RGT6",
  "url": null
}
```

== Module & Kconfig Endpoints

=== `GET /api/modules`

Returns all 27 Zephyr module definitions with their configuration options.

=== `POST /api/generate-module-config`

Generates `prj.conf` content from selected module options.

*Request body:*
```json
{
  "modules": {
    "bluetooth": {
      "CONFIG_BT": true,
      "CONFIG_BT_PERIPHERAL": true
    }
  }
}
```

== Peripheral Configuration Endpoints

=== `GET /api/peripheral-templates`

Returns all 11+ peripheral configuration templates.

=== `GET /api/peripheral-instances/<board>`

Returns board peripherals enriched with matching configuration templates.

=== `POST /api/generate-peripheral-config`

Generates DTS overlay and `prj.conf` from peripheral configuration values.

*Request body:*
```json
{
  "instances": [
    {
      "peripheral": "UART0",
      "template_id": "uart",
      "values": {
        "baudrate": 115200,
        "parity": "none",
        "flow_control": false
      }
    }
  ],
  "board_peripherals": []
}
```

== Clock Configuration Endpoints

=== `GET /api/clock-trees`

Returns a summary list of available clock-tree definitions.

*Response:*
```json
{
  "clock_trees": [
    { "id": "mspm0g3507", "name": "MSPM0G3507", "max_freq_mhz": 80 },
    { "id": "stm32_generic", "name": "STM32 Generic", "max_freq_mhz": 170 },
    { "id": "nrf52", "name": "nRF52", "max_freq_mhz": 64 }
  ]
}
```

=== `GET /api/clock-tree/<id>`

Returns the full clock-tree definition including nodes, connections, and
properties.

=== `POST /api/clock-frequencies`

Computes resulting clock frequencies from user-provided values.

=== `POST /api/generate-clock-config`

Generates clock DTS overlay and `prj.conf` from clock configuration.

== Import & Scan Endpoints

=== `POST /api/import-config`

Parses existing `.overlay` and `prj.conf` text into UI state.

*Request body:*
```json
{
  "overlay": "&pinctrl { … };",
  "conf": "CONFIG_SERIAL=y",
  "board_name": "stm32l476_lqfp64"
}
```

=== `POST /api/scan-project`

Scans a Zephyr project directory for configuration files.

*Request body:*
```json
{ "project_dir": "/home/user/zephyr-app" }
```

== Driver Generation Endpoints

=== `GET /api/driver-templates`

Returns available driver scaffolding templates.

*Response:* Array of driver type objects:
```json
[
  { "type": "sensor", "description": "Zephyr Sensor API driver" },
  { "type": "gpio", "description": "GPIO controller driver" },
  { "type": "custom", "description": "Minimal custom driver" }
]
```

=== `POST /api/generate-driver`

Generates a complete Zephyr driver package.

*Request body:*
```json
{
  "name": "bmp280",
  "driver_type": "sensor",
  "compatible": "bosch,bmp280",
  "bus": "i2c",
  "vendor": "bosch",
  "has_interrupt": false,
  "num_channels": 2,
  "registers": [
    { "name": "CHIP_ID", "address": "0xD0", "size": 1, "rw": "r" },
    { "name": "CTRL_MEAS", "address": "0xF4", "size": 1, "rw": "rw" }
  ]
}
```

*Response:*
```json
{
  "source_c": "…",
  "header_h": "…",
  "kconfig": "…",
  "cmake": "…",
  "overlay_sample": "…",
  "prj_conf_sample": "…",
  "readme": "…",
  "test_c": "…"
}
```

== Sensor Parsing Endpoints

=== `POST /api/parse-sensor-pdf`

Parses a sensor datasheet PDF for register maps and addressing.

=== `GET /api/sensor-jobs`

Lists parsed sensor jobs.

=== `GET /api/sensor-job/<id>`

Returns the full parsed sensor result including register map.

=== `GET /api/sensor-job/<id>/header`

Generates a C register header from parsed sensor data.

=== `POST /api/sensor-job/<id>/driver`

Generates a Zephyr sensor driver from parsed sensor data.

=== `POST /api/identify-sensor`

Identifies sensor vendor from a part number.

*Request body:*
```json
{ "part_number": "BMP280" }
```


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 6 — MODULE REFERENCE
// ═══════════════════════════════════════════════════════════════════════════════
= Module Reference

== `board_schema` — Core Data Model

Defines the fundamental data structures used throughout the application.

=== Enumerations

*`PinKind(str, Enum)`*
#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Value*], [*Description*],
  [`IO`],    [General-purpose I/O pin],
  [`PWR`],   [Power supply pin (VDD, VDDA, etc.)],
  [`GND`],   [Ground pin],
  [`SPEC`],  [Special-function pin (RESET, BOOT, etc.)],
)

*`PinSide(str, Enum)`*
#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Value*],   [*Description*],
  [`LEFT`],    [Left side of chip diagram],
  [`BOTTOM`],  [Bottom side],
  [`RIGHT`],   [Right side],
  [`TOP`],     [Top side],
)

=== Dataclasses

*`AltFunction`*
```python
@dataclass
class AltFunction:
    function_id: int       # AF index (0–15 for STM32, PINCM for TI)
    pincm: int             # Pin Control Multiplexer register index
    name: str              # Display name ("UART0_TX", "SPI1_MOSI")
    peripheral: str        # Parent peripheral ("UART0", "SPI1")
    signal: str            # Signal name ("TX", "MOSI")
    direction: str         # "in", "out", or "inout"
```

*`Pin`*
```python
@dataclass
class Pin:
    number: int            # Physical pin number
    name: str              # Pin name ("PA0", "PB5")
    port: str              # GPIO port ("A", "B")
    gpio_num: int          # GPIO number within port
    kind: PinKind          # IO / PWR / GND / SPEC
    side: PinSide          # Diagram placement
    alt_functions: list[AltFunction]
    selected_af: int | None
    properties: dict       # Additional pin attributes
```

*`Peripheral`*
```python
@dataclass
class Peripheral:
    name: str              # "UART0", "SPI1"
    display: str           # Human-readable name
    compatible: str        # DTS compatible string
    signals: list[str]     # ["TX", "RX", "CTS", "RTS"]
    reg_address: int | None
    dts_node: str          # "uart0", "spi1"
    enabled: bool
```

*`BoardDef`*
```python
@dataclass
class BoardDef:
    soc: str               # "mspm0g3507", "stm32l476xx"
    board: str             # Board name for DTS
    vendor: str            # "ti", "st"
    package: str           # "48QFP", "LQFP64"
    pin_count: int
    pins: list[Pin]
    peripherals: list[Peripheral]
    # DTS metadata
    dts_soc_path: str
    dts_pinctrl_compat: str
    dts_pin_macro_prefix: str
    dts_function_macro_prefix: str
    # Device specifications
    flash_size_kb: int
    sram_size_kb: int
    clock_hz: int
```

=== Functions

#table(
  columns: (1fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*],                [*Returns*],       [*Description*],
  [`save_board(board, path)`], [None],            [Serialize `BoardDef` to JSON file],
  [`load_board(path)`],        [`BoardDef`],      [Deserialize from JSON file],
  [`board_to_frontend(board)`],[`dict`],          [Convert for API response],
)

== `dts_generator` — Overlay Generation

=== Dataclasses

*`PinAssignment`*
```python
@dataclass
class PinAssignment:
    pin_name: str          # "PA10"
    pincm: int             # PINCM register index
    function_id: int       # AF number
    af_name: str           # "UART0_TX"
    peripheral: str        # "UART0"
    signal: str            # "TX"
    direction: str         # "out"
    bias_pull_up: bool     # Enable internal pull-up
    bias_pull_down: bool   # Enable internal pull-down
    drive_open_drain: bool # Open-drain mode
    input_enable: bool     # Enable input buffer
```

*`PeripheralConfig`*
```python
@dataclass
class PeripheralConfig:
    name: str              # "UART0"
    dts_node: str          # "uart0"
    compatible: str        # "ti,mspm0-uart"
    enabled: bool
```

*`GeneratedOutput`*
```python
@dataclass
class GeneratedOutput:
    overlay: str           # Complete DTS overlay text
    prj_conf: str          # Complete prj.conf text
```

=== Functions

#table(
  columns: (2fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Returns*], [*Description*],
  [`generate(assignments, peripherals, board_name)`], [`GeneratedOutput`],
    [Main entry point — produce overlay + prj.conf],
  [`_function_macro(function_id)`], [`str`],
    [Convert AF index to DTS macro name],
  [`_pinctrl_node_name(assignment)`], [`str`],
    [Generate pinctrl node label from assignment],
)

== `pdf_parser` — MCU Datasheet Extraction

=== Dataclasses

*`PinMuxEntry`* — Represents a single pin-mux mapping extracted from a datasheet.

*`PackagePin`* — Physical pin in a specific IC package.

*`PackageInfo`* — Complete pin-out for one package variant.

*`DeviceSummary`* — Extracted device metadata (part number, vendor, core, memory).

*`DatasheetInfo`* — Top-level result aggregating all extracted data.

=== Supported Vendors (18+)

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Vendor*],          [*Families*],
  [Texas Instruments], [MSPM0, MSP430, CC series],
  [STMicroelectronics],[STM32 (all series)],
  [Nordic Semi],       [nRF52, nRF53, nRF91],
  [NXP],               [LPC, i.MX RT, Kinetis],
  [Microchip],         [PIC, SAMx],
  [Espressif],         [ESP32 (all variants)],
  [Infineon],          [PSoC, XMC],
  [Renesas],           [RA, RX, RL78],
  [Silicon Labs],      [EFM32, EFR32],
  [GigaDevice],        [GD32],
  [WCH],               [CH32],
  [Nuvoton],           [M0/M4],
  [Bouffalo Lab],      [BL602, BL70x],
  [HPMicro],           [HPM series],
  [Puya Semi],         [PY32],
  [Artery],            [AT32],
  [MindMotion],        [MM32],
  [Luat (Air)],        [Air series],
)

=== Pipeline

```
parse_datasheet(pdf_path, verbose)
  ├─► vendor detection (_VENDOR_PATTERNS)
  ├─► _parse_ti()           if TI MSPM0
  ├─► _parse_stm32_like()   if STM32/GD32/AT32/PY32
  └─► _parse_generic()      if other vendor
         │
         ▼
      DatasheetInfo { device, packages[], pin_mux[] }
```

== `sensor_parser` — Sensor Datasheet Analysis

=== Dataclasses

*`RegisterField`*
```python
@dataclass
class RegisterField:
    name: str              # "OVERSAMP[2:0]"
    bits: str              # "7:5"
    bit_high: int
    bit_low: int
    access: str            # "rw", "r", "w"
    reset_value: str       # "0b000"
    description: str
```

*`SensorRegister`*
```python
@dataclass
class SensorRegister:
    address: int
    name: str
    size: int              # bytes
    access: str
    reset_value: str
    description: str
    fields: list[RegisterField]

    @property
    def c_name(self) -> str:  # Sanitized C identifier
```

*`RegisterMap`*
```python
@dataclass
class RegisterMap:
    registers: list[SensorRegister]
    address_bits: int      # 8 or 16
    auto_increment: bool

    def by_address(self, addr) -> SensorRegister | None
    def by_name(self, name) -> SensorRegister | None
```

*`SensorAddress`* — I²C/SPI addressing information.

*`SensorSummary`* — Part number, vendor, type, voltage range, temperature range.

*`SensorDatasheetInfo`* — Top-level aggregate with methods:
- `to_c_header()` — full C register header
- `to_zephyr_driver_regs()` — driver register snippet
- `to_json()` / `from_json()` — serialization

=== Register Extraction Strategy (4-phase)

+ *Structured tables* — locate register summary table.
+ *Bit-field detail tables* — standard and Bosch-style layouts.
+ *Pointer-based registers* — TI LM73-style + Bosch BMP/BME calibration.
+ *Text fallback* — regex scan of body text.

== `driver_generator` — Driver Scaffolding

=== Dataclasses

*`DriverSpec`*
```python
@dataclass
class DriverSpec:
    name: str              # "bmp280"
    driver_type: str       # "sensor" | "gpio" | "custom" | …
    compatible: str        # "bosch,bmp280"
    bus: str               # "i2c" | "spi"
    description: str
    vendor: str
    has_interrupt: bool
    num_channels: int
    registers: list[RegisterDef]
    author: str
    year: int
```

*`RegisterDef`* — `name`, `address`, `size`, `rw`.

*`GeneratedDriver`* — All output files as string fields:
`source_c`, `header_h`, `kconfig`, `cmake`, `overlay_sample`,
`prj_conf_sample`, `readme`, `test_c`.

=== Supported Driver Types

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Type*],    [*Description*],
  [`sensor`],  [Full Zephyr Sensor API implementation with `SENSOR_CHAN_*`],
  [`gpio`],    [GPIO controller driver],
  [`i2c`],     [I²C controller driver],
  [`spi`],     [SPI controller driver],
  [`uart`],    [UART / serial driver],
  [`pwm`],     [PWM controller driver],
  [`adc`],     [ADC driver],
  [`custom`],  [Minimal skeleton with `DEVICE_DT_INST_DEFINE`],
)

== `overlay_parser` — Configuration Import

Reverse-parses existing `.overlay` and `prj.conf` files back into the
application's internal state representation.

=== Dataclasses

*`ParsedPinAssignment`*, *`ParsedPeripheral`*, *`ParsedKconfig`*,
*`ImportResult`*.

=== Functions

#table(
  columns: (2fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Returns*], [*Description*],
  [`parse_overlay(text)`], [`(pins, periphs, kconfigs)`],
    [Parse DTS overlay text],
  [`parse_kconfig(text)`], [`list[ParsedKconfig]`],
    [Parse prj.conf text],
  [`parse_import(overlay, conf, board)`], [`ImportResult`],
    [Full import pipeline],
  [`import_result_to_json(result)`], [`dict`],
    [Serialize for API response],
)

== `clock_registry` — Clock Tree Definitions

Provides interactive clock-tree configuration with vendor-specific compute
engines.

=== Supported Clock Trees

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*ID*],              [*MCU*],       [*Max MHz*], [*Features*],
  [`mspm0g3507`],      [TI MSPM0],    [80],        [SYSOSC, LFCLK, MFCLK, ULPCLK],
  [`stm32_generic`],   [STM32],       [170],       [HSI/HSE, PLL (M/N/R), APB1/2 dividers],
  [`nrf52`],           [nRF52],       [64],        [HFCLK, LFCLK, HFXO/LFXO sources],
)

=== Functions

#table(
  columns: (2fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Returns*], [*Description*],
  [`get_all_clock_trees()`], [`list[dict]`], [Summary list of trees],
  [`get_clock_tree(id)`], [`dict | None`], [Full tree definition],
  [`compute_frequencies(id, values)`], [`dict`], [Compute clock outputs],
  [`generate_clock_config(id, values)`], [`dict`],
    [Generate overlay + prj.conf + frequencies],
)

== `peripheral_registry` — Peripheral Templates

=== Templates (11+)

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*ID*],         [*Icon*], [*Configurable Properties*],
  [`uart`],       [📡],    [Baudrate, parity, stop bits, flow control, HW flow ctrl],
  [`spi`],        [🔌],    [Frequency, CPOL, CPHA, bit order, word size],
  [`i2c`],        [🔗],    [Bit rate, address mode (7/10-bit)],
  [`can`],        [🚌],    [Bitrate, sample point, SJW, prop/phase segments],
  [`timer_pwm`],  [⏱],     [Prescaler, period, duty cycle, counter mode],
  [`adc`],        [📊],    [Resolution, reference voltage, sample time, oversampling],
  [`dac`],        [📈],    [Resolution, reference, output buffer],
  [`gpio`],       [🔲],    [Direction, pull, drive strength, interrupt trigger],
  [`comparator`], [⚡],    [Positive/negative input, hysteresis, output polarity],
  [`watchdog`],   [🐕],    [Timeout, window mode, interrupt before reset],
  [`dma`],        [🔄],    [Channel, priority, direction, burst size, FIFO threshold],
)

=== Functions

#table(
  columns: (2fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Returns*], [*Description*],
  [`get_all_peripheral_templates()`], [`list[dict]`], [All templates],
  [`get_peripheral_template(id)`], [`dict | None`], [Single template],
  [`match_template(compatible)`], [`dict | None`], [Match by DTS compatible],
  [`build_peripheral_instances(board)`], [`list[dict]`], [Merge board + templates],
  [`generate_peripheral_config(instances, board)`], [`dict`],
    [Generate DTS overlay + prj.conf],
)

== `module_registry` — Zephyr Module Catalog

Defines 27 Zephyr subsystem modules with a total of ~400 configuration
options.

=== Module List

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Module*],            [*Key Options*],
  [LVGL],                [Widget library, display driver, touch input],
  [Bluetooth],           [Central, Peripheral, Mesh, GATT, L2CAP],
  [Networking],          [IPv4/6, TCP/UDP, MQTT, HTTP, CoAP, LwM2M],
  [USB],                 [Device, CDC-ACM, Mass Storage, HID, DFU],
  [Shell],               [UART/RTT/Telnet backends, history, colors],
  [Logging],             [UART/RTT/SPI Flash backends, filtering, deferred],
  [Settings & NVS],      [NVS, FCB, file backend],
  [File Systems],        [LittleFS, FAT FS, disk access],
  [Power Management],    [System PM, device PM, device idle],
  [Display],             [Display drivers, framebuffer, pixel format],
  [Debug & Analysis],    [Thread analyzer, core dump, CPU load, stack sentinel],
  [Crypto & TLS],        [mbedTLS, PSA, DTLS, certificates],
  [DFU & MCUboot],       [MCUboot, serial recovery, image management],
  [Sensor],              [Sensor subsystem, triggers, IIO],
  [Watchdog],            [Enable, timeout, feed],
  [CAN Bus],             [CAN controller, ISO-TP, CANopen],
  [I²C / SPI / UART],   [Controller drivers, shell integration],
  [ADC / PWM / GPIO],    [Driver enable, shell commands],
  [Flash / Timer / DMA], [Driver enable, page layout, counter],
  [Console],             [UART console, INIT_PRIORITY],
  [Kernel],              [Tick rate, timeslicing, userspace, FPU],
)

== `package_generator` — Board File Generation

Generates Python board definition modules from parsed datasheet data.

=== Functions

#table(
  columns: (2fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Returns*], [*Description*],
  [`generate_board_file(device, package, …)`], [`str`],
    [Generate Python source for one board],
  [`generate_board_files(info, output_dir, …)`], [`list[str]`],
    [Generate for all packages, return file paths],
  [`_update_init(boards_dir, soc, packages)`], [None],
    [Update `boards/__init__.py` with new imports],
)

== `datasheet_fetcher` — Auto-Download

=== Vendor URL Patterns

Supports automatic datasheet URL construction for: TI, STM32, Nordic, NXP,
Microchip, Espressif, Infineon, Renesas.

=== Functions

#table(
  columns: (2fr, 1fr, 2fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Returns*], [*Description*],
  [`identify_vendor(part_number)`], [`VendorMatch | None`],
    [Identify vendor from part number string],
  [`download_datasheet(part, dir, url)`], [`(path | None, msg)`],
    [Download PDF to directory],
  [`fetch_and_parse(part, dir, url)`], [`(info | None, msg)`],
    [Download + parse in one step],
)


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 7 — BOARD DEFINITIONS
// ═══════════════════════════════════════════════════════════════════════════════
= Board Definitions

== Board Registry

Board definitions live in `boards/` as Python modules, each exporting a
`build_*()` function that returns a `BoardDef` instance.

=== Registry (`boards/__init__.py`)

```python
BOARDS: dict[str, Callable[[], BoardDef]] = {
    "mspm0g3507":            build_mspm0g3507_48qfp,
    "stm32l476_lqfp64":     build_stm32l476_lqfp64,
    "stm32l476_wlcsp72":    build_stm32l476_wlcsp72,
    "stm32l476_wlcsp81":    build_stm32l476_wlcsp81,
    "stm32l476_lqfp100":    build_stm32l476_lqfp100,
    "stm32l476_ufbga132":   build_stm32l476_ufbga132,
    "stm32l476_lqfp144":    build_stm32l476_lqfp144,
    "stm32l476_ufbga144":   build_stm32l476_ufbga144,
    "stm32f411_ufqfpn48":   build_stm32f411_ufqfpn48,
    "stm32f411_wlcsp49":    build_stm32f411_wlcsp49,
    "stm32f411_lqfp64":     build_stm32f411_lqfp64,
    "stm32f411_lqfp100":    build_stm32f411_lqfp100,
    "stm32f411_ufbga100":   build_stm32f411_ufbga100,
}
```

== Adding a Board Manually

+ Create `boards/<soc>_<package>.py`.
+ Define a `build_<soc>_<package>()` function returning `BoardDef`.
+ Use helper constructors for pins: `_io()`, `_pwr()`, `_gnd()`, `_spec()`.
+ Register in `boards/__init__.py`.

== Auto-Generating Boards from PDFs

Use the `generate_package.py` CLI:

```bash
python generate_package.py datasheet.pdf \
  --output boards/ \
  --board stm32l476 \
  --dts-soc "st/stm32/stm32l476xx" \
  --dts-pinctrl "st,stm32-pinctrl"
```

Or via the web UI: upload the PDF, select a package, and click "Generate".


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 8 — TESTING
// ═══════════════════════════════════════════════════════════════════════════════
= Testing

== Test Strategy

The project uses a three-tier test strategy:

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Tier*],       [*Marker*],       [*Description*],
  [Unit],         [_(default)_],    [Pure-function tests, data model construction, offline parsing],
  [Integration],  [`integration`],  [Flask test client API tests, end-to-end workflow],
  [Slow],         [`slow`],         [PDF parsing with real datasheets, network calls],
)

== Running Tests

```bash
# All tests
pytest

# Unit tests only (exclude integration + slow)
pytest -m "not integration and not slow"

# With coverage
pytest --cov=. --cov-report=html

# Specific module
pytest tests/test_driver_gen.py -v
```

== Compile-backed Zephyr Validation

The generated Zephyr export path is validated by
`tests/test_zephyr_codegen.py`.

This module combines:

- detailed assertions for generated `app.overlay` and `prj.conf`
- a real `west build` for `lp_mspm0g3507` using the demo app in
  `demo/zephyr_compile_demo`

For local execution, use the shared PowerShell helper:

```powershell
pwsh -File scripts/run_zephyr_codegen_tests.ps1 `
  -Workspace C:/path/to/west/workspace `
  -Python312Path C:/Python312/python.exe
```

The helper provisions the configurator test venv, creates a dedicated Python
3.12 Zephyr venv, exports the required environment variables, and runs the
requested pytest arguments.

CI uses the same entrypoint through the `pin-configurator-zephyr-codegen` job
in `.github/workflows/test.yml`, together with the self-contained west manifest
at `demo/zephyr_ci_workspace/west.yml`.

== Test Fixtures (`conftest.py`)

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Fixture*], [*Scope*], [*Description*],
  [`app`], [session], [Flask app in `TESTING` mode],
  [`client`], [session], [Flask test client],
  [`sample_uart_assignments`], [function], [UART0 TX+RX pin assignments for MSPM0G3507],
  [`sample_multi_peripheral_assignments`], [function], [UART0 + I2C0 + GPIO assignments],
  [`sample_overlay_text`], [function], [DTS overlay with `&pinctrl` and `&uart0`],
  [`sample_conf_text`], [function], [`prj.conf` with SERIAL + CONSOLE + GPIO],
)

== Test Modules

=== `test_api.py` (8 classes)

- `TestBoardEndpoints` — board list, detail, 404 handling
- `TestGenerateEndpoints` — UART overlay, multi-peripheral generation
- `TestImportEndpoints` — conf-only and overlay+conf import
- `TestMcuIdentification` — parametrized vendor detection
- `TestModuleEndpoints` — module list and config generation
- `TestPeripheralEndpoints` — template list, board instances
- `TestClockEndpoints` — clock tree listing
- `TestProjectFileEndpoints` — save/load `.zpinproj`, round-trip, error cases

=== `test_driver_gen.py` (7+ classes)

- `TestDriverSpec` — construction, JSON round-trip
- `TestSensorDriverGeneration` — `DT_DRV_COMPAT`, API functions, init,
  registers, bus helpers, logging, SPI variant, IRQ handler
- `TestCustomDriverGeneration` — custom skeleton validation
- `TestKconfig` — sensor Kconfig, SPI dependency
- `TestCMake` — conditional compilation
- `TestOverlaySample` — I2C/SPI overlay samples
- Additional tests for readme, test skeleton, `driver_to_json`

=== `test_overlay.py`

- `TestOverlayParser` — empty input, conf-only, pinctrl parsing, peripheral
  status, multi-peripheral round-trip

=== `test_zephyr_codegen.py`

- `TestZephyrGeneratedArtifacts` — verifies pinctrl labels, pin properties,
  external device nodes, and `prj.conf` symbol generation
- `test_generated_zephyr_artifacts_compile_for_mspm0_board` — writes generated
  Zephyr artifacts into the demo app and validates them with a real
  `west build`

=== `test_pdf_parser.py`

- `TestDataModels` — all dataclass constructors
- `TestVendorDetection` — parametrized (STM32, TI, Nordic, ESP32, Microchip)

=== `test_sensor_parser.py` (600+ lines)

- `TestDataModels` — all sensor model classes, `c_name` normalization
- `TestHelpers` — `_norm_access()`, `_parse_hex()` parametrized
- `TestVendorDetection` — 17 parametrized sensor parts
- `TestSensorTypeDetection` — classification tests
- JSON round-trip, C header generation, register defines


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 9 — DEPLOYMENT & RELEASE
// ═══════════════════════════════════════════════════════════════════════════════
= Deployment & Release

== Docker Deployment

=== Building the Image

```bash
docker build -t zephyr-pin-configurator .
```

The `Dockerfile` is a multi-concern image:

+ *Base*: `python:3.12-slim`
+ *System packages*: `git`, `cmake`, `ninja-build`, `wget`, `xz-utils`
+ *Zephyr SDK 0.17.0*: Cross-compilation toolchains for all supported architectures
+ *Renode 1.15.3*: Hardware-in-the-loop emulation
+ *West + RobotFramework*: Build and integration test tooling
+ *Application*: Pin Configurator + all dependencies

=== Running

```bash
# Basic
docker run -p 5100:5100 zephyr-pin-configurator

# With project directory mounted
docker run -p 5100:5100 \
  -v /path/to/project:/workspace \
  zephyr-pin-configurator

# With environment overrides
docker run -p 5100:5100 \
  -e ZEPHYR_BASE=/opt/zephyr \
  zephyr-pin-configurator
```

== Release Pipeline (`scripts/release.py`)

The release script produces a versioned archive with SPDX Bill of Materials:

```bash
python scripts/release.py \
  --board nucleo_l476rg \
  --source /path/to/zephyr-app \
  --output-dir ./releases
```

=== Pipeline Steps

+ Read `VERSION` file
+ Run `git describe --tags --dirty`
+ Initialize SPDX document
+ Execute `west build` (unless `--skip-build`)
+ Generate SPDX BOM (unless `--skip-spdx`)
+ Create `.tar.gz` archive containing:
  - Compiled firmware binary
  - `.config` build configuration
  - SPDX BOM documents
  - `VERSION` file

=== Archive Structure

```
release-v0.1.0-abc1234/
├── firmware.bin
├── firmware.elf
├── .config
├── VERSION
└── spdx/
    ├── app.spdx
    └── zephyr.spdx
```

== Production Considerations

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Concern*],         [*Recommendation*],
  [WSGI server],       [Deploy behind Gunicorn or uWSGI instead of Flask dev server],
  [Reverse proxy],     [Use nginx/Caddy for TLS termination and static file serving],
  [File uploads],      [Configure `MAX_CONTENT_LENGTH` (default 100 MB)],
  [Persistence],       [Mount `.uploads/` and `boards/` as Docker volumes],
  [Monitoring],        [Expose `/health` endpoint; instrument with Prometheus],
  [Scaling],           [Stateless design enables horizontal scaling behind LB],
)


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 10 — SECURITY CONSIDERATIONS
// ═══════════════════════════════════════════════════════════════════════════════
= Security Considerations

== Threat Model

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Threat*],                   [*Severity*], [*Mitigation*],
  [Malicious PDF upload],       [High],
    [File size limit (100 MB); pdfplumber sandboxed parsing; no shell exec],
  [Path traversal (project save)],[High],
    [Validate and normalize paths; reject `..` sequences],
  [Denial of service],          [Medium],
    [Upload size limit; job timeouts; rate limiting via reverse proxy],
  [Cross-site scripting (XSS)], [Medium],
    [JSON API responses; no user HTML rendering; CSP headers recommended],
  [Sensitive data exposure],    [Low],
    [Bind to `127.0.0.1` by default; no authentication (local tool)],
  [Dependency vulnerabilities], [Medium],
    [Pin dependency versions; regular `pip audit` scans],
)

== Input Validation

- All API endpoints validate required fields and return `400` with descriptive
  error messages.
- PDF uploads are restricted by content length and stored in isolated
  `.uploads/` directory.
- Part number inputs are sanitized before use in URL construction.
- File paths for project save/load are normalized via `os.path.realpath()`.

== Recommended Hardening

+ Deploy behind a reverse proxy with TLS (HTTPS).
+ Enable CORS restrictions (`flask-cors` with explicit origins).
+ Add rate limiting (`flask-limiter`).
+ Set Content Security Policy headers.
+ Run container as non-root user.
+ Mount `.uploads/` on tmpfs or size-limited volume.


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 11 — CONFIGURATION REFERENCE
// ═══════════════════════════════════════════════════════════════════════════════
= Configuration Reference

== Environment Variables

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Variable*],      [*Default*],       [*Description*],
  [`FLASK_ENV`],     [`production`],    [Set to `development` for debug mode],
  [`ZEPHYR_BASE`],   [_(auto)_],        [Path to Zephyr RTOS source tree],
  [`PORT`],          [`5100`],          [HTTP listen port (overridden by CLI `--port`)],
)

== CLI Arguments

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Flag*],     [*Type*],   [*Default*],      [*Description*],
  [`--port`],   [int],      [5100],           [HTTP listen port],
  [`--host`],   [string],   [127.0.0.1],      [Bind address],
  [`--debug`],  [flag],     [false],          [Flask debug mode with auto-reload],
  [`--open`],   [flag],     [false],          [Open browser on start],
)

== `pyproject.toml` — Build Configuration

```toml
[project]
name = "pyontrust-pin-configurator"
version = "0.1.0"
requires-python = ">=3.10"
license = "Apache-2.0"

[project.scripts]
pyontrust = "run:main"

[tool.pytest.ini_options]
markers = [
    "integration: marks integration tests",
    "slow: marks slow tests (PDF parsing, network)",
]

[tool.flake8]
max-line-length = 120

[tool.coverage.run]
omit = ["tests/*", ".venv/*"]
```

== Project File Schema (`.zpinproj`)

```json
{
  "version": 1,
  "board_id": "<board identifier>",
  "pin_states": {
    "<pin_name>": {
      "af": "<AF index>",
      "periph": "<peripheral name>"
    }
  },
  "periph_states": {
    "<peripheral name>": true | false
  },
  "generated_overlay": "<DTS overlay text>",
  "generated_conf": "<prj.conf text>"
}
```


// ═══════════════════════════════════════════════════════════════════════════════
//  CHAPTER 12 — TROUBLESHOOTING
// ═══════════════════════════════════════════════════════════════════════════════
= Troubleshooting

== Common Issues

=== Port Already in Use

```
OSError: [Errno 98] Address already in use
```

*Solution:* Use a different port: `pyontrust --port 5200`

=== PDF Parsing Fails

```json
{ "error": "No vendor detected in PDF" }
```

*Causes:*
- The datasheet is a non-supported vendor.
- The PDF is scanned (image-only) — pdfplumber requires text-layer PDFs.
- The PDF is encrypted or DRM-protected.

*Solution:* Use OCR tools first, or manually create a board definition.

=== Board Not Appearing After Generation

*Solution:* The server caches boards on startup. Either:
- Restart the server, or
- The `/api/generate-package` endpoint calls `_reload_boards()` automatically.

=== Docker Build Fails (Zephyr SDK Download)

*Cause:* Network issues downloading the SDK tarball.

*Solution:* Pre-download the SDK and use a local `COPY` in the Dockerfile.

=== West Extension Not Found

*Cause:* `west-commands.yml` not registered in `west.yml`.

*Solution:* Add the project entry to your workspace manifest.

== Logging

Enable Flask debug mode for verbose request logging:

```bash
pyontrust --debug
```

Or set the environment variable:

```bash
export FLASK_ENV=development
```


// ═══════════════════════════════════════════════════════════════════════════════
//  APPENDIX A — ENDPOINT QUICK REFERENCE
// ═══════════════════════════════════════════════════════════════════════════════
= Appendix A — Endpoint Quick Reference
<appendix-endpoints>

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 6pt,
  [*Method*], [*Route*], [*Purpose*],
  [`GET`],  [`/`],                              [Serve web UI],
  [`GET`],  [`/api/boards`],                    [List available boards],
  [`GET`],  [`/api/board/<name>`],              [Full board definition],
  [`POST`], [`/api/generate`],                  [Generate overlay + prj.conf],
  [`POST`], [`/api/save-project`],              [Write config to Zephyr project],
  [`POST`], [`/api/project-file/save`],         [Save .zpinproj],
  [`POST`], [`/api/project-file/load`],         [Load .zpinproj],
  [`POST`], [`/api/parse-pdf`],                 [Upload + parse MCU PDF],
  [`POST`], [`/api/generate-package`],          [Generate board .py],
  [`GET`],  [`/api/generated-packages`],        [List generated board files],
  [`GET`],  [`/api/parse-jobs`],                [List active parse jobs],
  [`GET`],  [`/api/modules`],                   [List Zephyr modules],
  [`POST`], [`/api/generate-module-config`],    [Generate module prj.conf],
  [`GET`],  [`/api/peripheral-templates`],      [List peripheral templates],
  [`GET`],  [`/api/peripheral-instances/<b>`],   [Board peripheral instances],
  [`POST`], [`/api/generate-peripheral-config`],[Generate peripheral DTS],
  [`GET`],  [`/api/clock-trees`],               [List clock trees],
  [`GET`],  [`/api/clock-tree/<id>`],           [Full clock tree definition],
  [`POST`], [`/api/clock-frequencies`],         [Compute clock frequencies],
  [`POST`], [`/api/generate-clock-config`],     [Generate clock DTS + conf],
  [`POST`], [`/api/import-config`],             [Import existing overlay/conf],
  [`POST`], [`/api/scan-project`],              [Scan project directory],
  [`POST`], [`/api/identify-mcu`],              [Identify MCU vendor],
  [`POST`], [`/api/fetch-datasheet`],           [Download + parse datasheet],
  [`GET`],  [`/api/driver-templates`],          [List driver templates],
  [`POST`], [`/api/generate-driver`],           [Generate driver package],
  [`POST`], [`/api/parse-sensor-pdf`],          [Parse sensor datasheet],
  [`GET`],  [`/api/sensor-jobs`],               [List sensor parse jobs],
  [`GET`],  [`/api/sensor-job/<id>`],           [Full sensor parse result],
  [`GET`],  [`/api/sensor-job/<id>/header`],    [Generate C register header],
  [`POST`], [`/api/sensor-job/<id>/driver`],    [Generate sensor driver],
  [`POST`], [`/api/identify-sensor`],           [Identify sensor vendor],
)


// ═══════════════════════════════════════════════════════════════════════════════
//  APPENDIX B — FILE STRUCTURE
// ═══════════════════════════════════════════════════════════════════════════════
= Appendix B — Project File Structure
<appendix-structure>

```
pin_configurator/
├── run.py                    CLI entry point
├── server.py                 Flask application (26+ routes)
├── board_schema.py           Core data model (Pin, BoardDef, etc.)
├── dts_generator.py          DTS overlay + prj.conf generation
├── overlay_parser.py         Reverse-parse overlay → UI state
├── pdf_parser.py             MCU datasheet PDF parser (18+ vendors)
├── sensor_parser.py          Sensor datasheet / register map parser
├── driver_generator.py       Zephyr driver scaffolding generator
├── package_generator.py      Board .py file generator
├── clock_registry.py         Clock-tree definitions + compute
├── module_registry.py        Zephyr module Kconfig catalog
├── peripheral_registry.py    Peripheral configuration templates
├── zephyr_kconfig_modules.py Extended Kconfig definitions
├── datasheet_fetcher.py      Auto-download vendor datasheets
├── generate_package.py       CLI for PDF → board .py
├── pyproject.toml            PEP 621 project metadata
├── requirements.txt          pip dependencies
├── Dockerfile                Dev Docker image
├── VERSION                   Semantic version (0.1.0)
├── README.md                 Project documentation
│
├── boards/                   Board definition registry
│   ├── __init__.py           BOARDS dict → build_*() functions
│   ├── mspm0g3507_48qfp.py  TI MSPM0G3507 48-pin QFP
│   ├── stm32f411_*.py        STM32F411 (5 packages)
│   └── stm32l476_*.py        STM32L476 (7 packages)
│
├── web/                      Frontend SPA
│   ├── index.html            2074-line single-page application
│   └── main.js               3753-line vanilla JavaScript
│
├── tests/                    Test suite
│   ├── conftest.py           Pytest fixtures
│   ├── test_api.py           API endpoint tests
│   ├── test_driver_gen.py    Driver generator tests
│   ├── test_overlay.py       Overlay parser tests
│   ├── test_pdf_parser.py    PDF parser tests
│   └── test_sensor_parser.py Sensor parser tests
│
├── scripts/
│   ├── release.py            Release archive + SPDX BOM
│   └── west/
│       ├── configure.py      West extension command
│       └── west-commands.yml West registration
│
├── example/
│   └── kecske.zpinproj       Example project file
│
└── .uploads/                 Temporary PDF upload directory
```


// ═══════════════════════════════════════════════════════════════════════════════
//  APPENDIX C — CHANGELOG
// ═══════════════════════════════════════════════════════════════════════════════
= Appendix C — Changelog
<appendix-changelog>

== v0.1.0 — Initial Release

*Date:* 2026-03-04

=== Features

- Interactive SVG chip diagram with clickable pin assignment
- DTS overlay and `prj.conf` generation
- Support for 13 board definitions (MSPM0G3507, STM32L476, STM32F411)
- Multi-vendor MCU datasheet PDF parser (18+ vendors)
- Sensor datasheet register map extraction
- Zephyr driver scaffolding generator (8 driver types)
- Clock-tree configuration (TI, STM32, nRF52)
- 27 Zephyr module Kconfig templates
- 11+ peripheral configuration templates
- Project file save/load (`.zpinproj`)
- Configuration import from existing overlay/prj.conf
- MCU vendor auto-identification and datasheet download
- West extension: `west configure`
- Docker deployment image with Zephyr SDK + Renode
- Release pipeline with SPDX BOM generation

=== Known Limitations

- PDF parser requires text-layer PDFs (no OCR fallback)
- Clock-tree support limited to 3 vendor families
- No authentication or multi-user support (local tool)
- Frontend is vanilla JS — no component framework


// ═══════════════════════════════════════════════════════════════════════════════
//  APPENDIX D — LICENSE
// ═══════════════════════════════════════════════════════════════════════════════
= Appendix D — License
<appendix-license>

This project is licensed under the *Apache License, Version 2.0*.

```
Copyright 2024–2026 Pyontrust Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
