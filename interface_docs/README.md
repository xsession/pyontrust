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
```

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
