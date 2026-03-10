"""ProtoSim Simulation Runner for Locator Base.

This module provides a bridge between pyontrust's HIL testing framework
and ProtoSim's MCU simulation capabilities, enabling:

1. Running Zephyr firmware in simulated Renode environment
2. Capturing GPIO, PWM, UART, ADC signals
3. Logging measurements to VCD, CSV, and JSON formats
4. Automated test scenario execution

Usage:
    # Run simulation with default config
    python -m pyontrust.simulation.runner --project locator_base
    
    # Run with custom firmware and duration
    python -m pyontrust.simulation.runner \\
        --firmware build/zephyr/zephyr.elf \\
        --duration 5s \\
        --output-dir ./sim_results

    # Run automation scenario
    python -m pyontrust.simulation.runner \\
        --scenario scenarios/blink_test.yaml
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger("pyontrust.simulation")


@dataclass
class SignalSample:
    """A single signal sample from simulation."""
    timestamp_s: float
    signal_name: str
    value: float
    domain: str = "digital"  # "digital", "analog", "pwm", "uart"
    
    def to_dict(self) -> dict:
        return {
            "timestamp_s": self.timestamp_s,
            "signal_name": self.signal_name,
            "value": self.value,
            "domain": self.domain,
        }


@dataclass
class SimulationConfig:
    """Configuration for simulation run."""
    project_name: str = "locator_base"
    firmware_path: Optional[str] = None
    duration_s: float = 10.0
    sync_interval_s: float = 100e-6  # 100µs
    output_dir: str = "./sim_logs"
    
    # Logging options
    enable_vcd: bool = True
    enable_csv: bool = True
    enable_json: bool = True
    
    # Renode options
    renode_port: int = 12345
    headless: bool = True
    
    # Channels to monitor
    monitor_pins: List[str] = field(default_factory=lambda: [
        "PA2", "PA4", "PA9", "PA25",  # Digital outputs
        "PA7", "PA21",                 # PWM
        "PA10", "PA11",                # UART
        "PA15", "PA16",                # ADC
    ])


@dataclass
class SimulationResults:
    """Container for simulation results."""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_s: float = 0.0
    samples: List[SignalSample] = field(default_factory=list)
    events: List[dict] = field(default_factory=list)
    uart_output: bytes = b""
    errors: List[str] = field(default_factory=list)
    
    @property
    def sample_count(self) -> int:
        return len(self.samples)
    
    def add_sample(self, sample: SignalSample) -> None:
        self.samples.append(sample)
    
    def add_event(self, event_type: str, timestamp: float, data: dict) -> None:
        self.events.append({
            "type": event_type,
            "timestamp_s": timestamp,
            "data": data,
        })
    
    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_s": self.duration_s,
            "sample_count": self.sample_count,
            "event_count": len(self.events),
            "errors": self.errors,
            "uart_output": self.uart_output.decode("utf-8", errors="replace"),
        }


class SimulationDataLogger:
    """Logs simulation data to multiple formats."""
    
    def __init__(self, output_dir: str, prefix: str = "sim"):
        self.output_dir = Path(output_dir)
        self.prefix = prefix
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._vcd_file = None
        self._csv_file = None
        self._csv_writer = None
        self._json_samples: List[dict] = []
        self._vcd_signals: Dict[str, str] = {}  # signal_name -> vcd_id
        self._vcd_id_counter = 0
        self._start_time: Optional[float] = None
    
    def start(self, signals: List[str]) -> None:
        """Start logging session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize VCD file
        vcd_path = self.output_dir / f"{self.prefix}_{timestamp}.vcd"
        self._vcd_file = open(vcd_path, "w")
        self._write_vcd_header(signals)
        
        # Initialize CSV file
        csv_path = self.output_dir / f"{self.prefix}_{timestamp}.csv"
        self._csv_file = open(csv_path, "w", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(["timestamp_s", "signal", "value", "domain"])
        
        self._json_samples = []
        self._start_time = time.perf_counter()
        
        logger.info(f"Started logging to {self.output_dir}")
    
    def log_sample(self, sample: SignalSample) -> None:
        """Log a single sample."""
        # CSV
        if self._csv_writer:
            self._csv_writer.writerow([
                f"{sample.timestamp_s:.9f}",
                sample.signal_name,
                sample.value,
                sample.domain,
            ])
        
        # VCD
        if self._vcd_file and sample.signal_name in self._vcd_signals:
            vcd_id = self._vcd_signals[sample.signal_name]
            timestamp_ns = int(sample.timestamp_s * 1e9)
            if sample.domain == "digital":
                value_str = "1" if sample.value else "0"
                self._vcd_file.write(f"#{timestamp_ns}\n{value_str}{vcd_id}\n")
            else:
                # For analog, encode as multi-bit
                value_int = int(sample.value * 1000)  # mV resolution
                self._vcd_file.write(f"#{timestamp_ns}\nb{value_int:032b} {vcd_id}\n")
        
        # JSON (in memory)
        self._json_samples.append(sample.to_dict())
    
    def stop(self) -> Path:
        """Stop logging and finalize files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Close VCD
        if self._vcd_file:
            self._vcd_file.close()
            self._vcd_file = None
        
        # Close CSV
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
        
        # Write JSON
        json_path = self.output_dir / f"{self.prefix}_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump({
                "samples": self._json_samples,
                "sample_count": len(self._json_samples),
                "timestamp": timestamp,
            }, f, indent=2)
        
        logger.info(f"Stopped logging. {len(self._json_samples)} samples recorded.")
        return json_path
    
    def _write_vcd_header(self, signals: List[str]) -> None:
        """Write VCD file header."""
        self._vcd_file.write("$version ProtoSim/PyOnTrust Simulation $end\n")
        self._vcd_file.write(f"$date {datetime.now().isoformat()} $end\n")
        self._vcd_file.write("$timescale 1ns $end\n")
        self._vcd_file.write("$scope module locator_base $end\n")
        
        for signal in signals:
            vcd_id = self._get_vcd_id()
            self._vcd_signals[signal] = vcd_id
            # Detect signal type from name
            if any(x in signal.upper() for x in ["ADC", "AIN", "PWM"]):
                self._vcd_file.write(f"$var real 32 {vcd_id} {signal} $end\n")
            else:
                self._vcd_file.write(f"$var wire 1 {vcd_id} {signal} $end\n")
        
        self._vcd_file.write("$upscope $end\n")
        self._vcd_file.write("$enddefinitions $end\n")
        self._vcd_file.write("$dumpvars\n")
        
        # Initial values
        for signal, vcd_id in self._vcd_signals.items():
            self._vcd_file.write(f"0{vcd_id}\n")
        
        self._vcd_file.write("$end\n")
    
    def _get_vcd_id(self) -> str:
        """Generate unique VCD signal identifier."""
        chars = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
        idx = self._vcd_id_counter
        self._vcd_id_counter += 1
        
        if idx < len(chars):
            return chars[idx]
        else:
            # Multi-char for >94 signals
            return chars[idx % len(chars)] + str(idx // len(chars))


class LocatorBaseSimulator:
    """Simulator for Locator Base board using ProtoSim/Renode.
    
    This class provides a high-level interface for running simulations
    of Locator Base firmware and capturing signal data.
    
    Example:
        config = SimulationConfig(
            firmware_path="build/zephyr/zephyr.elf",
            duration_s=5.0,
        )
        
        sim = LocatorBaseSimulator(config)
        results = sim.run()
        
        print(f"Captured {results.sample_count} samples")
        print(f"UART output: {results.uart_output.decode()}")
    """
    
    def __init__(self, config: SimulationConfig):
        self.config = config
        self._renode = None
        self._logger: Optional[SimulationDataLogger] = None
        self._results = SimulationResults()
        self._running = False
        self._sim_time = 0.0
        
        # Signal callbacks
        self._gpio_callbacks: List[Callable] = []
        self._uart_callbacks: List[Callable] = []
    
    def run(self) -> SimulationResults:
        """Run the simulation and return results.
        
        Returns:
            SimulationResults with all captured data
        """
        self._results = SimulationResults()
        self._results.start_time = datetime.now()
        
        try:
            self._initialize()
            self._run_simulation()
        except Exception as e:
            self._results.errors.append(str(e))
            logger.error(f"Simulation error: {e}")
        finally:
            self._cleanup()
        
        self._results.end_time = datetime.now()
        self._results.duration_s = self._sim_time
        
        return self._results
    
    def _initialize(self) -> None:
        """Initialize simulation components."""
        logger.info("Initializing Locator Base simulation...")
        
        # Initialize data logger
        self._logger = SimulationDataLogger(
            output_dir=self.config.output_dir,
            prefix="locator_base",
        )
        self._logger.start(self.config.monitor_pins)
        
        # Try to import and use protosim
        try:
            from protosim_kicad.core.config import MCUConfig, PinMapping, PinType
            from protosim_kicad.core.renode_bridge import RenodeBridge
            
            # Create MCU config for MSPM0G3507
            mcu_config = MCUConfig(
                platform="ti_mspm0g3507",
                firmware=self.config.firmware_path or "",
                renode_port=self.config.renode_port,
                machine_name="locator_base",
                cpu_frequency=80_000_000,
            )
            
            # Create pin mappings
            pin_mappings = self._create_pin_mappings()
            
            # Initialize Renode bridge
            self._renode = RenodeBridge(mcu_config, pin_mappings)
            self._renode.start()
            
            # Load firmware
            if self.config.firmware_path and os.path.isfile(self.config.firmware_path):
                self._renode.load_firmware(self.config.firmware_path)
            
            # Register callbacks
            self._renode.on_gpio_change(self._on_gpio_change)
            
            logger.info("ProtoSim/Renode initialized successfully")
            
        except ImportError as e:
            logger.warning(f"ProtoSim not available: {e}")
            logger.info("Running in mock/standalone simulation mode")
            self._renode = None
        except Exception as e:
            logger.warning(f"Failed to initialize Renode: {e}")
            logger.info("Running in mock simulation mode")
            self._renode = None
    
    def _create_pin_mappings(self) -> list:
        """Create pin mapping objects for ProtoSim."""
        try:
            from protosim_kicad.core.config import PinMapping, PinType
        except ImportError:
            return []
        
        mappings = []
        
        # Digital outputs
        for pin in ["PA2", "PA4", "PA9", "PA25"]:
            mappings.append(PinMapping(
                mcu_pin=pin,
                net=f"/{pin}",
                pin_type=PinType.DIGITAL_OUT,
            ))
        
        # PWM outputs
        for pin, timer in [("PA7", "TIMG8"), ("PA21", "TIMG6")]:
            mappings.append(PinMapping(
                mcu_pin=pin,
                net=f"/{pin}",
                pin_type=PinType.PWM,
                timer=timer,
            ))
        
        # UART
        mappings.append(PinMapping(
            mcu_pin="PA10",
            net="/UART0_TX",
            pin_type=PinType.UART_TX,
            peripheral="UART0",
        ))
        mappings.append(PinMapping(
            mcu_pin="PA11",
            net="/UART0_RX",
            pin_type=PinType.UART_RX,
            peripheral="UART0",
        ))
        
        # ADC inputs
        for i, pin in enumerate(["PA15", "PA16", "PA17", "PA18"]):
            mappings.append(PinMapping(
                mcu_pin=pin,
                net=f"/{pin}",
                pin_type=PinType.ADC,
                adc_channel=i,
            ))
        
        return mappings
    
    def _run_simulation(self) -> None:
        """Execute the main simulation loop."""
        logger.info(f"Starting simulation for {self.config.duration_s}s...")
        
        self._running = True
        self._sim_time = 0.0
        wall_start = time.perf_counter()
        
        while self._running and self._sim_time < self.config.duration_s:
            step_end = min(
                self._sim_time + self.config.sync_interval_s,
                self.config.duration_s
            )
            
            # Advance simulation
            if self._renode:
                self._renode.run_until(step_end)
                self._read_mcu_state()
            else:
                # Mock simulation - generate test data
                self._generate_mock_data(step_end)
            
            self._sim_time = step_end
            
            # Progress logging
            if int(self._sim_time * 10) % 10 == 0:  # Every 1s
                progress = self._sim_time / self.config.duration_s * 100
                logger.debug(f"Simulation progress: {progress:.1f}%")
        
        wall_elapsed = time.perf_counter() - wall_start
        logger.info(
            f"Simulation complete. "
            f"Sim time: {self._sim_time:.3f}s, "
            f"Wall time: {wall_elapsed:.3f}s, "
            f"Speedup: {self._sim_time/wall_elapsed:.1f}x"
        )
    
    def _read_mcu_state(self) -> None:
        """Read current MCU state and log signals."""
        if not self._renode:
            return
        
        for pin in self.config.monitor_pins:
            try:
                value = self._renode.read_gpio(pin)
                sample = SignalSample(
                    timestamp_s=self._sim_time,
                    signal_name=pin,
                    value=float(value),
                    domain="digital",
                )
                self._results.add_sample(sample)
                if self._logger:
                    self._logger.log_sample(sample)
            except Exception:
                pass  # Pin may not be readable
        
        # Read UART output
        try:
            uart_data = self._renode.read_uart("UART0")
            if uart_data:
                self._results.uart_output += uart_data
                self._results.add_event("uart_rx", self._sim_time, {
                    "data": uart_data.hex(),
                    "text": uart_data.decode("utf-8", errors="replace"),
                })
        except Exception:
            pass
    
    def _generate_mock_data(self, timestamp: float) -> None:
        """Generate mock simulation data for testing without Renode."""
        import math
        
        # Simulate blinking LED (1 Hz)
        led_value = 1 if int(timestamp * 2) % 2 == 0 else 0
        sample = SignalSample(
            timestamp_s=timestamp,
            signal_name="PA2",
            value=float(led_value),
            domain="digital",
        )
        self._results.add_sample(sample)
        if self._logger:
            self._logger.log_sample(sample)
        
        # Simulate PWM (1 kHz, 50% duty)
        pwm_value = 1 if (timestamp * 1000) % 1 < 0.5 else 0
        sample = SignalSample(
            timestamp_s=timestamp,
            signal_name="PA7",
            value=float(pwm_value),
            domain="pwm",
        )
        self._results.add_sample(sample)
        if self._logger:
            self._logger.log_sample(sample)
        
        # Simulate ADC (sine wave)
        adc_value = 1.65 + 1.5 * math.sin(2 * math.pi * 10 * timestamp)
        sample = SignalSample(
            timestamp_s=timestamp,
            signal_name="PA15",
            value=adc_value,
            domain="analog",
        )
        self._results.add_sample(sample)
        if self._logger:
            self._logger.log_sample(sample)
    
    def _on_gpio_change(self, pin_name: str, value: int, timestamp: float) -> None:
        """Callback for GPIO state changes."""
        sample = SignalSample(
            timestamp_s=timestamp,
            signal_name=pin_name,
            value=float(value),
            domain="digital",
        )
        self._results.add_sample(sample)
        if self._logger:
            self._logger.log_sample(sample)
        
        for callback in self._gpio_callbacks:
            callback(pin_name, value, timestamp)
    
    def _cleanup(self) -> None:
        """Clean up simulation resources."""
        self._running = False
        
        if self._renode:
            try:
                self._renode.stop()
            except Exception as e:
                logger.warning(f"Error stopping Renode: {e}")
            self._renode = None
        
        if self._logger:
            json_path = self._logger.stop()
            logger.info(f"Results saved to {json_path}")
    
    def stop(self) -> None:
        """Stop the simulation."""
        self._running = False
    
    def on_gpio_change(self, callback: Callable[[str, int, float], None]) -> None:
        """Register callback for GPIO changes."""
        self._gpio_callbacks.append(callback)


def parse_time_string(s: str) -> float:
    """Parse time string like '10s', '500ms', '100us' to seconds."""
    s = s.strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000
    elif s.endswith("us") or s.endswith("µs"):
        return float(s[:-2]) / 1_000_000
    elif s.endswith("ns"):
        return float(s[:-2]) / 1_000_000_000
    elif s.endswith("s"):
        return float(s[:-1])
    else:
        return float(s)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run Locator Base simulation and log measurements"
    )
    parser.add_argument(
        "--firmware", "-f", type=str, default=None,
        help="Path to firmware ELF file"
    )
    parser.add_argument(
        "--duration", "-d", type=str, default="10s",
        help="Simulation duration (default: 10s)"
    )
    parser.add_argument(
        "--output-dir", "-o", type=str, default="./sim_logs",
        help="Output directory for logs (default: ./sim_logs)"
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Run in mock mode without Renode"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    
    # Create configuration
    config = SimulationConfig(
        firmware_path=args.firmware,
        duration_s=parse_time_string(args.duration),
        output_dir=args.output_dir,
    )
    
    print(f"\n{'='*60}")
    print("Locator Base Simulation Runner")
    print(f"{'='*60}")
    print(f"Firmware: {config.firmware_path or '(mock mode)'}")
    print(f"Duration: {config.duration_s}s")
    print(f"Output:   {config.output_dir}")
    print(f"{'='*60}\n")
    
    # Run simulation
    simulator = LocatorBaseSimulator(config)
    results = simulator.run()
    
    # Print summary
    print(f"\n{'='*60}")
    print("Simulation Results")
    print(f"{'='*60}")
    print(f"Duration:     {results.duration_s:.3f}s")
    print(f"Samples:      {results.sample_count}")
    print(f"Events:       {len(results.events)}")
    print(f"Errors:       {len(results.errors)}")
    
    if results.uart_output:
        print(f"\nUART Output:")
        print("-" * 40)
        print(results.uart_output.decode("utf-8", errors="replace")[:500])
    
    if results.errors:
        print(f"\nErrors:")
        print("-" * 40)
        for err in results.errors:
            print(f"  - {err}")
    
    print(f"{'='*60}\n")
    
    # Save summary JSON
    summary_path = Path(config.output_dir) / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(results.to_dict(), f, indent=2)
    print(f"Summary saved to: {summary_path}")
    
    return 0 if not results.errors else 1


if __name__ == "__main__":
    sys.exit(main())
