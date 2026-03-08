"""Base classes for board pinout definitions.

Provides dataclasses and enums for defining board pin configurations
that can be mapped to test instrument channels (e.g., Analog Discovery 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Iterator


class PinFunction(Enum):
    """Pin function types supported for HIL testing."""
    
    # Digital
    GPIO_OUT = auto()       # Digital output
    GPIO_IN = auto()        # Digital input
    
    # Analog
    ADC = auto()            # Analog-to-Digital converter input
    DAC = auto()            # Digital-to-Analog converter output
    
    # PWM
    PWM = auto()            # PWM output
    
    # Communication
    UART_TX = auto()
    UART_RX = auto()
    SPI_MOSI = auto()       # SPI PICO (Peripheral In, Controller Out)
    SPI_MISO = auto()       # SPI POCI (Peripheral Out, Controller In)
    SPI_SCK = auto()
    SPI_CS = auto()
    I2C_SDA = auto()
    I2C_SCL = auto()
    CAN_TX = auto()
    CAN_RX = auto()
    
    # Debug
    SWDIO = auto()
    SWCLK = auto()
    
    # Oscillator
    OSC = auto()
    
    # Power
    VCC = auto()
    GND = auto()


@dataclass(frozen=True)
class Pin:
    """Represents a single MCU pin with its configuration.
    
    Attributes:
        name: MCU pin name (e.g., 'PA0', 'PB3')
        function: Primary pin function
        alt_functions: Alternative pin functions
        ad3_dio: AD3 digital I/O channel (DIO0-15), None if not connected
        ad3_ain: AD3 analog input channel (0-1), None if not connected
        ad3_aout: AD3 analog output channel (0-1), None if not connected
        description: Human-readable description of pin usage
    """
    
    name: str
    function: PinFunction
    alt_functions: tuple[PinFunction, ...] = ()
    ad3_dio: Optional[int] = None
    ad3_ain: Optional[int] = None
    ad3_aout: Optional[int] = None
    description: str = ""
    
    @property
    def has_digital(self) -> bool:
        """Check if pin is mapped to AD3 digital I/O."""
        return self.ad3_dio is not None
    
    @property
    def has_analog_in(self) -> bool:
        """Check if pin is mapped to AD3 analog input."""
        return self.ad3_ain is not None
    
    @property
    def has_analog_out(self) -> bool:
        """Check if pin is mapped to AD3 analog output."""
        return self.ad3_aout is not None


@dataclass
class BoardPinout:
    """Complete board pinout definition for HIL testing.
    
    Attributes:
        name: Board name (matches Zephyr board name, e.g., 'locator_base')
        mcu: MCU part number
        description: Board description
        pins: Dictionary of pins by name
        voltage_level: Logic voltage level in volts (3.3V, 5V, etc.)
    """
    
    name: str
    mcu: str
    description: str = ""
    pins: dict[str, Pin] = field(default_factory=dict)
    voltage_level: float = 3.3
    
    def add_pin(self, pin: Pin) -> None:
        """Add a pin to the board definition."""
        self.pins[pin.name] = pin
    
    def get_pin(self, name: str) -> Optional[Pin]:
        """Get pin by MCU pin name."""
        return self.pins.get(name)
    
    def get_pins_by_function(self, function: PinFunction) -> list[Pin]:
        """Get all pins with a specific primary function."""
        return [p for p in self.pins.values() if p.function == function]
    
    def get_pins_with_ad3_dio(self) -> list[Pin]:
        """Get all pins mapped to AD3 digital I/O."""
        return [p for p in self.pins.values() if p.has_digital]
    
    def get_pins_with_ad3_ain(self) -> list[Pin]:
        """Get all pins mapped to AD3 analog input."""
        return [p for p in self.pins.values() if p.has_analog_in]
    
    def get_pins_with_ad3_aout(self) -> list[Pin]:
        """Get all pins mapped to AD3 analog output."""
        return [p for p in self.pins.values() if p.has_analog_out]
    
    def __iter__(self) -> Iterator[Pin]:
        """Iterate over all pins."""
        return iter(self.pins.values())
    
    def __len__(self) -> int:
        return len(self.pins)
    
    # Convenience accessors for common peripherals
    
    @property
    def i2c_pins(self) -> dict[str, Optional[Pin]]:
        """Get I2C pins as a dict with 'sda' and 'scl' keys."""
        sda = next((p for p in self.pins.values() if p.function == PinFunction.I2C_SDA), None)
        scl = next((p for p in self.pins.values() if p.function == PinFunction.I2C_SCL), None)
        return {"sda": sda, "scl": scl}
    
    @property
    def spi_pins(self) -> dict[str, Optional[Pin]]:
        """Get SPI pins as a dict."""
        return {
            "mosi": next((p for p in self.pins.values() if p.function == PinFunction.SPI_MOSI), None),
            "miso": next((p for p in self.pins.values() if p.function == PinFunction.SPI_MISO), None),
            "sck": next((p for p in self.pins.values() if p.function == PinFunction.SPI_SCK), None),
            "cs": self.get_pins_by_function(PinFunction.SPI_CS),
        }
    
    @property
    def uart_pins(self) -> dict[str, Optional[Pin]]:
        """Get UART pins as a dict."""
        return {
            "tx": next((p for p in self.pins.values() if p.function == PinFunction.UART_TX), None),
            "rx": next((p for p in self.pins.values() if p.function == PinFunction.UART_RX), None),
        }
    
    @property
    def can_pins(self) -> dict[str, Optional[Pin]]:
        """Get CAN pins as a dict."""
        return {
            "tx": next((p for p in self.pins.values() if p.function == PinFunction.CAN_TX), None),
            "rx": next((p for p in self.pins.values() if p.function == PinFunction.CAN_RX), None),
        }
    
    @property
    def pwm_pins(self) -> list[Pin]:
        """Get all PWM capable pins."""
        return self.get_pins_by_function(PinFunction.PWM)
    
    @property
    def adc_pins(self) -> list[Pin]:
        """Get all ADC capable pins."""
        return self.get_pins_by_function(PinFunction.ADC)
    
    @property
    def gpio_out_pins(self) -> list[Pin]:
        """Get all GPIO output pins."""
        return self.get_pins_by_function(PinFunction.GPIO_OUT)
    
    @property
    def gpio_in_pins(self) -> list[Pin]:
        """Get all GPIO input pins."""
        return self.get_pins_by_function(PinFunction.GPIO_IN)
