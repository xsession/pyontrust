"""
Raspberry Pi Pico board definition for the Pin Configurator.

The board models the 40-pin Pico header around the dual-core RP2040 SoC and
provides common UART/I2C/SPI/PWM/ADC alternate functions that can be exported
to Zephyr, Arduino, and bare-metal starter files.
"""

from __future__ import annotations

from board_schema import (
    AltFunction,
    BoardDef,
    Core,
    OutputKind,
    OutputTarget,
    Peripheral,
    Pin,
    PinKind,
    PinSide,
)


def _af(function_id: int, gpio_num: int, name: str, peripheral: str, signal: str, direction: str = "io") -> AltFunction:
    zephyr_pinmux = f"{name}_GP{gpio_num}" if peripheral != "gpio0" else f"GPIO_GP{gpio_num}"
    return AltFunction(
        function_id=function_id,
        pincm=gpio_num + 1,
        name=name,
        peripheral=peripheral,
        signal=signal,
        direction=direction,
        zephyr_pinmux=zephyr_pinmux,
    )


def _gpio_pin(number: int, gpio_num: int, side: PinSide, extra_functions: list[tuple[int, str, str, str, str]]) -> Pin:
    functions = [_af(1, gpio_num, f"GPIO{gpio_num}", "gpio0", f"gp{gpio_num}")]
    for function_id, name, peripheral, signal, direction in extra_functions:
        functions.append(_af(function_id, gpio_num, name, peripheral, signal, direction))
    return Pin(
        number=number,
        name=f"GP{gpio_num}",
        port="GPIO",
        gpio_num=gpio_num,
        kind=PinKind.IO,
        side=side,
        alt_functions=functions,
        default_function="GPIO",
    )


def _special_pin(number: int, name: str, side: PinSide, kind: PinKind, default_function: str) -> Pin:
    return Pin(
        number=number,
        name=name,
        kind=kind,
        side=side,
        default_function=default_function,
    )


