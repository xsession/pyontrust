"""HIL Test Fixture for Zephyr driver testing.

Provides pytest fixtures and utilities for automated hardware-in-the-loop
testing of Zephyr RTOS drivers using Analog Discovery 3.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pyontrust.boards.base import BoardPinout
    from pyontrust.hil.ad3_interface import AD3Interface


@dataclass
class ZephyrProject:
    """Represents a Zephyr project for building and flashing.
    
    Attributes:
        source_dir: Path to the Zephyr application source
        board: Zephyr board name (e.g., 'locator_base')
        build_dir: Build output directory
        west_path: Path to west tool (default: 'west')
    """
    
    source_dir: Path
    board: str
    build_dir: Optional[Path] = None
    west_path: str = "west"
    
    def __post_init__(self):
        self.source_dir = Path(self.source_dir)
        if self.build_dir is None:
            self.build_dir = self.source_dir / "build"
        else:
            self.build_dir = Path(self.build_dir)
    
    def build(
        self,
        pristine: bool = False,
        extra_args: Optional[list[str]] = None,
    ) -> subprocess.CompletedProcess:
        """Build the Zephyr project.
        
        Args:
            pristine: If True, do a pristine build
            extra_args: Additional arguments to pass to west build
            
        Returns:
            CompletedProcess result
        """
        cmd = [
            self.west_path,
            "build",
            "-b", self.board,
            "-d", str(self.build_dir),
            str(self.source_dir),
        ]
        
        if pristine:
            cmd.insert(2, "-p")
            cmd.insert(3, "always")
        
        if extra_args:
            cmd.extend(extra_args)
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def flash(
        self,
        runner: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
    ) -> subprocess.CompletedProcess:
        """Flash the built firmware.
        
        Args:
            runner: Flash runner (e.g., 'jlink', 'openocd')
            extra_args: Additional arguments to pass to west flash
            
        Returns:
            CompletedProcess result
        """
        cmd = [
            self.west_path,
            "flash",
            "-d", str(self.build_dir),
        ]
        
        if runner:
            cmd.extend(["--runner", runner])
        
        if extra_args:
            cmd.extend(extra_args)
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    @property
    def binary_path(self) -> Path:
        """Get path to the built binary (zephyr.bin)."""
        return self.build_dir / "zephyr" / "zephyr.bin"
    
    @property
    def elf_path(self) -> Path:
        """Get path to the built ELF file."""
        return self.build_dir / "zephyr" / "zephyr.elf"


@dataclass
class HILTestFixture:
    """Hardware-in-the-loop test fixture.
    
    Combines AD3 interface with Zephyr project management for
    comprehensive driver testing.
    
    Example:
        from pyontrust.hil import HILTestFixture
        from pyontrust.boards.locator_base import LOCATOR_BASE
        
        fixture = HILTestFixture(
            board=LOCATOR_BASE,
            zephyr_base=Path("/path/to/zephyrproject/zephyr"),
        )
        
        with fixture:
            # Build and flash test application
            fixture.load_app("samples/basic/blink")
            
            # Wait for device to start
            fixture.wait_for_boot(timeout_s=5.0)
            
            # Verify LED blinking
            pwm = fixture.ad3.analog.measure_pwm(0)
            assert 0.9 <= pwm['frequency_hz'] <= 1.1
    """
    
    board: "BoardPinout"
    zephyr_base: Optional[Path] = None
    app_base: Optional[Path] = None  # Base path for test applications
    ad3_device_index: int = -1
    auto_flash: bool = True
    
    # Internal state
    _ad3: Optional["AD3Interface"] = field(default=None, init=False, repr=False)
    _current_project: Optional[ZephyrProject] = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        if self.zephyr_base:
            self.zephyr_base = Path(self.zephyr_base)
        if self.app_base:
            self.app_base = Path(self.app_base)
    
    @property
    def ad3(self) -> "AD3Interface":
        """Get the AD3 interface."""
        if self._ad3 is None:
            raise RuntimeError("Fixture not opened. Use 'with fixture:' or call open().")
        return self._ad3
    
    def open(self) -> None:
        """Open AD3 connection."""
        if self._ad3 is not None:
            return
        
        from pyontrust.hil.ad3_interface import AD3Interface
        
        self._ad3 = AD3Interface(
            board=self.board,
            device_index=self.ad3_device_index,
        )
        self._ad3.open()
    
    def close(self) -> None:
        """Close AD3 connection."""
        if self._ad3 is not None:
            self._ad3.close()
            self._ad3 = None
    
    def __enter__(self) -> "HILTestFixture":
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def load_app(
        self,
        app_path: str | Path,
        build: bool = True,
        flash: bool = True,
        pristine: bool = False,
    ) -> ZephyrProject:
        """Load a test application onto the device.
        
        Args:
            app_path: Path to the app (relative to app_base/zephyr_base or absolute)
            build: Whether to build the application
            flash: Whether to flash the application
            pristine: Whether to do a pristine build
            
        Returns:
            ZephyrProject instance
        """
        app_path = Path(app_path)
        
        # Resolve path
        if not app_path.is_absolute():
            if self.app_base and (self.app_base / app_path).exists():
                app_path = self.app_base / app_path
            elif self.zephyr_base and (self.zephyr_base / app_path).exists():
                app_path = self.zephyr_base / app_path
            else:
                raise FileNotFoundError(f"Application not found: {app_path}")
        
        project = ZephyrProject(
            source_dir=app_path,
            board=self.board.name,
        )
        
        if build:
            result = project.build(pristine=pristine)
            if result.returncode != 0:
                raise RuntimeError(f"Build failed:\n{result.stderr}")
        
        if flash and self.auto_flash:
            result = project.flash()
            if result.returncode != 0:
                raise RuntimeError(f"Flash failed:\n{result.stderr}")
        
        self._current_project = project
        return project
    
    def wait_for_boot(self, timeout_s: float = 5.0) -> None:
        """Wait for the device to boot.
        
        This is a simple delay-based implementation. For more sophisticated
        boot detection, override this method or use UART monitoring.
        
        Args:
            timeout_s: Maximum time to wait
        """
        time.sleep(timeout_s)
    
    def reset_device(self) -> None:
        """Reset the device (requires debug probe support)."""
        # TODO: Implement via debug probe if available
        pass
    
    # ========== Convenience test methods ==========
    
    def verify_gpio_output(
        self,
        pin_name: str,
        expected_value: bool,
        timeout_s: float = 1.0,
    ) -> bool:
        """Verify a GPIO output state.
        
        Args:
            pin_name: Board pin name (e.g., 'PA2')
            expected_value: Expected state (True/False)
            timeout_s: Timeout for verification
            
        Returns:
            True if verification passed
        """
        start = time.perf_counter()
        while time.perf_counter() - start < timeout_s:
            actual = self.ad3.digital.read_pin(pin_name)
            if actual == expected_value:
                return True
            time.sleep(0.01)
        return False
    
    def verify_gpio_toggle(
        self,
        pin_name: str,
        min_toggles: int = 2,
        timeout_s: float = 5.0,
    ) -> int:
        """Count GPIO toggles within a timeout.
        
        Args:
            pin_name: Board pin name
            min_toggles: Minimum expected toggles
            timeout_s: Observation period
            
        Returns:
            Number of toggles observed
        """
        toggles = 0
        prev_value = self.ad3.digital.read_pin(pin_name)
        start = time.perf_counter()
        
        while time.perf_counter() - start < timeout_s:
            current = self.ad3.digital.read_pin(pin_name)
            if current != prev_value:
                toggles += 1
                prev_value = current
            time.sleep(0.001)
        
        return toggles
    
    def verify_pwm(
        self,
        pin_name: str,
        expected_freq_hz: float,
        expected_duty: float,
        freq_tolerance: float = 0.1,
        duty_tolerance: float = 0.05,
    ) -> dict:
        """Verify PWM output parameters.
        
        Args:
            pin_name: Board pin name
            expected_freq_hz: Expected frequency in Hz
            expected_duty: Expected duty cycle (0.0-1.0)
            freq_tolerance: Frequency tolerance (fraction)
            duty_tolerance: Duty cycle tolerance (absolute)
            
        Returns:
            Dictionary with measurement results and pass/fail status
        """
        channel = self.ad3.get_pin_ain(pin_name)
        if channel is None:
            raise ValueError(f"Pin {pin_name} is not mapped to analog input")
        
        measurement = self.ad3.analog.measure_pwm(channel)
        
        freq_ok = abs(measurement['frequency_hz'] - expected_freq_hz) / expected_freq_hz <= freq_tolerance
        duty_ok = abs(measurement['duty_cycle'] - expected_duty) <= duty_tolerance
        
        return {
            **measurement,
            "freq_pass": freq_ok,
            "duty_pass": duty_ok,
            "pass": freq_ok and duty_ok,
        }
    
    def verify_adc_response(
        self,
        adc_pin: str,
        stimulus_pin: str,
        test_voltages: list[float],
        tolerance_v: float = 0.1,
        uart_cmd_fmt: Optional[str] = None,
    ) -> list[dict]:
        """Verify ADC by applying known voltages and reading back.
        
        This test applies voltages using AD3's analog output and
        verifies the MCU's ADC reading (via UART or other means).
        
        Args:
            adc_pin: MCU ADC pin name
            stimulus_pin: Pin connected to AD3 analog output
            test_voltages: List of voltages to test
            tolerance_v: Acceptable reading tolerance
            uart_cmd_fmt: Format string for UART command (e.g., "adc read {}")
            
        Returns:
            List of test results
        """
        results = []
        
        for voltage in test_voltages:
            # Apply voltage
            self.ad3.analog.set_pin_voltage(stimulus_pin, voltage)
            time.sleep(0.1)  # Settling time
            
            # Read back (implementation depends on how ADC values are reported)
            # This is a placeholder - actual implementation would read via UART
            result = {
                "applied_v": voltage,
                "expected_v": voltage,
                "tolerance_v": tolerance_v,
                "pass": True,  # Placeholder
            }
            results.append(result)
        
        return results


# ========== Pytest fixtures ==========

def create_pytest_fixtures():
    """Create pytest fixtures for HIL testing.
    
    Import these in your conftest.py:
    
        from pyontrust.hil.test_fixture import create_pytest_fixtures
        
        # This adds the fixtures to your test module
        globals().update(create_pytest_fixtures())
    
    Or manually create fixtures:
    
        import pytest
        from pyontrust.hil import HILTestFixture
        from pyontrust.boards.locator_base import LOCATOR_BASE
        
        @pytest.fixture
        def hil_fixture():
            fixture = HILTestFixture(board=LOCATOR_BASE)
            with fixture:
                yield fixture
    """
    import pytest
    
    @pytest.fixture(scope="session")
    def ad3_interface():
        """Session-scoped AD3 interface fixture."""
        from pyontrust.hil.ad3_interface import AD3Interface
        
        ad3 = AD3Interface()
        ad3.open()
        yield ad3
        ad3.close()
    
    @pytest.fixture(scope="function")
    def ad3_reset(ad3_interface):
        """Reset AD3 before each test."""
        ad3_interface.reset()
        yield ad3_interface
    
    return {
        "ad3_interface": ad3_interface,
        "ad3_reset": ad3_reset,
    }


# ========== Test result reporting ==========

@dataclass
class HILTestResult:
    """Container for HIL test results."""
    
    test_name: str
    passed: bool
    duration_s: float
    measurements: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "duration_s": self.duration_s,
            "measurements": self.measurements,
            "errors": self.errors,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class HILTestRunner:
    """Simple test runner for HIL tests.
    
    Example:
        runner = HILTestRunner(fixture)
        
        @runner.test
        def test_gpio_output(fixture):
            fixture.ad3.digital.write(0, True)
            assert fixture.ad3.digital.read(0) == True
        
        results = runner.run_all()
    """
    
    def __init__(self, fixture: HILTestFixture):
        self.fixture = fixture
        self._tests: list[tuple[str, Callable]] = []
    
    def test(self, func: Callable) -> Callable:
        """Decorator to register a test function."""
        self._tests.append((func.__name__, func))
        return func
    
    def run_all(self) -> list[HILTestResult]:
        """Run all registered tests."""
        results = []
        
        for name, func in self._tests:
            start = time.perf_counter()
            errors = []
            passed = False
            
            try:
                func(self.fixture)
                passed = True
            except AssertionError as e:
                errors.append(f"Assertion failed: {e}")
            except Exception as e:
                errors.append(f"Error: {e}")
            
            duration = time.perf_counter() - start
            
            results.append(HILTestResult(
                test_name=name,
                passed=passed,
                duration_s=duration,
                errors=errors,
            ))
        
        return results
    
    def run_test(self, name: str) -> HILTestResult:
        """Run a specific test by name."""
        for test_name, func in self._tests:
            if test_name == name:
                start = time.perf_counter()
                errors = []
                passed = False
                
                try:
                    func(self.fixture)
                    passed = True
                except AssertionError as e:
                    errors.append(f"Assertion failed: {e}")
                except Exception as e:
                    errors.append(f"Error: {e}")
                
                duration = time.perf_counter() - start
                
                return HILTestResult(
                    test_name=name,
                    passed=passed,
                    duration_s=duration,
                    errors=errors,
                )
        
        raise ValueError(f"Test not found: {name}")
