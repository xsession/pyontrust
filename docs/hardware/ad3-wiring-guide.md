# Locator Base AD3 Wiring Guide

This document describes how to wire the Codelayer Locator Base board to an
Analog Discovery 3 (AD3) for Hardware-in-the-Loop (HIL) testing of Zephyr drivers.

## Overview

The AD3 provides:
- **16 Digital I/O** (DIO0-15): 3.3V tolerant, configurable as input or output
- **2 Analog Inputs** (C1+, C2+): ±25V range oscilloscope channels  
- **2 Analog Outputs** (W1, W2): ±5V waveform generator channels
- **Protocol Support**: SPI, I2C, UART via digital I/O

## Pin Mapping Table

### Digital Outputs (MCU → AD3)

| MCU Pin | Function | AD3 Channel | Wire Color (Suggested) |
|---------|----------|-------------|------------------------|
| PA2     | DOUT0    | DIO0        | Orange                 |
| PA4     | DOUT1    | DIO1        | Yellow                 |
| PA9     | DOUT2    | DIO2        | Green                  |
| PA25    | DOUT3    | DIO3        | Blue                   |

### Digital Inputs / ADC (AD3 → MCU)

| MCU Pin | Function    | AD3 DIO | AD3 AOUT | Notes                    |
|---------|-------------|---------|----------|--------------------------|
| PA15    | AIN0/DIN0   | DIO4    | W1       | Can drive with waveform  |
| PA16    | AIN1/DIN1   | DIO5    | W2       | Can drive with waveform  |
| PA17    | AIN2/DIN2   | DIO6    | -        | Digital only             |
| PA18    | AIN3/DIN3   | DIO7    | -        | Digital only             |

### SPI Interface

| MCU Pin | Function     | AD3 Channel | Notes               |
|---------|--------------|-------------|---------------------|
| PA12    | SPI0_SCK     | DIO8        | Clock               |
| PA14    | SPI0_PICO    | DIO9        | MOSI (to peripheral)|
| PA13    | SPI0_POCI    | DIO10       | MISO (from periph)  |
| PA8     | SPI0_CS0     | DIO11       | Chip select 0       |

### UART Interface

| MCU Pin | Function  | AD3 Channel | Notes        |
|---------|-----------|-------------|--------------|
| PA10    | UART0_TX  | DIO12       | MCU transmit |
| PA11    | UART0_RX  | DIO13       | MCU receive  |

### I2C Interface (Optional)

| MCU Pin | Function  | AD3 Channel | Notes                     |
|---------|-----------|-------------|---------------------------|
| PA0     | I2C0_SDA  | DIO14       | Needs level shifter if 5V |
| PA1     | I2C0_SCL  | DIO15       | Needs level shifter if 5V |

### PWM Measurement (MCU → AD3 Scope)

| MCU Pin | Function     | AD3 Channel | Notes                  |
|---------|--------------|-------------|------------------------|
| PA7     | TIMG8_C0 PWM | C1+ (AIN0)  | Use scope for PWM meas |
| PA21    | TIMG6_C0 PWM | C2+ (AIN1)  | Use scope for PWM meas |

### Power

| Signal | AD3 Pin | Notes                         |
|--------|---------|-------------------------------|
| GND    | GND     | Common ground (mandatory!)    |
| 3.3V   | V+      | Optional - AD3 can supply 3.3V|

## Wiring Diagram

```
                    ANALOG DISCOVERY 3
    ┌─────────────────────────────────────────────┐
    │                                             │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
    │  │ SCOPE   │  │ WAVEGEN │  │ DIGITAL │     │
    │  │  C1+    │  │   W1    │  │ DIO0-15 │     │
    │  │  C1-    │  │   W2    │  │         │     │
    │  │  C2+    │  │         │  │         │     │
    │  │  C2-    │  │         │  │         │     │
    │  └────┬────┘  └────┬────┘  └────┬────┘     │
    │       │            │            │          │
    └───────┼────────────┼────────────┼──────────┘
            │            │            │
            │            │            │
    ┌───────┼────────────┼────────────┼──────────┐
    │       │            │            │          │
    │  PWM ─┤       ADC ─┤      GPIO ─┤          │
    │  PA7 ─┘       PA15─┘      PA2  ─┘(DOUT0)   │
    │  PA21─────────PA16───────PA4  ──(DOUT1)   │
    │                           PA9  ──(DOUT2)   │
    │               LOCATOR BASE     PA25 ─(DOUT3)   │
    │                                             │
    │    SPI         UART        I2C             │
    │    PA12(SCK)   PA10(TX)    PA0(SDA)        │
    │    PA14(MOSI)  PA11(RX)    PA1(SCL)        │
    │    PA13(MISO)                              │
    │    PA8(CS0)                                │
    │                                             │
    └─────────────────────────────────────────────┘
```

## AD3 Connector Pinout Reference

The AD3 uses a 30-pin header with this layout:

```
Pin 1-8:   DIO0-DIO7   (accent color wires)
Pin 9-16:  DIO8-DIO15  (accent color wires)
Pin 17-24: V+, GND pairs
Pin 25-30: Trigger, etc.

BNC Connectors:
- C1+/C1-: Oscilloscope Channel 1
- C2+/C2-: Oscilloscope Channel 2
- W1: Waveform Generator Channel 1
- W2: Waveform Generator Channel 2
```

## Usage Examples

### Python - Basic GPIO Test

