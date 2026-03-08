"""Board definitions for Hardware-in-the-Loop testing.

This module provides board pinout definitions that map MCU pins
to Analog Discovery 3 (AD3) channels for automated testing.
"""

from pyontrust.boards.base import BoardPinout, Pin, PinFunction
from pyontrust.boards.registry import get_board, register_board, list_boards

__all__ = [
    "BoardPinout",
    "Pin",
    "PinFunction",
    "get_board",
    "register_board",
    "list_boards",
]
