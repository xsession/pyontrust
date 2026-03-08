// ─────────────────────────────────────────────────────────────────────────────
// Zephyr Pin Configurator — Developer Guide
// ─────────────────────────────────────────────────────────────────────────────

#import "template.typ": *

#show: doc => enterprise-doc(
  title: "Developer Guide",
  subtitle: "Zephyr Pin Configurator",
  version: "0.1.0",
  date: datetime(year: 2026, month: 3, day: 4),
  doc,
)

= Development Setup

== Prerequisites

- Python ≥ 3.10
- pip with virtualenv support
- Git
- A code editor (VS Code recommended with the Typst Preview extension)

== Environment Setup

```bash
cd gui_app/pin_configurator

# Create isolated environment
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows

# Install in editable mode with all dependencies
pip install -e .

# Verify installation
pyontrust --help
```

== Running in Development Mode

```bash
pyontrust --debug --port 5100 --open
```

Flask debug mode enables:
- Auto-reload on source file changes
- Interactive debugger on unhandled exceptions
- Verbose request logging


= Code Organization

== Module Map

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Module*], [*Category*], [*Responsibility*],
  [`run.py`], [Entry], [CLI argument parsing, Flask app launch],
  [`server.py`], [API], [HTTP routing, validation, response formatting],
  [`board_schema.py`], [Model], [Core dataclasses: Pin, BoardDef, Peripheral],
  [`dts_generator.py`], [Gen], [DTS overlay + prj.conf forward generation],
  [`overlay_parser.py`], [Parse], [DTS + Kconfig reverse parsing],
  [`pdf_parser.py`], [Parse], [MCU datasheet extraction (18+ vendors)],
  [`sensor_parser.py`], [Parse], [Sensor register map extraction],
  [`driver_generator.py`], [Gen], [Zephyr driver scaffolding],
  [`package_generator.py`], [Gen], [Board .py generation from parsed data],
  [`clock_registry.py`], [Reg], [Clock tree definitions + compute],
  [`module_registry.py`], [Reg], [Zephyr module Kconfig catalog],
  [`peripheral_registry.py`], [Reg], [Peripheral config templates],
  [`zephyr_kconfig_modules.py`], [Reg], [Extended Kconfig definitions],
  [`datasheet_fetcher.py`], [Net], [Vendor URL construction + download],
)

== Naming Conventions

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Convention*], [*Rule*],
  [Modules], [snake_case, descriptive: `pdf_parser.py`, `clock_registry.py`],
  [Classes], [PascalCase dataclasses: `BoardDef`, `PinAssignment`],
  [Functions], [snake_case verbs: `generate_driver()`, `parse_datasheet()`],
  [Constants], [UPPER_SNAKE: `DRIVER_TYPES`, `ZEPHYR_MODULES`, `PROJECT_FILE_VERSION`],
  [Private], [Single underscore prefix: `_parse_ti()`, `_KCONFIG_MAP`],
  [API routes], [kebab-case paths: `/api/clock-trees`, `/api/parse-pdf`],
  [Board files], [`<soc>_<package>.py`: `stm32l476_lqfp64.py`],
  [Board builders], [`build_<soc>_<package>()`: `build_stm32l476_lqfp64()`],
)


= Adding Features

== Adding a New Board (Manual)

+ Create `boards/<soc>_<package>.py`:

```python
from board_schema import (
    BoardDef, Pin, Peripheral, AltFunction,
    PinKind, PinSide,
)

def _io(num, name, port, gpio, side, afs):
    return Pin(num, name, port, gpio, PinKind.IO, side, afs, None, {})

def _pwr(num, name, side):
    return Pin(num, name, "", 0, PinKind.PWR, side, [], None, {})

def _gnd(num, name, side):
    return Pin(num, name, "", 0, PinKind.GND, side, [], None, {})

def _AF(fid, pincm, name, periph, signal, direction="inout"):
    return AltFunction(fid, pincm, name, periph, signal, direction)

def build_<soc>_<package>():
    return BoardDef(
        soc="<soc>",
        board="<board>",
        vendor="<vendor>",
        package="<package>",
        pin_count=N,
        pins=[
            _io(1, "PA0", "A", 0, PinSide.LEFT, [
                _AF(0, 1, "UART0_TX", "UART0", "TX", "out"),
                _AF(1, 1, "SPI0_MOSI", "SPI0", "MOSI", "out"),
            ]),
            # ... more pins
        ],
        peripherals=[
            Peripheral("UART0", "UART 0", "vendor,uart", ["TX","RX"], 0x40000, "uart0", False),
            # ... more peripherals
        ],
        # DTS metadata
        dts_soc_path="vendor/soc/socxx",
        dts_pinctrl_compat="vendor,soc-pinctrl",
        dts_pin_macro_prefix="SOC_PIN",
        dts_function_macro_prefix="SOC_FUNC",
        flash_size_kb=256,
        sram_size_kb=64,
        clock_hz=80_000_000,
    )
```

