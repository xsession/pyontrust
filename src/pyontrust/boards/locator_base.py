"""Codelayer Locator Base board definition.

Based on the TI MSPM0G3507 microcontroller.
This file defines the pin mapping between the Locator Base board
and the Analog Discovery 3 for hardware-in-the-loop testing.

Pin mapping strategy:
- DIO0-7:  General purpose digital I/O (DOUT0-3, DIN0-3)
- DIO8-15: Communication interfaces (SPI, UART, I2C)
- AIN0-1:  Analog measurements (ADC verification, current sensing)
- AOUT0-1: Analog stimulus (DAC testing, PWM verification)
"""

from pyontrust.boards.base import BoardPinout, Pin, PinFunction
from pyontrust.boards.registry import register_board


def create_locator_base_pinout() -> BoardPinout:
    """Create and return the Locator Base board pinout definition.
    
    AD3 Pin Mapping (recommended wiring):
    =====================================
    
    Digital I/O (accent connector on AD3):
    - DIO0  -> PA2  (DOUT0)
    - DIO1  -> PA4  (DOUT1)
    - DIO2  -> PA9  (DOUT2)
    - DIO3  -> PA25 (DOUT3)
    - DIO4  -> PA15 (AIN0/DIN0) - bidirectional
    - DIO5  -> PA16 (AIN1/DIN1) - bidirectional
    - DIO6  -> PA17 (AIN2/DIN2) - bidirectional
    - DIO7  -> PA18 (AIN3/DIN3) - bidirectional
    - DIO8  -> PA12 (SPI0_SCK)
    - DIO9  -> PA14 (SPI0_PICO/MOSI)
    - DIO10 -> PA13 (SPI0_POCI/MISO)
    - DIO11 -> PA8  (SPI0_CS0)
    - DIO12 -> PA10 (UART0_TX)
    - DIO13 -> PA11 (UART0_RX)
    - DIO14 -> PA0  (I2C0_SDA) - optional, needs level shifter
    - DIO15 -> PA1  (I2C0_SCL) - optional, needs level shifter
    
    Analog I/O (BNC connectors on AD3):
    - AIN0 (C1+) -> PA7 (TIMG8_C0 PWM) - for PWM duty cycle measurement
    - AIN1 (C2+) -> PA21 (TIMG6_C0 PWM) - for PWM duty cycle measurement
    - AOUT0 (W1) -> PA15 (AIN0/DIN0) - for ADC stimulus
    - AOUT1 (W2) -> PA16 (AIN1/DIN1) - for ADC stimulus
    
    Returns:
        Configured BoardPinout for Locator Base
    """
    
    board = BoardPinout(
        name="locator_base",
        mcu="MSPM0G3507",
        description="Codelayer Locator Base - CANopen development board",
        voltage_level=3.3,
    )
    
    # I2C0 pins
    board.add_pin(Pin(
        name="PA0",
        function=PinFunction.I2C_SDA,
        ad3_dio=14,
        description="I2C0_SDA - External I2C bus"
    ))
    board.add_pin(Pin(
        name="PA1",
        function=PinFunction.I2C_SCL,
        ad3_dio=15,
        description="I2C0_SCL - External I2C bus"
    ))
    
    # Digital outputs (directly controlled by MCU)
    board.add_pin(Pin(
        name="PA2",
        function=PinFunction.GPIO_OUT,
        ad3_dio=0,
        description="DOUT0 - Digital output 0"
    ))
    board.add_pin(Pin(
        name="PA4",
        function=PinFunction.GPIO_OUT,
        ad3_dio=1,
        description="DOUT1 - Digital output 1"
    ))
    board.add_pin(Pin(
        name="PA9",
        function=PinFunction.GPIO_OUT,
        ad3_dio=2,
        description="DOUT2 - Digital output 2"
    ))
    board.add_pin(Pin(
        name="PA25",
        function=PinFunction.GPIO_OUT,
        ad3_dio=3,
        description="DOUT3 - Digital output 3"
    ))
    
    # SPI0 chip select pins (directly controlled by MCU)
    board.add_pin(Pin(
        name="PA3",
        function=PinFunction.SPI_CS,
        description="SPI0_CS1 - SPI chip select 1"
    ))
    board.add_pin(Pin(
        name="PA8",
        function=PinFunction.SPI_CS,
        ad3_dio=11,
        description="SPI0_CS0 - SPI chip select 0"
    ))
    board.add_pin(Pin(
        name="PA24",
        function=PinFunction.SPI_CS,
        description="SPI0_CS2 - SPI chip select 2"
    ))
    
    # Oscillator pins (not connected to AD3)
    board.add_pin(Pin(
        name="PA5",
        function=PinFunction.OSC,
        description="OSC1 - Crystal oscillator"
    ))
    board.add_pin(Pin(
        name="PA6",
        function=PinFunction.OSC,
        description="OSC2 - Crystal oscillator"
    ))
    
    # PWM outputs (measure with AD3 analog inputs)
    board.add_pin(Pin(
        name="PA7",
        function=PinFunction.PWM,
        ad3_ain=0,  # Measure PWM with analog scope
        description="TIMG8_C0 PWM - Timer 8 Channel 0"
    ))
    board.add_pin(Pin(
        name="PA21",
        function=PinFunction.PWM,
        ad3_ain=1,
        description="TIMG6_C0 PWM - Timer 6 Channel 0"
    ))
    board.add_pin(Pin(
        name="PA22",
        function=PinFunction.PWM,
        description="TIMG6_C1 PWM - Timer 6 Channel 1"
    ))
    board.add_pin(Pin(
        name="PA23",
        function=PinFunction.PWM,
        description="TIMG0_C0 PWM - Timer 0 Channel 0"
    ))
    
    # UART0 pins
    board.add_pin(Pin(
        name="PA10",
        function=PinFunction.UART_TX,
        ad3_dio=12,
        description="UART0_TX - Console/debug UART transmit"
    ))
    board.add_pin(Pin(
        name="PA11",
        function=PinFunction.UART_RX,
        ad3_dio=13,
        description="UART0_RX - Console/debug UART receive"
    ))
    
    # SPI0 data/clock pins
    board.add_pin(Pin(
        name="PA12",
        function=PinFunction.SPI_SCK,
        ad3_dio=8,
        description="SPI0_SCK - SPI clock"
    ))
    board.add_pin(Pin(
        name="PA13",
        function=PinFunction.SPI_MISO,
        ad3_dio=10,
        description="SPI0_POCI - SPI peripheral out, controller in (MISO)"
    ))
    board.add_pin(Pin(
        name="PA14",
        function=PinFunction.SPI_MOSI,
        ad3_dio=9,
        description="SPI0_PICO - SPI peripheral in, controller out (MOSI)"
    ))
    
    # Analog inputs / Digital inputs (dual purpose)
    board.add_pin(Pin(
        name="PA15",
        function=PinFunction.ADC,
        alt_functions=(PinFunction.GPIO_IN,),
        ad3_dio=4,
        ad3_aout=0,  # Can drive with AD3 for ADC testing
        description="AIN0/DIN0 - Analog/Digital input 0"
    ))
    board.add_pin(Pin(
        name="PA16",
        function=PinFunction.ADC,
        alt_functions=(PinFunction.GPIO_IN,),
        ad3_dio=5,
        ad3_aout=1,
        description="AIN1/DIN1 - Analog/Digital input 1"
    ))
    board.add_pin(Pin(
        name="PA17",
        function=PinFunction.ADC,
        alt_functions=(PinFunction.GPIO_IN,),
        ad3_dio=6,
        description="AIN2/DIN2 - Analog/Digital input 2"
    ))
    board.add_pin(Pin(
        name="PA18",
        function=PinFunction.ADC,
        alt_functions=(PinFunction.GPIO_IN,),
        ad3_dio=7,
        description="AIN3/DIN3 - Analog/Digital input 3"
    ))
    
    # Debug pins (usually not connected to AD3)
    board.add_pin(Pin(
        name="PA19",
        function=PinFunction.SWDIO,
        description="SWDIO - Debug data I/O"
    ))
    board.add_pin(Pin(
        name="PA20",
        function=PinFunction.SWCLK,
        description="SWCLK - Debug clock"
    ))
    
    # CAN bus pins
    board.add_pin(Pin(
        name="PA26",
        function=PinFunction.CAN_TX,
        description="CAN_TX - CAN bus transmit"
    ))
    board.add_pin(Pin(
        name="PA27",
        function=PinFunction.CAN_RX,
        description="CAN_RX - CAN bus receive"
    ))
    
    return board


