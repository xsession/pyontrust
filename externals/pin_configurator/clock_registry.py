"""
Clock System Configurator – MCU clock-tree registry.

Models the hierarchical clock distribution of common Zephyr-supported MCUs:
  • Clock sources (internal RC oscillators, external crystals, PLLs)
  • Clock multiplexers (system clock source selection)
  • Dividers (bus prescalers, peripheral clock dividers)
  • Output assignments (which clock feeds which peripheral)
  • DTS & Kconfig output for each setting

Board-specific clock trees are registered here.  The frontend renders
an interactive visual tree + per-node configuration panel.
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════
#
# ClockTree = {
#   "id":          "mspm0g3507",
#   "name":        "MSPM0G3507 Clock Tree",
#   "soc":         "MSPM0G3507",
#   "desc":        "...",
#   "max_freq":    80_000_000,
#   "nodes": [
#     {
#       "id":       "sysosc",
#       "name":     "SYSOSC",
#       "type":     "source",          # source | pll | mux | divider | output
#       "icon":     "🔷",
#       "desc":     "Internal system oscillator",
#       "parent":   null,              # id of upstream node (null for roots)
#       "freq_hz":  32_000_000,        # base frequency (sources only)
#       "props": [
#         { "key": ..., "label": ..., "type": "choice"|"int"|"bool",
#           "default": ..., "choices": [...], "help": ...,
#           "dts": true/false, "kconfig": null|"CONFIG_..." }
#       ]
#     }, ...
#   ],
#   "connections": [                   # edges in the clock graph
#     { "from": "sysosc", "to": "mclk_mux" },
#     ...
#   ]
# }
# ═══════════════════════════════════════════════════════════════════════


# ── TI MSPM0G3507 Clock Tree ──────────────────────────────────────────

_MSPM0G3507_CLOCK_TREE: dict = {
    "id": "mspm0g3507",
    "name": "MSPM0G3507 Clock Tree",
    "soc": "MSPM0G3507",
    "desc": (
        "MSPM0G3507 has SYSOSC (up to 32 MHz), LFOSC (32 kHz), optional "
        "HFXT (4–48 MHz crystal), LFXT (32.768 kHz crystal), SYSPLL (up to "
        "80 MHz), and flexible MCLK / ULPCLK / LFCLK routing."
    ),
    "max_freq": 80_000_000,
    "nodes": [
        # ── Sources ──
        {
            "id": "sysosc",
            "name": "SYSOSC",
            "type": "source",
            "icon": "🔷",
            "desc": "Internal system oscillator, 4/16/24/32 MHz (±1% accuracy)",
            "parent": None,
            "freq_hz": 32_000_000,
            "props": [
                {
                    "key": "sysosc-freq",
                    "label": "SYSOSC Frequency",
                    "type": "choice",
                    "choices": [4_000_000, 16_000_000, 24_000_000, 32_000_000],
                    "default": 32_000_000,
                    "help": "SYSOSC base frequency (Hz)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "lfosc",
            "name": "LFOSC",
            "type": "source",
            "icon": "🔷",
            "desc": "Internal low-frequency oscillator, 32.768 kHz",
            "parent": None,
            "freq_hz": 32_768,
            "props": [],
        },
        {
            "id": "hfxt",
            "name": "HFXT",
            "type": "source",
            "icon": "💎",
            "desc": "High-frequency external crystal (4–48 MHz)",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "hfxt-enable",
                    "label": "Enable HFXT",
                    "type": "bool",
                    "default": False,
                    "help": "Enable high-frequency external crystal",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "hfxt-freq",
                    "label": "Crystal Frequency (Hz)",
                    "type": "int",
                    "default": 48_000_000,
                    "help": "HFXT crystal frequency: 4–48 MHz",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "hfxt-range",
                    "label": "Frequency Range",
                    "type": "choice",
                    "choices": ["4-8 MHz", "8-16 MHz", "16-32 MHz", "32-48 MHz"],
                    "default": "32-48 MHz",
                    "help": "HFXT frequency range selection",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "lfxt",
            "name": "LFXT",
            "type": "source",
            "icon": "💎",
            "desc": "Low-frequency external crystal (32.768 kHz)",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "lfxt-enable",
                    "label": "Enable LFXT",
                    "type": "bool",
                    "default": False,
                    "help": "Enable low-frequency external crystal",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },

        # ── PLL ──
        {
            "id": "syspll",
            "name": "SYSPLL",
            "type": "pll",
            "icon": "⚡",
            "desc": "System PLL (up to 80 MHz output)",
            "parent": "sysosc",
            "freq_hz": 0,
            "props": [
                {
                    "key": "syspll-enable",
                    "label": "Enable SYSPLL",
                    "type": "bool",
                    "default": False,
                    "help": "Enable the system PLL",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "syspll-input",
                    "label": "PLL Reference",
                    "type": "choice",
                    "choices": ["SYSOSC", "HFXT"],
                    "default": "SYSOSC",
                    "help": "PLL reference clock source",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "syspll-pdiv",
                    "label": "Pre-Divider (PDIV)",
                    "type": "choice",
                    "choices": [1, 2, 4, 8],
                    "default": 1,
                    "help": "PLL input pre-divider",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "syspll-qdiv",
                    "label": "Multiplier (QDIV)",
                    "type": "int",
                    "default": 5,
                    "help": "PLL feedback multiplier (2–20)",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "syspll-clk0-div",
                    "label": "CLK0 Post-Divider",
                    "type": "choice",
                    "choices": [2, 4, 6, 8, 10, 12, 14, 16],
                    "default": 2,
                    "help": "Post-divider for SYSPLL CLK0 output",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "syspll-clk2x-div",
                    "label": "CLK2X Post-Divider",
                    "type": "choice",
                    "choices": [1, 2, 3, 4, 5, 6, 7, 8],
                    "default": 1,
                    "help": "Post-divider for SYSPLL CLK2X output",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },

        # ── MUX: Main clock source selection ──
        {
            "id": "mclk_mux",
            "name": "MCLK Source",
            "type": "mux",
            "icon": "🔀",
            "desc": "Master clock source selector",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "mclk-source",
                    "label": "MCLK Source",
                    "type": "choice",
                    "choices": ["SYSOSC", "HFXT", "SYSPLL_CLK0", "SYSPLL_CLK2X"],
                    "default": "SYSOSC",
                    "help": "Select the source for the master clock (MCLK)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "lfclk_mux",
            "name": "LFCLK Source",
            "type": "mux",
            "icon": "🔀",
            "desc": "Low-frequency clock source selector",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "lfclk-source",
                    "label": "LFCLK Source",
                    "type": "choice",
                    "choices": ["LFOSC", "LFXT"],
                    "default": "LFOSC",
                    "help": "Select the source for the LF clock domain",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },

        # ── Dividers ──
        {
            "id": "mclk_div",
            "name": "MCLK Divider",
            "type": "divider",
            "icon": "➗",
            "desc": "Master clock divider (UDIV)",
            "parent": "mclk_mux",
            "freq_hz": 0,
            "props": [
                {
                    "key": "mclk-divider",
                    "label": "MCLK Divider",
                    "type": "choice",
                    "choices": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                    "default": 1,
                    "help": "MCLK frequency divider (1–16)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "ulpclk_div",
            "name": "ULPCLK Divider",
            "type": "divider",
            "icon": "➗",
            "desc": "Ultra-low-power clock divider",
            "parent": "mclk_mux",
            "freq_hz": 0,
            "props": [
                {
                    "key": "ulpclk-divider",
                    "label": "ULPCLK Divider",
                    "type": "choice",
                    "choices": [1, 2, 4, 8, 16, 32],
                    "default": 1,
                    "help": "ULPCLK = MCLK / divider (used in low-power modes)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "canclk_div",
            "name": "CANCLK Source",
            "type": "divider",
            "icon": "🚗",
            "desc": "CAN clock source and divider",
            "parent": "mclk_mux",
            "freq_hz": 0,
            "props": [
                {
                    "key": "canclk-source",
                    "label": "CAN Clock Source",
                    "type": "choice",
                    "choices": ["MCLK", "SYSPLL_CLK0", "HFXT"],
                    "default": "MCLK",
                    "help": "Clock source for CAN controller",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "canclk-divider",
                    "label": "CAN Clock Divider",
                    "type": "choice",
                    "choices": [1, 2, 3, 4, 5, 6, 7, 8],
                    "default": 1,
                    "help": "CAN clock divider",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },

        # ── Output domains ──
        {
            "id": "mclk_out",
            "name": "MCLK",
            "type": "output",
            "icon": "🏁",
            "desc": "Master clock – CPU & AHB bus",
            "parent": "mclk_div",
            "freq_hz": 0,
            "props": [],
        },
        {
            "id": "ulpclk_out",
            "name": "ULPCLK",
            "type": "output",
            "icon": "🏁",
            "desc": "Ultra-low-power clock domain",
            "parent": "ulpclk_div",
            "freq_hz": 0,
            "props": [],
        },
        {
            "id": "lfclk_out",
            "name": "LFCLK",
            "type": "output",
            "icon": "🏁",
            "desc": "Low-frequency clock domain (32 kHz)",
            "parent": "lfclk_mux",
            "freq_hz": 0,
            "props": [],
        },
        {
            "id": "canclk_out",
            "name": "CANCLK",
            "type": "output",
            "icon": "🏁",
            "desc": "CAN peripheral clock",
            "parent": "canclk_div",
            "freq_hz": 0,
            "props": [],
        },
    ],
    "connections": [
        {"from": "sysosc", "to": "mclk_mux"},
        {"from": "hfxt", "to": "mclk_mux"},
        {"from": "sysosc", "to": "syspll"},
        {"from": "hfxt", "to": "syspll"},
        {"from": "syspll", "to": "mclk_mux"},
        {"from": "mclk_mux", "to": "mclk_div"},
        {"from": "mclk_mux", "to": "ulpclk_div"},
        {"from": "mclk_mux", "to": "canclk_div"},
        {"from": "mclk_div", "to": "mclk_out"},
        {"from": "ulpclk_div", "to": "ulpclk_out"},
        {"from": "canclk_div", "to": "canclk_out"},
        {"from": "lfosc", "to": "lfclk_mux"},
        {"from": "lfxt", "to": "lfclk_mux"},
        {"from": "lfclk_mux", "to": "lfclk_out"},
    ],
    "kconfig": [
        "CONFIG_CLOCK_CONTROL=y",
    ],
    "peripheral_clocks": {
        "uart0": "mclk_out",
        "uart1": "mclk_out",
        "uart2": "mclk_out",
        "uart3": "mclk_out",
        "spi0": "mclk_out",
        "spi1": "mclk_out",
        "i2c0": "mclk_out",
        "i2c1": "mclk_out",
        "can0": "canclk_out",
        "adc0": "ulpclk_out",
        "tima0": "mclk_out",
        "tima1": "mclk_out",
        "timg0": "mclk_out",
        "timg6": "mclk_out",
        "timg7": "mclk_out",
        "timg8": "mclk_out",
        "timg12": "mclk_out",
    },
}


# ── Generic STM32-style clock tree (placeholder) ─────────────────────

_STM32_GENERIC_CLOCK_TREE: dict = {
    "id": "stm32_generic",
    "name": "STM32 Generic Clock Tree",
    "soc": "STM32 (Generic)",
    "desc": (
        "Generic STM32 clock tree with HSI/HSE, PLL, and AHB/APB prescalers. "
        "Covers F4, L4, G4, H7 families at a high level."
    ),
    "max_freq": 170_000_000,
    "nodes": [
        {
            "id": "hsi",
            "name": "HSI",
            "type": "source",
            "icon": "🔷",
            "desc": "Internal high-speed RC oscillator (8/16 MHz)",
            "parent": None,
            "freq_hz": 16_000_000,
            "props": [
                {
                    "key": "hsi-freq",
                    "label": "HSI Frequency",
                    "type": "choice",
                    "choices": [8_000_000, 16_000_000],
                    "default": 16_000_000,
                    "help": "HSI base frequency (family-dependent)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "hse",
            "name": "HSE",
            "type": "source",
            "icon": "💎",
            "desc": "High-speed external crystal (4–48 MHz)",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "hse-enable",
                    "label": "Enable HSE",
                    "type": "bool",
                    "default": False,
                    "help": "Enable the high-speed external oscillator",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "hse-freq",
                    "label": "HSE Frequency (Hz)",
                    "type": "int",
                    "default": 8_000_000,
                    "help": "External crystal frequency",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "lsi",
            "name": "LSI",
            "type": "source",
            "icon": "🔷",
            "desc": "Internal low-speed RC oscillator (~32 kHz)",
            "parent": None,
            "freq_hz": 32_000,
            "props": [],
        },
        {
            "id": "lse",
            "name": "LSE",
            "type": "source",
            "icon": "💎",
            "desc": "Low-speed external crystal (32.768 kHz)",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "lse-enable",
                    "label": "Enable LSE",
                    "type": "bool",
                    "default": False,
                    "help": "Enable the low-speed external crystal",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "pll_main",
            "name": "PLL",
            "type": "pll",
            "icon": "⚡",
            "desc": "Main PLL",
            "parent": "hsi",
            "freq_hz": 0,
            "props": [
                {
                    "key": "pll-enable",
                    "label": "Enable PLL",
                    "type": "bool",
                    "default": True,
                    "help": "Enable the main PLL",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "pll-source",
                    "label": "PLL Source",
                    "type": "choice",
                    "choices": ["HSI", "HSE"],
                    "default": "HSI",
                    "help": "PLL reference clock source",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "pll-m",
                    "label": "PLL M (pre-divider)",
                    "type": "int",
                    "default": 1,
                    "help": "PLL input prescaler (1–16)",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "pll-n",
                    "label": "PLL N (multiplier)",
                    "type": "int",
                    "default": 20,
                    "help": "PLL VCO multiplier (8–432)",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "pll-p",
                    "label": "PLL P (SYSCLK div)",
                    "type": "choice",
                    "choices": [2, 4, 6, 8],
                    "default": 2,
                    "help": "PLL output divider for SYSCLK",
                    "dts": True,
                    "kconfig": None,
                },
                {
                    "key": "pll-q",
                    "label": "PLL Q (48 MHz div)",
                    "type": "choice",
                    "choices": [2, 4, 6, 8],
                    "default": 4,
                    "help": "PLL output divider for USB/SDIO (target 48 MHz)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "sysclk_mux",
            "name": "SYSCLK Source",
            "type": "mux",
            "icon": "🔀",
            "desc": "System clock source selector",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "sysclk-source",
                    "label": "SYSCLK Source",
                    "type": "choice",
                    "choices": ["HSI", "HSE", "PLL"],
                    "default": "PLL",
                    "help": "Select the system clock source",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "ahb_div",
            "name": "AHB Prescaler",
            "type": "divider",
            "icon": "➗",
            "desc": "AHB bus clock prescaler",
            "parent": "sysclk_mux",
            "freq_hz": 0,
            "props": [
                {
                    "key": "ahb-prescaler",
                    "label": "AHB Prescaler",
                    "type": "choice",
                    "choices": [1, 2, 4, 8, 16, 64, 128, 256, 512],
                    "default": 1,
                    "help": "HCLK = SYSCLK / prescaler",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "apb1_div",
            "name": "APB1 Prescaler",
            "type": "divider",
            "icon": "➗",
            "desc": "APB1 low-speed bus prescaler",
            "parent": "ahb_div",
            "freq_hz": 0,
            "props": [
                {
                    "key": "apb1-prescaler",
                    "label": "APB1 Prescaler",
                    "type": "choice",
                    "choices": [1, 2, 4, 8, 16],
                    "default": 1,
                    "help": "PCLK1 = HCLK / prescaler",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "apb2_div",
            "name": "APB2 Prescaler",
            "type": "divider",
            "icon": "➗",
            "desc": "APB2 high-speed bus prescaler",
            "parent": "ahb_div",
            "freq_hz": 0,
            "props": [
                {
                    "key": "apb2-prescaler",
                    "label": "APB2 Prescaler",
                    "type": "choice",
                    "choices": [1, 2, 4, 8, 16],
                    "default": 1,
                    "help": "PCLK2 = HCLK / prescaler",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "hclk",
            "name": "HCLK",
            "type": "output",
            "icon": "🏁",
            "desc": "CPU / AHB bus clock",
            "parent": "ahb_div",
            "freq_hz": 0,
            "props": [],
        },
        {
            "id": "pclk1",
            "name": "PCLK1",
            "type": "output",
            "icon": "🏁",
            "desc": "APB1 peripheral clock (UART2-5, SPI2-3, I2C, CAN)",
            "parent": "apb1_div",
            "freq_hz": 0,
            "props": [],
        },
        {
            "id": "pclk2",
            "name": "PCLK2",
            "type": "output",
            "icon": "🏁",
            "desc": "APB2 peripheral clock (UART1, SPI1, TIM1, ADC)",
            "parent": "apb2_div",
            "freq_hz": 0,
            "props": [],
        },
    ],
    "connections": [
        {"from": "hsi", "to": "sysclk_mux"},
        {"from": "hse", "to": "sysclk_mux"},
        {"from": "hsi", "to": "pll_main"},
        {"from": "hse", "to": "pll_main"},
        {"from": "pll_main", "to": "sysclk_mux"},
        {"from": "sysclk_mux", "to": "ahb_div"},
        {"from": "ahb_div", "to": "apb1_div"},
        {"from": "ahb_div", "to": "apb2_div"},
        {"from": "ahb_div", "to": "hclk"},
        {"from": "apb1_div", "to": "pclk1"},
        {"from": "apb2_div", "to": "pclk2"},
    ],
    "kconfig": [
        "CONFIG_CLOCK_CONTROL=y",
        "CONFIG_CLOCK_CONTROL_STM32=y",
    ],
    "peripheral_clocks": {
        "usart1": "pclk2",
        "usart2": "pclk1",
        "usart3": "pclk1",
        "spi1": "pclk2",
        "spi2": "pclk1",
        "i2c1": "pclk1",
        "i2c2": "pclk1",
        "can1": "pclk1",
        "adc1": "pclk2",
        "tim1": "pclk2",
        "tim2": "pclk1",
        "tim3": "pclk1",
    },
}


# ── Nordic nRF52/nRF53 simplified clock tree ──────────────────────────

_NRF52_CLOCK_TREE: dict = {
    "id": "nrf52",
    "name": "nRF52 Clock Tree",
    "soc": "nRF52 (Generic)",
    "desc": (
        "nRF52 series clock system with HFCLK (64 MHz), LFCLK (32.768 kHz), "
        "and selectable internal/external sources."
    ),
    "max_freq": 64_000_000,
    "nodes": [
        {
            "id": "hfint",
            "name": "HFINT",
            "type": "source",
            "icon": "🔷",
            "desc": "Internal 64 MHz RC oscillator",
            "parent": None,
            "freq_hz": 64_000_000,
            "props": [],
        },
        {
            "id": "hfxo",
            "name": "HFXO",
            "type": "source",
            "icon": "💎",
            "desc": "External 32 MHz crystal (doubled to 64 MHz internally)",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "hfxo-enable",
                    "label": "Enable HFXO",
                    "type": "bool",
                    "default": True,
                    "help": "Enable 32 MHz external crystal (required for BLE)",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "lfrc",
            "name": "LFRC",
            "type": "source",
            "icon": "🔷",
            "desc": "Internal 32.768 kHz RC oscillator",
            "parent": None,
            "freq_hz": 32_768,
            "props": [],
        },
        {
            "id": "lfxo",
            "name": "LFXO",
            "type": "source",
            "icon": "💎",
            "desc": "External 32.768 kHz crystal",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "lfxo-enable",
                    "label": "Enable LFXO",
                    "type": "bool",
                    "default": False,
                    "help": "Enable low-frequency crystal for accurate RTC",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "hfclk_mux",
            "name": "HFCLK Source",
            "type": "mux",
            "icon": "🔀",
            "desc": "High-frequency clock source selector",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "hfclk-source",
                    "label": "HFCLK Source",
                    "type": "choice",
                    "choices": ["HFINT", "HFXO"],
                    "default": "HFXO",
                    "help": "HFXO required for Bluetooth; HFINT for lower power",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "lfclk_mux",
            "name": "LFCLK Source",
            "type": "mux",
            "icon": "🔀",
            "desc": "Low-frequency clock source selector",
            "parent": None,
            "freq_hz": 0,
            "props": [
                {
                    "key": "lfclk-source",
                    "label": "LFCLK Source",
                    "type": "choice",
                    "choices": ["LFRC", "LFXO", "LFSYNTH"],
                    "default": "LFRC",
                    "help": "LFXO for accuracy, LFRC for cost, LFSYNTH from HFCLK",
                    "dts": True,
                    "kconfig": None,
                },
            ],
        },
        {
            "id": "hfclk_out",
            "name": "HFCLK (64 MHz)",
            "type": "output",
            "icon": "🏁",
            "desc": "CPU & high-speed peripherals",
            "parent": "hfclk_mux",
            "freq_hz": 0,
            "props": [],
        },
        {
            "id": "lfclk_out",
            "name": "LFCLK (32 kHz)",
            "type": "output",
            "icon": "🏁",
            "desc": "RTC, WDT, low-power peripherals",
            "parent": "lfclk_mux",
            "freq_hz": 0,
            "props": [],
        },
    ],
    "connections": [
        {"from": "hfint", "to": "hfclk_mux"},
        {"from": "hfxo", "to": "hfclk_mux"},
        {"from": "hfclk_mux", "to": "hfclk_out"},
        {"from": "lfrc", "to": "lfclk_mux"},
        {"from": "lfxo", "to": "lfclk_mux"},
        {"from": "lfclk_mux", "to": "lfclk_out"},
    ],
    "kconfig": [
        "CONFIG_CLOCK_CONTROL=y",
        "CONFIG_CLOCK_CONTROL_NRF=y",
    ],
    "peripheral_clocks": {},
}


# ── Registry ──────────────────────────────────────────────────────────

_ALL_CLOCK_TREES: list[dict] = [
    _MSPM0G3507_CLOCK_TREE,
    _STM32_GENERIC_CLOCK_TREE,
    _NRF52_CLOCK_TREE,
]


def get_all_clock_trees() -> list[dict]:
    """Return summary list of all available clock trees."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "soc": t["soc"],
            "desc": t["desc"],
            "max_freq": t["max_freq"],
            "node_count": len(t["nodes"]),
        }
        for t in _ALL_CLOCK_TREES
    ]


