"""HIL-Simulation Bridge.

Provides a unified interface that can switch between:
1. Real hardware via AD3 (Analog Discovery 3)
2. Simulated hardware via ProtoSim/Renode

This enables test code to run unchanged against both real
hardware and simulation, supporting:
- Early development without hardware
- CI/CD automated testing
- Regression testing at scale
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Sequence

logger = logging.getLogger("pyontrust.hil_bridge")


class BackendType(Enum):
    """Available HIL backends."""
    AUTO = auto()       # Auto-detect (prefer hardware)
    HARDWARE = auto()   # AD3 hardware
    SIMULATION = auto() # ProtoSim/Renode simulation
    MOCK = auto()       # Mock for unit testing


class DigitalValue(Enum):
    """Digital signal value."""
    LOW = 0
    HIGH = 1
    UNKNOWN = -1


@dataclass
class PinState:
    """State of a single pin."""
    name: str
    value: float
    is_digital: bool = True
    timestamp_s: float = 0.0
    
    @property
    def digital_value(self) -> DigitalValue:
        if self.value > 0.5:
            return DigitalValue.HIGH
        elif self.value < 0.5:
            return DigitalValue.LOW
        return DigitalValue.UNKNOWN


class HILBackend(Protocol):
    """Protocol for HIL backends."""
    
    def open(self) -> None:
        """Open connection to the backend."""
        ...
    
    def close(self) -> None:
        """Close connection."""
        ...
    
    def digital_write(self, pin: str, value: bool) -> None:
        """Write digital value to pin."""
        ...
    
    def digital_read(self, pin: str) -> bool:
        """Read digital value from pin."""
        ...
    
    def analog_read(self, pin: str) -> float:
        """Read analog value (voltage) from pin."""
        ...
    
    def analog_write(self, pin: str, voltage: float) -> None:
        """Write analog value (voltage) to pin."""
        ...
    
    def get_pin_state(self, pin: str) -> PinState:
        """Get complete pin state."""
        ...
    
    @property
    def is_simulation(self) -> bool:
        """True if this is a simulated backend."""
        ...


class AD3Backend:
    """AD3 hardware backend using pyontrust.hil."""
    
    def __init__(self, board_name: str = "locator_base", device_index: int = -1):
        self.board_name = board_name
        self.device_index = device_index
        self._ad3 = None
        self._board = None
    
    def open(self) -> None:
        from pyontrust.hil import AD3Interface
        from pyontrust.boards import get_board
        
        self._board = get_board(self.board_name)
        if self._board is None:
            raise ValueError(f"Unknown board: {self.board_name}")
        
        self._ad3 = AD3Interface(
            board=self._board,
            device_index=self.device_index,
        )
        self._ad3.open()
        logger.info(f"AD3 backend opened for board: {self.board_name}")
    
    def close(self) -> None:
        if self._ad3:
            self._ad3.close()
            self._ad3 = None
        logger.info("AD3 backend closed")
    
    def digital_write(self, pin: str, value: bool) -> None:
        if self._ad3 is None:
            raise RuntimeError("Backend not open")
        self._ad3.digital.write_pin(pin, value)
    
    def digital_read(self, pin: str) -> bool:
        if self._ad3 is None:
            raise RuntimeError("Backend not open")
        return self._ad3.digital.read_pin(pin)
    
    def analog_read(self, pin: str) -> float:
        if self._ad3 is None:
            raise RuntimeError("Backend not open")
        return self._ad3.analog.read_pin_voltage(pin)
    
    def analog_write(self, pin: str, voltage: float) -> None:
        if self._ad3 is None:
            raise RuntimeError("Backend not open")
        self._ad3.analog.set_pin_voltage(pin, voltage)
    
    def get_pin_state(self, pin: str) -> PinState:
        if self._ad3 is None:
            raise RuntimeError("Backend not open")
        
        # Try digital first
        try:
            value = float(self._ad3.digital.read_pin(pin))
            return PinState(name=pin, value=value, is_digital=True)
        except ValueError:
            pass
        
        # Try analog
        try:
            value = self._ad3.analog.read_pin_voltage(pin)
            return PinState(name=pin, value=value, is_digital=False)
        except ValueError:
            pass
        
        return PinState(name=pin, value=-1, is_digital=True)
    
    @property
    def is_simulation(self) -> bool:
        return False
    
    @property
    def ad3(self):
        """Get the underlying AD3Interface for advanced operations."""
        return self._ad3


class SimulationBackend:
    """ProtoSim/Renode simulation backend."""
    
    def __init__(
        self,
        firmware_path: Optional[str] = None,
        board_name: str = "locator_base",
        auto_advance: bool = True,
    ):
        self.firmware_path = firmware_path
        self.board_name = board_name
        self.auto_advance = auto_advance
        self._simulator = None
        self._renode = None
        self._pin_states: Dict[str, PinState] = {}
        self._sim_time = 0.0
    
    def open(self) -> None:
        try:
            from pyontrust.simulation import LocatorBaseSimulator, SimulationConfig
            
            config = SimulationConfig(
                project_name=self.board_name,
                firmware_path=self.firmware_path,
                duration_s=3600.0,  # Long duration, manual control
                sync_interval_s=100e-6,
            )
            
            self._simulator = LocatorBaseSimulator(config)
            self._simulator._initialize()
            self._renode = self._simulator._renode
            
            logger.info(f"Simulation backend opened for: {self.board_name}")
            
        except ImportError as e:
            logger.warning(f"ProtoSim not available: {e}")
            logger.info("Using mock simulation")
            self._simulator = None
            self._renode = None
    
    def close(self) -> None:
        if self._simulator:
            self._simulator._cleanup()
            self._simulator = None
            self._renode = None
        logger.info("Simulation backend closed")
    
    def digital_write(self, pin: str, value: bool) -> None:
        """Inject digital value into simulation (for stimulating MCU inputs)."""
        if self._renode:
            try:
                self._renode.write_gpio(pin, 1 if value else 0)
            except Exception as e:
                logger.warning(f"Failed to write GPIO {pin}: {e}")
        
        # Update local state
        self._pin_states[pin] = PinState(
            name=pin,
            value=float(value),
            is_digital=True,
            timestamp_s=self._sim_time,
        )
        
        if self.auto_advance:
            self._advance_simulation(1e-6)  # Advance 1µs
    
    def digital_read(self, pin: str) -> bool:
        """Read digital output from simulated MCU."""
        if self.auto_advance:
            self._advance_simulation(1e-6)
        
        if self._renode:
            try:
                value = self._renode.read_gpio(pin)
                self._pin_states[pin] = PinState(
                    name=pin,
                    value=float(value),
                    is_digital=True,
                    timestamp_s=self._sim_time,
                )
                return bool(value)
            except Exception as e:
                logger.warning(f"Failed to read GPIO {pin}: {e}")
        
        # Return cached state or default
        state = self._pin_states.get(pin)
        return bool(state.value) if state else False
    
    def analog_read(self, pin: str) -> float:
        """Read analog value from simulation (e.g., DAC output)."""
        if self.auto_advance:
            self._advance_simulation(1e-6)
        
        # For analog, we'd need to read from LTSpice or the MCU's DAC
        # For now, return cached state
        state = self._pin_states.get(pin)
        return state.value if state else 0.0
    
    def analog_write(self, pin: str, voltage: float) -> None:
        """Inject analog value into simulation (for ADC input)."""
        if self._renode:
            try:
                # Convert voltage to ADC value (assuming 3.3V ref, 12-bit)
                adc_value = int(voltage / 3.3 * 4095)
                # Find ADC channel for pin
                pin_to_channel = {
                    "PA15": 0, "PA16": 1, "PA17": 2, "PA18": 3,
                }
                channel = pin_to_channel.get(pin, 0)
                self._renode.set_adc_value(channel, adc_value)
            except Exception as e:
                logger.warning(f"Failed to set ADC value for {pin}: {e}")
        
        self._pin_states[pin] = PinState(
            name=pin,
            value=voltage,
            is_digital=False,
            timestamp_s=self._sim_time,
        )
        
        if self.auto_advance:
            self._advance_simulation(1e-6)
    
    def get_pin_state(self, pin: str) -> PinState:
        if pin in self._pin_states:
            return self._pin_states[pin]
        return PinState(name=pin, value=0.0, timestamp_s=self._sim_time)
    
    @property
    def is_simulation(self) -> bool:
        return True
    
    @property
    def sim_time(self) -> float:
        """Current simulation time in seconds."""
        return self._sim_time
    
    def advance(self, duration_s: float) -> None:
        """Manually advance simulation time."""
        self._advance_simulation(duration_s)
    
    def _advance_simulation(self, duration_s: float) -> None:
        """Advance the simulation by given duration."""
        target = self._sim_time + duration_s
        
        if self._renode:
            try:
                self._renode.run_until(target)
            except Exception as e:
                logger.warning(f"Failed to advance simulation: {e}")
        
        self._sim_time = target


class MockBackend:
    """Mock backend for unit testing."""
    
    def __init__(self):
        self._pin_states: Dict[str, PinState] = {}
        self._is_open = False
    
    def open(self) -> None:
        self._is_open = True
        logger.info("Mock backend opened")
    
    def close(self) -> None:
        self._is_open = False
        logger.info("Mock backend closed")
    
    def digital_write(self, pin: str, value: bool) -> None:
        self._pin_states[pin] = PinState(name=pin, value=float(value), is_digital=True)
    
    def digital_read(self, pin: str) -> bool:
        state = self._pin_states.get(pin)
        return bool(state.value) if state else False
    
    def analog_read(self, pin: str) -> float:
        state = self._pin_states.get(pin)
        return state.value if state else 0.0
    
    def analog_write(self, pin: str, voltage: float) -> None:
        self._pin_states[pin] = PinState(name=pin, value=voltage, is_digital=False)
    
    def get_pin_state(self, pin: str) -> PinState:
        return self._pin_states.get(pin, PinState(name=pin, value=0.0))
    
    def set_pin_state(self, pin: str, value: float, is_digital: bool = True) -> None:
        """Test helper to set pin state."""
        self._pin_states[pin] = PinState(name=pin, value=value, is_digital=is_digital)
    
    @property
    def is_simulation(self) -> bool:
        return True


class UnifiedHIL:
    """Unified HIL interface that works with any backend.
    
    Provides a consistent API for hardware testing that works
    with real hardware (AD3), simulation (ProtoSim), or mocks.
    
    Example:
        # Auto-detect backend (prefers hardware)
        hil = UnifiedHIL()
        hil.open()
        
        # Or explicitly choose simulation
        hil = UnifiedHIL(backend_type=BackendType.SIMULATION)
        hil.open()
        
        # Test code works the same either way
        hil.digital_write("PA2", True)
        assert hil.digital_read("PA2") == True
        
        hil.close()
    """
    
    def __init__(
        self,
        backend_type: BackendType = BackendType.AUTO,
        board_name: str = "locator_base",
        firmware_path: Optional[str] = None,
        ad3_device_index: int = -1,
    ):
        self.backend_type = backend_type
        self.board_name = board_name
        self.firmware_path = firmware_path
        self.ad3_device_index = ad3_device_index
        self._backend: Optional[HILBackend] = None
    
    def open(self) -> None:
        """Open the appropriate backend."""
        if self._backend is not None:
            return
        
        backend_type = self._resolve_backend_type()
        
        if backend_type == BackendType.HARDWARE:
            self._backend = AD3Backend(
                board_name=self.board_name,
                device_index=self.ad3_device_index,
            )
        elif backend_type == BackendType.SIMULATION:
            self._backend = SimulationBackend(
                firmware_path=self.firmware_path,
                board_name=self.board_name,
            )
        else:  # MOCK
            self._backend = MockBackend()
        
        self._backend.open()
        logger.info(f"UnifiedHIL opened with backend: {backend_type.name}")
    
    def close(self) -> None:
        """Close the backend."""
        if self._backend:
            self._backend.close()
            self._backend = None
    
    def __enter__(self) -> "UnifiedHIL":
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def _resolve_backend_type(self) -> BackendType:
        """Resolve AUTO backend type."""
        if self.backend_type != BackendType.AUTO:
            return self.backend_type
        
        # Try hardware first
        try:
            from pyontrust.instruments import dwf_loader
            dwf = dwf_loader.load_dwf()
            
            # Check if AD3 is connected
            import ctypes
            device_count = ctypes.c_int()
            dwf.FDwfEnum(ctypes.c_int(0), ctypes.byref(device_count))
            
            if device_count.value > 0:
                logger.info("AD3 detected, using hardware backend")
                return BackendType.HARDWARE
        except Exception as e:
            logger.debug(f"Hardware detection failed: {e}")
        
        # Try simulation
        try:
            from pyontrust.simulation import LocatorBaseSimulator
            logger.info("Using simulation backend")
            return BackendType.SIMULATION
        except ImportError:
            pass
        
        # Fall back to mock
        logger.info("Using mock backend")
        return BackendType.MOCK
    
    @property
    def backend(self) -> HILBackend:
        """Get the underlying backend."""
        if self._backend is None:
            raise RuntimeError("HIL not open")
        return self._backend
    
    @property
    def is_simulation(self) -> bool:
        """True if using simulation backend."""
        return self._backend.is_simulation if self._backend else True
    
    @property
    def is_hardware(self) -> bool:
        """True if using hardware backend."""
        return not self.is_simulation
    
    # ─── Digital I/O ─────────────────────────────────────────────────
    
    def digital_write(self, pin: str, value: bool) -> None:
        """Write digital value to a pin."""
        self.backend.digital_write(pin, value)
    
    def digital_read(self, pin: str) -> bool:
        """Read digital value from a pin."""
        return self.backend.digital_read(pin)
    
    def digital_toggle(self, pin: str) -> bool:
        """Toggle a digital pin and return new value."""
        current = self.digital_read(pin)
        new_value = not current
        self.digital_write(pin, new_value)
        return new_value
    
    # ─── Analog I/O ──────────────────────────────────────────────────
    
    def analog_read(self, pin: str) -> float:
        """Read analog voltage from a pin."""
        return self.backend.analog_read(pin)
    
    def analog_write(self, pin: str, voltage: float) -> None:
        """Write analog voltage to a pin."""
        self.backend.analog_write(pin, voltage)
    
    # ─── State Access ────────────────────────────────────────────────
    
    def get_pin_state(self, pin: str) -> PinState:
        """Get complete pin state."""
        return self.backend.get_pin_state(pin)
    
    def get_all_pin_states(self, pins: Sequence[str]) -> Dict[str, PinState]:
        """Get states for multiple pins."""
        return {pin: self.get_pin_state(pin) for pin in pins}
    
    # ─── Simulation-specific ─────────────────────────────────────────
    
    def advance_simulation(self, duration_s: float) -> None:
        """Advance simulation time (no-op for hardware)."""
        if isinstance(self._backend, SimulationBackend):
            self._backend.advance(duration_s)
    
    @property
    def sim_time(self) -> float:
        """Get simulation time (0.0 for hardware)."""
        if isinstance(self._backend, SimulationBackend):
            return self._backend.sim_time
        return 0.0


# ─── Pytest Fixtures ─────────────────────────────────────────────────

def create_hil_fixtures():
    """Create pytest fixtures for unified HIL testing.
    
    Usage in conftest.py:
        from pyontrust.simulation.hil_bridge import create_hil_fixtures
        globals().update(create_hil_fixtures())
    """
    import pytest
    
    @pytest.fixture(scope="session")
    def hil():
        """Session-scoped unified HIL fixture."""
        h = UnifiedHIL()
        h.open()
        yield h
        h.close()
    
    @pytest.fixture
    def hil_reset(hil):
        """Reset state before each test."""
        # Reset simulation time if applicable
        if isinstance(hil._backend, SimulationBackend):
            hil._backend._sim_time = 0.0
            hil._backend._pin_states.clear()
        return hil
    
    @pytest.fixture
    def mock_hil():
        """Mock HIL for unit tests."""
        h = UnifiedHIL(backend_type=BackendType.MOCK)
        h.open()
        yield h
        h.close()
    
    return {
        "hil": hil,
        "hil_reset": hil_reset,
        "mock_hil": mock_hil,
    }