```python
from pyontrust.hil import AD3Interface
from pyontrust.boards.locator_base import LOCATOR_BASE, LocatorBaseAD3 as AD3

# Connect to AD3 with board definition
with AD3Interface(board=LOCATOR_BASE) as ad3:
    # Configure DIO0-3 as inputs (to read MCU outputs)
    ad3.digital.set_output_enable(0x0000)
    
    # Read DOUT0 state
    dout0 = ad3.digital.read(AD3.DIO_DOUT0)
    print(f"DOUT0 (PA2): {dout0}")
    
    # Read all digital outputs
    for i, ch in enumerate(AD3.DOUT_CHANNELS):
        print(f"DOUT{i}: {ad3.digital.read(ch)}")
```

### Python - PWM Measurement

```python
from pyontrust.hil import AD3Interface
from pyontrust.boards.locator_base import LOCATOR_BASE

with AD3Interface(board=LOCATOR_BASE) as ad3:
    # Configure analog input for PWM measurement
    ad3.analog.configure_input(
        channel=0,  # C1+ connected to PA7
        range_v=5.0,
        sample_rate_hz=1_000_000,
    )
    
    # Measure PWM parameters
    pwm = ad3.analog.measure_pwm(channel=0)
    
    print(f"Frequency: {pwm['frequency_hz']:.1f} Hz")
    print(f"Duty Cycle: {pwm['duty_cycle']*100:.1f}%")
    print(f"Min Voltage: {pwm['min_v']:.2f} V")
    print(f"Max Voltage: {pwm['max_v']:.2f} V")
```

### Python - ADC Stimulus

```python
from pyontrust.hil import AD3Interface
from pyontrust.boards.locator_base import LOCATOR_BASE

with AD3Interface(board=LOCATOR_BASE) as ad3:
    # Apply known voltage to ADC input (PA15)
    test_voltages = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    for voltage in test_voltages:
        # Set DC voltage on W1 (connected to PA15)
        ad3.analog.set_dc(channel=0, voltage_v=voltage)
        ad3.analog.output_enable(channel=0, enable=True)
        
        # Wait for settling
        import time
        time.sleep(0.1)
        
        # Read ADC value via UART (application-specific)
        # adc_value = read_adc_via_uart()
        # print(f"Applied: {voltage:.2f}V, ADC: {adc_value}")
    
    # Disable output
    ad3.analog.output_enable(channel=0, enable=False)
```

### Python - SPI Communication

```python
from pyontrust.hil import AD3Interface
from pyontrust.boards.locator_base import LocatorBaseAD3 as AD3

with AD3Interface() as ad3:
    # Configure SPI master
    ad3.spi.configure(
        clock_hz=1_000_000,
        mode=0,  # CPOL=0, CPHA=0
        dio_sck=AD3.DIO_SPI_SCK,
        dio_mosi=AD3.DIO_SPI_MOSI,
        dio_miso=AD3.DIO_SPI_MISO,
        dio_cs=AD3.DIO_SPI_CS0,
    )
    
    # Read device ID (example for SPI flash)
    response = ad3.spi.transfer([0x9F, 0x00, 0x00, 0x00])
    manufacturer_id = response[1]
    device_id = (response[2] << 8) | response[3]
    print(f"Manufacturer: 0x{manufacturer_id:02X}")
    print(f"Device ID: 0x{device_id:04X}")
```

## pytest Integration

Add to your `conftest.py`:

```python
import pytest
from pathlib import Path
from pyontrust.hil import HILTestFixture
from pyontrust.boards.locator_base import LOCATOR_BASE

@pytest.fixture(scope="session")
def hil_fixture():
    """Session-scoped HIL test fixture."""
    fixture = HILTestFixture(
        board=LOCATOR_BASE,
        zephyr_base=Path.home() / "zephyrproject" / "zephyr",
    )
    with fixture:
        yield fixture

@pytest.fixture
def ad3(hil_fixture):
    """Reset AD3 before each test."""
    hil_fixture.ad3.reset()
    return hil_fixture.ad3
```

Then write tests:

```python
def test_gpio_output(ad3):
    """Test that MCU can toggle GPIO."""
    toggles = 0
    prev = ad3.digital.read(0)
    
    for _ in range(100):
        current = ad3.digital.read(0)
        if current != prev:
            toggles += 1
            prev = current
    
    assert toggles > 0, "No GPIO activity detected"
```

## Troubleshooting

### Common Issues

1. **"DWF library not found"**
   - Install Digilent WaveForms software
   - Set `DWF_LIB_PATH` environment variable if needed

2. **"Failed to open AD3 device"**
   - Check USB connection
   - Verify AD3 appears in WaveForms application
   - Try `device_index=0` explicitly

3. **Incorrect readings**
   - Verify GND connection between AD3 and board
   - Check voltage levels (3.3V vs 5V)
   - Ensure correct channel mapping

4. **I2C not working**
   - I2C requires pull-up resistors
   - Check if level shifting is needed
   - Verify clock speed is appropriate

### Debug Tips

```python
# Check AD3 connection
from pyontrust.instruments import dwf_loader

try:
    dwf = dwf_loader.load_dwf()
    print("DWF library loaded successfully")
except Exception as e:
    print(f"Failed to load DWF: {e}")

# List available devices
import ctypes
device_count = ctypes.c_int()
dwf.FDwfEnum(ctypes.c_int(0), ctypes.byref(device_count))
print(f"Found {device_count.value} device(s)")
```
