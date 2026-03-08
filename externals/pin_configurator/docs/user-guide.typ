// ─────────────────────────────────────────────────────────────────────────────
// Zephyr Pin Configurator — User Guide
// ─────────────────────────────────────────────────────────────────────────────

#import "template.typ": *

#show: doc => enterprise-doc(
  title: "User Guide",
  subtitle: "Zephyr Pin Configurator",
  version: "0.1.0",
  date: datetime(year: 2026, month: 3, day: 4),
  doc,
)

= Getting Started

== System Requirements

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Component*],   [*Requirement*],
  [Python],        [≥ 3.10 (3.12 recommended)],
  [pip],           [Bundled with Python],
  [Browser],       [Chrome, Firefox, Edge, or Safari (latest)],
  [Disk space],    [~50 MB (application) + space for uploaded PDFs],
  [Network],       [Optional — only needed for datasheet auto-download],
)

== Installation

=== Option A — pip (recommended)

```bash
cd gui_app/pin_configurator
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows
pip install -e .
```

=== Option B — requirements.txt

```bash
pip install -r requirements.txt
```

=== Option C — Docker

```bash
docker build -t pin-configurator .
docker run -p 5100:5100 pin-configurator
```

== Launching

```bash
# Default (localhost:5100)
pyontrust

# Custom port + auto-open browser
pyontrust --port 8080 --open

# Development mode with auto-reload
pyontrust --debug
```

Navigate to `http://127.0.0.1:5100` in your browser.


= Interface Overview

The web interface has five regions:

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Region*], [*Purpose*],
  [*Header*], [Board selector, project file buttons (Save / Load), MCU lookup],
  [*Left panel*], [Peripheral list with enable/disable toggles. Color-coded.],
  [*Center*], [Interactive SVG chip diagram. Click pins to configure.],
  [*Right panel*], [Selected pin details: AF dropdown, bias, drive mode.],
  [*Bottom bar*], [Generated output tabs: `.overlay` and `prj.conf`. Copy button.],
)

The interface uses the *Catppuccin Mocha* dark theme. Each peripheral
is assigned a distinct color that is reflected on both the pin diagram and
the peripheral toggle list.

== Zoom & Navigation

- *Scroll* to zoom in/out on the chip diagram.
- *Drag* to pan the view.
- Use the zoom control buttons for precise adjustment.


= Pin-Mux Configuration

== Step-by-Step

+ *Select a board* from the header dropdown.
  - Boards are grouped by SoC family (e.g., STM32L476, STM32F411, MSPM0G3507).
  - The chip diagram and peripheral list refresh automatically.

+ *Enable peripherals* using the toggle switches in the left panel.
  - Enabled peripherals appear in color; disabled ones are greyed out.
  - Enabling a peripheral does not auto-assign pins — you must assign them
    manually for full control.

+ *Click a pin* on the chip diagram.
  - The right panel shows pin details:
    - Pin name and number
    - Pin kind (IO / PWR / GND / SPEC)
    - Available alternate functions as a dropdown
  - Only IO pins have configurable alternate functions.

+ *Select an alternate function (AF)* from the dropdown.
  - The pin changes color to match the assigned peripheral.
  - Conflicts (two pins assigned to the same peripheral signal) are
    highlighted in red.

+ *Configure pin properties* (optional):
  - *Bias pull-up / pull-down* — enable internal resistors
  - *Drive open-drain* — for I2C or wired-OR buses
  - *Input enable* — enable input buffer for input signals

+ *Review generated output* in the bottom bar:
  - The `.overlay` tab shows the DTS overlay
  - The `prj.conf` tab shows Kconfig entries
  - Output regenerates automatically on each change.

== Pin Assignment Rules

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Rule*], [*Detail*],
  [One AF per pin], [A pin can have at most one alternate function selected],
  [Signal uniqueness], [A peripheral signal (e.g., UART0_TX) should map to one pin],
  [PWR/GND/SPEC pins], [Cannot be configured — they are fixed-function],
  [AF availability], [Only AFs defined in the board definition are shown],
)


= Datasheet Import

== MCU Datasheet Parsing

+ Open the *Datasheet Parser* section (or navigate to the parsing tab).
+ Click *Upload PDF* and select an MCU datasheet.
+ The parser automatically:
  - Detects the MCU vendor (18+ supported)
  - Extracts pin-mux tables and package pinouts
  - Identifies device metadata (part number, core, memory)