def get_clock_tree(tree_id: str) -> dict | None:
    """Return a full clock tree definition by its id."""
    for t in _ALL_CLOCK_TREES:
        if t["id"] == tree_id:
            return t
    return None


def compute_frequencies(tree_id: str, values: dict) -> dict:
    """
    Compute the resulting frequency at each node given user config values.

    Returns { "node_id": freq_hz, ... }
    """
    tree = get_clock_tree(tree_id)
    if not tree:
        return {}

    node_map = {n["id"]: n for n in tree["nodes"]}
    freqs: dict[str, int] = {}

    if tree_id == "mspm0g3507":
        freqs = _compute_mspm0(node_map, values)
    elif tree_id == "stm32_generic":
        freqs = _compute_stm32(node_map, values)
    elif tree_id == "nrf52":
        freqs = _compute_nrf52(node_map, values)
    else:
        # Fallback: use base freq_hz
        for n in tree["nodes"]:
            freqs[n["id"]] = n.get("freq_hz") or 0

    return freqs


def _compute_mspm0(nodes: dict, v: dict) -> dict:
    """Compute MSPM0G3507 clock frequencies."""
    f = {}

    # Sources
    f["sysosc"] = v.get("sysosc-freq", 32_000_000)
    f["lfosc"] = 32_768
    f["hfxt"] = v.get("hfxt-freq", 48_000_000) if v.get("hfxt-enable") else 0
    f["lfxt"] = 32_768 if v.get("lfxt-enable") else 0

    # PLL
    pll_en = v.get("syspll-enable", False)
    if pll_en:
        pll_src = v.get("syspll-input", "SYSOSC")
        pll_in = f["hfxt"] if pll_src == "HFXT" and f["hfxt"] else f["sysosc"]
        pdiv = v.get("syspll-pdiv", 1) or 1
        qdiv = v.get("syspll-qdiv", 5) or 5
        vco = pll_in // pdiv * qdiv
        clk0_div = v.get("syspll-clk0-div", 2) or 2
        clk2x_div = v.get("syspll-clk2x-div", 1) or 1
        f["syspll"] = vco
        f["_syspll_clk0"] = vco // clk0_div
        f["_syspll_clk2x"] = (vco * 2) // clk2x_div
    else:
        f["syspll"] = 0
        f["_syspll_clk0"] = 0
        f["_syspll_clk2x"] = 0

    # MCLK mux
    mclk_src = v.get("mclk-source", "SYSOSC")
    if mclk_src == "HFXT" and f["hfxt"]:
        mclk_raw = f["hfxt"]
    elif mclk_src == "SYSPLL_CLK0" and pll_en:
        mclk_raw = f["_syspll_clk0"]
    elif mclk_src == "SYSPLL_CLK2X" and pll_en:
        mclk_raw = f["_syspll_clk2x"]
    else:
        mclk_raw = f["sysosc"]
    f["mclk_mux"] = mclk_raw

    # Dividers
    mclk_div = v.get("mclk-divider", 1) or 1
    f["mclk_div"] = mclk_raw // mclk_div
    f["mclk_out"] = f["mclk_div"]

    ulp_div = v.get("ulpclk-divider", 1) or 1
    f["ulpclk_div"] = mclk_raw // ulp_div
    f["ulpclk_out"] = f["ulpclk_div"]

    # LFCLK
    lfclk_src = v.get("lfclk-source", "LFOSC")
    f["lfclk_mux"] = f["lfxt"] if lfclk_src == "LFXT" and f["lfxt"] else 32_768
    f["lfclk_out"] = f["lfclk_mux"]

    # CAN clock
    canclk_src = v.get("canclk-source", "MCLK")
    if canclk_src == "SYSPLL_CLK0" and pll_en:
        can_base = f["_syspll_clk0"]
    elif canclk_src == "HFXT" and f["hfxt"]:
        can_base = f["hfxt"]
    else:
        can_base = f["mclk_out"]
    can_div = v.get("canclk-divider", 1) or 1
    f["canclk_div"] = can_base // can_div
    f["canclk_out"] = f["canclk_div"]

    return f