+ Register in `boards/__init__.py`:

```python
from .<soc>_<package> import build_<soc>_<package>

BOARDS["<board_id>"] = build_<soc>_<package>
```

== Adding a New Vendor Parser

+ Add vendor regex to `_VENDOR_PATTERNS` in `pdf_parser.py`:

```python
_VENDOR_PATTERNS = [
    # ... existing patterns ...
    (r"(?i)newvendor|NV\d{3}", "newvendor", "NewVendor Inc."),
]
```

+ Implement vendor parser:

```python
def _parse_newvendor(pdf, text_pages, verbose):
    """Parse NewVendor datasheets."""
    device = DeviceSummary(...)
    packages = [PackageInfo(...)]
    pin_mux = [PinMuxEntry(...)]
    return DatasheetInfo(
        device=device,
        packages=packages,
        pin_mux=pin_mux,
        vendor="newvendor",
        raw_text="",
    )
```

+ Wire into `parse_datasheet()`:

```python
if vendor == "newvendor":
    return _parse_newvendor(pdf, text_pages, verbose)
```

== Adding a New Peripheral Template

Add to `PERIPHERAL_TEMPLATES` in `peripheral_registry.py`:

```python
{
    "id": "my_periph",
    "name": "My Peripheral",
    "icon": "🔧",
    "desc": "Description of the peripheral",
    "compatible": ["vendor,periph-compat"],
    "signals": ["SIG_A", "SIG_B"],
    "kconfig": ["CONFIG_MY_PERIPH=y"],
    "groups": [
        {
            "label": "Basic",
            "props": [
                {
                    "id": "param1",
                    "label": "Parameter 1",
                    "type": "int",
                    "default": 100,
                    "help": "Help text",
                    "dts": "param-1",        # DTS property name
                    "kconfig": None,
                },
            ],
        },
    ],
}
```

== Adding a New Clock Tree

Add to `clock_registry.py`:

```python
_MY_CLOCK_TREE = {
    "id": "my_mcu",
    "name": "My MCU Family",
    "vendor": "myvendor",
    "max_freq_mhz": 120,
    "nodes": [
        {
            "id": "hsi",
            "type": "source",
            "label": "HSI",
            "freq_hz": 16_000_000,
        },
        {
            "id": "pll",
            "type": "pll",
            "label": "PLL",
        },
        # ... more nodes
    ],
    "connections": [("hsi", "pll"), ("pll", "sysclk")],
    "props": [
        {"id": "pll_mul", "label": "PLL Multiplier", "type": "int", "default": 8, "min": 2, "max": 16},
    ],
    "kconfig": [],
}
```

Implement `_compute_my_mcu(values)` and register in routing.


= Testing

== Test Structure

```
tests/
├── conftest.py           Shared fixtures
├── test_api.py           Flask endpoint tests (8 classes)
├── test_driver_gen.py    Driver generator tests (7+ classes)
├── test_overlay.py       Overlay parser tests
├── test_pdf_parser.py    PDF parser unit tests
└── test_sensor_parser.py Sensor parser tests (600+ lines)
```

== Running Tests

```bash
# Full suite
pytest

# Verbose with output
pytest -v -s

# Specific file
pytest tests/test_api.py

# Specific test class
pytest tests/test_api.py::TestBoardEndpoints

# Specific test
pytest tests/test_api.py::TestBoardEndpoints::test_board_list

# With coverage
pytest --cov=. --cov-report=html --cov-report=term

# Exclude slow/integration tests
pytest -m "not integration and not slow"
```

== Writing Tests

=== Using fixtures

```python
def test_board_list(client):
    """Test GET /api/boards returns list."""
    resp = client.get("/api/boards")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "boards" in data
    assert len(data["boards"]) > 0

def test_generate_uart(client, sample_uart_assignments):
    """Test overlay generation."""
    resp = client.post("/api/generate", json={
        "board": "mspm0g3507",
        "assignments": sample_uart_assignments,
        "peripherals": [{"name": "UART0", "dts_node": "uart0",
                         "compatible": "ti,mspm0-uart", "enabled": True}],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "&pinctrl" in data["overlay"]
```

