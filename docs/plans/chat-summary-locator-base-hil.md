# Chat Summary: Locator Base HIL & Simulation Framework

**Date:** March 9, 2026  
**Repositories:** `pyontrust`, `locator_base`  
**Board:** Codelayer Locator Base (TI MSPM0G3507)

---

## Objective

Build a reusable, readable framework in `pyontrust` that:

1. Generates an **Analog Discovery 3 (AD3) pinout** from the Locator Base board documentation
2. Integrates with pyontrust for **Zephyr driver development** and **Hardware-in-the-Loop (HIL) testing**
3. Puts the Locator Base into a **simulated environment** using ProtoSim/Renode with measured data logging

---

## Phase 1: Board Pinout & AD3 Integration

### Created: `pyontrust/boards/` module

| File | Purpose |
|------|---------|
| `boards/__init__.py` | Module exports and board registry access |
| `boards/base.py` | `BoardPinout`, `Pin`, `PinFunction` base classes for defining MCU pin configurations |
| `boards/registry.py` | Board registration system — register/lookup boards by name |
| `boards/locator_base.py` | Full MSPM0G3507 pinout with AD3 channel mappings. Includes `LocatorBaseAD3` constants class mapping MCU pins to AD3 DIO/analog channels |

### Key Design Decisions

- Pins are modeled with multiple `PinFunction` entries (GPIO, SPI, I2C, UART, PWM, ADC, CAN)
- AD3 channel mapping stored alongside pin definitions for direct hardware access
- Registry pattern allows adding new boards without modifying existing code

---

## Phase 2: AD3 HIL Interface

### Created: `pyontrust/hil/` module

| File | Purpose |
|------|---------|
| `hil/__init__.py` | Module exports |
| `hil/ad3_interface.py` | Main `AD3Interface` — unified facade combining digital, analog, and protocol access |
| `hil/digital_io.py` | 16-channel digital I/O with bulk read/write operations |
| `hil/analog_io.py` | Oscilloscope (2-ch), waveform generator (2-ch), PWM measurement |
| `hil/protocols.py` | `SPIController`, `I2CController`, `UARTController` — both hardware and bitbang modes |

### Key Features

- **Digital I/O:** 16 channels, configurable direction, edge detection, bulk operations
- **Analog I/O:** Configurable sample rate/buffer, trigger modes, PWM frequency/duty measurement
- **Protocols:** SPI (modes 0–3, configurable clock), I2C (7/10-bit addressing, clock stretching), UART (configurable baud/parity/stop)
- All use DWF library via ctypes (`dwf.dll` / `libdwf.so`)

---

## Phase 3: HIL Test Fixtures

### Created: Test infrastructure

| File | Purpose |
|------|---------|
| `hil/test_fixture.py` | `HILTestFixture`, `ZephyrProject`, `HILTestRunner` classes |
| `tests/hil_tests/__init__.py` | Test package |
| `tests/hil_tests/test_locator_base.py` | Example HIL tests (GPIO, UART loopback, ADC, PWM, I2C scan, SPI) |

### Test Fixture Capabilities

- Automatic AD3 connection lifecycle
- Zephyr firmware build (`west build`) and flash (`west flash`)
- Serial console capture
- Pin reset between tests
- Pytest integration with markers (`@pytest.mark.hil`)

---

## Phase 4: ProtoSim Simulation Integration

### Created: `pyontrust/simulation/` module

| File | Purpose |
|------|---------|
| `simulation/__init__.py` | Module exports for all simulation components |
| `simulation/runner.py` | `LocatorBaseSimulator` — main simulation orchestrator using ProtoSim/Renode |
| `simulation/hil_bridge.py` | `UnifiedHIL` — backend-agnostic interface (AD3 / Simulation / Mock) |
| `simulation/scenario_runner.py` | YAML-based test scenario executor with analysis capabilities |
| `configs/locator_base_protosim.yaml` | ProtoSim YAML configuration for Locator Base |
| `scenarios/locator_base_blink_test.yaml` | Example LED blink test scenario |
| `examples/run_locator_base_sim.py` | Demo script showing how to run the full stack |

### Simulation Runner (`runner.py`)

- `SimulationConfig` — configurable duration, sync interval, monitored pins, output formats
- `SimulationDataLogger` — writes VCD (GTKWave), CSV, JSON simultaneously
- `LocatorBaseSimulator` — orchestrates Renode MCU emulation, captures GPIO/UART/ADC data
- Mock simulation mode for testing without Renode installed
- CLI interface with argument parsing