# Create and register the board on module import
LOCATOR_BASE = create_locator_base_pinout()
register_board(LOCATOR_BASE)


# Convenience constants for direct channel access
class LocatorBaseAD3:
    """AD3 channel constants for Locator Base board.
    
    Use these constants to reference specific AD3 channels in tests
    without looking up the pin mapping each time.
    
    Example:
        from pyontrust.boards.locator_base import LocatorBaseAD3 as AD3
        
        # Set digital output
        ad3.digital_write(AD3.DIO_DOUT0, True)
        
        # Read PWM with scope
        ad3.scope_channel(AD3.AIN_PWM0)
    """
    
    # Digital I/O channels for digital outputs
    DIO_DOUT0 = 0   # PA2
    DIO_DOUT1 = 1   # PA4
    DIO_DOUT2 = 2   # PA9
    DIO_DOUT3 = 3   # PA25
    
    # Digital I/O channels for analog/digital inputs
    DIO_AIN0 = 4    # PA15
    DIO_AIN1 = 5    # PA16
    DIO_AIN2 = 6    # PA17
    DIO_AIN3 = 7    # PA18
    
    # Digital I/O channels for SPI
    DIO_SPI_SCK = 8     # PA12
    DIO_SPI_MOSI = 9    # PA14
    DIO_SPI_MISO = 10   # PA13
    DIO_SPI_CS0 = 11    # PA8
    
    # Digital I/O channels for UART
    DIO_UART_TX = 12    # PA10
    DIO_UART_RX = 13    # PA11
    
    # Digital I/O channels for I2C
    DIO_I2C_SDA = 14    # PA0
    DIO_I2C_SCL = 15    # PA1
    
    # Analog input channels (scope)
    AIN_PWM0 = 0    # PA7 - TIMG8_C0
    AIN_PWM1 = 1    # PA21 - TIMG6_C0
    
    # Analog output channels (waveform generator)
    AOUT_ADC0 = 0   # Can drive PA15
    AOUT_ADC1 = 1   # Can drive PA16
    
    # Logical groupings for batch operations
    DOUT_CHANNELS = (DIO_DOUT0, DIO_DOUT1, DIO_DOUT2, DIO_DOUT3)
    DIN_CHANNELS = (DIO_AIN0, DIO_AIN1, DIO_AIN2, DIO_AIN3)
    SPI_CHANNELS = (DIO_SPI_SCK, DIO_SPI_MOSI, DIO_SPI_MISO, DIO_SPI_CS0)