=== Pytest markers

```python
import pytest

@pytest.mark.integration
def test_full_workflow(client):
    """End-to-end test — requires running server."""
    ...

@pytest.mark.slow
def test_parse_real_pdf():
    """Parse actual datasheet — network/IO bound."""
    ...
```

== Code Quality

```bash
# Lint
flake8 --max-line-length=120

# Type checking (optional, not enforced)
mypy --ignore-missing-imports .
```


= Frontend Development

== Architecture

The frontend is a zero-dependency SPA:

- `web/index.html` — 2,074 lines: HTML structure + embedded CSS
- `web/main.js` — 3,753 lines: all application logic in vanilla JavaScript

=== State Management

```javascript
// Global state (module-level variables)
let boardData = null;       // Current board definition
let pinStates = {};         // Pin → AF assignment map
let periphStates = {};      // Peripheral → enabled boolean
let selectedPin = null;     // Currently selected pin name
let generatedOverlay = "";  // Last generated overlay
let generatedConf = "";     // Last generated prj.conf
let activeTab = "overlay";  // "overlay" or "conf"
let chipZoom = 1.0;         // Current zoom level
```

=== Key Functions

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Function*], [*Purpose*],
  [`loadBoardList()`], [Fetch board list and populate selector],
  [`loadBoard(name)`], [Fetch full board definition and render UI],
  [`renderPeripherals()`], [Update left panel peripheral toggles],
  [`renderChip()`], [Redraw SVG chip diagram with pin states],
  [`renderConfigPanel()`], [Update right panel for selected pin],
  [`periphColor(name)`], [Get peripheral's assigned color],
  [`toast(message)`], [Show temporary notification],
)

=== API Communication

All API calls use `fetch()` with JSON:

```javascript
async function loadBoard(name) {
    const resp = await fetch(`/api/board/${name}`);
    boardData = await resp.json();
    renderChip();
    renderPeripherals();
}
```

== Modifying the Frontend

=== Adding a new UI section

+ Add HTML structure in `index.html`.
+ Add CSS styles (use existing CSS variables for consistency).
+ Add JavaScript logic in `main.js`.
+ Connect to API endpoints as needed.

=== Color palette (CSS variables)

```css
:root {
    --bg:      #1e1e2e;   /* Catppuccin Base */
    --surface: #313244;   /* Catppuccin Surface0 */
    --overlay: #45475a;   /* Catppuccin Surface1 */
    --text:    #cdd6f4;   /* Catppuccin Text */
    --subtext: #a6adc8;   /* Catppuccin Subtext0 */
    --accent:  #89b4fa;   /* Catppuccin Blue */
    --green:   #a6e3a1;   /* Catppuccin Green */
    --red:     #f38ba8;   /* Catppuccin Red */
    --yellow:  #f9e2af;   /* Catppuccin Yellow */
}
```


= Release Process

== Version Bumping

+ Update `VERSION` file.
+ Update `version` in `pyproject.toml`.
+ Commit with message: `release: v<VERSION>`.
+ Tag: `git tag v<VERSION>`.

== Building a Release Archive

```bash
python scripts/release.py \
    --board nucleo_l476rg \
    --source /path/to/app \
    --output-dir ./releases
```

The script:
+ Reads `VERSION`
+ Gets git commit hash
+ Runs `west build`
+ Generates SPDX BOM
+ Creates `release-v<VER>-<hash>.tar.gz`

== Docker Image

```bash
docker build -t pin-configurator:$(cat VERSION) .
docker tag pin-configurator:$(cat VERSION) pin-configurator:latest
```


= Contributing

== Pull Request Checklist

- [ ] Tests pass: `pytest`
- [ ] Lint clean: `flake8`
- [ ] Coverage not decreased
- [ ] New endpoints documented in this guide
- [ ] New modules include docstrings
- [ ] Board definitions follow naming convention
- [ ] Version bumped if needed

== Commit Message Format

```
<type>: <short description>

<optional body>

Types: feat, fix, docs, style, refactor, test, chore
```

Examples:
```
feat: add ESP32-S3 clock tree support
fix: handle missing AF in overlay parser
docs: update API reference for sensor endpoints
test: add parametrized vendor detection tests
```