def _compute_stm32(nodes: dict, v: dict) -> dict:
    """Compute STM32 generic clock frequencies."""
    f = {}

    f["hsi"] = v.get("hsi-freq", 16_000_000)
    f["hse"] = v.get("hse-freq", 8_000_000) if v.get("hse-enable") else 0
    f["lsi"] = 32_000
    f["lse"] = 32_768 if v.get("lse-enable") else 0

    # PLL
    pll_en = v.get("pll-enable", True)
    if pll_en:
        pll_src = v.get("pll-source", "HSI")
        pll_in = f["hse"] if pll_src == "HSE" and f["hse"] else f["hsi"]
        m = max(1, v.get("pll-m", 1) or 1)
        n = max(1, v.get("pll-n", 20) or 20)
        p = max(2, v.get("pll-p", 2) or 2)
        vco = (pll_in // m) * n
        f["pll_main"] = vco // p
    else:
        f["pll_main"] = 0

    # SYSCLK mux
    sys_src = v.get("sysclk-source", "PLL")
    if sys_src == "HSE" and f["hse"]:
        sysclk = f["hse"]
    elif sys_src == "PLL" and pll_en:
        sysclk = f["pll_main"]
    else:
        sysclk = f["hsi"]
    f["sysclk_mux"] = sysclk

    # Bus dividers
    ahb = max(1, v.get("ahb-prescaler", 1) or 1)
    apb1 = max(1, v.get("apb1-prescaler", 1) or 1)
    apb2 = max(1, v.get("apb2-prescaler", 1) or 1)

    f["ahb_div"] = sysclk // ahb
    f["hclk"] = f["ahb_div"]
    f["apb1_div"] = f["ahb_div"] // apb1
    f["pclk1"] = f["apb1_div"]
    f["apb2_div"] = f["ahb_div"] // apb2
    f["pclk2"] = f["apb2_div"]

    return f


def _compute_nrf52(nodes: dict, v: dict) -> dict:
    """Compute nRF52 clock frequencies."""
    f = {}
    f["hfint"] = 64_000_000
    f["hfxo"] = 64_000_000 if v.get("hfxo-enable", True) else 0
    f["lfrc"] = 32_768
    f["lfxo"] = 32_768 if v.get("lfxo-enable") else 0

    hf_src = v.get("hfclk-source", "HFXO")
    f["hfclk_mux"] = f["hfxo"] if hf_src == "HFXO" and f["hfxo"] else f["hfint"]
    f["hfclk_out"] = f["hfclk_mux"]

    lf_src = v.get("lfclk-source", "LFRC")
    if lf_src == "LFXO" and f["lfxo"]:
        f["lfclk_mux"] = f["lfxo"]
    elif lf_src == "LFSYNTH":
        f["lfclk_mux"] = 32_768  # synthesised from HFCLK
    else:
        f["lfclk_mux"] = f["lfrc"]
    f["lfclk_out"] = f["lfclk_mux"]

    return f


def generate_clock_config(tree_id: str, values: dict) -> dict:
    """
    Generate DTS overlay + prj.conf for the clock configuration.

    Returns { "overlay": "...", "prj_conf": "...", "frequencies": { node: hz } }
    """
    tree = get_clock_tree(tree_id)
    if not tree:
        return {"overlay": "", "prj_conf": "", "frequencies": {}}

    freqs = compute_frequencies(tree_id, values)
    node_map = {n["id"]: n for n in tree["nodes"]}

    # ── DTS overlay ──
    dts = [
        "/*",
        " * Clock system configuration",
        f" * SoC: {tree['soc']}",
        " * Generated by Zephyr Clock System Configurator",
        " */",
        "",
    ]

    # Collect DTS properties from all nodes
    for node in tree["nodes"]:
        dts_props = []
        for prop in node.get("props", []):
            if not prop.get("dts"):
                continue
            key = prop["key"]
            val = values.get(key, prop["default"])
            if val == prop["default"]:
                continue  # skip defaults

            if prop["type"] == "bool":
                if val:
                    dts_props.append(f"\t{key};")
            elif prop["type"] == "int":
                dts_props.append(f"\t{key} = <{val}>;")
            elif prop["type"] == "choice":
                if isinstance(val, (int, float)):
                    dts_props.append(f"\t{key} = <{int(val)}>;")
                else:
                    dts_props.append(f'\t{key} = "{val}";')
            else:
                dts_props.append(f'\t{key} = "{val}";')

        if dts_props:
            dts.append(f"/* {node['name']} ({node['type']}) */")
            dts.append(f"&clocks {{")
            dts.extend(dts_props)
            dts.append("};")
            dts.append("")

    # ── Frequency summary comment ──
    dts.append("/*")
    dts.append(" * Computed frequencies:")
    for node in tree["nodes"]:
        hz = freqs.get(node["id"], 0)
        if hz > 0:
            if hz >= 1_000_000:
                label = f"{hz / 1_000_000:.2f} MHz"
            elif hz >= 1_000:
                label = f"{hz / 1_000:.2f} kHz"
            else:
                label = f"{hz} Hz"
            dts.append(f" *   {node['name']:20s} = {label}")
    dts.append(" */")

    # ── Kconfig ──
    kc = [
        "# ─── Clock system configuration ──────────────────────────────────",
        f"# SoC: {tree['soc']}",
        "# Generated by Zephyr Clock System Configurator",
        "",
    ]
    for line in tree.get("kconfig", []):
        kc.append(line)

    # Add Kconfig props from nodes
    for node in tree["nodes"]:
        for prop in node.get("props", []):
            kcfg = prop.get("kconfig")
            if not kcfg:
                continue
            val = values.get(prop["key"], prop["default"])
            if prop["type"] == "bool":
                kc.append(f"{kcfg}={'y' if val else 'n'}")
            elif prop["type"] == "int":
                kc.append(f"{kcfg}={val}")
            else:
                kc.append(f'{kcfg}="{val}"')

    return {
        "overlay": "\n".join(dts),
        "prj_conf": "\n".join(kc),
        "frequencies": {k: v for k, v in freqs.items() if not k.startswith("_")},
    }
