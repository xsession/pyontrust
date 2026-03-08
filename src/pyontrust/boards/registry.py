"""Board registry for managing multiple board definitions.

Provides functions to register, lookup, and list available board
pinout definitions for HIL testing.
"""

from __future__ import annotations

from typing import Optional

from pyontrust.boards.base import BoardPinout

# Global registry of board definitions
_BOARDS: dict[str, BoardPinout] = {}


def register_board(board: BoardPinout) -> None:
    """Register a board definition in the global registry.
    
    Args:
        board: BoardPinout instance to register
        
    Raises:
        ValueError: If a board with the same name is already registered
    """
    if board.name in _BOARDS:
        raise ValueError(f"Board '{board.name}' is already registered")
    _BOARDS[board.name] = board


def get_board(name: str) -> Optional[BoardPinout]:
    """Get a board definition by name.
    
    Args:
        name: Board name (e.g., 'locator_base')
        
    Returns:
        BoardPinout instance or None if not found
    """
    return _BOARDS.get(name)


def list_boards() -> list[str]:
    """List all registered board names.
    
    Returns:
        List of registered board names
    """
    return list(_BOARDS.keys())


def unregister_board(name: str) -> bool:
    """Remove a board from the registry.
    
    Args:
        name: Board name to remove
        
    Returns:
        True if board was removed, False if not found
    """
    if name in _BOARDS:
        del _BOARDS[name]
        return True
    return False


def clear_registry() -> None:
    """Clear all registered boards (mainly for testing)."""
    _BOARDS.clear()