### HIL-Simulation Bridge (`hil_bridge.py`)

Core abstraction enabling **identical test code** against real hardware or simulation:

```
BackendType.AUTO       → Auto-detect (prefers hardware)
BackendType.HARDWARE   → AD3 via DWF library
BackendType.SIMULATION → ProtoSim/Renode
BackendType.MOCK       → In-memory mock for unit tests
```

- `UnifiedHIL` — context manager with digital/analog read/write
- `AD3Backend` — wraps `pyontrust.hil.AD3Interface`
- `SimulationBackend` — wraps `LocatorBaseSimulator` with Renode GPIO injection
- `MockBackend` — stateful in-memory mock with test helpers
- Pytest fixture factory (`create_hil_fixtures()`)

### Scenario Runner (`scenario_runner.py`)

Executes test scenarios defined in YAML:

- **Step types:** `wait`, `set` (write pin), `assert` (check pin), `capture` (record signal), `analyze` (frequency/duty cycle)
- **Variable expansion:** `${WORKSPACE}`, `${OUTPUT}` in paths
- **Analysis:** Frequency measurement, duty cycle calculation with tolerance checks
- **Reporting:** HTML and text reports with pass/fail per test
- **Hooks:** `before_all`, `after_each`, `after_all` with conditional actions

---

## Phase 5: Validation

### Demo Run Results

```
Unified HIL Demo (Mock Backend):     ✓ All operations passed
Scenario Runner (Blink Test):        2/4 tests passed (expected with mock)
  ✓ LED Initial State
  ✗ Status LED Blink       (needs real firmware for frequency analysis)
  ✗ Button Toggle           (needs real firmware for GPIO response)
  ✓ PWM LED Dimming
```

### Generated Output Files

| File | Size | Format |
|------|------|--------|
| `*.vcd` | 8.7 MB | GTKWave waveform viewer |
| `*.csv` | 18.7 MB | Spreadsheet / pandas analysis |
| `*.json` | 70.5 MB | Programmatic access |
| `test_report.html` | 1 KB | Browser-viewable report |

---

## Architecture Overview

```
pyontrust/
├── boards/
│   ├── base.py              # Pin/Board abstractions
│   ├── registry.py          # Board lookup
│   └── locator_base.py      # MSPM0G3507 pinout + AD3 mapping
├── hil/
│   ├── ad3_interface.py     # AD3 unified interface
│   ├── digital_io.py        # 16-ch digital I/O
│   ├── analog_io.py         # Scope + waveform gen
│   ├── protocols.py         # SPI, I2C, UART
│   └── test_fixture.py      # Pytest HIL fixtures
├── simulation/
│   ├── runner.py            # Renode simulation orchestrator
│   ├── hil_bridge.py        # UnifiedHIL (HW ↔ Sim ↔ Mock)
│   └── scenario_runner.py   # YAML test scenario executor
├── configs/
│   └── locator_base_protosim.yaml
├── scenarios/
│   └── locator_base_blink_test.yaml
├── examples/
│   └── run_locator_base_sim.py
├── tests/hil_tests/
│   └── test_locator_base.py
└── docs/
    └── AD3_WIRING_GUIDE.md
```

---

## Usage Quick Reference

### Run with real AD3 hardware
```python
from pyontrust.simulation import UnifiedHIL, BackendType

with UnifiedHIL(backend_type=BackendType.HARDWARE) as hil:
    hil.digital_write("PA0", True)
    assert hil.digital_read("PA0") == True
```

### Run with simulation
```python
with UnifiedHIL(backend_type=BackendType.SIMULATION, firmware_path="build/zephyr/zephyr.elf") as hil:
    hil.advance_simulation(0.5)  # 500ms
    led_state = hil.digital_read("PA0")
```

### Run a YAML test scenario
```bash
python -m pyontrust.simulation.scenario_runner scenarios/locator_base_blink_test.yaml --backend mock -o test_output
```

### Run the full demo
```bash
python examples/run_locator_base_sim.py --output sim_output
```

---

## Next Steps

- [ ] Add MSPM0G3507 Renode platform template (`.repl` file) for full MCU emulation
- [ ] Integrate LTSpice analog co-simulation via ProtoSim for mixed-signal testing
- [ ] Add CAN-FD protocol controller to `hil/protocols.py`
- [ ] Create CI/CD pipeline running mock scenario tests on every commit
- [ ] Add real firmware test with blink sample (`examples_apps/01_blink`)