+ Review the parsed data:
  - Number of packages found
  - Number of pin-mux entries
  - Vendor and device identification
+ Click *Generate Board Package*:
  - Select the desired package variant
  - Enter board name and DTS paths
  - A new `.py` board definition is created in `boards/`
+ The new board is immediately available in the board selector.

#note[
  The PDF parser requires text-layer PDFs. Scanned/image-only datasheets
  will not parse correctly. Use OCR tools first if needed.
]

== MCU Auto-Lookup

Instead of uploading a PDF manually:

+ Enter the MCU part number (e.g., `STM32L476RGT6`, `MSPM0G3507`).
+ Click *Identify MCU*.
+ If recognized, the Tool displays vendor info and datasheet URLs.
+ Click *Fetch & Parse* to download and parse automatically.

Supported vendors for auto-lookup: TI, STMicroelectronics, Nordic, NXP,
Microchip, Espressif, Infineon, Renesas.


= Sensor Datasheet Parsing

== Register Map Extraction

+ Open the *Sensor Parser* tab.
+ Upload a sensor IC datasheet PDF.
+ The parser extracts:
  - Device summary (part number, vendor, type, voltage range)
  - I²C / SPI addressing (addresses, max frequency, mode)
  - Complete register map with bit-field definitions
+ The extraction uses a 4-phase strategy:
  + Structured register summary tables
  + Bit-field detail tables
  + Pointer-based / calibration registers
  + Text-based fallback

== Code Generation from Sensor Data

After parsing, you can generate:

*C Register Header:*
- Includes `#define` for all register addresses
- Bit masks and shift values for all fields
- Reset values as comments

*Zephyr Sensor Driver:*
- Complete driver source (`.c` + `.h`)
- `DT_DRV_COMPAT` integration
- Sensor API callbacks (`sample_fetch`, `channel_get`)
- I²C and/or SPI bus helpers
- Optional interrupt handler


= Clock Tree Configuration

== Supported Clock Trees

#table(
  columns: (auto, auto, auto),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*MCU Family*], [*Max Frequency*], [*Clock Sources*],
  [TI MSPM0], [80 MHz], [SYSOSC, LFCLK, MFCLK, ULPCLK],
  [STM32 (Generic)], [170 MHz], [HSI, HSE, PLL (M/N/R), APB1/2 dividers],
  [Nordic nRF52], [64 MHz], [HFCLK, LFCLK, HFXO, LFXO],
)

== Configuration Steps

+ Select a board with a supported clock tree.
+ Open the *Clock Configuration* panel.
+ Adjust clock source selections and PLL parameters:
  - For STM32: set HSE frequency, PLL M/N/R dividers
  - For MSPM0: configure SYSOSC, enable LFCLK
  - For nRF52: select HFXO/LFXO sources
+ Computed frequencies display in real-time.
+ Generate clock-specific DTS overlay and Kconfig entries.


= Driver Generation

== Creating a New Driver

+ Open the *Driver Generator* tab.
+ Fill in the driver specification:

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Field*], [*Required*], [*Description*],
  [Name], [Yes], [Driver name (e.g., "bmp280")],
  [Type], [Yes], [sensor / gpio / i2c / spi / uart / pwm / adc / custom],
  [Compatible], [Yes], [DTS compatible string (e.g., "bosch,bmp280")],
  [Bus], [Yes], [Communication bus: i2c or spi],
  [Vendor], [No], [Vendor slug for file organization],
  [Interrupt], [No], [Enable interrupt handler generation],
  [Channels], [No], [Number of sensor channels (for sensor type)],
  [Registers], [No], [Array of register definitions],
)

+ Click *Generate*.
+ The tool produces a complete driver package:

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*File*], [*Content*],
  [`<name>.c`], [Full driver source with init, API, bus helpers, logging],
  [`<name>.h`], [Public header with register defines and channel enums],
  [`Kconfig`], [Build configuration with dependencies],
  [`CMakeLists.txt`], [Build system integration],
  [`<board>.overlay`], [Sample DTS overlay for testing],
  [`prj.conf`], [Sample project configuration],
  [`README.md`], [Driver documentation template],
  [`test_<name>.c`], [Test skeleton],
)


= Module Configuration

== Zephyr Module Catalog

The Tool includes definitions for 27 Zephyr subsystem modules covering ~400
configuration options.

