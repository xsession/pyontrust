# Zephyr Pin Configurator (Pyontrust)

> **A comprehensive web-based configuration tool for Zephyr RTOS embedded projects.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Overview

Pyontrust Pin Configurator is a Flask-powered web application that provides an
interactive GUI for configuring embedded projects. It covers the full
embedded workflow — from parsing MCU datasheets to generating production-ready
Zephyr overlays and Kconfig fragments, plus starter Arduino and bare-metal pin
configuration files.

![Architecture](docs/img/architecture.png)

### Key Features

| Feature | Description |
|---------|-------------|
| **Pin Configurator** | Interactive chip diagram with drag-and-drop pin assignment |
| **Multi-target Export** | Generate Zephyr, Arduino, and bare-metal pin configuration outputs |
| **Package Manager** | Parse MCU datasheet PDFs (18+ vendor families), auto-download by part number |
| **Module Configurator** | Browse & enable 27 Zephyr Kconfig modules (399 options) |
| **Peripheral Configurator** | 11 peripheral templates, 22 instances with DTS generation |
| **Clock Configurator** | Visual clock-tree editor for MSPM0 / STM32 / nRF52 |
| **Overlay Import** | Import existing `.overlay` / `prj.conf` / scan Zephyr projects |
| **Driver Generator** | Scaffold complete Zephyr driver boilerplate from templates |
| **Renode Testbench** | Simulate generated firmware in Renode with RobotFramework |

### Supported MCU Vendors

TI · STMicroelectronics · Nordic Semiconductor · NXP · Microchip · Espressif ·
Infineon · Renesas · Silicon Labs · GigaDevice · WCH · Nuvoton · Bouffalo Lab ·
HPMicro · Puya · Artery · MindMotion · Luat

The built-in board registry now also includes a dual-core RP2040 target for
the Raspberry Pi Pico, exposing CPU-core metadata and export-target metadata to
both the Python and TypeScript backends.

---

## Quick Start

### Prerequisites

