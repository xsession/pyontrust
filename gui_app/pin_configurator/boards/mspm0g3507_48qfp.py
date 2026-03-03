"""
MSPM0G3507 – 48-pin QFP board definition for the Zephyr Pin Configurator.

Pin-mux data derived from the MSPM0G3507 datasheet (PINCM table) and the
Zephyr ``mspm0-pinctrl.h`` header: MSP_PINMUX(pincm, function).

PINCM register index is 1-based.  Function codes use MSPM0_PIN_FUNCTION_*.
"""

from board_schema import (
    BoardDef, Pin, AltFunction, Peripheral,
    PinKind, PinSide,
)


def _io(number, name, port, gpio, side, pincm, alts, default="Reset"):
    """Shorthand for an I/O pin with alt-functions."""
    return Pin(
        number=number,
        name=name,
        port=port,
        gpio_num=gpio,
        kind=PinKind.IO,
        side=side,
        default_function=default,
        alt_functions=[
            AltFunction(
                function_id=fid,
                pincm=pincm,
                name=n,
                peripheral=per,
                signal=sig,
                direction=d,
            )
            for fid, n, per, sig, d in alts
        ],
    )


def _pwr(number, name, side):
    return Pin(number=number, name=name, kind=PinKind.PWR, side=side)


def _gnd(number, name, side):
    return Pin(number=number, name=name, kind=PinKind.GND, side=side)


def _spec(number, name, side, default=""):
    return Pin(number=number, name=name, kind=PinKind.SPEC, side=side,
               default_function=default or name)


# ── Alt-function tuples: (function_id, label, peripheral, signal, dir) ─

# Convenience aliases for function codes
_AF = lambda fid, label, periph, sig, d="io": (fid, label, periph, sig, d)
_GPIO = lambda port, bit: _AF(1, f"GPIO{port}{bit}", f"gpio{port.lower()}", f"{bit}", "io")
_ANA  = lambda label, periph, sig: _AF(0, label, periph, sig, "analog")