_GPIO_FUNCTIONS = {
    0: [(2, "UART0_TX", "uart0", "tx", "out"), (3, "I2C0_SDA", "i2c0", "sda", "io"), (4, "SPI0_RX", "spi0", "rx", "in"), (5, "PWM0_A", "pwm0", "a", "out")],
    1: [(2, "UART0_RX", "uart0", "rx", "in"), (3, "I2C0_SCL", "i2c0", "scl", "io"), (4, "SPI0_CSN", "spi0", "cs", "out"), (5, "PWM0_B", "pwm0", "b", "out")],
    2: [(2, "UART0_CTS", "uart0", "cts", "in"), (3, "I2C1_SDA", "i2c1", "sda", "io"), (4, "SPI0_SCK", "spi0", "sck", "out"), (5, "PWM1_A", "pwm1", "a", "out")],
    3: [(2, "UART0_RTS", "uart0", "rts", "out"), (3, "I2C1_SCL", "i2c1", "scl", "io"), (4, "SPI0_TX", "spi0", "tx", "out"), (5, "PWM1_B", "pwm1", "b", "out")],
    4: [(2, "UART1_TX", "uart1", "tx", "out"), (3, "I2C0_SDA", "i2c0", "sda", "io"), (4, "SPI0_RX", "spi0", "rx", "in"), (5, "PWM2_A", "pwm2", "a", "out")],
    5: [(2, "UART1_RX", "uart1", "rx", "in"), (3, "I2C0_SCL", "i2c0", "scl", "io"), (4, "SPI0_CSN", "spi0", "cs", "out"), (5, "PWM2_B", "pwm2", "b", "out")],
    6: [(2, "UART1_CTS", "uart1", "cts", "in"), (3, "I2C1_SDA", "i2c1", "sda", "io"), (4, "SPI0_SCK", "spi0", "sck", "out"), (5, "PWM3_A", "pwm3", "a", "out")],
    7: [(2, "UART1_RTS", "uart1", "rts", "out"), (3, "I2C1_SCL", "i2c1", "scl", "io"), (4, "SPI0_TX", "spi0", "tx", "out"), (5, "PWM3_B", "pwm3", "b", "out")],
    8: [(2, "UART1_TX", "uart1", "tx", "out"), (3, "I2C0_SDA", "i2c0", "sda", "io"), (4, "SPI1_RX", "spi1", "rx", "in"), (5, "PWM4_A", "pwm4", "a", "out")],
    9: [(2, "UART1_RX", "uart1", "rx", "in"), (3, "I2C0_SCL", "i2c0", "scl", "io"), (4, "SPI1_CSN", "spi1", "cs", "out"), (5, "PWM4_B", "pwm4", "b", "out")],
    10: [(2, "UART1_CTS", "uart1", "cts", "in"), (3, "I2C1_SDA", "i2c1", "sda", "io"), (4, "SPI1_SCK", "spi1", "sck", "out"), (5, "PWM5_A", "pwm5", "a", "out")],
    11: [(2, "UART1_RTS", "uart1", "rts", "out"), (3, "I2C1_SCL", "i2c1", "scl", "io"), (4, "SPI1_TX", "spi1", "tx", "out"), (5, "PWM5_B", "pwm5", "b", "out")],
    12: [(2, "UART0_TX", "uart0", "tx", "out"), (3, "I2C0_SDA", "i2c0", "sda", "io"), (4, "SPI1_RX", "spi1", "rx", "in"), (5, "PWM6_A", "pwm6", "a", "out")],
    13: [(2, "UART0_RX", "uart0", "rx", "in"), (3, "I2C0_SCL", "i2c0", "scl", "io"), (4, "SPI1_CSN", "spi1", "cs", "out"), (5, "PWM6_B", "pwm6", "b", "out")],
    14: [(2, "UART0_CTS", "uart0", "cts", "in"), (3, "I2C1_SDA", "i2c1", "sda", "io"), (4, "SPI1_SCK", "spi1", "sck", "out"), (5, "PWM7_A", "pwm7", "a", "out")],
    15: [(2, "UART0_RTS", "uart0", "rts", "out"), (3, "I2C1_SCL", "i2c1", "scl", "io"), (4, "SPI1_TX", "spi1", "tx", "out"), (5, "PWM7_B", "pwm7", "b", "out")],
    16: [(2, "UART0_TX", "uart0", "tx", "out"), (3, "I2C0_SDA", "i2c0", "sda", "io"), (4, "SPI0_RX", "spi0", "rx", "in"), (5, "PWM0_A", "pwm0", "a", "out")],
    17: [(2, "UART0_RX", "uart0", "rx", "in"), (3, "I2C0_SCL", "i2c0", "scl", "io"), (4, "SPI0_CSN", "spi0", "cs", "out"), (5, "PWM0_B", "pwm0", "b", "out")],
    18: [(2, "UART0_CTS", "uart0", "cts", "in"), (3, "I2C1_SDA", "i2c1", "sda", "io"), (4, "SPI0_SCK", "spi0", "sck", "out"), (5, "PWM1_A", "pwm1", "a", "out")],
    19: [(2, "UART0_RTS", "uart0", "rts", "out"), (3, "I2C1_SCL", "i2c1", "scl", "io"), (4, "SPI0_TX", "spi0", "tx", "out"), (5, "PWM1_B", "pwm1", "b", "out")],
    20: [(2, "UART1_TX", "uart1", "tx", "out"), (3, "I2C0_SDA", "i2c0", "sda", "io"), (4, "SPI0_RX", "spi0", "rx", "in"), (5, "PWM2_A", "pwm2", "a", "out")],
    21: [(2, "UART1_RX", "uart1", "rx", "in"), (3, "I2C0_SCL", "i2c0", "scl", "io"), (4, "SPI0_CSN", "spi0", "cs", "out"), (5, "PWM2_B", "pwm2", "b", "out")],
    22: [(2, "PWM3_A", "pwm3", "a", "out")],
    26: [(2, "ADC0", "adc0", "ch0", "analog"), (3, "PWM5_A", "pwm5", "a", "out")],
    27: [(2, "ADC1", "adc0", "ch1", "analog"), (3, "PWM5_B", "pwm5", "b", "out")],
    28: [(2, "ADC2", "adc0", "ch2", "analog"), (3, "PWM6_A", "pwm6", "a", "out")],
}