- Python ≥ 3.10
- [Zephyr SDK](https://docs.zephyrproject.org/latest/develop/getting_started/)
  (for west + toolchain)
- Renode ≥ 1.15 (optional, for simulation)

### Installation

```bash
# Clone and enter the project
cd pyontrust/gui_app/pin_configurator

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Launch the configurator
python run.py
# → Open http://localhost:5100 in your browser
```

### Using the West Extension (optional)

If you are inside a Zephyr west workspace, you can register the configurator as
a west command:

```bash
# From your west workspace root
west configure          # launch the GUI
west configure --port 5200  # custom port
west configure --headless   # API-only mode (no browser)
```

See [West Extension](#west-extension) below for setup instructions.

### Using the VS Code Extension (TypeScript backend)

The repository also includes a VS Code extension wrapper around the TypeScript backend:

```bash
cd vscode-extension
npm install
npm run package:vsix
```

The packaged extension starts `backend_ts/dist/server_entry.js` and hosts the Pin Configurator UI directly inside VS Code.

---

## Architecture

```
pin_configurator/
├── server.py               # Flask backend — 22 REST endpoints
├── run.py                  # CLI launcher with argument parsing
├── board_schema.py         # Data classes: Pin, Peripheral, BoardDef
├── dts_generator.py        # DTS overlay & prj.conf generation
├── overlay_parser.py       # Import existing overlay/conf files
├── pdf_parser.py           # Multi-vendor MCU datasheet parser
├── package_generator.py    # Generate board .py from parsed data
├── datasheet_fetcher.py    # Auto-download datasheets by part number
├── module_registry.py      # Zephyr Kconfig module definitions
├── peripheral_registry.py  # Peripheral templates & DTS codegen
├── clock_registry.py       # Clock-tree definitions & frequency calc
├── driver_generator.py     # Zephyr driver boilerplate scaffolding
├── boards/                 # Board definition packages
│   ├── __init__.py         # Board registry
│   └── mspm0g3507_48qfp.py
├── web/                    # Frontend (served as static files)
│   ├── index.html          # Single-page app (dark theme)
│   └── main.js             # Vanilla JS — no framework dependencies
├── testbench/              # Renode simulation testbenches
│   └── CMakeLists.txt      # Build targets: testbench, robotbench
├── scripts/                # Automation & west extensions
│   ├── west/               # Custom west commands
│   │   └── configure.py    # `west configure` command
│   └── release.py          # Release archive + SPDX generation
├── tests/                  # Test suite (pytest)
│   ├── conftest.py         # Fixtures: Flask test client, sample data
│   ├── test_api.py         # API endpoint smoke tests
│   ├── test_pdf_parser.py  # PDF parser unit tests
│   ├── test_overlay.py     # Overlay import/export round-trip
│   └── test_driver_gen.py  # Driver generator output validation
├── Dockerfile              # Reproducible dev environment
├── requirements.txt        # Python dependencies
├── pyproject.toml          # PEP 621 project metadata
└── VERSION                 # Semantic version file
```

### Design Principles (inspired by [Swedish Embedded SDK](https://github.com/swedishembedded/sdk))

1. **West-native integration** — The tool registers as a west extension command,
   fitting naturally into the Zephyr workflow (like SE-SDK's `west simulate`).

2. **Testbench-driven development** — Renode simulation testbenches can be
   generated alongside firmware, with CMake targets for interactive
   (`testbench`) and automated (`robotbench`) testing.

3. **Multi-level testing** — Unit tests (pytest + mocks), integration tests
   (Flask test client), and system tests (RobotFramework + Renode).

4. **SPDX compliance** — All source files carry SPDX license headers. Release
   archives include SPDX BOMs via `west spdx`.

5. **Reproducible environments** — Docker image and `requirements.txt` ensure
   identical builds across machines.

6. **Driver scaffolding** — Like SE-SDK's example driver pattern
   (`DT_DRV_COMPAT`, `DEVICE_DT_INST_DEFINE`), the tool can generate complete
   Zephyr driver boilerplate.

---

## API Reference

### Board & Pin Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/boards` | List available board packages |
| `GET`  | `/api/board/<name>` | Get full board definition |
| `POST` | `/api/generate` | Generate Zephyr, Arduino, and bare-metal output files |
| `POST` | `/api/save-project` | Write generated files to disk |

### Package Manager

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/parse-pdf` | Upload & parse MCU datasheet PDF |
| `POST` | `/api/generate-package` | Generate board `.py` from parse results |
| `POST` | `/api/identify-mcu` | Identify MCU vendor from part number |
| `POST` | `/api/fetch-datasheet` | Auto-download & parse datasheet |

### Module Configurator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/module-defs` | List all Zephyr module definitions |
| `POST` | `/api/generate-module-conf` | Generate prj.conf from module picks |

### Peripheral Configurator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/peripheral-templates` | List peripheral config templates |
| `GET`  | `/api/peripheral-instances/<board>` | Get instances for a board |
| `POST` | `/api/generate-peripheral` | Generate peripheral DTS config |

### Clock Configurator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/clock-trees` | List available clock trees |
| `GET`  | `/api/clock-tree/<name>` | Get specific clock tree |
| `POST` | `/api/calculate-clocks` | Compute frequencies from settings |
| `POST` | `/api/generate-clock-config` | Generate clock DTS config |

### Import & Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/import-overlay` | Import overlay + conf text |
| `POST` | `/api/scan-project` | Scan Zephyr project directory |

### Driver Generator

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/driver-templates` | List driver scaffolding templates |
| `POST` | `/api/generate-driver` | Generate Zephyr driver boilerplate |

---

## West Extension

Register the configurator as a custom west command by adding to your workspace
`west.yml`:

```yaml
manifest:
  self:
    west-commands: pyontrust/gui_app/pin_configurator/scripts/west/west-commands.yml
```

Then create `scripts/west/west-commands.yml`:

```yaml
west-commands:
  - file: scripts/west/configure.py
    commands:
      - name: configure
        class: Configure
        help: Launch the Pyontrust pin configurator GUI
```

Usage:

```bash
west configure                     # Open GUI in browser
west configure --port 5200         # Custom port
west configure --headless          # API-only, no browser
west configure --board lp_mspm0g3507  # Pre-select board
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run only unit tests (no server required)
pytest tests/ -m "not integration" -v

# Run integration tests (requires running server)
pytest tests/ -m integration -v
```

---

## Simulation / Testbench

The tool can generate Renode testbench files alongside your firmware. Inspired
by the Swedish Embedded SDK testbench architecture:

```bash
# Build firmware
west build -p -b lp_mspm0g3507 .

# Run interactive testbench (Renode GUI)
west build -t testbench

# Run automated tests (RobotFramework + Renode)
west build -t robotbench

# Run board-level simulation
west build -t boardbench
```

---

## Release

```bash
# Generate a release archive with SPDX BOM
python scripts/release.py --board lp_mspm0g3507 --source apps/locator_base

# Output: release/<name>-<board>-<version>.tar.gz
#   Contains: zephyr.elf, .config, spdx/
```

---

## Docker

```bash
# Build the dev image
docker build -t pyontrust:latest .

# Run with USB passthrough (for flashing)
docker run -ti --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  -p 5100:5100 \
  pyontrust:latest

# Inside container:
python run.py
```

---

## Contributing

1. All source files must include SPDX license headers
2. Run `pytest` before submitting changes
3. Follow PEP 8 style (enforced by flake8)
4. Add tests for new features

---

## License

SPDX-License-Identifier: Apache-2.0

Copyright 2024-2025 Pyontrust Contributors