=== Module Categories

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Category*], [*Modules*],
  [Connectivity], [Bluetooth, Networking, USB, CAN Bus],
  [Storage], [Settings & NVS, File Systems, Flash],
  [UI & Display], [LVGL, Display Drivers, Console],
  [Diagnostics], [Logging, Shell, Debug & Analysis],
  [Security], [Crypto & TLS, DFU & MCUboot],
  [Peripherals], [I²C, SPI, UART, ADC, PWM, GPIO, Timer, DMA, Watchdog, Sensor],
  [System], [Power Management, Kernel],
)

=== Generating Module Config

+ Browse modules in the *Module Configuration* panel.
+ Expand a module to see its options.
+ Toggle individual Kconfig options.
+ Click *Generate* to produce `prj.conf` lines.
+ Copy or append to your existing project configuration.


= Peripheral Configuration

== Template-Based Configuration

The Tool provides rich configuration templates for 11+ peripheral types.
Each template includes:

- Typed configuration properties (bool, int, string, enum)
- Default values and help text
- Automatic DTS property mapping
- Kconfig line generation

=== Example: UART Configuration

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Property*], [*Type*], [*Default*], [*Description*],
  [Baudrate], [enum], [115200], [9600 / 19200 / 38400 / 57600 / 115200 / …],
  [Parity], [enum], [none], [none / odd / even],
  [Stop bits], [enum], [1], [1 / 2],
  [Flow control], [bool], [false], [Hardware flow control enable],
  [HW flow ctrl], [enum], [rts-cts], [rts-cts / dtr-dsr],
)

== Generating Peripheral Config

+ Select a board.
+ Open the *Peripheral Configuration* panel.
+ Board peripherals are automatically matched to templates.
+ Adjust property values as needed.
+ Click *Generate* to produce DTS overlay and `prj.conf`.


= Project File Management

== Saving Projects

Project state is saved as `.zpinproj` files (JSON format):

+ Click *Save Project* in the header.
+ Choose a file path.
+ The file captures: board selection, all pin assignments, peripheral states,
  and generated output.

== Loading Projects

+ Click *Load Project* in the header.
+ Select a `.zpinproj` file.
+ The UI restores completely: board, pins, peripherals, and output.

== Import from Existing Zephyr Project

+ Use *Import Config* to paste existing `.overlay` and `prj.conf` content.
+ Or use *Scan Project* to auto-discover files in a Zephyr project directory.
+ The parser reconstructs the UI state from the configuration files.

#tip[
  This enables round-trip workflows: generate from UI → edit manually →
  re-import → continue in UI.
]


= West Integration

== Setup

Add the Pin Configurator as a west extension in your Zephyr workspace:

```yaml
# west.yml
manifest:
  projects:
    - name: pin-configurator
      url: https://github.com/pyontrust/pyontrust
      path: tools/pin-configurator
      west-commands: gui_app/pin_configurator/scripts/west/west-commands.yml
```

== Usage

```bash
# Launch with default settings
west configure

# Specify board and port
west configure --board stm32l476_lqfp64 --port 8080

# Headless mode (API only, no browser)
west configure --headless
```

The command auto-detects `ZEPHYR_BASE` from the workspace and configures
the Flask application accordingly.


= Keyboard Shortcuts

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Shortcut*], [*Action*],
  [Scroll wheel], [Zoom chip diagram],
  [Click + drag], [Pan chip diagram],
  [Click pin], [Select pin for configuration],
  [Escape], [Deselect current pin],
)


= Troubleshooting

== Common Issues

=== Server won't start

Check that port 5100 is available:
```bash
# Linux/macOS
lsof -i :5100

# Windows
netstat -ano | findstr :5100
```

Use `--port` to specify an alternative.

=== PDF parsing returns "No vendor detected"

- Ensure the PDF has a text layer (not scanned/image-only).
- Try a different datasheet — some vendor formats are not yet supported.
- Use `--verbose` for debug output.

=== Generated overlay is empty

- Verify that at least one peripheral is enabled.
- Verify that at least one pin has an AF assigned.
- Check the browser console for JavaScript errors.

=== Board not appearing after generation

Board generation calls `_reload_boards()` automatically. If the board still
doesn't appear, restart the server.

#warning[
  The application stores parse jobs in memory. Restarting the server will
  clear all pending parse jobs and sensor jobs.
]
