"""Core AD3 interface for HIL testing.

Provides a unified interface to the Analog Discovery 3 that combines
digital I/O, analog I/O, and protocol interfaces into a single class.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from pyontrust.boards.base import BoardPinout, Pin
from pyontrust.instruments import dwf_loader


@dataclass
class AD3Interface:
    """High-level interface to Analog Discovery 3 for HIL testing.
    
    This class provides a unified interface combining:
    - Digital I/O (16 channels, DIO0-15)
    - Analog inputs (2 channels, scope/voltmeter)
    - Analog outputs (2 channels, waveform generator)
    - Protocol analyzers (SPI, I2C, UART)
    
    Example:
        from pyontrust.hil import AD3Interface
        from pyontrust.boards.locator_base import LOCATOR_BASE
        
        ad3 = AD3Interface(board=LOCATOR_BASE)
        ad3.open()
        
        # Digital I/O
        ad3.digital.write(0, True)
        value = ad3.digital.read(4)
        
        # Analog
        voltage = ad3.analog.read_voltage(0)
        ad3.analog.set_waveform(0, 'sine', 1000, 1.0)
        
        ad3.close()
    """
    
    board: Optional[BoardPinout] = None
    device_index: int = -1  # -1 = auto-select first available
    
    # Internal state
    _dwf: Any = field(default=None, init=False, repr=False)
    _hdwf: Any = field(default=None, init=False, repr=False)
    _digital: Any = field(default=None, init=False, repr=False)
    _analog: Any = field(default=None, init=False, repr=False)
    _spi: Any = field(default=None, init=False, repr=False)
    _i2c: Any = field(default=None, init=False, repr=False)
    _uart: Any = field(default=None, init=False, repr=False)
    
    def open(self) -> None:
        """Open connection to AD3 device."""
        if self._hdwf is not None:
            return
        
        import ctypes
        
        self._dwf = dwf_loader.load_dwf()
        self._setup_ctypes_prototypes()
        
        hdwf = ctypes.c_int()
        ok = self._dwf.FDwfDeviceOpen(
            ctypes.c_int(self.device_index),
            ctypes.byref(hdwf)
        )
        
        if ok == 0 or hdwf.value == 0:
            raise RuntimeError(self._get_last_error() or "Failed to open AD3 device")
        
        self._hdwf = hdwf
        
        # Initialize sub-interfaces lazily
        self._digital = None
        self._analog = None
        self._spi = None
        self._i2c = None
        self._uart = None
    
    def close(self) -> None:
        """Close connection to AD3 device."""
        if self._hdwf is None:
            return
        
        try:
            self._dwf.FDwfDeviceClose(self._hdwf)
        finally:
            self._hdwf = None
            self._digital = None
            self._analog = None
            self._spi = None
            self._i2c = None
            self._uart = None
    
    def __enter__(self) -> "AD3Interface":
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    @property
    def is_open(self) -> bool:
        """Check if device is open."""
        return self._hdwf is not None
    
    @property
    def dwf(self) -> Any:
        """Get the raw DWF library handle."""
        if self._dwf is None:
            raise RuntimeError("Device not open")
        return self._dwf
    
    @property
    def hdwf(self) -> Any:
        """Get the device handle."""
        if self._hdwf is None:
            raise RuntimeError("Device not open")
        return self._hdwf
    
    @property
    def digital(self) -> "DigitalIO":
        """Get the digital I/O interface."""
        if self._hdwf is None:
            raise RuntimeError("Device not open")
        if self._digital is None:
            from pyontrust.hil.digital_io import DigitalIO
            self._digital = DigitalIO(self)
        return self._digital
    
    @property
    def analog(self) -> "AnalogIO":
        """Get the analog I/O interface."""
        if self._hdwf is None:
            raise RuntimeError("Device not open")
        if self._analog is None:
            from pyontrust.hil.analog_io import AnalogIO
            self._analog = AnalogIO(self)
        return self._analog
    
    @property
    def spi(self) -> "SPIController":
        """Get the SPI protocol controller."""
        if self._hdwf is None:
            raise RuntimeError("Device not open")
        if self._spi is None:
            from pyontrust.hil.protocols import SPIController
            self._spi = SPIController(self)
        return self._spi
    
    @property
    def i2c(self) -> "I2CController":
        """Get the I2C protocol controller."""
        if self._hdwf is None:
            raise RuntimeError("Device not open")
        if self._i2c is None:
            from pyontrust.hil.protocols import I2CController
            self._i2c = I2CController(self)
        return self._i2c
    
    @property
    def uart(self) -> "UARTController":
        """Get the UART protocol controller."""
        if self._hdwf is None:
            raise RuntimeError("Device not open")
        if self._uart is None:
            from pyontrust.hil.protocols import UARTController
            self._uart = UARTController(self)
        return self._uart
    
    def get_pin_dio(self, pin_name: str) -> Optional[int]:
        """Get AD3 DIO channel for a board pin."""
        if self.board is None:
            return None
        pin = self.board.get_pin(pin_name)
        return pin.ad3_dio if pin else None
    
    def get_pin_ain(self, pin_name: str) -> Optional[int]:
        """Get AD3 analog input channel for a board pin."""
        if self.board is None:
            return None
        pin = self.board.get_pin(pin_name)
        return pin.ad3_ain if pin else None
    
    def get_pin_aout(self, pin_name: str) -> Optional[int]:
        """Get AD3 analog output channel for a board pin."""
        if self.board is None:
            return None
        pin = self.board.get_pin(pin_name)
        return pin.ad3_aout if pin else None
    
    def reset(self) -> None:
        """Reset all AD3 functions to default state."""
        if self._hdwf is None:
            return
        self._dwf.FDwfDeviceReset(self._hdwf)
    
    def _get_last_error(self) -> str:
        """Get the last DWF error message."""
        import ctypes
        buf = ctypes.create_string_buffer(512)
        try:
            self._dwf.FDwfGetLastErrorMsg(buf)
            return buf.value.decode("utf-8", errors="replace")
        except Exception:
            return ""
    
    def _setup_ctypes_prototypes(self) -> None:
        """Set up ctypes function prototypes for type safety."""
        import ctypes
        
        try:
            dwf = self._dwf
            
            # Device functions
            dwf.FDwfDeviceOpen.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            dwf.FDwfDeviceOpen.restype = ctypes.c_int
            dwf.FDwfDeviceClose.argtypes = [ctypes.c_int]
            dwf.FDwfDeviceClose.restype = ctypes.c_int
            dwf.FDwfDeviceReset.argtypes = [ctypes.c_int]
            dwf.FDwfDeviceReset.restype = ctypes.c_int
            dwf.FDwfGetLastErrorMsg.argtypes = [ctypes.c_char_p]
            
            # Digital I/O functions
            dwf.FDwfDigitalIOOutputEnableSet.argtypes = [ctypes.c_int, ctypes.c_uint]
            dwf.FDwfDigitalIOOutputEnableGet.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
            dwf.FDwfDigitalIOOutputSet.argtypes = [ctypes.c_int, ctypes.c_uint]
            dwf.FDwfDigitalIOOutputGet.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
            dwf.FDwfDigitalIOInputStatus.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
            dwf.FDwfDigitalIOConfigure.argtypes = [ctypes.c_int]
            
            # Analog input (scope) functions
            dwf.FDwfAnalogInChannelEnableSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInChannelRangeSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInChannelOffsetSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInFrequencySet.argtypes = [ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogInConfigure.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogInStatus.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            dwf.FDwfAnalogInStatusSample.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
            dwf.FDwfAnalogInStatusData.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double), ctypes.c_int]
            dwf.FDwfAnalogInBufferSizeSet.argtypes = [ctypes.c_int, ctypes.c_int]
            
            # Analog output (waveform generator) functions
            dwf.FDwfAnalogOutNodeEnableSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogOutNodeFunctionSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
            dwf.FDwfAnalogOutNodeFrequencySet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogOutNodeAmplitudeSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogOutNodeOffsetSet.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_double]
            dwf.FDwfAnalogOutConfigure.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            
        except Exception:
            pass  # Some functions may not exist in all DWF versions