def build_rpi_pico() -> BoardDef:
    shared_cores = ["core0", "core1"]
    pins = [
        _gpio_pin(1, 0, PinSide.LEFT, _GPIO_FUNCTIONS[0]),
        _gpio_pin(2, 1, PinSide.LEFT, _GPIO_FUNCTIONS[1]),
        _special_pin(3, "GND", PinSide.LEFT, PinKind.GND, "Ground"),
        _gpio_pin(4, 2, PinSide.LEFT, _GPIO_FUNCTIONS[2]),
        _gpio_pin(5, 3, PinSide.LEFT, _GPIO_FUNCTIONS[3]),
        _gpio_pin(6, 4, PinSide.LEFT, _GPIO_FUNCTIONS[4]),
        _gpio_pin(7, 5, PinSide.LEFT, _GPIO_FUNCTIONS[5]),
        _special_pin(8, "GND", PinSide.LEFT, PinKind.GND, "Ground"),
        _gpio_pin(9, 6, PinSide.LEFT, _GPIO_FUNCTIONS[6]),
        _gpio_pin(10, 7, PinSide.LEFT, _GPIO_FUNCTIONS[7]),
        _gpio_pin(11, 8, PinSide.LEFT, _GPIO_FUNCTIONS[8]),
        _gpio_pin(12, 9, PinSide.LEFT, _GPIO_FUNCTIONS[9]),
        _special_pin(13, "GND", PinSide.LEFT, PinKind.GND, "Ground"),
        _gpio_pin(14, 10, PinSide.LEFT, _GPIO_FUNCTIONS[10]),
        _gpio_pin(15, 11, PinSide.LEFT, _GPIO_FUNCTIONS[11]),
        _gpio_pin(16, 12, PinSide.LEFT, _GPIO_FUNCTIONS[12]),
        _gpio_pin(17, 13, PinSide.LEFT, _GPIO_FUNCTIONS[13]),
        _special_pin(18, "GND", PinSide.LEFT, PinKind.GND, "Ground"),
        _gpio_pin(19, 14, PinSide.LEFT, _GPIO_FUNCTIONS[14]),
        _gpio_pin(20, 15, PinSide.LEFT, _GPIO_FUNCTIONS[15]),
        _gpio_pin(21, 16, PinSide.RIGHT, _GPIO_FUNCTIONS[16]),
        _gpio_pin(22, 17, PinSide.RIGHT, _GPIO_FUNCTIONS[17]),
        _special_pin(23, "GND", PinSide.RIGHT, PinKind.GND, "Ground"),
        _gpio_pin(24, 18, PinSide.RIGHT, _GPIO_FUNCTIONS[18]),
        _gpio_pin(25, 19, PinSide.RIGHT, _GPIO_FUNCTIONS[19]),
        _gpio_pin(26, 20, PinSide.RIGHT, _GPIO_FUNCTIONS[20]),
        _gpio_pin(27, 21, PinSide.RIGHT, _GPIO_FUNCTIONS[21]),
        _special_pin(28, "GND", PinSide.RIGHT, PinKind.GND, "Ground"),
        _gpio_pin(29, 22, PinSide.RIGHT, _GPIO_FUNCTIONS[22]),
        _special_pin(30, "RUN", PinSide.RIGHT, PinKind.SPEC, "Reset"),
        _gpio_pin(31, 26, PinSide.RIGHT, _GPIO_FUNCTIONS[26]),
        _gpio_pin(32, 27, PinSide.RIGHT, _GPIO_FUNCTIONS[27]),
        _special_pin(33, "AGND", PinSide.RIGHT, PinKind.GND, "Analog Ground"),
        _gpio_pin(34, 28, PinSide.RIGHT, _GPIO_FUNCTIONS[28]),
        _special_pin(35, "ADC_VREF", PinSide.RIGHT, PinKind.SPEC, "ADC Reference"),
        _special_pin(36, "3V3_OUT", PinSide.RIGHT, PinKind.PWR, "3.3V Output"),
        _special_pin(37, "3V3_EN", PinSide.RIGHT, PinKind.SPEC, "3.3V Enable"),
        _special_pin(38, "GND", PinSide.RIGHT, PinKind.GND, "Ground"),
        _special_pin(39, "VSYS", PinSide.RIGHT, PinKind.PWR, "System Supply"),
        _special_pin(40, "VBUS", PinSide.RIGHT, PinKind.PWR, "USB 5V"),
    ]

    peripherals = [
        Peripheral("gpio0", "GPIO Bank 0", "raspberrypi,rp2040-gpio", ["pins"], dts_node="&gpio0", core_id="core0", available_cores=shared_cores),
        Peripheral("uart0", "UART 0", "raspberrypi,rp2040-uart", ["tx", "rx", "cts", "rts"], dts_node="&uart0", core_id="core0", available_cores=shared_cores),
        Peripheral("uart1", "UART 1", "raspberrypi,rp2040-uart", ["tx", "rx", "cts", "rts"], dts_node="&uart1", core_id="core0", available_cores=shared_cores),
        Peripheral("i2c0", "I2C 0", "raspberrypi,rp2040-i2c", ["sda", "scl"], dts_node="&i2c0", core_id="core0", available_cores=shared_cores),
        Peripheral("i2c1", "I2C 1", "raspberrypi,rp2040-i2c", ["sda", "scl"], dts_node="&i2c1", core_id="core0", available_cores=shared_cores),
        Peripheral("spi0", "SPI 0", "raspberrypi,rp2040-spi", ["rx", "tx", "sck", "cs"], dts_node="&spi0", core_id="core0", available_cores=shared_cores),
        Peripheral("spi1", "SPI 1", "raspberrypi,rp2040-spi", ["rx", "tx", "sck", "cs"], dts_node="&spi1", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm0", "PWM Slice 0", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm0", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm1", "PWM Slice 1", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm1", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm2", "PWM Slice 2", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm2", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm3", "PWM Slice 3", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm3", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm4", "PWM Slice 4", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm4", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm5", "PWM Slice 5", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm5", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm6", "PWM Slice 6", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm6", core_id="core0", available_cores=shared_cores),
        Peripheral("pwm7", "PWM Slice 7", "raspberrypi,rp2040-pwm", ["a", "b"], dts_node="&pwm7", core_id="core0", available_cores=shared_cores),
        Peripheral("adc0", "ADC", "raspberrypi,rp2040-adc", ["ch0", "ch1", "ch2"], dts_node="&adc", core_id="core0", available_cores=shared_cores),
    ]

    return BoardDef(
        soc="RP2040",
        board="rpi_pico",
        vendor="raspberrypi",
        package="Pico DIP-40",
        pin_count=40,
        pins=pins,
        peripherals=peripherals,
        cores=[
            Core("core0", "Cortex-M0+ Core 0", "armv6-m", role="primary", clock_hz=133_000_000, default=True),
            Core("core1", "Cortex-M0+ Core 1", "armv6-m", role="secondary", clock_hz=133_000_000, default=False),
        ],
        output_targets=[
            OutputTarget(OutputKind.ZEPHYR, "Zephyr", [".overlay", "prj.conf"]),
            OutputTarget(OutputKind.ARDUINO, "Arduino", [".ino", ".h"]),
            OutputTarget(OutputKind.BAREMETAL, "Bare Metal", [".c", ".h"]),
        ],
        dts_soc_include="<raspberrypi/rp2040.dtsi>",
        dts_pinctrl_include="<zephyr/dt-bindings/pinctrl/rpi-pico-pinctrl.h>",
        pinctrl_header="rpi-pico-pinctrl.h",
        flash_size_kb=2048,
        sram_size_kb=264,
        clock_hz=133_000_000,
    )