def build_mspm0g3507_48qfp() -> BoardDef:
    """
    Return the full MSPM0G3507 48-QFP board definition.

    Pin numbering follows the 48-QFP package:
      Left   (top→bottom): pins 1-12
      Bottom (left→right): pins 13-24
      Right  (bottom→top): pins 25-36
      Top    (right→left): pins 37-48
    """
    L, B, R, T = PinSide.LEFT, PinSide.BOTTOM, PinSide.RIGHT, PinSide.TOP

    pins: list[Pin] = [
        # ═══ LEFT SIDE (pins 1–12, top to bottom) ═══
        _io(1, "PA0", "A", 0, L, 1, [
            _GPIO("A", 0),
            _AF(2, "TIMA0_CCP0", "tima0", "ccp0", "out"),
            _AF(3, "TIMG8_CCP0", "timg8", "ccp0", "out"),
            _AF(4, "SPI0_CS2", "spi0", "cs2", "out"),
            _AF(5, "UART0_CTS", "uart0", "cts", "in"),
        ]),
        _io(2, "PA1", "A", 1, L, 2, [
            _GPIO("A", 1),
            _AF(2, "TIMA0_CCP0_C", "tima0", "ccp0_cmpl", "out"),
            _AF(3, "TIMG8_IDX", "timg8", "idx", "in"),
            _AF(4, "SPI0_CS3", "spi0", "cs3", "out"),
            _AF(5, "UART0_RTS", "uart0", "rts", "out"),
            _AF(7, "COMP0_OUT", "comp0", "out", "out"),
        ]),
        _io(3, "PA2", "A", 2, L, 3, [
            _GPIO("A", 2),
            _AF(2, "TIMA0_CCP1", "tima0", "ccp1", "out"),
            _AF(3, "TIMG8_CCP1", "timg8", "ccp1", "out"),
            _AF(5, "UART0_TX", "uart0", "tx", "out"),
        ]),
        _io(4, "PA3", "A", 3, L, 4, [
            _GPIO("A", 3),
            _AF(2, "TIMA0_CCP1_C", "tima0", "ccp1_cmpl", "out"),
            _AF(3, "SPI0_CS0", "spi0", "cs0", "out"),
            _AF(5, "UART1_TX", "uart1", "tx", "out"),
            _AF(7, "I2C1_SCL", "i2c1", "scl", "io"),
        ]),
        _io(5, "PA4", "A", 4, L, 5, [
            _GPIO("A", 4),
            _AF(2, "TIMA0_CCP2", "tima0", "ccp2", "out"),
            _AF(3, "SPI0_POCI", "spi0", "poci", "in"),
            _AF(5, "UART1_RX", "uart1", "rx", "in"),
            _AF(7, "I2C1_SDA", "i2c1", "sda", "io"),
        ]),
        _io(6, "PA5", "A", 5, L, 6, [
            _GPIO("A", 5),
            _AF(2, "TIMA0_CCP2_C", "tima0", "ccp2_cmpl", "out"),
            _AF(3, "SPI0_SCLK", "spi0", "sclk", "out"),
            _AF(5, "UART1_CTS", "uart1", "cts", "in"),
        ]),
        _io(7, "PA6", "A", 6, L, 7, [
            _GPIO("A", 6),
            _AF(2, "TIMA0_CCP3", "tima0", "ccp3", "out"),
            _AF(3, "SPI0_PICO", "spi0", "pico", "out"),
            _AF(5, "UART1_RTS", "uart1", "rts", "out"),
        ]),
        _io(8, "PA7", "A", 7, L, 8, [
            _GPIO("A", 7),
            _AF(2, "TIMA0_CCP3_C", "tima0", "ccp3_cmpl", "out"),
            _AF(3, "TIMG8_CCP0", "timg8", "ccp0", "out"),
            _AF(5, "UART2_TX", "uart2", "tx", "out"),
            _AF(8, "SPI1_CS0", "spi1", "cs0", "out"),
        ]),
        _pwr(9, "VDD", L),
        _gnd(10, "GND", L),
        _io(11, "PA8", "A", 8, L, 11, [
            _GPIO("A", 8),
            _AF(2, "TIMG12_CCP0", "timg12", "ccp0", "out"),
            _AF(3, "TIMG8_CCP1", "timg8", "ccp1", "out"),
            _AF(5, "UART2_RX", "uart2", "rx", "in"),
            _AF(8, "SPI1_POCI", "spi1", "poci", "in"),
        ]),
        _io(12, "PA9", "A", 9, L, 12, [
            _GPIO("A", 9),
            _AF(2, "TIMG12_CCP1", "timg12", "ccp1", "out"),
            _AF(5, "UART2_CTS", "uart2", "cts", "in"),
            _AF(8, "SPI1_SCLK", "spi1", "sclk", "out"),
        ]),

        # ═══ BOTTOM SIDE (pins 13–24, left to right) ═══
        _io(13, "PA10", "A", 10, B, 13, [
            _GPIO("A", 10),
            _AF(2, "UART0_TX", "uart0", "tx", "out"),
            _AF(3, "SPI1_PICO", "spi1", "pico", "out"),
            _AF(5, "UART2_RTS", "uart2", "rts", "out"),
            _AF(8, "I2C0_SCL", "i2c0", "scl", "io"),
        ]),
        _io(14, "PA11", "A", 11, B, 14, [
            _GPIO("A", 11),
            _AF(2, "UART0_RX", "uart0", "rx", "in"),
            _AF(3, "SPI1_CS0", "spi1", "cs0", "out"),
            _AF(5, "COMP0_OUT", "comp0", "out", "out"),
            _AF(8, "I2C0_SDA", "i2c0", "sda", "io"),
        ]),
        _io(15, "PA12", "A", 12, B, 15, [
            _GPIO("A", 12),
            _AF(2, "TIMG6_CCP0", "timg6", "ccp0", "out"),
            _AF(3, "SPI1_CS1", "spi1", "cs1", "out"),
            _AF(5, "UART3_TX", "uart3", "tx", "out"),
            _AF(8, "I2C1_SCL", "i2c1", "scl", "io"),
        ]),
        _io(16, "PA13", "A", 13, B, 16, [
            _GPIO("A", 13),
            _AF(2, "TIMG6_CCP1", "timg6", "ccp1", "out"),
            _AF(3, "SPI1_CS2", "spi1", "cs2", "out"),
            _AF(5, "UART3_RX", "uart3", "rx", "in"),
            _AF(8, "I2C1_SDA", "i2c1", "sda", "io"),
        ]),
        _io(17, "PA14", "A", 14, B, 17, [
            _GPIO("A", 14),
            _AF(2, "TIMG7_CCP0", "timg7", "ccp0", "out"),
            _AF(3, "SPI1_CS3", "spi1", "cs3", "out"),
            _AF(5, "UART3_CTS", "uart3", "cts", "in"),
        ]),
        _io(18, "PA15", "A", 15, B, 18, [
            _GPIO("A", 15),
            _ANA("ADC0_CH0", "adc0", "ch0"),
            _AF(2, "TIMG7_CCP1", "timg7", "ccp1", "out"),
            _AF(5, "UART3_RTS", "uart3", "rts", "out"),
        ]),
        _io(19, "PA16", "A", 16, B, 19, [
            _GPIO("A", 16),
            _ANA("ADC0_CH1", "adc0", "ch1"),
            _AF(2, "TIMG0_CCP0", "timg0", "ccp0", "out"),
            _AF(5, "COMP1_OUT", "comp1", "out", "out"),
        ]),
        _io(20, "PA17", "A", 17, B, 20, [
            _GPIO("A", 17),
            _ANA("ADC0_CH2", "adc0", "ch2"),
            _AF(2, "TIMG0_CCP1", "timg0", "ccp1", "out"),
        ]),
        _io(21, "PA18", "A", 18, B, 21, [
            _GPIO("A", 18),
            _ANA("ADC0_CH3", "adc0", "ch3"),
            _AF(2, "TIMA1_CCP0", "tima1", "ccp0", "out"),
        ]),
        _pwr(22, "AVDD", B),
        _gnd(23, "AVSS", B),
        _io(24, "PA19", "A", 19, B, 24, [
            _GPIO("A", 19),
            _ANA("ADC0_CH4", "adc0", "ch4"),
            _AF(2, "TIMA1_CCP0_C", "tima1", "ccp0_cmpl", "out"),
        ]),

        # ═══ RIGHT SIDE (pins 25–36, bottom to top) ═══
        _io(25, "PA20", "A", 20, R, 25, [
            _GPIO("A", 20),
            _ANA("ADC0_CH5", "adc0", "ch5"),
            _AF(2, "TIMA1_CCP1", "tima1", "ccp1", "out"),
            _ANA("DAC0_OUT", "dac0", "out"),
        ]),
        _io(26, "PA21", "A", 21, R, 26, [
            _GPIO("A", 21),
            _ANA("ADC0_CH6", "adc0", "ch6"),
            _AF(2, "TIMG6_CCP0", "timg6", "ccp0", "out"),
        ]),
        _io(27, "PA22", "A", 22, R, 27, [
            _GPIO("A", 22),
            _ANA("ADC0_CH7", "adc0", "ch7"),
            _AF(2, "TIMG6_CCP1", "timg6", "ccp1", "out"),
            _AF(4, "CAN0_TX", "can0", "tx", "out"),
        ]),
        _io(28, "PA23", "A", 23, R, 28, [
            _GPIO("A", 23),
            _AF(2, "TIMG0_CCP0", "timg0", "ccp0", "out"),
        ]),
        _spec(29, "NRST", R, "NRST"),
        _pwr(30, "VDD", R),
        _gnd(31, "GND", R),
        _io(32, "PA24", "A", 24, R, 32, [
            _GPIO("A", 24),
            _AF(2, "TIMG7_CCP0", "timg7", "ccp0", "out"),
            _AF(4, "CAN0_RX", "can0", "rx", "in"),
        ]),
        _io(33, "PA25", "A", 25, R, 33, [
            _GPIO("A", 25),
            _AF(2, "TIMG7_CCP1", "timg7", "ccp1", "out"),
            _AF(5, "I2C0_SCL", "i2c0", "scl", "io"),
        ]),
        _io(34, "PA26", "A", 26, R, 34, [
            _GPIO("A", 26),
            _AF(2, "TIMA1_CCP1_C", "tima1", "ccp1_cmpl", "out"),
            _AF(4, "CAN0_TX", "can0", "tx", "out"),
            _AF(5, "I2C0_SDA", "i2c0", "sda", "io"),
        ]),
        _io(35, "PA27", "A", 27, R, 35, [
            _GPIO("A", 27),
            _AF(2, "TIMA0_CCP0", "tima0", "ccp0", "out"),
            _AF(4, "CAN0_RX", "can0", "rx", "in"),
        ]),
        _io(36, "PA28", "A", 28, R, 36, [
            _GPIO("A", 28),
            _AF(2, "TIMA1_CCP0", "tima1", "ccp0", "out"),
            _AF(5, "SPI0_CS1", "spi0", "cs1", "out"),
        ]),

        # ═══ TOP SIDE (pins 37–48, right to left) ═══
        _io(37, "PA31", "A", 31, T, 37, [
            _GPIO("A", 31),
            _AF(2, "TIMA1_CCP1", "tima1", "ccp1", "out"),
            _AF(3, "UART0_TX", "uart0", "tx", "out"),
        ]),
        _io(38, "PB0", "B", 0, T, 38, [
            _GPIO("B", 0),
            _AF(2, "TIMA0_CCP0", "tima0", "ccp0", "out"),
            _AF(3, "UART0_RX", "uart0", "rx", "in"),
        ]),
        _spec(39, "XIN", T, "XIN"),
        _spec(40, "XOUT", T, "XOUT"),
        _io(41, "PB2", "B", 2, T, 41, [
            _GPIO("B", 2),
            _AF(4, "I2C1_SCL", "i2c1", "scl", "io"),
            _AF(5, "UART1_TX", "uart1", "tx", "out"),
        ]),
        _io(42, "PB3", "B", 3, T, 42, [
            _GPIO("B", 3),
            _AF(4, "I2C1_SDA", "i2c1", "sda", "io"),
            _AF(5, "UART1_RX", "uart1", "rx", "in"),
        ]),
        _io(43, "PB6", "B", 6, T, 43, [
            _GPIO("B", 6),
            _AF(2, "TIMG6_CCP0", "timg6", "ccp0", "out"),
            _AF(5, "UART1_CTS", "uart1", "cts", "in"),
        ]),
        _io(44, "PB7", "B", 7, T, 44, [
            _GPIO("B", 7),
            _AF(2, "TIMG6_CCP1", "timg6", "ccp1", "out"),
            _AF(5, "UART1_RTS", "uart1", "rts", "out"),
        ]),
        _pwr(45, "DVDD", T),
        _gnd(46, "DVSS", T),
        _io(47, "PB16", "B", 16, T, 47, [
            _GPIO("B", 16),
            _AF(2, "TIMG7_CCP0", "timg7", "ccp0", "out"),
        ]),
        _io(48, "PB22", "B", 22, T, 48, [
            _GPIO("B", 22),
            _AF(2, "TIMG7_CCP1", "timg7", "ccp1", "out"),
        ]),
    ]

    peripherals = [
        Peripheral("gpioa", "GPIO A", "ti,mspm0-gpio", [], "0x400a0000", "&gpioa"),
        Peripheral("gpiob", "GPIO B", "ti,mspm0-gpio", [], "0x400a2000", "&gpiob"),
        Peripheral("uart0", "UART 0", "ti,mspm0-uart", ["tx", "rx"], "0x40108000", "&uart0"),
        Peripheral("uart1", "UART 1", "ti,mspm0-uart", ["tx", "rx"], "0x40100000", "&uart1"),
        Peripheral("uart2", "UART 2", "ti,mspm0-uart", ["tx", "rx"], "0x40102000", "&uart2"),
        Peripheral("uart3", "UART 3", "ti,mspm0-uart", ["tx", "rx"], "0x40500000", "&uart3"),
        Peripheral("spi0",  "SPI 0",  "ti,mspm0-spi",  ["sclk", "pico", "poci", "cs0"], "", "&spi0"),
        Peripheral("spi1",  "SPI 1",  "ti,mspm0-spi",  ["sclk", "pico", "poci", "cs0"], "", "&spi1"),
        Peripheral("i2c0",  "I2C 0",  "ti,mspm0-i2c",  ["scl", "sda"], "", "&i2c0"),
        Peripheral("i2c1",  "I2C 1",  "ti,mspm0-i2c",  ["scl", "sda"], "", "&i2c1"),
        Peripheral("can0",  "CAN 0",  "ti,mspm0-can",  ["tx", "rx"], "", "&can0"),
        Peripheral("tima0", "Timer A0 (PWM)", "ti,mspm0-timer-pwm", ["ccp0", "ccp1", "ccp2", "ccp3"], "0x40860000", "&tima0"),
        Peripheral("tima1", "Timer A1 (PWM)", "ti,mspm0-timer-pwm", ["ccp0", "ccp1"], "0x40862000", "&tima1"),
        Peripheral("timg0", "Timer G0", "ti,mspm0-timer", ["ccp0", "ccp1"], "0x40084000", "&timg0"),
        Peripheral("timg6", "Timer G6", "ti,mspm0-timer", ["ccp0", "ccp1"], "0x40868000", "&timg6"),
        Peripheral("timg7", "Timer G7", "ti,mspm0-timer", ["ccp0", "ccp1"], "0x4086a000", "&timg7"),
        Peripheral("timg8", "Timer G8", "ti,mspm0-timer", ["ccp0", "ccp1"], "0x40090000", "&timg8"),
        Peripheral("timg12","Timer G12","ti,mspm0-timer", ["ccp0", "ccp1"], "0x40870000", "&timg12"),
        Peripheral("adc0",  "ADC 0",   "ti,mspm0-adc",  ["ch0","ch1","ch2","ch3","ch4","ch5","ch6","ch7"], "", "&adc0"),
        Peripheral("dac0",  "DAC 0",   "ti,mspm0-dac",  ["out"], "", "&dac0"),
        Peripheral("comp0", "Comp 0",  "ti,mspm0-comp", ["out"], "", "&comp0"),
        Peripheral("comp1", "Comp 1",  "ti,mspm0-comp", ["out"], "", "&comp1"),
    ]

    return BoardDef(
        soc="MSPM0G3507",
        board="lp_mspm0g3507",
        vendor="ti",
        package="QFP-48",
        pin_count=48,
        pins=pins,
        peripherals=peripherals,
        dts_soc_include="<ti/mspm0/g/mspm0g3507.dtsi>",
        dts_pinctrl_include="<ti/mspm0g1x0x_g3x0x/mspm0g350x-pinctrl.dtsi>",
        pinctrl_header="mspm0-pinctrl.h",
        flash_size_kb=128,
        sram_size_kb=32,
        clock_hz=80_000_000,
    )
