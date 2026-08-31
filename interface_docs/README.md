# Interface Documentation (YAML)

Single-source-of-truth YAML descriptions for every communication interface
on the Locator Base board (TI MSPM0G3507).

## Structure

```
interface_docs/
├── README.md
├── mp.yaml                        # Batch / code-generation manifest
├── generate.py                    # Code-generation processor
├── locator_base/
│   ├── canopen_mcu.yaml           # CANopen object dictionary
│   ├── canopen_mcu_types.yaml     # CANopen bitfield / union types
│   ├── uart_mcu.yaml              # UART debug / command interface
│   ├── uart_mcu_types.yaml        # UART frame types
│   ├── rs485_mcu.yaml             # RS-485 / Modbus RTU interface
│   ├── rs485_mcu_types.yaml       # Modbus register types
│   ├── tcp_udp_mcu.yaml           # TCP command + UDP telemetry
│   ├── tcp_udp_mcu_types.yaml     # TCP/UDP message types
│   ├── i2c_mcu.yaml               # I²C sensor / EEPROM bus
│   ├── i2c_mcu_types.yaml         # I²C register types
│   ├── spi_mcu.yaml               # SPI peripheral bus
│   └── spi_mcu_types.yaml         # SPI frame / register types
└── generated/                     # Auto-generated outputs
    ├── c/
    ├── py/
    └── html/
```

## Quick Start

```bash
# Generate all targets listed in mp.yaml
python interface_docs/generate.py interface_docs/mp.yaml

# Generate a single interface
python interface_docs/generate.py interface_docs/mp.yaml --only uart

# Generate only one format class
python interface_docs/generate.py interface_docs/mp.yaml --format python
```

## Supported Formats

`interface_docs/generate.py` currently supports these batch `format` values:

- `c-typedefs`
- `c-objdict`
- `c-uart-protocol`
- `c-modbus-registers`
- `c-i2c-registers`
- `c-spi-devices`
- `c-tcp-protocol`
- `python`
- `py`
- `html`
- `html-confluence`
- `gui-jinja`
- `mlxcheck`
- `xml-canether`
- `c-types`
- `c-od`
- `xml-od`
- `xml-to-yaml`
- `c-pdo_macro`
- `vhdl-package`
- `vhdl-arch`
- `gui-app`
- `test-sequence`

## Job Fields

Common batch-job fields:

- `source`: input YAML or XML file
- `output`: generated output path
- `format`: generator selector
- `dependencies`: optional list of extra YAML type files
- `includes`: optional include list for C-family outputs
- `od_name`: object-dictionary / generated class name seed where applicable
- `debug`: optional sidecar JSON path with resolved job metadata
- `generate_init`: optional boolean for Python outputs; when true, create `__init__.py` next to the generated module if it does not already exist
- `overwrite_if_exists`: optional boolean for directory scaffold formats
- `context`: optional mapping of extra scaffold template values
- `context_file`: optional JSON file with extra scaffold template values
- `build_icon_path`: optional icon path for `gui-app` scaffold packaging helpers

Some formats also require format-specific fields such as `target`, `template_params`, `minMLX`, or `maxMLX`.

## Python Generator Notes

The generated Python drivers now include more than plain stubs.

- CANopen drivers emit field metadata, enum tables, bitfield definitions, normalized units, and conversion-aware helper methods.
- UART, RS-485, TCP/UDP, I2C, and SPI drivers now emit transport metadata dictionaries so callers can inspect commands, registers, devices, enums, and bitfields programmatically.
- Dependency YAML files are scanned for enum values authored as hex literals so generated enum tables preserve that formatting.

## Validation

Focused validation for the generator lives under `tests/interface_docs/`.

Typical checks:

```bash
python -m pytest tests/interface_docs
python interface_docs/generate.py interface_docs/mp.yaml --format python
```

## Scaffold Formats

The `gui-app` and `test-sequence` formats now generate pyontrust-native directory scaffolds instead of depending on the older PWTK/cookiecutter runtime.

- `gui-app` emits a small Flask dashboard wired to `pyontrust.gateway.create_app`, with an embedded generated driver and metadata API routes.
- `gui-app` also emits a `build_install.py` helper that uses `pyontrust.build_install.AppBuilder` to package the scaffold with PyInstaller or Nuitka.
- `gui-app` packaging can optionally set `build_icon_path` to thread an icon file into the generated build helper.
- `test-sequence` emits a pytest-oriented scaffold with an embedded generated driver, sequence helper, and optional `HILTestFixture` smoke test.

These formats treat the job `output` as a directory root. Set `overwrite_if_exists: true` if you want to replace an existing generated scaffold.

## YAML Conventions

| Key             | Purpose                                     |
|-----------------|---------------------------------------------|
| `interface`     | Top-level container                         |
| `title`         | Human-readable name                         |
| `transport`     | Discriminator: `canopen`, `uart`, `rs485`, `tcp`, `udp`, `i2c`, `spi` |
| `version history` | Changelog array                           |
| `physical`      | Pin assignments & electrical parameters     |
| `EXT__name`     | Reference to a type in the `_types.yaml`    |

## Pin Reference (MCU → AD3)

See `docs/AD3_WIRING_GUIDE.md` for the complete mapping.
