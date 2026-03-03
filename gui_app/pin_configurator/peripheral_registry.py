"""
Peripheral Configurator – registry of MCU peripheral templates.

Each peripheral template describes:
  - DTS node properties (status, label, baud-rate, etc.)
  - Kconfig dependencies
  - Configuration groups and options
  - Pin signal requirements

This module is board-agnostic: it describes *what* a UART/SPI/I2C/etc.
supports.  Board-specific instance data (base address, interrupts) comes
from the board definition files.
"""

from __future__ import annotations

# ── Peripheral Template Schema ─────────────────────────────────────────
#
# {
#   "id":          "uart",
#   "name":        "UART",
#   "icon":        "📡",
#   "desc":        "Universal Asynchronous Receiver/Transmitter",
#   "compatible":  ["ti,mspm0-uart"],          # matching DTS compatibles
#   "signals":     ["tx", "rx", "cts", "rts"], # required / optional pins
#   "kconfig":     ["CONFIG_SERIAL=y"],
#   "groups": [
#     {
#       "id":    "general",
#       "title": "General",
#       "props": [
#         {
#           "key":     "current-speed",
#           "label":   "Baud Rate",
#           "type":    "choice",
#           "choices": [9600, 19200, 38400, 57600, 115200, 230400, ...],
#           "default": 115200,
#           "help":    "Serial port baud rate",
#           "dts":     true,           # emitted into DTS overlay
#           "kconfig": null,           # or "CONFIG_UART_x_BAUD_RATE"
#         }, ...
#       ]
#     }
#   ]
# }

