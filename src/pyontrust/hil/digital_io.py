"""Digital I/O interface for AD3.

Provides high-level digital I/O operations using the AD3's
16 digital I/O channels (DIO0-15).
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from pyontrust.hil.ad3_interface import AD3Interface


@dataclass
class DigitalIO:
    """Digital I/O interface for AD3.
    
    Supports:
    - Individual pin read/write
    - Bulk read/write operations
    - Pin direction configuration (input/output)
    - Pull-up/pull-down configuration (where supported)
    
    The AD3 has 16 digital I/O channels (DIO0-15) that can be
    individually configured as inputs or outputs.
    
    Example:
        # Using AD3Interface
        ad3 = AD3Interface()
        ad3.open()
        
        # Configure DIO0-3 as outputs
        ad3.digital.set_output_enable(0b1111)
        
        # Write to DIO0
        ad3.digital.write(0, True)
        
        # Read from DIO4
        value = ad3.digital.read(4)
        
        # Bulk write
        ad3.digital.write_all(0b1010)  # DIO1 and DIO3 high
    """
    
    ad3: "AD3Interface"
    
    # Cache output enable mask
    _output_mask: int = 0
    
    def set_output_enable(self, mask: int) -> None:
        """Set which channels are outputs (1 = output, 0 = input).
        
        Args:
            mask: 16-bit mask where each bit represents a DIO channel
                  Bit 0 = DIO0, Bit 15 = DIO15
        """
        self._output_mask = mask & 0xFFFF
        self.ad3.dwf.FDwfDigitalIOOutputEnableSet(
            self.ad3.hdwf,
            ctypes.c_uint(self._output_mask)
        )
    
    def get_output_enable(self) -> int:
        """Get the current output enable mask."""
        mask = ctypes.c_uint()
        self.ad3.dwf.FDwfDigitalIOOutputEnableGet(
            self.ad3.hdwf,
            ctypes.byref(mask)
        )
        self._output_mask = mask.value
        return self._output_mask
    
    def set_channel_output(self, channel: int, output: bool = True) -> None:
        """Configure a single channel as output or input.
        
        Args:
            channel: DIO channel number (0-15)
            output: True for output, False for input
        """
        if output:
            self._output_mask |= (1 << channel)
        else:
            self._output_mask &= ~(1 << channel)
        self.set_output_enable(self._output_mask)
    
    def write(self, channel: int, value: bool) -> None:
        """Write a value to a single digital output.
        
        Args:
            channel: DIO channel number (0-15)
            value: True for high, False for low
        """
        # First ensure the channel is configured as output
        if not (self._output_mask & (1 << channel)):
            self.set_channel_output(channel, True)
        
        # Get current output state
        current = ctypes.c_uint()
        self.ad3.dwf.FDwfDigitalIOOutputGet(self.ad3.hdwf, ctypes.byref(current))
        
        # Update the specific bit
        if value:
            new_value = current.value | (1 << channel)
        else:
            new_value = current.value & ~(1 << channel)
        
        # Write the new value
        self.ad3.dwf.FDwfDigitalIOOutputSet(self.ad3.hdwf, ctypes.c_uint(new_value))
        self.ad3.dwf.FDwfDigitalIOConfigure(self.ad3.hdwf)
    
    def write_all(self, values: int, mask: Optional[int] = None) -> None:
        """Write values to multiple digital outputs.
        
        Args:
            values: 16-bit value to write to outputs
            mask: Optional mask of which bits to update (None = all configured outputs)
        """
        if mask is None:
            mask = self._output_mask
        
        # Get current output state
        current = ctypes.c_uint()
        self.ad3.dwf.FDwfDigitalIOOutputGet(self.ad3.hdwf, ctypes.byref(current))
        
        # Apply mask: keep unchanged bits, update masked bits
        new_value = (current.value & ~mask) | (values & mask)
        
        self.ad3.dwf.FDwfDigitalIOOutputSet(self.ad3.hdwf, ctypes.c_uint(new_value))
        self.ad3.dwf.FDwfDigitalIOConfigure(self.ad3.hdwf)
    
    def read(self, channel: int) -> bool:
        """Read a single digital input.
        
        Args:
            channel: DIO channel number (0-15)
            
        Returns:
            True if high, False if low
        """
        status = ctypes.c_uint()
        self.ad3.dwf.FDwfDigitalIOInputStatus(self.ad3.hdwf, ctypes.byref(status))
        return bool(status.value & (1 << channel))
    
    def read_all(self) -> int:
        """Read all digital inputs.
        
        Returns:
            16-bit value with current state of all DIO channels
        """
        status = ctypes.c_uint()
        self.ad3.dwf.FDwfDigitalIOInputStatus(self.ad3.hdwf, ctypes.byref(status))
        return status.value
    
    def read_channels(self, channels: Sequence[int]) -> dict[int, bool]:
        """Read multiple digital inputs.
        
        Args:
            channels: Sequence of DIO channel numbers to read
            
        Returns:
            Dictionary mapping channel numbers to their values
        """
        all_values = self.read_all()
        return {ch: bool(all_values & (1 << ch)) for ch in channels}
    
    def toggle(self, channel: int) -> bool:
        """Toggle a digital output.
        
        Args:
            channel: DIO channel number (0-15)
            
        Returns:
            New value after toggle
        """
        current = self.read(channel)
        new_value = not current
        self.write(channel, new_value)
        return new_value
    
    def pulse(self, channel: int, high_time_s: float = 0.001, initial_low: bool = True) -> None:
        """Generate a single pulse on a digital output.
        
        Args:
            channel: DIO channel number (0-15)
            high_time_s: Duration of high state in seconds
            initial_low: If True, start low, go high, return low
                        If False, start high, go low, return high
        """
        import time
        
        self.write(channel, not initial_low)
        self.write(channel, initial_low)
        time.sleep(high_time_s)
        self.write(channel, not initial_low)
    
    # Convenience methods for working with board definitions
    
    def write_pin(self, pin_name: str, value: bool) -> None:
        """Write to a pin by its board pin name.
        
        Args:
            pin_name: Board pin name (e.g., 'PA2')
            value: True for high, False for low
            
        Raises:
            ValueError: If pin is not mapped to AD3 DIO
        """
        channel = self.ad3.get_pin_dio(pin_name)
        if channel is None:
            raise ValueError(f"Pin {pin_name} is not mapped to AD3 DIO")
        self.write(channel, value)
    
    def read_pin(self, pin_name: str) -> bool:
        """Read from a pin by its board pin name.
        
        Args:
            pin_name: Board pin name (e.g., 'PA15')
            
        Returns:
            True if high, False if low
            
        Raises:
            ValueError: If pin is not mapped to AD3 DIO
        """
        channel = self.ad3.get_pin_dio(pin_name)
        if channel is None:
            raise ValueError(f"Pin {pin_name} is not mapped to AD3 DIO")
        return self.read(channel)


# Bit manipulation helpers for working with multiple channels

def channels_to_mask(*channels: int) -> int:
    """Convert a list of channel numbers to a bitmask.
    
    Example:
        mask = channels_to_mask(0, 2, 4)  # 0b10101 = 21
    """
    mask = 0
    for ch in channels:
        mask |= (1 << ch)
    return mask


def mask_to_channels(mask: int) -> list[int]:
    """Convert a bitmask to a list of channel numbers.
    
    Example:
        channels = mask_to_channels(0b10101)  # [0, 2, 4]
    """
    channels = []
    for i in range(16):
        if mask & (1 << i):
            channels.append(i)
    return channels