PERIPHERAL_TEMPLATES: list[dict] = [
    # ── UART / Serial ──────────────────────────────────────────────────
    {
        "id":         "uart",
        "name":       "UART",
        "icon":       "📡",
        "desc":       "Universal Asynchronous Receiver/Transmitter",
        "compatible": ["ti,mspm0-uart", "ns16550", "nordic,nrf-uarte",
                       "st,stm32-usart", "espressif,esp32-uart"],
        "signals":    ["tx", "rx", "cts", "rts"],
        "kconfig":    ["CONFIG_SERIAL=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this peripheral in the DTS",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "label",
                        "label": "Node Label",
                        "type": "string",
                        "default": "",
                        "help": "Optional DTS label (e.g. 'console_uart')",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "serial",
                "title": "Serial Parameters",
                "props": [
                    {
                        "key": "current-speed",
                        "label": "Baud Rate",
                        "type": "choice",
                        "choices": [1200, 2400, 4800, 9600, 14400, 19200,
                                    38400, 57600, 115200, 230400, 460800,
                                    921600, 1000000, 2000000, 3000000],
                        "default": 115200,
                        "help": "Serial port baud rate (bps)",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "hw-flow-control",
                        "label": "HW Flow Control",
                        "type": "bool",
                        "default": False,
                        "help": "Enable RTS/CTS hardware flow control",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "parity",
                        "label": "Parity",
                        "type": "choice",
                        "choices": ["none", "odd", "even"],
                        "default": "none",
                        "help": "Parity bit configuration",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "stop-bits",
                        "label": "Stop Bits",
                        "type": "choice",
                        "choices": ["1", "2"],
                        "default": "1",
                        "help": "Number of stop bits",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "data-bits",
                        "label": "Data Bits",
                        "type": "choice",
                        "choices": ["7", "8", "9"],
                        "default": "8",
                        "help": "Number of data bits per frame",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "features",
                "title": "Features",
                "props": [
                    {
                        "key": "CONFIG_UART_INTERRUPT_DRIVEN",
                        "label": "Interrupt-Driven API",
                        "type": "bool",
                        "default": True,
                        "help": "Enable interrupt-driven UART API",
                        "dts": False,
                        "kconfig": "CONFIG_UART_INTERRUPT_DRIVEN",
                    },
                    {
                        "key": "CONFIG_UART_ASYNC_API",
                        "label": "Async API (DMA)",
                        "type": "bool",
                        "default": False,
                        "help": "Enable DMA-based asynchronous UART API",
                        "dts": False,
                        "kconfig": "CONFIG_UART_ASYNC_API",
                    },
                    {
                        "key": "CONFIG_UART_LINE_CTRL",
                        "label": "Line Control",
                        "type": "bool",
                        "default": False,
                        "help": "Enable UART line control API (baud, etc.)",
                        "dts": False,
                        "kconfig": "CONFIG_UART_LINE_CTRL",
                    },
                ],
            },
            {
                "id": "console",
                "title": "Console",
                "props": [
                    {
                        "key": "CONFIG_UART_CONSOLE",
                        "label": "Console UART",
                        "type": "bool",
                        "default": False,
                        "help": "Use this UART as Zephyr console output",
                        "dts": False,
                        "kconfig": "CONFIG_UART_CONSOLE",
                    },
                    {
                        "key": "CONFIG_CONSOLE",
                        "label": "Console Subsystem",
                        "type": "bool",
                        "default": False,
                        "help": "Enable the console subsystem",
                        "dts": False,
                        "kconfig": "CONFIG_CONSOLE",
                    },
                ],
            },
        ],
    },

    # ── SPI ────────────────────────────────────────────────────────────
    {
        "id":         "spi",
        "name":       "SPI",
        "icon":       "🔄",
        "desc":       "Serial Peripheral Interface",
        "compatible": ["ti,mspm0-spi", "nordic,nrf-spim", "st,stm32-spi",
                       "espressif,esp32-spi"],
        "signals":    ["sclk", "pico", "poci", "cs0", "cs1", "cs2", "cs3"],
        "kconfig":    ["CONFIG_SPI=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this SPI controller",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "label",
                        "label": "Node Label",
                        "type": "string",
                        "default": "",
                        "help": "Optional DTS label",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "bus",
                "title": "Bus Configuration",
                "props": [
                    {
                        "key": "clock-frequency",
                        "label": "Clock Frequency (Hz)",
                        "type": "int",
                        "default": 1000000,
                        "help": "SPI clock frequency in Hz",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "cs-gpios-active-low",
                        "label": "CS Active Low",
                        "type": "bool",
                        "default": True,
                        "help": "Chip select is active-low (standard)",
                        "dts": False,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "features",
                "title": "Features",
                "props": [
                    {
                        "key": "CONFIG_SPI_ASYNC",
                        "label": "Async API (DMA)",
                        "type": "bool",
                        "default": False,
                        "help": "Enable DMA-based asynchronous SPI API",
                        "dts": False,
                        "kconfig": "CONFIG_SPI_ASYNC",
                    },
                    {
                        "key": "CONFIG_SPI_SLAVE",
                        "label": "Slave Support",
                        "type": "bool",
                        "default": False,
                        "help": "Enable SPI slave mode support",
                        "dts": False,
                        "kconfig": "CONFIG_SPI_SLAVE",
                    },
                    {
                        "key": "CONFIG_SPI_EXTENDED_MODES",
                        "label": "Extended Modes",
                        "type": "bool",
                        "default": False,
                        "help": "Enable dual/quad/octal SPI modes",
                        "dts": False,
                        "kconfig": "CONFIG_SPI_EXTENDED_MODES",
                    },
                ],
            },
        ],
    },

    # ── I2C ────────────────────────────────────────────────────────────
    {
        "id":         "i2c",
        "name":       "I²C",
        "icon":       "🔗",
        "desc":       "Inter-Integrated Circuit bus",
        "compatible": ["ti,mspm0-i2c", "nordic,nrf-twim", "st,stm32-i2c",
                       "espressif,esp32-i2c"],
        "signals":    ["scl", "sda"],
        "kconfig":    ["CONFIG_I2C=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this I2C controller",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "label",
                        "label": "Node Label",
                        "type": "string",
                        "default": "",
                        "help": "Optional DTS label",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "bus",
                "title": "Bus Configuration",
                "props": [
                    {
                        "key": "clock-frequency",
                        "label": "Bus Speed",
                        "type": "choice",
                        "choices": [100000, 400000, 1000000, 3400000],
                        "default": 400000,
                        "help": "I2C bus speed: 100k=Standard, 400k=Fast, 1M=Fast+, 3.4M=HS",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "features",
                "title": "Features",
                "props": [
                    {
                        "key": "CONFIG_I2C_TARGET",
                        "label": "Target (Slave) Mode",
                        "type": "bool",
                        "default": False,
                        "help": "Enable I2C target/slave mode support",
                        "dts": False,
                        "kconfig": "CONFIG_I2C_TARGET",
                    },
                    {
                        "key": "CONFIG_I2C_CALLBACK",
                        "label": "Callback API",
                        "type": "bool",
                        "default": False,
                        "help": "Enable I2C async callback API",
                        "dts": False,
                        "kconfig": "CONFIG_I2C_CALLBACK",
                    },
                ],
            },
            {
                "id": "devices",
                "title": "Child Devices",
                "props": [
                    {
                        "key": "child-device",
                        "label": "Add I2C Device",
                        "type": "string",
                        "default": "",
                        "help": "compatible@addr (e.g. bosch,bme280@76)",
                        "dts": False,
                        "kconfig": None,
                    },
                ],
            },
        ],
    },

    # ── CAN ────────────────────────────────────────────────────────────
    {
        "id":         "can",
        "name":       "CAN Bus",
        "icon":       "🚗",
        "desc":       "Controller Area Network",
        "compatible": ["ti,mspm0-can", "st,stm32-fdcan", "espressif,esp32-twai",
                       "microchip,mcp2515", "bosch,m-can"],
        "signals":    ["tx", "rx"],
        "kconfig":    ["CONFIG_CAN=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this CAN controller",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "label",
                        "label": "Node Label",
                        "type": "string",
                        "default": "",
                        "help": "Optional DTS label",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "timing",
                "title": "Bus Timing",
                "props": [
                    {
                        "key": "bus-speed",
                        "label": "Bitrate",
                        "type": "choice",
                        "choices": [10000, 20000, 50000, 100000, 125000,
                                    250000, 500000, 800000, 1000000],
                        "default": 500000,
                        "help": "CAN bus bitrate in bps",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "sample-point",
                        "label": "Sample Point (‰)",
                        "type": "int",
                        "default": 875,
                        "help": "Bit sample point in per-mille (e.g. 875 = 87.5%)",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "fd",
                "title": "CAN FD",
                "props": [
                    {
                        "key": "CONFIG_CAN_FD_MODE",
                        "label": "CAN FD Mode",
                        "type": "bool",
                        "default": False,
                        "help": "Enable CAN Flexible Data-rate support",
                        "dts": False,
                        "kconfig": "CONFIG_CAN_FD_MODE",
                    },
                    {
                        "key": "bus-speed-data",
                        "label": "FD Data Bitrate",
                        "type": "choice",
                        "choices": [500000, 1000000, 2000000, 4000000, 5000000, 8000000],
                        "default": 2000000,
                        "help": "CAN FD data phase bitrate",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "sample-point-data",
                        "label": "FD Sample Point (‰)",
                        "type": "int",
                        "default": 750,
                        "help": "CAN FD data phase sample point in per-mille",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "protocols",
                "title": "Protocols",
                "props": [
                    {
                        "key": "CONFIG_CANOPEN",
                        "label": "CANopen",
                        "type": "bool",
                        "default": False,
                        "help": "Enable CANopen protocol stack",
                        "dts": False,
                        "kconfig": "CONFIG_CANOPEN",
                    },
                    {
                        "key": "CONFIG_ISOTP",
                        "label": "ISO-TP",
                        "type": "bool",
                        "default": False,
                        "help": "Enable ISO 15765-2 (ISO-TP) transport protocol",
                        "dts": False,
                        "kconfig": "CONFIG_ISOTP",
                    },
                    {
                        "key": "CONFIG_CAN_STATS",
                        "label": "Statistics",
                        "type": "bool",
                        "default": False,
                        "help": "Enable CAN bus statistics (error counters, etc.)",
                        "dts": False,
                        "kconfig": "CONFIG_CAN_STATS",
                    },
                ],
            },
        ],
    },

    # ── Timer / PWM ────────────────────────────────────────────────────
    {
        "id":         "timer",
        "name":       "Timer / PWM",
        "icon":       "⏱️",
        "desc":       "Hardware timers, PWM outputs, and counter inputs",
        "compatible": ["ti,mspm0-timer", "ti,mspm0-timer-pwm",
                       "nordic,nrf-timer", "st,stm32-timers",
                       "espressif,esp32-ledc"],
        "signals":    ["ccp0", "ccp1", "ccp2", "ccp3"],
        "kconfig":    [],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this timer",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "label",
                        "label": "Node Label",
                        "type": "string",
                        "default": "",
                        "help": "Optional DTS label",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "mode",
                "title": "Mode",
                "props": [
                    {
                        "key": "timer-mode",
                        "label": "Operating Mode",
                        "type": "choice",
                        "choices": ["counter", "pwm", "capture", "one-shot"],
                        "default": "pwm",
                        "help": "Primary timer operating mode",
                        "dts": False,
                        "kconfig": None,
                    },
                    {
                        "key": "CONFIG_PWM",
                        "label": "PWM Subsystem",
                        "type": "bool",
                        "default": True,
                        "help": "Enable Zephyr PWM subsystem",
                        "dts": False,
                        "kconfig": "CONFIG_PWM",
                    },
                    {
                        "key": "CONFIG_COUNTER",
                        "label": "Counter Subsystem",
                        "type": "bool",
                        "default": False,
                        "help": "Enable Zephyr counter/timer subsystem",
                        "dts": False,
                        "kconfig": "CONFIG_COUNTER",
                    },
                ],
            },
            {
                "id": "pwm",
                "title": "PWM Settings",
                "props": [
                    {
                        "key": "pwm-frequency",
                        "label": "PWM Frequency (Hz)",
                        "type": "int",
                        "default": 1000,
                        "help": "Target PWM output frequency",
                        "dts": False,
                        "kconfig": None,
                    },
                    {
                        "key": "pwm-duty",
                        "label": "Initial Duty (%)",
                        "type": "int",
                        "default": 50,
                        "help": "Initial duty cycle percentage",
                        "dts": False,
                        "kconfig": None,
                    },
                    {
                        "key": "num-channels",
                        "label": "Channels Used",
                        "type": "int",
                        "default": 1,
                        "help": "Number of PWM/capture channels to configure",
                        "dts": False,
                        "kconfig": None,
                    },
                ],
            },
        ],
    },

    # ── ADC ────────────────────────────────────────────────────────────
    {
        "id":         "adc",
        "name":       "ADC",
        "icon":       "📊",
        "desc":       "Analog-to-Digital Converter",
        "compatible": ["ti,mspm0-adc", "nordic,nrf-saadc",
                       "st,stm32-adc", "espressif,esp32-adc"],
        "signals":    ["ch0", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7"],
        "kconfig":    ["CONFIG_ADC=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this ADC",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "sampling",
                "title": "Sampling",
                "props": [
                    {
                        "key": "resolution",
                        "label": "Resolution (bits)",
                        "type": "choice",
                        "choices": [8, 10, 12, 14, 16],
                        "default": 12,
                        "help": "ADC conversion resolution",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "reference-voltage",
                        "label": "Reference (mV)",
                        "type": "int",
                        "default": 3300,
                        "help": "ADC reference voltage in millivolts",
                        "dts": False,
                        "kconfig": None,
                    },
                    {
                        "key": "oversampling",
                        "label": "Oversampling",
                        "type": "choice",
                        "choices": ["none", "2x", "4x", "8x", "16x", "32x", "64x"],
                        "default": "none",
                        "help": "Hardware oversampling ratio",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "channels",
                "title": "Channel Config",
                "props": [
                    {
                        "key": "num-channels",
                        "label": "Active Channels",
                        "type": "int",
                        "default": 1,
                        "help": "Number of ADC channels to configure",
                        "dts": False,
                        "kconfig": None,
                    },
                    {
                        "key": "CONFIG_ADC_ASYNC",
                        "label": "Async API",
                        "type": "bool",
                        "default": False,
                        "help": "Enable ADC async/callback API",
                        "dts": False,
                        "kconfig": "CONFIG_ADC_ASYNC",
                    },
                ],
            },
        ],
    },

    # ── DAC ────────────────────────────────────────────────────────────
    {
        "id":         "dac",
        "name":       "DAC",
        "icon":       "📈",
        "desc":       "Digital-to-Analog Converter",
        "compatible": ["ti,mspm0-dac", "nordic,nrf-dac",
                       "st,stm32-dac", "microchip,mcp4725"],
        "signals":    ["out"],
        "kconfig":    ["CONFIG_DAC=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this DAC",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "output",
                "title": "Output",
                "props": [
                    {
                        "key": "resolution",
                        "label": "Resolution (bits)",
                        "type": "choice",
                        "choices": [8, 10, 12],
                        "default": 12,
                        "help": "DAC output resolution",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "reference-voltage",
                        "label": "Reference (mV)",
                        "type": "int",
                        "default": 3300,
                        "help": "DAC reference voltage in millivolts",
                        "dts": False,
                        "kconfig": None,
                    },
                ],
            },
        ],
    },

    # ── GPIO ───────────────────────────────────────────────────────────
    {
        "id":         "gpio",
        "name":       "GPIO",
        "icon":       "📌",
        "desc":       "General-Purpose I/O port",
        "compatible": ["ti,mspm0-gpio", "nordic,nrf-gpio",
                       "st,stm32-gpio", "espressif,esp32-gpio"],
        "signals":    [],
        "kconfig":    ["CONFIG_GPIO=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this GPIO port",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "features",
                "title": "Features",
                "props": [
                    {
                        "key": "CONFIG_GPIO_GET_DIRECTION",
                        "label": "Get Direction API",
                        "type": "bool",
                        "default": False,
                        "help": "Enable API to read pin direction at runtime",
                        "dts": False,
                        "kconfig": "CONFIG_GPIO_GET_DIRECTION",
                    },
                    {
                        "key": "CONFIG_GPIO_GET_CONFIG",
                        "label": "Get Config API",
                        "type": "bool",
                        "default": False,
                        "help": "Enable API to read pin config at runtime",
                        "dts": False,
                        "kconfig": "CONFIG_GPIO_GET_CONFIG",
                    },
                    {
                        "key": "CONFIG_GPIO_ENABLE_DISABLE_INTERRUPT",
                        "label": "En/Dis Interrupt API",
                        "type": "bool",
                        "default": False,
                        "help": "Enable API to enable/disable GPIO interrupts",
                        "dts": False,
                        "kconfig": "CONFIG_GPIO_ENABLE_DISABLE_INTERRUPT",
                    },
                ],
            },
        ],
    },

    # ── Comparator ─────────────────────────────────────────────────────
    {
        "id":         "comp",
        "name":       "Comparator",
        "icon":       "⚖️",
        "desc":       "Analog comparator",
        "compatible": ["ti,mspm0-comp"],
        "signals":    ["inp", "inn", "out"],
        "kconfig":    [],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable this comparator",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "config",
                "title": "Configuration",
                "props": [
                    {
                        "key": "hysteresis",
                        "label": "Hysteresis",
                        "type": "choice",
                        "choices": ["none", "10mV", "20mV", "30mV"],
                        "default": "none",
                        "help": "Comparator hysteresis level",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "output-polarity",
                        "label": "Output Polarity",
                        "type": "choice",
                        "choices": ["non-inverted", "inverted"],
                        "default": "non-inverted",
                        "help": "Comparator output polarity",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
        ],
    },

    # ── Watchdog ───────────────────────────────────────────────────────
    {
        "id":         "watchdog",
        "name":       "Watchdog",
        "icon":       "🐕",
        "desc":       "Watchdog timer for system reset on hang",
        "compatible": ["ti,mspm0-watchdog", "nordic,nrf-wdt",
                       "st,stm32-watchdog"],
        "signals":    [],
        "kconfig":    ["CONFIG_WATCHDOG=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "disabled",
                        "help": "Enable or disable the watchdog",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "timing",
                "title": "Timing",
                "props": [
                    {
                        "key": "timeout-period",
                        "label": "Timeout (ms)",
                        "type": "int",
                        "default": 2000,
                        "help": "Watchdog timeout period in milliseconds",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "CONFIG_WDT_DISABLE_AT_BOOT",
                        "label": "Disable at Boot",
                        "type": "bool",
                        "default": True,
                        "help": "Disable watchdog automatically at startup",
                        "dts": False,
                        "kconfig": "CONFIG_WDT_DISABLE_AT_BOOT",
                    },
                ],
            },
        ],
    },

    # ── DMA ────────────────────────────────────────────────────────────
    {
        "id":         "dma",
        "name":       "DMA",
        "icon":       "🔀",
        "desc":       "Direct Memory Access controller",
        "compatible": ["ti,mspm0-dma", "nordic,nrf-dma",
                       "st,stm32-dma", "espressif,esp32-gdma"],
        "signals":    [],
        "kconfig":    ["CONFIG_DMA=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "okay",
                        "help": "Enable or disable the DMA controller",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "config",
                "title": "Configuration",
                "props": [
                    {
                        "key": "dma-channels",
                        "label": "Available Channels",
                        "type": "int",
                        "default": 4,
                        "help": "Number of DMA channels available",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
        ],
    },

    # ── RTC ────────────────────────────────────────────────────────────
    {
        "id":         "rtc",
        "name":       "RTC",
        "icon":       "🕐",
        "desc":       "Real-Time Clock",
        "compatible": ["ti,mspm0-rtc", "nordic,nrf-rtc",
                       "st,stm32-rtc"],
        "signals":    [],
        "kconfig":    ["CONFIG_COUNTER=y"],
        "groups": [
            {
                "id": "general",
                "title": "General",
                "props": [
                    {
                        "key": "status",
                        "label": "Status",
                        "type": "choice",
                        "choices": ["okay", "disabled"],
                        "default": "disabled",
                        "help": "Enable or disable the RTC",
                        "dts": True,
                        "kconfig": None,
                    },
                ],
            },
            {
                "id": "config",
                "title": "Configuration",
                "props": [
                    {
                        "key": "prescaler",
                        "label": "Prescaler",
                        "type": "int",
                        "default": 32768,
                        "help": "RTC clock prescaler (typically 32768 for 1 Hz)",
                        "dts": True,
                        "kconfig": None,
                    },
                    {
                        "key": "alarm-enable",
                        "label": "Alarm",
                        "type": "bool",
                        "default": False,
                        "help": "Enable RTC alarm support",
                        "dts": False,
                        "kconfig": None,
                    },
                ],
            },
        ],
    },
]


# ── Public API ─────────────────────────────────────────────────────────

def get_all_peripheral_templates() -> list[dict]:
    """Return all peripheral templates."""
    return PERIPHERAL_TEMPLATES


def get_peripheral_template(template_id: str) -> dict | None:
    """Return a single peripheral template by its id."""
    for t in PERIPHERAL_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def match_template(compatible: str) -> dict | None:
    """Find the template that matches a DTS compatible string."""
    for t in PERIPHERAL_TEMPLATES:
        if compatible in t["compatible"]:
            return t
    return None


def build_peripheral_instances(board_peripherals: list[dict]) -> list[dict]:
    """
    Merge board peripheral instances with their configuration templates.

    Takes the list of peripherals from a board definition and enriches each
    with the matching template's configuration groups and defaults.

    Returns a list of dicts suitable for the frontend:
    [
      {
        "instance":  "uart0",
        "display":   "UART 0",
        "compatible": "ti,mspm0-uart",
        "dts_node":  "&uart0",
        "signals":   ["tx", "rx"],
        "enabled":   false,
        "template":  "uart",
        "icon":      "📡",
        "groups":    [ ... template groups with per-instance defaults ... ]
      },
      ...
    ]
    """
    result = []
    for periph in board_peripherals:
        tmpl = match_template(periph.get("compatible", ""))
        if not tmpl:
            # Peripheral has no template → include with minimal info
            result.append({
                "instance":   periph["name"],
                "display":    periph.get("display", periph["name"]),
                "compatible": periph.get("compatible", ""),
                "dts_node":   periph.get("dts_node", ""),
                "signals":    periph.get("signals", []),
                "enabled":    periph.get("enabled", False),
                "template":   None,
                "icon":       "⚙️",
                "groups":     [],
            })
            continue

        result.append({
            "instance":   periph["name"],
            "display":    periph.get("display", periph["name"]),
            "compatible": periph.get("compatible", ""),
            "dts_node":   periph.get("dts_node", ""),
            "signals":    tmpl["signals"],
            "enabled":    periph.get("enabled", False),
            "template":   tmpl["id"],
            "icon":       tmpl["icon"],
            "groups":     tmpl["groups"],    # deep-copy not needed: read-only
        })

    return result


def generate_peripheral_config(
    instances: dict[str, dict],
    board_peripherals: list[dict],
) -> dict:
    """
    Generate a DTS overlay fragment and a prj.conf fragment from
    peripheral instance configurations.

    Parameters
    ----------
    instances : dict[str, dict]
        { "uart0": { "current-speed": 115200, "status": "okay", ... }, ... }
    board_peripherals : list[dict]
        Board peripheral definitions (from board_to_frontend).

    Returns
    -------
    dict with keys: "overlay", "prj_conf"
    """
    dts_lines = [
        "/*",
        " * Peripheral configuration overlay",
        " * Generated by Zephyr Peripheral Configurator",
        " */",
        "",
    ]
    kconfig_lines = [
        "# ─── Peripheral configuration ──────────────────────────────────",
        "# Generated by Zephyr Peripheral Configurator",
        "",
    ]

    kconfig_set = set()  # Track unique Kconfig lines

    for inst_name, values in instances.items():
        # Find board peripheral info
        bp = None
        for p in board_peripherals:
            if p["name"] == inst_name:
                bp = p
                break
        if not bp:
            continue

        tmpl = match_template(bp.get("compatible", ""))
        if not tmpl:
            continue

        dts_node = bp.get("dts_node", f"&{inst_name}")

        # Build defaults map
        defaults = {}
        for grp in tmpl["groups"]:
            for prop in grp["props"]:
                defaults[prop["key"]] = prop["default"]

        # ── DTS overlay ──
        dts_props = []
        for grp in tmpl["groups"]:
            for prop in grp["props"]:
                if not prop.get("dts"):
                    continue
                key = prop["key"]
                val = values.get(key, prop["default"])

                if key == "label" and not val:
                    continue  # Skip empty labels

                if key == "status":
                    dts_props.append(f'\tstatus = "{val}";')
                elif key == "label" and val:
                    dts_props.append(f'\tlabel = "{val}";')
                elif prop["type"] == "bool":
                    if val:
                        dts_props.append(f"\t{key};")
                elif prop["type"] == "int":
                    dts_props.append(f"\t{key} = <{val}>;")
                elif prop["type"] == "string":
                    dts_props.append(f'\t{key} = "{val}";')
                elif prop["type"] == "choice":
                    # Numeric choices → DTS integer, string choices → DTS string
                    if isinstance(val, (int, float)):
                        dts_props.append(f"\t{key} = <{int(val)}>;")
                    else:
                        dts_props.append(f'\t{key} = "{val}";')

        if dts_props:
            dts_lines.append(f"{dts_node} {{")
            dts_lines.extend(dts_props)
            dts_lines.append("};")
            dts_lines.append("")

        # ── Kconfig ──
        # Base kconfig from template
        for kc in tmpl.get("kconfig", []):
            kconfig_set.add(kc)

        # Per-option kconfig
        for grp in tmpl["groups"]:
            for prop in grp["props"]:
                kc = prop.get("kconfig")
                if not kc:
                    continue
                key = prop["key"]
                val = values.get(key, prop["default"])

                if prop["type"] == "bool":
                    kconfig_set.add(f"{kc}={'y' if val else 'n'}")
                elif prop["type"] == "int":
                    kconfig_set.add(f"{kc}={val}")
                else:
                    kconfig_set.add(f'{kc}="{val}"')

    # Sort kconfig lines for consistency
    sorted_kconfig = sorted(kconfig_set)
    kconfig_lines.extend(sorted_kconfig)
    if not sorted_kconfig:
        kconfig_lines.append("# (no Kconfig changes)")

    return {
        "overlay": "\n".join(dts_lines),
        "prj_conf": "\n".join(kconfig_lines),
    }
